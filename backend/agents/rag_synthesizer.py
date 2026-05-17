"""
agents/rag_synthesizer.py — Agent 3: RAG Synthesizer

WHAT THIS AGENT DOES:
Takes the community evidence collected by the Community Researcher,
embeds it into Chroma, then for each ICP hypothesis runs a semantic
search to find the most relevant evidence and synthesizes a grounded
assessment of whether the pain is real and confirmed.

WHY THIS IS THE MOST TECHNICALLY INTERESTING AGENT:
This is pure RAG — Retrieval Augmented Generation. The LLM doesn't
answer from memory or hallucinate. It can only work with what was
retrieved from the vector store. Every claim must be supported by
a specific retrieved chunk.

The key difference from the Community Researcher:
  - Researcher: "go find posts about this topic"
  - Synthesizer: "here are the posts we found, what do they actually say?"

The synthesizer is grounded. The researcher is exploratory.
Both are necessary — explore first, then analyze what you found.

INTERVIEW TALKING POINT:
"The RAG synthesizer is the anti-hallucination layer. The PMF Scorer
downstream can only score what the synthesizer confirms with retrieved
evidence. If we found zero relevant posts for a hypothesis, the
synthesizer returns pain_confirmed=False and the PMF Scorer routes
to 'insufficient data' instead of making up a score."
"""

import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

load_dotenv()

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from schemas import (
    ProductAnalysis,
    ICPHypothesis,
    CommunityEvidence,
    SynthesisResult,
)
from rag_pipeline import embed_and_store, semantic_search, format_retrieved_docs


# ─────────────────────────────────────────────────────────────
# Synthesis prompt
# ─────────────────────────────────────────────────────────────

SYNTHESIS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a research analyst synthesizing community evidence.
Your job: determine whether the community evidence confirms or denies the pain
described in an ICP hypothesis.

CRITICAL RULES:
1. Only use information from the retrieved evidence below. Do not invent posts.
2. Quote or paraphrase specific posts when making claims.
3. If the evidence is thin or irrelevant, say so honestly.
4. pain_confirmed should be True only if multiple posts clearly describe this pain.
5. confidence_score: 0.0-1.0. Base it on evidence volume and relevance.
   0.0-0.3: weak or no evidence
   0.4-0.6: some signal but not conclusive
   0.7-0.9: strong, multiple corroborating posts
   1.0: overwhelming evidence, very high-upvote posts about this exact pain"""),

    ("human", """ICP Hypothesis to evaluate:
Persona: {persona}
Pain they experience: {pain_description}

Retrieved community evidence:
{retrieved_evidence}

