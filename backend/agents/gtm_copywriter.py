"""
agents/gtm_copywriter.py — Agent 5: GTM Copywriter

WHAT THIS AGENT DOES:
Takes the product analysis + PMF score and generates Go-To-Market copy
in the customer's own language. Three outputs:
  1. Cold DM — direct message to reach a customer
  2. Reddit post angle — how to introduce product to community
  3. Landing page copy — headline + subheadline

WHY "IN THE CUSTOMER'S OWN LANGUAGE":
The RAG Synthesizer has retrieved actual phrases from real community posts.
("chasing payment", "ghost clients", "invoice follow-up stress")
These are the words the customer uses. The copywriter uses this language
to make the messaging credible and resonant.

INTERVIEW TALKING POINT:
"The copywriter is grounded in community evidence. It doesn't write generic
marketing copy — it pulls actual customer phrases from Reddit/HN, ensuring
the messaging resonates with the real pain the community articulates."

STRUCTURE:
- Cold DM: Personal, conversational, builds urgency from specific pain
- Reddit angle: Community-first, not salesy, positions as solving a problem people talk about
- Landing page: Benefit-driven, speaks to outcome not features
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
    GTMPack,
)


# ─────────────────────────────────────────────────────────────
# Cold DM Template
# ─────────────────────────────────────────────────────────────

COLD_DM_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a GTM copywriter. Write a cold DM that:
  1. Opens with specific pain the recipient feels (use actual customer language from evidence)
  2. Suggests a solution without being salesy
  3. Creates low-friction next step (reply, 5-min call, link)
  4. Feels personal, not templated

CONSTRAINTS:
  • Max 150 words
  • No "breakthrough", "revolutionary", "game-changer" — these turn off engineers
  • No exclamation marks (too marketing-y)
  • Reference something specific about their pain"""),

    ("human", """Product solves: {problem_solved}

Target persona: {persona}

Customer pain points (from evidence): {pain_points}

Key language they use: {customer_language}

Write a cold DM that would actually get a response from this person.""")
])


# ─────────────────────────────────────────────────────────────
# Reddit Post Angle Template
# ─────────────────────────────────────────────────────────────

REDDIT_ANGLE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are writing a Reddit post angle for a product launch.

GOAL: Present the product as a solution to a problem the community talks about.
NOT a sales pitch — a genuine discussion starter.

FORMAT:
Title: [What problem does this solve, stated as a question or frustration]
Approach: [How to introduce the product naturally to the conversation]
Community hook: [Why this community specifically cares about this problem]

CONSTRAINTS:
  • Sound like a regular person, not a marketer
  • Reference actual Reddit vernacular or r/ subreddit culture
  • Position product as "thing I built because I had this problem"
  • Make it clear you're not spam"""),

    ("human", """Product: {product_name}

Solves: {problem_solved}

Target community: {community}

Evidence from community: {evidence}

Generate a Reddit post angle for this product.""")
])


# ─────────────────────────────────────────────────────────────
# Landing Page Copy Template
# ─────────────────────────────────────────────────────────────

LANDING_PAGE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are writing a landing page headline and subheadline.

HEADLINE: [5-8 words, speaks to the outcome, uses customer language]
  • Example: "Stop chasing client payments"
  • NOT: "Payment tracking SaaS for freelancers"

