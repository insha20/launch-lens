"""
agents/pmf_scorer.py — Agent 4: PMF Scorer

WHAT THIS AGENT DOES:
Takes the RAG Synthesizer's evidence about each ICP hypothesis (pain_confirmed,
confidence_score) and synthesizes it into a single Product-Market Fit score
(1-10) with mandatory chain-of-thought reasoning.

WHY CHAIN-OF-THOUGHT MATTERS:
Without reasoning, an LLM can hallucinate a score out of thin air.
With chain-of-thought, the LLM must:
  1. Count confirmed pain points
  2. Weight by confidence scores
  3. Assess market size signals
  4. Identify gaps in the evidence
  5. Then justify the final score

This reasoning is the audit trail — when you show someone the report,
they can see exactly why the score is what it is.

INTERVIEW TALKING POINT:
"I implemented chain-of-thought scoring to prevent hallucination. The LLM
can't skip to a score without reasoning through the evidence. The 'reasoning'
field is mandatory and becomes the executive summary of the analysis."

THE ROUTING DECISION:
After scoring, the agent classifies the signal:
  - "strong signal" (7-10): product likely has PMF, move to GTM copywriting
  - "weak signal" (4-6): product has potential but needs pivots
  - "insufficient data" (1-3 or <2 confirmed hypotheses): need more research

This routes the pipeline downstream — e.g., if insufficient data, the
GTM Copywriter doesn't run (Day 6 LangGraph orchestrator handles routing).
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
    SynthesisResult,
    PMFScore,
)


# ─────────────────────────────────────────────────────────────
# Chain-of-thought scoring prompt
# ─────────────────────────────────────────────────────────────

SCORING_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a product-market fit analyst. Your job: convert evidence
into a rigorous PMF score with chain-of-thought reasoning.

SCORING RUBRIC:
8-10: "Strong signal"
  • 2-3 hypotheses with pain_confirmed=True
  • Average confidence_score >= 0.75
  • Evidence suggests significant market pain
  • Clear differentiation from existing solutions
  
6-7: "Moderate signal"
  • 1-2 hypotheses with pain_confirmed=True
  • Average confidence_score 0.5-0.74
  • Evidence is real but not overwhelming
  • Possible but needs validation or differentiation

4-5: "Weak signal"
  • Some confirmed pain but gaps in evidence
  • Confidence_scores scattered or low
  • Market may be too small or too saturated
  
1-3: "Insufficient data"
  • <1 hypothesis confirmed
  • Most confidence_scores < 0.4
  • Cannot score reliably — need more research

YOUR RESPONSE FORMAT:
STEP 1: Count confirmed hypotheses
STEP 2: Analyze confidence distribution (mean, spread)
STEP 3: List strongest signals and biggest gaps
STEP 4: Consider market sizing (from evidence language like "thousands" vs "hundreds")
STEP 5: Assess differentiation — does the product solve the pain better than existing solutions?
STEP 6: Assign score 1-10 based on rubric above
REASONING: [2-3 sentences justifying the score]
VERDICT: [strong signal | moderate signal | weak signal | insufficient data]
NEXT_STEP: [if strong signal: "move to GTM copywriting" | else: "flag for more research"]"""),

    ("human", """Product: {product_description}

Assumed customer: {assumed_customer}

Market category: {market_category}

ICP Analysis Results:
{synthesis_results}

Provide your PMF score (1-10) with complete chain-of-thought reasoning.""")
])


# ─────────────────────────────────────────────────────────────
# Parse the LLM's scoring response
# ─────────────────────────────────────────────────────────────

