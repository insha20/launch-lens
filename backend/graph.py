"""
graph.py — LangGraph Orchestrator (Day 6)

WHAT THIS FILE DOES:
Connects all 5 agents into a stateful directed graph.
Each agent is a node. Edges define what runs next.
One conditional edge implements routing logic based on PMF verdict.

WHY LANGGRAPH FOR ORCHESTRATION:
LangGraph models your pipeline as a state machine — each node reads
from and writes to a shared TypedDict state. This means:
  - No passing dozens of arguments between functions
  - Every intermediate result is inspectable (great for debugging)
  - Conditional routing is explicit in code, not buried in if/else chains
  - LangGraph handles retries, streaming, and checkpointing for free

THE STATE OBJECT:
Think of PipelineState as a shared whiteboard. Every node reads what
it needs and writes its result. By the end, the whiteboard has the
complete report. This is the Actor model pattern.

THE CONDITIONAL EDGE:
After PMF Scorer runs, should_write_copy() inspects the verdict:
  - "insufficient data" or "weak signal" → skip GTM, return early
  - "moderate signal" or "strong signal" → run GTM Copywriter

This is real product logic. If the PMF score says "insufficient data",
generating GTM copy would be fabricating advice without evidence —
exactly the hallucination problem RAG was supposed to solve. So we
refuse to run GTM and tell the user to research more first.

INTERVIEW TALKING POINT:
"The conditional edge is the reliability guarantee. The system won't
generate marketing copy if the evidence doesn't support it. Agents
downstream only run when upstream quality thresholds are met."

DATA FLOW:
    User input (product_description)
         │
    [product_analyst_node]     → writes: product_analysis
         │
    [community_researcher_node] → writes: evidence_list
         │
    [rag_synthesizer_node]     → writes: synthesis_results
         │
    [pmf_scorer_node]          → writes: pmf_score
         │
    should_write_copy() ──────────────────────────────────┐
         │ strong/moderate signal                          │ weak/insufficient
         ▼                                                 ▼
    [gtm_copywriter_node]                          [early_exit_node]
         │                                                 │
    writes: gtm_pack                              writes: pipeline_status
         └──────────────────────┬──────────────────────────┘
                                ▼
                      [assemble_report_node]
                                │
                      returns: LaunchLensReport
"""

import uuid
import asyncio
from typing import TypedDict, Optional, Annotated
from langgraph.graph import StateGraph, END

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from schemas import (
    ProductAnalysis,
    CommunityEvidence,
    SynthesisResult,
    PMFScore,
    GTMPack,
    LaunchLensReport,
)


# ─────────────────────────────────────────────────────────────
# Pipeline State
# ─────────────────────────────────────────────────────────────

class PipelineState(TypedDict):
    """
    Shared state passed between every node in the graph.

    TypedDict means it's a plain dict at runtime — LangGraph reads
    and writes keys from this dict as state flows through nodes.

    WHY NOT A PYDANTIC MODEL HERE:
    LangGraph requires TypedDict for state so it can merge partial
    updates from each node. A node only needs to return the keys it
    changed — not the entire state. Pydantic doesn't support this
    partial-update pattern cleanly.
    """
    # Input
    product_description: str

    # Set at runtime — each pipeline run gets a unique ID
    # Used to namespace the Chroma vector store per run
    session_id: str

    # Written by each agent node
    product_analysis: Optional[ProductAnalysis]
    evidence_list: Optional[list[CommunityEvidence]]
    synthesis_results: Optional[list[SynthesisResult]]
    pmf_score: Optional[PMFScore]
    gtm_pack: Optional[GTMPack]

    # Routing signals
    pipeline_status: str                # "running" | "complete" | "insufficient_data" | "error"
    error_message: Optional[str]


# ─────────────────────────────────────────────────────────────
# Node: Product Analyst
# ─────────────────────────────────────────────────────────────

import re

