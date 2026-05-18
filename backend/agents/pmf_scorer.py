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
STEP 3: Strongest signals — what evidence most strongly confirms demand? Biggest gaps — what market, customer, or competitive questions remain unanswered for a founder? Write 1-2 plain sentences for each, as if advising a founder reading this report. Do NOT reference quotes, data extraction, or internal pipeline terms.
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
    import re

    lines = response.strip().split("\n")
    result = {
        "score": 5,
        "reasoning": response[:200],
        "strongest_signal": "",
        "biggest_gap": "",
        "verdict": "weak signal",
    }

    # State machine: track which multi-line section we're currently collecting
    # Sections switch when we hit a new recognised header.
    collecting = None   # "signal" | "gap" | "reasoning" | None
    signal_lines: list[str] = []
    gap_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        lower = stripped.lower()

        # ── Any STEP N: line ends the current collecting section ──────
        if re.match(r"^step\s+\d+", lower):
            # Only STEP 6 carries a score we care about
            if re.match(r"^step\s*6", lower):
                collecting = None
                # Normalise all "N/10" and "N out of 10" variants to just "N"
                # so the denominator 10 is never mistaken for the score.
                clean = re.sub(r'(\d+)\s*/\s*10', r'\1', stripped)
                clean = re.sub(r'(\d+)\s+out\s+of\s+10', r'\1', clean, flags=re.IGNORECASE)
                # Also strip bare " 10" that follows "score" to avoid grabbing it
                clean = re.sub(r'\b10\b', '', clean)
                numbers = re.findall(r'\b([1-9])\b', clean)
                if numbers:
                    # Take the FIRST digit found — that's the actual score
                    result["score"] = int(numbers[0])
            elif re.match(r"^step\s*3", lower):
                # STEP 3 starts the signal/gap section but the header
                # line itself is just a description — don't collect it
                collecting = "signal"
            else:
                collecting = None
            continue

        # ── Named section headers (can appear outside of STEP N) ─────
        # Catch "Score: N" or "Score: N/10" on its own line (LLM sometimes
        # puts the number on the line after STEP 6 instead of inline).
        m_score = re.match(r"^score\s*[:\-]\s*(.+)", stripped, re.IGNORECASE)
        if m_score:
            score_raw = m_score.group(1)
            score_raw = re.sub(r'(\d+)\s*/\s*10', r'\1', score_raw)
            score_raw = re.sub(r'(\d+)\s+out\s+of\s+10', r'\1', score_raw, flags=re.IGNORECASE)
            score_raw = re.sub(r'\b10\b', '', score_raw)
            nums = re.findall(r'\b([1-9])\b', score_raw)
            if nums:
                result["score"] = int(nums[0])
            continue

        if stripped.startswith("REASONING:"):
            collecting = "reasoning"
            inline = stripped.replace("REASONING:", "").strip()
            if inline:
                result["reasoning"] = inline
            continue

        if stripped.startswith("VERDICT:"):
            collecting = None
            verdict_text = stripped.replace("VERDICT:", "").strip().lower()
            if "strong" in verdict_text:
                result["verdict"] = "strong signal"
            elif "moderate" in verdict_text:
                result["verdict"] = "moderate signal"
            elif "insufficient" in verdict_text:
                result["verdict"] = "insufficient data"
            else:
                result["verdict"] = "weak signal"
            continue

        if stripped.startswith("NEXT_STEP:"):
            collecting = None
            continue

        # ── Sub-headers inside STEP 3 ─────────────────────────────────
        # Match both "Strongest signals:" alone on a line AND
        # "Strongest signals: inline content here" on the same line.
        # Also tolerates **markdown bold** wrappers and em dashes (—) the
        # LLM uses instead of colons or hyphens.
        bare = re.sub(r"\*+", "", stripped).strip()  # strip ** markers
        m_signal = re.match(r"^strongest signals?\s*(?:[:\-—\u2014])\s*(.*)", bare, re.IGNORECASE)
        if m_signal:
            collecting = "signal"
            inline = m_signal.group(1).strip()
            if inline:
                signal_lines.append(inline)
            continue

        m_gap = re.match(r"^biggest gaps?\s*(?:[:\-—\u2014])\s*(.*)", bare, re.IGNORECASE)
        if m_gap:
            collecting = "gap"
            inline = m_gap.group(1).strip()
            if inline:
                gap_lines.append(inline)
            continue

        # ── Content lines belonging to the current section ────────────
        if not stripped:
            # Blank lines only end collection when we're outside STEP 3's
            # signal/gap context — avoids losing the gap section when the LLM
            # puts a blank line between "Strongest signals:" bullets and
            # "Biggest gaps:" header.
            if collecting not in ("signal", "gap"):
                collecting = None
            continue

        if collecting == "signal":
            signal_lines.append(stripped)
        elif collecting == "gap":
            gap_lines.append(stripped)
        elif collecting == "reasoning":
            result["reasoning"] = (result["reasoning"] + " " + stripped).strip()

    # ── Consolidate collected bullet lines ───────────────────────────
    def join_bullets(bullet_lines: list[str]) -> str:
        # Strip leading bullet chars and join into one readable string
        cleaned = [re.sub(r"^[\*\-\•]\s*", "", b) for b in bullet_lines if b]
        return " | ".join(cleaned)

    if signal_lines:
        result["strongest_signal"] = join_bullets(signal_lines)[:600]
    if gap_lines:
        result["biggest_gap"] = join_bullets(gap_lines)[:600]

    # Nuclear fallback — if gap_lines is still empty, scan raw response
    # for any line that contains "gap" and grab content after the colon.
    # Guards: skip STEP N: lines and lines that echo the prompt instruction
    # (detected by containing both "strongest signals" and "biggest gaps").
    PROMPT_ECHO = re.compile(r"strongest signals.{0,60}biggest gaps", re.IGNORECASE)
    if not gap_lines:
        for line in lines:
            bare_fb = re.sub(r"\*+", "", line.strip()).strip()
            if re.match(r"^step\s+\d+", bare_fb, re.IGNORECASE):
                continue
            if PROMPT_ECHO.search(bare_fb):
                continue
            if "gap" in bare_fb.lower() and ":" in bare_fb:
                content = bare_fb.split(":", 1)[1].strip()
                if content and len(content) > 5:
                    result["biggest_gap"] = content[:600]
                    break

    # Sanitise: if either field still contains the echoed STEP 3 prompt
    # instruction, replace with a clean no-data message.
    for field in ("strongest_signal", "biggest_gap"):
        val = result.get(field, "")
        if val and PROMPT_ECHO.search(val):
            result[field] = ""

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