Analyze this evidence and respond with:
PAIN_CONFIRMED: [yes/no]
CONFIDENCE: [0.0-1.0]
SUPPORTING_QUOTES: [2-3 specific quotes or paraphrases from the evidence above]
SUMMARY: [2-3 sentences synthesizing what the evidence tells us]
KEY_LANGUAGE: [actual phrases the community uses to describe this pain]""")
])


# ─────────────────────────────────────────────────────────────
# Parse the LLM's synthesis response
# ─────────────────────────────────────────────────────────────

def parse_synthesis_response(
    response: str,
    hypothesis: ICPHypothesis,
) -> SynthesisResult:
    """
    Parses the structured text response from the synthesizer LLM
    into a SynthesisResult Pydantic object.

    We use structured text parsing here instead of with_structured_output()
    because the synthesis involves long free-form quotes that benefit from
    the LLM having more flexibility in formatting before we extract fields.
    """
    lines = response.strip().split("\n")
    result = {
        "pain_confirmed": False,
        "confidence_score": 0.0,
        "supporting_quotes": [],
        "summary": response[:300],  # fallback
    }

    for line in lines:
        line = line.strip()
        if line.startswith("PAIN_CONFIRMED:"):
            value = line.replace("PAIN_CONFIRMED:", "").strip().lower()
            result["pain_confirmed"] = value in ("yes", "true", "confirmed")

        elif line.startswith("CONFIDENCE:"):
            try:
                value = line.replace("CONFIDENCE:", "").strip()
                result["confidence_score"] = float(value)
            except ValueError:
                pass

        elif line.startswith("SUPPORTING_QUOTES:"):
            quote = line.replace("SUPPORTING_QUOTES:", "").strip()
            if quote:
                result["supporting_quotes"] = [quote]

        elif line.startswith("SUMMARY:"):
            result["summary"] = line.replace("SUMMARY:", "").strip()

        elif line.startswith("KEY_LANGUAGE:"):
            key_lang = line.replace("KEY_LANGUAGE:", "").strip()
            if key_lang and key_lang not in result["supporting_quotes"]:
                result["supporting_quotes"].append(key_lang)

    return SynthesisResult(
        hypothesis_persona=hypothesis.persona,
        supporting_quotes=result["supporting_quotes"] or ["No specific quotes extracted"],
        pain_confirmed=result["pain_confirmed"],
        confidence_score=min(max(result["confidence_score"], 0.0), 1.0),
    )


# ─────────────────────────────────────────────────────────────
# Main synthesis function
# ─────────────────────────────────────────────────────────────

def build_synthesizer_chain():
    """
    Simple LangChain chain: prompt → LLM → string output.
    No structured output here — the synthesis is free-form text
    that we parse manually for flexibility.
    """
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=os.getenv("GEMINI_API_KEY"),
        temperature=0.1,   # low — analysis needs consistency
    )
    return SYNTHESIS_PROMPT | llm | StrOutputParser()


_synthesizer_chain = None

def get_synthesizer_chain():
    global _synthesizer_chain
    if _synthesizer_chain is None:
        _synthesizer_chain = build_synthesizer_chain()
    return _synthesizer_chain


async def synthesize_hypothesis(
    hypothesis: ICPHypothesis,
    store,                          # Chroma vector store
) -> SynthesisResult:
    """
    For one ICP hypothesis:
    1. Build targeted search queries from the hypothesis
    2. Run semantic search against the vector store
    3. Format retrieved docs as context
    4. Run LLM synthesis on that context
    5. Parse and return structured result
    """
    chain = get_synthesizer_chain()

    # Build search queries from the hypothesis
    # We search for the persona's pain, not just keywords
    search_queries = [
        hypothesis.why_they_pay,
        hypothesis.persona,
    ]
    # Add the first search query from the hypothesis if available
    if hasattr(hypothesis, "search_queries") and hypothesis.search_queries:
        search_queries.append(hypothesis.search_queries[0])

    # Retrieve relevant chunks for each query and deduplicate
    all_docs = []
    seen_content = set()
    for query in search_queries:
        docs = semantic_search(store, query, k=3)
        for doc in docs:
            # Deduplicate by content hash
            content_hash = hashlib.md5(doc.page_content.encode()).hexdigest()
            if content_hash not in seen_content:
                seen_content.add(content_hash)
                all_docs.append(doc)

    # Format retrieved docs for the LLM
    retrieved_text = format_retrieved_docs(all_docs[:6])  # max 6 chunks

    print(f"  [RAG] Hypothesis: {hypothesis.persona[:45]}...")
    print(f"  [RAG] Retrieved {len(all_docs)} relevant chunks")

    # Run the synthesis chain
    response = await chain.ainvoke({
        "persona": hypothesis.persona,
        "pain_description": hypothesis.why_they_pay,
        "retrieved_evidence": retrieved_text,
    })

    return parse_synthesis_response(response, hypothesis)


async def synthesize_all(
    analysis: ProductAnalysis,
    evidence_list: list[CommunityEvidence],
    session_id: str,
) -> list[SynthesisResult]:
    """
    Full RAG synthesis pipeline:
    1. Embed all community evidence into Chroma
    2. For each ICP hypothesis, retrieve + synthesize
    3. Return list of SynthesisResult objects

    This is the function the LangGraph orchestrator (Day 6) will call.
    """
    print(f"\n[RAG Synthesizer] Embedding {len(evidence_list)} evidence sets...")

    # Step 1: embed all evidence into vector store
    store = embed_and_store(evidence_list, session_id)

    # Step 2: synthesize each hypothesis against the store
    results = []
    for i, hypothesis in enumerate(analysis.icp_hypotheses):
        print(f"\n[RAG Synthesizer] Synthesizing hypothesis {i+1}/3...")
        try:
            result = await synthesize_hypothesis(hypothesis, store)
            results.append(result)
            print(f"  ✓ Pain confirmed: {result.pain_confirmed} | "
                  f"Confidence: {result.confidence_score:.1f}")
        except Exception as e:
            print(f"  ✗ Synthesis failed: {e}")
            results.append(SynthesisResult(
                hypothesis_persona=hypothesis.persona,
                supporting_quotes=[f"Synthesis error: {str(e)}"],
                pain_confirmed=False,
                confidence_score=0.0,
            ))

    return results


# needed for parse_synthesis_response
import hashlib