SUBHEADLINE: [15-20 words, expands on the outcome, mentions who it's for]
  • Example: "Invoice follow-ups that actually get paid. Built for freelancers tired of chasing money."
  • NOT: "Our proprietary AI-driven invoice management platform..."

RULES:
  • Use actual phrases from community evidence
  • Speak to the pain, not the solution
  • No marketing buzzwords
  • Under 100 words total"""),

    ("human", """Product solves: {problem}

For: {persona}

Evidence phrases: {evidence_language}

Pain intensity (1-10): {pain_intensity}

Generate landing page headline + subheadline.""")
])


# ─────────────────────────────────────────────────────────────
# Parse LLM responses into GTMPack fields
# ─────────────────────────────────────────────────────────────

def parse_cold_dm_response(response: str) -> str:
    """Extract cold DM from LLM response."""
    return response.strip()[:500]


def parse_reddit_angle_response(response: str) -> str:
    """Extract Reddit post angle from LLM response."""
    return response.strip()[:800]


def parse_landing_page_response(response: str, field: str = "headline") -> str:
    """
    Extract headline or subheadline from LLM response.
    field: "headline" or "subheadline"
    """
    lines = response.strip().split("\n")
    for line in lines:
        line = line.strip()
        if field == "headline" and line.startswith("HEADLINE:"):
            return line.replace("HEADLINE:", "").strip()[:100]
        elif field == "subheadline" and line.startswith("SUBHEADLINE:"):
            return line.replace("SUBHEADLINE:", "").strip()[:200]

    # Fallback
    if field == "headline":
        return response.split("\n")[0][:100]
    else:
        return response.split("\n")[-1][:200]


# ─────────────────────────────────────────────────────────────
# Build chains
# ─────────────────────────────────────────────────────────────

def build_cold_dm_chain():
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=os.getenv("GEMINI_API_KEY"),
        temperature=0.7,   # higher — copywriting benefits from creativity
    )
    return COLD_DM_PROMPT | llm | StrOutputParser()


def build_reddit_angle_chain():
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=os.getenv("GEMINI_API_KEY"),
        temperature=0.7,
    )
    return REDDIT_ANGLE_PROMPT | llm | StrOutputParser()


def build_landing_page_chain():
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=os.getenv("GEMINI_API_KEY"),
        temperature=0.7,
    )
    return LANDING_PAGE_PROMPT | llm | StrOutputParser()


_dm_chain = None
_reddit_chain = None
_landing_chain = None


def get_cold_dm_chain():
    global _dm_chain
    if _dm_chain is None:
        _dm_chain = build_cold_dm_chain()
    return _dm_chain


def get_reddit_chain():
    global _reddit_chain
    if _reddit_chain is None:
        _reddit_chain = build_reddit_angle_chain()
    return _reddit_chain


def get_landing_chain():
    global _landing_chain
    if _landing_chain is None:
        _landing_chain = build_landing_page_chain()
    return _landing_chain


# ─────────────────────────────────────────────────────────────
# Main GTM generation function
# ─────────────────────────────────────────────────────────────

async def generate_gtm_pack(
    analysis: ProductAnalysis,
    synthesis_results: list[SynthesisResult],
    pmf_score: PMFScore,
) -> GTMPack:
    """
    Full GTM copywriting pipeline:
    1. Format evidence into copywriting context
    2. Generate cold DM
    3. Generate Reddit angle
    4. Generate landing page copy
    5. Return GTMPack

    This is the function the LangGraph orchestrator (Day 6) will call.
    """
    print(f"\n[GTM Copywriter] Generating copy for score {pmf_score.score}/10...")

    # Pick the strongest ICP for targeting
    best_hypothesis = max(
        synthesis_results,
        key=lambda x: x.confidence_score if x.pain_confirmed else 0.0
    )

    pain_points = ", ".join([
        quote[:50]
        for result in synthesis_results
        for quote in (result.supporting_quotes[:1] if result.supporting_quotes else [])
    ])

    customer_language = _extract_key_phrases(synthesis_results)

    # Generate cold DM
    dm_chain = get_cold_dm_chain()
    cold_dm_response = await dm_chain.ainvoke({
        "problem_solved": analysis.problem_being_solved,
        "persona": best_hypothesis.hypothesis_persona,
        "pain_points": pain_points,
        "customer_language": customer_language,
    })
    cold_dm = parse_cold_dm_response(cold_dm_response)
    print("  ✓ Cold DM generated")

    # Generate Reddit angle
    reddit_chain = get_reddit_chain()
    reddit_response = await reddit_chain.ainvoke({
        "product_name": analysis.market_category,
        "problem_solved": analysis.problem_being_solved,
        "community": analysis.icp_hypotheses[0].communities[0] if analysis.icp_hypotheses[0].communities else "relevant community",
        "evidence": pain_points,
    })
    reddit_angle = parse_reddit_angle_response(reddit_response)
    print("  ✓ Reddit post angle generated")

    # Generate landing page copy
    landing_chain = get_landing_chain()
    landing_response = await landing_chain.ainvoke({
        "problem": analysis.problem_being_solved,
        "persona": best_hypothesis.hypothesis_persona,
        "evidence_language": customer_language,
        "pain_intensity": best_hypothesis.hypothesis_persona if hasattr(best_hypothesis, 'hypothesis_persona') else "high",
    })
    headline = parse_landing_page_response(landing_response, "headline")
    subheadline = parse_landing_page_response(landing_response, "subheadline")
    print("  ✓ Landing page copy generated")

    gtm_pack = GTMPack(
        target_persona=best_hypothesis.hypothesis_persona,
        cold_dm=cold_dm,
        reddit_post_angle=reddit_angle,
        landing_page_headline=headline,
        landing_page_subheadline=subheadline,
        community_targets=analysis.icp_hypotheses[0].communities if analysis.icp_hypotheses else [],
    )

    print(f"  ✓ GTM Pack complete")
    return gtm_pack


def _extract_key_phrases(synthesis_results: list[SynthesisResult]) -> str:
    """Extract key phrases from all synthesis results for copywriting context."""
    phrases = []
    for result in synthesis_results:
        for quote in result.supporting_quotes[:2]:
            # Take first 40 chars to keep it punchy
            phrase = quote[:40].strip()
            if phrase and len(phrase) > 5:
                phrases.append(f'"{phrase}"')

    return ", ".join(phrases[:5])  # top 5 phrases