async def _retry_on_rate_limit(coro_fn, label: str, max_attempts: int = 4):
    """
    Run an async coroutine function, retrying up to max_attempts times
    when Gemini returns a 429 / RESOURCE_EXHAUSTED rate-limit error.
    Extracts the server-suggested retryDelay from the error message.
    Raises the last exception if all retries are exhausted.
    """
    for attempt in range(max_attempts):
        try:
            return await coro_fn()
        except Exception as e:
            error_str = str(e)
            is_rate_limit = "429" in error_str or "RESOURCE_EXHAUSTED" in error_str
            if is_rate_limit and attempt < max_attempts - 1:
                delay_match = re.search(r'retryDelay.*?(\d+)', error_str)
                wait = int(delay_match.group(1)) + 5 if delay_match else 60
                print(f"  ⏳ [{label}] Rate limited — waiting {wait}s (attempt {attempt+1}/{max_attempts})...")
                await asyncio.sleep(wait)
                continue
            raise


async def product_analyst_node(state: PipelineState) -> dict:
    """
    Node 1: Analyze the product description and extract ICP hypotheses.
    Reads: product_description
    Writes: product_analysis
    """
    print("\n[Graph] ▶ Node: product_analyst")
    from agents.product_analyst import analyze_product

    try:
        analysis = await _retry_on_rate_limit(
            lambda: analyze_product(state["product_description"]),
            label="product_analyst",
        )
        print(f"  ✓ Extracted {len(analysis.icp_hypotheses)} ICP hypotheses")
        return {"product_analysis": analysis}
    except Exception as e:
        print(f"  ✗ Product Analyst failed: {e}")
        return {
            "pipeline_status": "error",
            "error_message": f"Product Analyst failed: {str(e)}",
        }


# ─────────────────────────────────────────────────────────────
# Node: Community Researcher
# ─────────────────────────────────────────────────────────────

async def community_researcher_node(state: PipelineState) -> dict:
    """
    Node 2: Research each ICP hypothesis against Reddit + HN.
    Reads: product_analysis
    Writes: evidence_list
    """
    print("\n[Graph] ▶ Node: community_researcher")
    from agents.community_researcher import research_all_hypotheses

    if state.get("pipeline_status") == "error":
        print("  ⏩ Skipping — upstream error")
        return {}

    try:
        evidence_list = await _retry_on_rate_limit(
            lambda: research_all_hypotheses(state["product_analysis"]),
            label="community_researcher",
        )
        total_posts = sum(len(e.posts) for e in evidence_list)
        print(f"  ✓ Found {total_posts} posts across {len(evidence_list)} hypotheses")
        return {"evidence_list": evidence_list}
    except Exception as e:
        print(f"  ✗ Community Researcher failed: {e}")
        return {
            "pipeline_status": "error",
            "error_message": f"Community Researcher failed: {str(e)}",
        }


# ─────────────────────────────────────────────────────────────
# Node: RAG Synthesizer
# ─────────────────────────────────────────────────────────────

async def rag_synthesizer_node(state: PipelineState) -> dict:
    """
    Node 3: Embed evidence into Chroma, retrieve + synthesize per hypothesis.
    Reads: product_analysis, evidence_list, session_id
    Writes: synthesis_results
    """
    print("\n[Graph] ▶ Node: rag_synthesizer")
    from agents.rag_synthesizer import synthesize_all

    if state.get("pipeline_status") == "error":
        print("  ⏩ Skipping — upstream error")
        return {}

    try:
        synthesis_results = await _retry_on_rate_limit(
            lambda: synthesize_all(
                analysis=state["product_analysis"],
                evidence_list=state["evidence_list"],
                session_id=state["session_id"],
            ),
            label="rag_synthesizer",
        )
        confirmed = sum(1 for r in synthesis_results if r.pain_confirmed)
        print(f"  ✓ {confirmed}/{len(synthesis_results)} hypotheses confirmed by evidence")
        return {"synthesis_results": synthesis_results}
    except Exception as e:
        print(f"  ✗ RAG Synthesizer failed: {e}")
        return {
            "pipeline_status": "error",
            "error_message": f"RAG Synthesizer failed: {str(e)}",
        }


# ─────────────────────────────────────────────────────────────
# Node: PMF Scorer
# ─────────────────────────────────────────────────────────────