def parse_scoring_response(response: str) -> PMFScore:
    """
    Parses the structured text response from the scoring LLM
    into a PMFScore Pydantic object.

    Extracts: score (1-10), reasoning, strongest_signal, biggest_gap, verdict
    """
    lines = response.strip().split("\n")
    result = {
        "score": 5,                           # default safe middle ground
        "reasoning": response[:200],           # fallback
        "strongest_signal": "",
        "biggest_gap": "",
        "verdict": "weak signal",             # conservative default
    }

    for line in lines:
        line = line.strip()

        if line.startswith("STEP 6:") or "score" in line.lower():
            # Try to extract a number 1-10
            import re
            numbers = re.findall(r'\b([1-9]|10)\b', line)
            if numbers:
                result["score"] = int(numbers[-1])  # take last found number

        elif line.startswith("REASONING:"):
            result["reasoning"] = line.replace("REASONING:", "").strip()

        elif line.startswith("VERDICT:"):
            verdict_text = line.replace("VERDICT:", "").strip().lower()
            # Normalize verdict
            if "strong" in verdict_text:
                result["verdict"] = "strong signal"
            elif "moderate" in verdict_text:
                result["verdict"] = "moderate signal"
            elif "insufficient" in verdict_text:
                result["verdict"] = "insufficient data"
            else:
                result["verdict"] = "weak signal"

        elif line.startswith("STEP 3:") or "strongest signal" in line.lower():
            result["strongest_signal"] = line.replace("STEP 3:", "").strip()[:200]

        elif "biggest gap" in line.lower() or "gaps" in line.lower():
            result["biggest_gap"] = line[:200]

    # Ensure score is valid
    result["score"] = max(1, min(10, result["score"]))

    return PMFScore(
        score=result["score"],
        reasoning=result["reasoning"],
        strongest_signal=result["strongest_signal"] or "See reasoning above",
        biggest_gap=result["biggest_gap"] or "Insufficient evidence to assess",
        verdict=result["verdict"],
    )


# ─────────────────────────────────────────────────────────────
# Build the scoring chain
# ─────────────────────────────────────────────────────────────

def build_scorer_chain():
    """
    Simple LangChain chain: prompt → LLM → string output.
    No structured output — we parse the text response for flexibility.
    """
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=os.getenv("GEMINI_API_KEY"),
        temperature=0.1,   # low — scoring needs consistency
    )
    return SCORING_PROMPT | llm | StrOutputParser()


_scorer_chain = None

def get_scorer_chain():
    global _scorer_chain
    if _scorer_chain is None:
        _scorer_chain = build_scorer_chain()
    return _scorer_chain


# ─────────────────────────────────────────────────────────────
# Main scoring function
# ─────────────────────────────────────────────────────────────

async def score_pmf(
    analysis: ProductAnalysis,
    synthesis_results: list[SynthesisResult],
) -> PMFScore:
    """
    Full PMF scoring pipeline:
    1. Format synthesis results into readable evidence summary
    2. Run LLM scoring with chain-of-thought prompt
    3. Parse response into PMFScore
    4. Return structured score + reasoning

    This is the function the LangGraph orchestrator (Day 6) will call.
    """
    chain = get_scorer_chain()

    # Format synthesis results into a readable summary
    synthesis_text = _format_synthesis_for_scoring(synthesis_results)

    print(f"\n[PMF Scorer] Analyzing {len(synthesis_results)} hypotheses...")

    # Run the scoring chain
    response = await chain.ainvoke({
        "product_description": analysis.problem_being_solved,
        "assumed_customer": analysis.assumed_customer,
        "market_category": analysis.market_category,
        "synthesis_results": synthesis_text,
    })

    pmf_score = parse_scoring_response(response)

    print(f"  ✓ Score: {pmf_score.score}/10 | Verdict: {pmf_score.verdict}")

    return pmf_score


def _format_synthesis_for_scoring(results: list[SynthesisResult]) -> str:
    """
    Formats SynthesisResult objects into readable text for the scoring LLM.
    """
    lines = ["ICP Analysis Results:\n"]

    confirmed_count = sum(1 for r in results if r.pain_confirmed)
    avg_confidence = sum(r.confidence_score for r in results) / len(results) if results else 0.0

    lines.append(f"Summary: {confirmed_count}/{len(results)} hypotheses confirmed")
    lines.append(f"Average confidence: {avg_confidence:.2f}/1.0\n")

    for i, result in enumerate(results, 1):
        status = "✓ CONFIRMED" if result.pain_confirmed else "✗ NOT CONFIRMED"
        lines.append(f"Hypothesis {i}: {result.hypothesis_persona}")
        lines.append(f"  Status: {status} | Confidence: {result.confidence_score:.2f}")
        lines.append(f"  Evidence: {result.supporting_quotes[0][:150] if result.supporting_quotes else 'None'}")
        lines.append("")

    return "\n".join(lines)
