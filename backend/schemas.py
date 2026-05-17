"""
schemas.py — single source of truth for all data shapes in LaunchLens.

Every agent reads from and writes to these schemas.
Defining them in one file means:
- No circular imports between agents
- One place to update when shapes change
- Interviewers can read this file and understand the entire data model
"""

from pydantic import BaseModel, Field
from typing import Optional


# ─────────────────────────────────────────────────────────────
# INPUT schemas — what enters the pipeline
# ─────────────────────────────────────────────────────────────

class ProductInput(BaseModel):
    """What the user submits to start the pipeline."""
    description: str = Field(
        ...,                          # ... means required, no default
        min_length=20,
        max_length=1000,
        description="Plain English description of the product"
    )
    url: Optional[str] = Field(
        default=None,
        description="Optional product URL for the scraper agent"
    )


# ─────────────────────────────────────────────────────────────
# AGENT 1 OUTPUT — Product Analyst
# ─────────────────────────────────────────────────────────────

class ICPHypothesis(BaseModel):
    """
    A single Ideal Customer Profile hypothesis.
    The Product Analyst generates 3 of these.
    The Community Researcher validates each one against real data.
    """
    persona: str = Field(
        description="Who this customer is in one sentence. e.g. 'Solo freelance developer billing 3-10 clients'"
    )
    pain_intensity: int = Field(
        ge=1, le=10,                  # ge = greater or equal, le = less or equal
        description="How painful is this problem for this persona? 1=mild annoyance, 10=costs them money daily"
    )
    why_they_pay: str = Field(
        description="One sentence: what outcome makes them open their wallet"
    )
    communities: list[str] = Field(
        description="Subreddits or online communities where this persona spends time. e.g. ['r/freelance', 'r/webdev']"
    )
    search_queries: list[str] = Field(
        description="3-5 search queries this persona would type when frustrated with this problem"
    )


class ProductAnalysis(BaseModel):
    """
    Full output of the Product Analyst agent.
    This is what gets passed to the Community Researcher.
    """
    problem_being_solved: str = Field(
        description="The core problem in one sentence, from the customer's perspective not the builder's"
    )
    assumed_customer: str = Field(
        description="Who the builder seems to think their customer is"
    )
    market_category: str = Field(
        description="What category this product fits into. e.g. 'freelancer productivity', 'B2B SaaS tooling'"
    )
    icp_hypotheses: list[ICPHypothesis] = Field(
        description="Exactly 3 different ICP hypotheses to validate, ordered from most to least likely"
    )
    red_flags: list[str] = Field(
        default=[],
        description="Any obvious problems with the idea worth flagging before spending time researching"
    )


# ─────────────────────────────────────────────────────────────
# AGENT 2 OUTPUT — Community Researcher (Day 3)
# ─────────────────────────────────────────────────────────────

class CommunityPost(BaseModel):
    """A single post from Reddit or HN."""
    source: str                        # "reddit" or "hackernews"
    title: str
    url: str
    score: int
    relevance_note: Optional[str] = None   # added by the researcher agent


class CommunityEvidence(BaseModel):
    """Evidence found for one ICP hypothesis."""
    hypothesis_persona: str            # which ICP this evidence is for
    posts: list[CommunityPost]
    total_posts_found: int
    strongest_signal: str              # one sentence summary of the most compelling evidence


# ─────────────────────────────────────────────────────────────
# AGENT 3 OUTPUT — RAG Synthesizer (Day 4)
# ─────────────────────────────────────────────────────────────

class SynthesisResult(BaseModel):
    """RAG synthesizer output — evidence mapped to each ICP."""
    hypothesis_persona: str
    supporting_quotes: list[str]       # actual phrases from community posts
    pain_confirmed: bool
    confidence_score: float            # 0.0 to 1.0


# ─────────────────────────────────────────────────────────────
# AGENT 4 OUTPUT — PMF Scorer (Day 5)
# ─────────────────────────────────────────────────────────────

class PMFScore(BaseModel):
    """
    Product-Market Fit score with mandatory reasoning.
    The 'reasoning' field is the key to stopping hallucination —
    the LLM must justify its score before committing to a number.
    """
    score: int = Field(ge=1, le=10)
    reasoning: str = Field(
        description="Step by step reasoning that led to this score. Must cite specific evidence."
    )
    strongest_signal: str
    biggest_gap: str
    verdict: str                       # "strong signal" | "weak signal" | "insufficient data"


# ─────────────────────────────────────────────────────────────
# AGENT 5 OUTPUT — GTM Copywriter (Day 5)
# ─────────────────────────────────────────────────────────────

class GTMPack(BaseModel):
    """Go-to-market starter pack written in the customer's own language."""
    target_persona: str
    cold_dm: str
    reddit_post_angle: str
    landing_page_headline: str
    landing_page_subheadline: str
    community_targets: list[str]


# ─────────────────────────────────────────────────────────────
# FINAL PIPELINE OUTPUT — assembled by the orchestrator
# ─────────────────────────────────────────────────────────────

class LaunchLensReport(BaseModel):
    """The complete report returned to the user."""
    product_analysis: Optional[ProductAnalysis] = None
    pmf_score: Optional[PMFScore] = None
    gtm_pack: Optional[GTMPack] = None
    pipeline_status: str               # "complete" | "insufficient_data" | "error"
    error_message: Optional[str] = None