async def pmf_scorer_node(state: PipelineState) -> dict:
    """
    Node 4: Score product-market fit with chain-of-thought reasoning.
    Reads: product_analysis, synthesis_results
    Writes: pmf_score
    """
    print("\n[Graph] ▶ Node: pmf_scorer")
    from agents.pmf_scorer import score_pmf

    if state.get("pipeline_status") == "error":
        print("  ⏩ Skipping — upstream error")
        return {}

    try:
        pmf_score = await _retry_on_rate_limit(
            lambda: score_pmf(
                analysis=state["product_analysis"],
                synthesis_results=state["synthesis_results"],
            ),
            label="pmf_scorer",
        )
        print(f"  ✓ PMF Score: {pmf_score.score}/10 — {pmf_score.verdict}")
        return {"pmf_score": pmf_score}
    except Exception as e:
        print(f"  ✗ PMF Scorer failed: {e}")
        return {
            "pipeline_status": "error",
            "error_message": f"PMF Scorer failed: {str(e)}",
        }


# ─────────────────────────────────────────────────────────────
# Conditional Edge: should_write_copy
# ─────────────────────────────────────────────────────────────

def should_write_copy(state: PipelineState) -> str:
    """
    Routing function called after PMF Scorer.

    Returns the name of the next node to run.

    ROUTING LOGIC:
    - Error: go straight to assemble_report (with error info)
    - insufficient data or weak signal: skip GTM, go to assemble_report
    - moderate/strong signal: run GTM Copywriter first

    WHY THIS MATTERS:
    Generating GTM copy when PMF evidence is weak would be the system
    fabricating marketing advice without evidence backing it. The whole
    point of RAG was grounded answers — the routing enforces that
    principle at the orchestration level too.
    """
    if state.get("pipeline_status") == "error":
        print("\n[Graph] ↪ Routing: error → assemble_report")
        return "assemble_report"

    pmf_score = state.get("pmf_score")
    if pmf_score is None:
        print("\n[Graph] ↪ Routing: no score → assemble_report")
        return "assemble_report"

    verdict = pmf_score.verdict.lower()

    if "insufficient" in verdict or "weak" in verdict:
        print(f"\n[Graph] ↪ Routing: '{verdict}' → skip GTM → assemble_report")
        return "assemble_report"
    else:
        print(f"\n[Graph] ↪ Routing: '{verdict}' → gtm_copywriter")
        return "gtm_copywriter"


# ─────────────────────────────────────────────────────────────
# Node: GTM Copywriter
# ─────────────────────────────────────────────────────────────

async def gtm_copywriter_node(state: PipelineState) -> dict:
    """
    Node 5 (conditional): Generate GTM copy grounded in evidence.
    Reads: product_analysis, synthesis_results, pmf_score
    Writes: gtm_pack
    Only runs if PMF verdict is moderate signal or strong signal.
    """
    print("\n[Graph] ▶ Node: gtm_copywriter")
    from agents.gtm_copywriter import generate_gtm_pack

    try:
        gtm_pack = await _retry_on_rate_limit(
            lambda: generate_gtm_pack(
                analysis=state["product_analysis"],
                synthesis_results=state["synthesis_results"],
                pmf_score=state["pmf_score"],
            ),
            label="gtm_copywriter",
        )
        print(f"  ✓ GTM Pack generated for: {gtm_pack.target_persona[:50]}...")
        return {"gtm_pack": gtm_pack}
    except Exception as e:
        print(f"  ✗ GTM Copywriter failed: {e}")
        # Non-fatal — report can still be assembled without GTM copy
        return {"error_message": f"GTM Copywriter failed: {str(e)}"}


# ─────────────────────────────────────────────────────────────
# Node: Assemble Report
# ─────────────────────────────────────────────────────────────

async def assemble_report_node(state: PipelineState) -> dict:
    """
    Final node: assemble all agent outputs into LaunchLensReport.
    Reads: everything
    Writes: pipeline_status (sets final status)

    This node always runs — it's the single exit point of the graph.
    It determines the final pipeline_status based on what's present.
    """
    print("\n[Graph] ▶ Node: assemble_report")

    if state.get("pipeline_status") == "error":
        status = "error"
    elif state.get("pmf_score") and state["pmf_score"].verdict.lower() in ("insufficient data",):
        status = "insufficient_data"
    elif state.get("gtm_pack"):
        status = "complete"
    elif state.get("pmf_score"):
        # Scored but no GTM (weak signal path)
        status = "complete"
    else:
        status = "error"

    print(f"  ✓ Pipeline status: {status}")
    return {"pipeline_status": status}


