"""
test_pmf_and_gtm.py — Day 5 test script

Tests in two stages:
  Stage 1: PMF Scorer — can it score hypotheses with reasoning?
  Stage 2: GTM Copywriter — can it generate copy grounded in evidence?

Run from backend/ folder:
    python test_pmf_and_gtm.py

What to look for:
  Stage 1: Score 1-10 with clear reasoning, correct verdict
  Stage 2: Cold DM, Reddit angle, landing page all use customer language
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


async def test_stage1_pmf_scorer():
    """Test PMF scoring with chain-of-thought reasoning."""
    print("=" * 65)
    print("STAGE 1: PMF Scorer")
    print("=" * 65)

    from agents.pmf_scorer import score_pmf
    from schemas import ProductAnalysis, ICPHypothesis, SynthesisResult

    # Mock analysis
    analysis = ProductAnalysis(
        problem_being_solved="Freelancers lose deals because they forget to follow up on proposals",
        assumed_customer="Solo freelancers billing 5-15 clients monthly",
        market_category="Freelancer productivity",
        icp_hypotheses=[
            ICPHypothesis(
                persona="Solo freelancer billing 5-15 clients",
                pain_intensity=8,
                why_they_pay="To stop losing deals from missed follow-ups",
                communities=["r/freelance", "r/webdev"],
                search_queries=["forget follow up proposal", "lost client deal"],
            ),
        ],
    )

    # Mock synthesis results (strong evidence)
    synthesis_results = [
        SynthesisResult(
            hypothesis_persona="Solo freelancer billing 5-15 clients",
            supporting_quotes=[
                "Lost a $5k client because I forgot to follow up on my proposal",
                "I use a manual spreadsheet and still miss follow-ups",
                "This is why I'm not growing past 5 clients",
            ],
            pain_confirmed=True,
            confidence_score=0.89,
        ),
        SynthesisResult(
            hypothesis_persona="Growing freelancer scaling to 10+ clients",
            supporting_quotes=[
                "At scale my follow-up system breaks down",
            ],
            pain_confirmed=True,
            confidence_score=0.72,
        ),
        SynthesisResult(
            hypothesis_persona="Freelancer with long-term retainer relationships",
            supporting_quotes=[
                "Not applicable — retainers change the dynamics",
            ],
            pain_confirmed=False,
            confidence_score=0.2,
        ),
    ]

    print("\nInput: 2/3 hypotheses confirmed, avg confidence 0.6")
    print("Expected: Score 7-8 range (strong signal)")

    if not os.getenv("GEMINI_API_KEY"):
        print("✗ GEMINI_API_KEY not set — skipping LLM test")
        return None

    try:
        pmf_score = await score_pmf(analysis, synthesis_results)

        print(f"\n✓ Scoring complete")
        print(f"  Score: {pmf_score.score}/10")
        print(f"  Verdict: {pmf_score.verdict}")
        print(f"  Reasoning: {pmf_score.reasoning[:200]}...")
        print(f"  Strongest signal: {pmf_score.strongest_signal[:100]}...")
        print(f"  Biggest gap: {pmf_score.biggest_gap[:100]}...")

        # Validate output
        assert 1 <= pmf_score.score <= 10, f"Score out of range: {pmf_score.score}"
        assert pmf_score.verdict in ["strong signal", "moderate signal", "weak signal", "insufficient data"]
        assert len(pmf_score.reasoning) > 20, "Reasoning too short"
        print(f"\n✓ Schema validation passed")

        return pmf_score

    except Exception as e:
        print(f"✗ Scoring error: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_stage2_gtm_copywriter(pmf_score):
    """Test GTM copy generation grounded in evidence."""
    print("\n" + "=" * 65)
    print("STAGE 2: GTM Copywriter")
    print("=" * 65)

    if pmf_score is None:
        print("✗ Skipping — Stage 1 failed")
        return

    if not os.getenv("GEMINI_API_KEY"):
        print("✗ GEMINI_API_KEY not set — skipping LLM test")
        return

    from agents.gtm_copywriter import generate_gtm_pack
    from schemas import ProductAnalysis, ICPHypothesis, SynthesisResult

    # Same mock data as Stage 1
    analysis = ProductAnalysis(
        problem_being_solved="Freelancers lose deals because they forget to follow up on proposals",
        assumed_customer="Solo freelancers billing 5-15 clients monthly",
        market_category="Freelancer productivity",
        icp_hypotheses=[
            ICPHypothesis(
                persona="Solo freelancer billing 5-15 clients",
                pain_intensity=8,
                why_they_pay="To stop losing deals from missed follow-ups",
                communities=["r/freelance", "r/webdev"],
                search_queries=["forget follow up proposal", "lost client deal"],
            ),
        ],
    )

    synthesis_results = [
        SynthesisResult(
            hypothesis_persona="Solo freelancer billing 5-15 clients",
            supporting_quotes=[
                "Lost a $5k client because I forgot to follow up",
                "I use a manual spreadsheet and still miss follow-ups",
                "This is why I'm not growing",
            ],
            pain_confirmed=True,
            confidence_score=0.89,
        ),
        SynthesisResult(
            hypothesis_persona="Growing freelancer scaling to 10+ clients",
            supporting_quotes=["At scale my follow-up system breaks"],
            pain_confirmed=True,
            confidence_score=0.72,
        ),
        SynthesisResult(
            hypothesis_persona="Retainer freelancer",
            supporting_quotes=["Not applicable"],
            pain_confirmed=False,
            confidence_score=0.2,
        ),
    ]

    print("\nGenerating copy grounded in evidence...")
    print("Expected: Cold DM uses phrases like 'forgot to follow up' or 'lost deal'")
    print("Expected: Landing page headline speaks to outcome, not features")

    try:
        gtm_pack = await generate_gtm_pack(analysis, synthesis_results, pmf_score)

        print(f"\n✓ GTM Pack generated")

        print(f"\n--- Cold DM ---")
        print(gtm_pack.cold_dm)

        print(f"\n--- Reddit Post Angle ---")
        print(gtm_pack.reddit_post_angle[:300])

        print(f"\n--- Landing Page ---")
        print(f"Headline: {gtm_pack.landing_page_headline}")
        print(f"Subheadline: {gtm_pack.landing_page_subheadline}")

        # Validate output
        assert len(gtm_pack.cold_dm) > 50, "Cold DM too short"
        assert len(gtm_pack.reddit_post_angle) > 50, "Reddit angle too short"
        assert len(gtm_pack.landing_page_headline) > 5, "Headline too short"
        assert len(gtm_pack.landing_page_subheadline) > 10, "Subheadline too short"
        print(f"\n✓ Schema validation passed")

    except Exception as e:
        print(f"✗ GTM generation error: {e}")
        import traceback
        traceback.print_exc()


async def main():
    pmf_score = await test_stage1_pmf_scorer()
    await test_stage2_gtm_copywriter(pmf_score)

    print("\n" + "=" * 65)
    print("Day 5 tests complete.")
    print("If both stages ✓, you're ready for Day 6.")
    print("Day 6: LangGraph orchestrator — wire all 5 agents into a state machine")
    print("=" * 65)


if __name__ == "__main__":
    asyncio.run(main())
