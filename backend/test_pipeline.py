"""
test_pipeline.py — Day 6 end-to-end test

Runs the full 5-agent pipeline on a real product description.
This is the test that proves the whole system works together.

Run from backend/ folder:
    python test_pipeline.py

What to look for:
  ✓ Each node prints its output in order
  ✓ Conditional routing decision is printed
  ✓ Final report has: product_analysis, pmf_score, and (if signal strong enough) gtm_pack
  ✓ pipeline_status = "complete"

Runtime: 30-90 seconds (5 LLM calls + embedding + search)
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


# ─────────────────────────────────────────────────────────────
# Test product descriptions
# ─────────────────────────────────────────────────────────────

PRODUCTS = {
    "freelancer_tool": """
        A Notion-based CRM for freelancers that automatically reminds you
        to follow up on proposals, tracks invoice status, and sends
        polite follow-up emails when clients go quiet. Built specifically
        for solo developers and designers billing 5-20 clients per month.
    """,

    "dev_tool": """
        A CLI tool that watches your git commits and automatically writes
        JIRA ticket comments with what changed and why. Connects to JIRA
        via API, reads the diff, and posts a human-readable summary so
        engineers stop copy-pasting from terminal to JIRA every day.
    """,
}


async def run_test(product_key: str = "freelancer_tool"):
    from graph import run_pipeline

    product = PRODUCTS[product_key].strip()

    print(f"\nProduct under test: {product_key}")
    print(f"Description: {product[:100]}...")

    report = await run_pipeline(product)

    print("\n" + "=" * 65)
    print("FINAL REPORT")
    print("=" * 65)

    print(f"\n📊 Pipeline Status: {report.pipeline_status}")

    if report.error_message:
        print(f"❌ Error: {report.error_message}")
        return

    if report.product_analysis:
        pa = report.product_analysis
        print(f"\n📋 Product Analysis")
        print(f"  Problem: {pa.problem_being_solved}")
        print(f"  Market: {pa.market_category}")
        print(f"  ICPs identified: {len(pa.icp_hypotheses)}")
        for h in pa.icp_hypotheses:
            print(f"    • {h.persona}")

    if report.pmf_score:
        ps = report.pmf_score
        print(f"\n🎯 PMF Score: {ps.score}/10 — {ps.verdict}")
        print(f"  Reasoning: {ps.reasoning[:200]}...")

    if report.gtm_pack:
        gp = report.gtm_pack
        print(f"\n✍️  GTM Pack — targeting: {gp.target_persona[:60]}")
        print(f"\n  Cold DM (first 200 chars):")
        print(f"  {gp.cold_dm[:200]}...")
        print(f"\n  Landing Page Headline: {gp.landing_page_headline}")
        print(f"  Subheadline: {gp.landing_page_subheadline}")
        print(f"\n  Community targets: {', '.join(gp.community_targets[:3])}")
    else:
        print("\n⚠️  GTM Pack skipped (PMF signal too weak or insufficient data)")
        print("  → Collect more community evidence before writing copy")

    print("\n" + "=" * 65)
    print("Full pipeline test complete ✓")
    print("=" * 65)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--product",
        choices=list(PRODUCTS.keys()),
        default="freelancer_tool",
        help="Which test product to run",
    )
    args = parser.parse_args()
    asyncio.run(run_test(args.product))