# ─────────────────────────────────────────────────────────────
# Build the graph
# ─────────────────────────────────────────────────────────────

def build_graph():
    """
    Constructs and compiles the LangGraph state machine.

    GRAPH STRUCTURE:
      START
        └→ product_analyst
              └→ community_researcher
                    └→ rag_synthesizer
                          └→ pmf_scorer
                                └→ [should_write_copy]
                                      ├→ gtm_copywriter → assemble_report → END
                                      └→ assemble_report → END

    compile() validates the graph structure (no dangling edges,
    no unreachable nodes) and returns an executable Runnable.
    """
    graph = StateGraph(PipelineState)

    # Add all nodes
    graph.add_node("product_analyst", product_analyst_node)
    graph.add_node("community_researcher", community_researcher_node)
    graph.add_node("rag_synthesizer", rag_synthesizer_node)
    graph.add_node("pmf_scorer", pmf_scorer_node)
    graph.add_node("gtm_copywriter", gtm_copywriter_node)
    graph.add_node("assemble_report", assemble_report_node)

    # Linear edges (always run in order)
    graph.set_entry_point("product_analyst")
    graph.add_edge("product_analyst", "community_researcher")
    graph.add_edge("community_researcher", "rag_synthesizer")
    graph.add_edge("rag_synthesizer", "pmf_scorer")

    # Conditional edge after PMF Scorer
    graph.add_conditional_edges(
        "pmf_scorer",
        should_write_copy,
        {
            "gtm_copywriter": "gtm_copywriter",
            "assemble_report": "assemble_report",
        }
    )

    # Both paths converge at assemble_report → END
    graph.add_edge("gtm_copywriter", "assemble_report")
    graph.add_edge("assemble_report", END)

    return graph.compile()


# Compile once at import time — reused across all requests
_pipeline = None

def get_pipeline():
    global _pipeline
    if _pipeline is None:
        _pipeline = build_graph()
    return _pipeline


# ─────────────────────────────────────────────────────────────
# Public entry point — called by FastAPI and tests
# ─────────────────────────────────────────────────────────────

async def run_pipeline(product_description: str) -> LaunchLensReport:
    """
    Run the full LaunchLens pipeline for a product description.

    This is the single function FastAPI calls. Everything else is
    internal to the graph.

    Returns a LaunchLensReport with all agent outputs assembled.
    """
    session_id = str(uuid.uuid4())
    print(f"\n{'='*65}")
    print(f"LaunchLens Pipeline — Session {session_id[:8]}")
    print(f"Product: {product_description[:80]}...")
    print(f"{'='*65}")

    pipeline = get_pipeline()

    # Initial state — only product_description and session_id are set.
    # Every other field starts as None and gets filled in by nodes.
    initial_state: PipelineState = {
        "product_description": product_description,
        "session_id": session_id,
        "product_analysis": None,
        "evidence_list": None,
        "synthesis_results": None,
        "pmf_score": None,
        "gtm_pack": None,
        "pipeline_status": "running",
        "error_message": None,
    }

    final_state = await pipeline.ainvoke(initial_state)

    print(f"\n{'='*65}")
    print(f"Pipeline complete — status: {final_state['pipeline_status']}")
    print(f"{'='*65}\n")

    # If the pipeline hit an unrecoverable error, surface it clearly
    if final_state["pipeline_status"] == "error":
        raise RuntimeError(
            final_state.get("error_message") or "Pipeline failed with unknown error"
        )

    # Assemble final report from state
    return LaunchLensReport(
        product_analysis=final_state["product_analysis"],
        pmf_score=final_state.get("pmf_score"),
        gtm_pack=final_state.get("gtm_pack"),
        pipeline_status=final_state["pipeline_status"],
        error_message=final_state.get("error_message"),
    )
