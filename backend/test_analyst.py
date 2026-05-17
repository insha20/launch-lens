"""
test_analyst.py — Day 2 test script

Tests the Product Analyst agent directly, without going through FastAPI.
Run this BEFORE starting the server to confirm the agent works.

Usage:
    python test_analyst.py

What to look for in the output:
- Exactly 3 ICP hypotheses
- pain_intensity values that feel realistic (not all 9/10)
- communities that are specific subreddits, not generic terms
- search_queries that sound like a frustrated person typed them
- red_flags that are honest (saturated market, weak pain, etc.)

If you get a validation error, the LLM returned a shape that doesn't
match your Pydantic schema — read the error, it tells you exactly
which field failed. This is Pydantic doing its job.
"""

import asyncio
import json
import os
from dotenv import load_dotenv

load_dotenv()

import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agents.product_analyst import analyze_product


# ── Test products — try a range of ideas ──────────────────────
TEST_PRODUCTS = [
    {
        "name": "Freelancer follow-up tool",
        "description": (
            "A tool that helps freelancers automatically send follow-up emails "
            "to clients who haven't paid invoices or responded to proposals. "
            "It tracks when the last contact was made and sends reminders at "
            "the right intervals without being annoying."
        )
    },
    {
        "name": "LaunchLens itself",
        "description": (
            "An AI tool for indie hackers and vibe coders who built a product "
            "but don't know how to find their first customers. You describe your "
            "app and it researches Reddit and Hacker News to find who is already "
            "complaining about the problem you solve, scores product-market fit, "
            "and gives you a go-to-market starter pack written in your customer's "
            "own language."
        )
    },
]


async def test_analyst():
    print("=" * 65)
    print("LaunchLens — Day 2: Product Analyst Agent Test")
    print("=" * 65)

    if not os.getenv("GEMINI_API_KEY"):
        print("\n✗ GEMINI_API_KEY not set.")
        print("  1. Copy .env.example to .env")
        print("  2. Get a free key at https://aistudio.google.com/app/apikey")
        print("  3. Add it to your .env file")
        return

    for product in TEST_PRODUCTS:
        print(f"\n{'─' * 65}")
        print(f"Testing: {product['name']}")
        print(f"{'─' * 65}")
        print(f"Input: {product['description'][:120]}...")

        try:
            result = await analyze_product(product["description"])

            print(f"\n✓ Product Analysis complete")
            print(f"\n  Problem being solved:")
            print(f"    {result.problem_being_solved}")
            print(f"\n  Market category: {result.market_category}")

            print(f"\n  ICP Hypotheses ({len(result.icp_hypotheses)} generated):")
            for i, icp in enumerate(result.icp_hypotheses, 1):
                print(f"\n  [{i}] {icp.persona}")
                print(f"      Pain intensity: {icp.pain_intensity}/10")
                print(f"      Why they pay: {icp.why_they_pay}")
                print(f"      Communities: {', '.join(icp.communities)}")
                print(f"      Search queries:")
                for q in icp.search_queries:
                    print(f"        • {q}")

            if result.red_flags:
                print(f"\n  ⚠ Red flags:")
                for flag in result.red_flags:
                    print(f"    • {flag}")
            else:
                print(f"\n  No red flags identified")

            # Validate the shape is exactly right
            assert len(result.icp_hypotheses) == 3, \
                f"Expected 3 ICP hypotheses, got {len(result.icp_hypotheses)}"
            for icp in result.icp_hypotheses:
                assert 1 <= icp.pain_intensity <= 10, \
                    f"pain_intensity {icp.pain_intensity} out of range 1-10"
                assert len(icp.search_queries) >= 3, \
                    f"Expected at least 3 search queries, got {len(icp.search_queries)}"

            print(f"\n  ✓ Schema validation passed")

        except Exception as e:
            print(f"\n  ✗ Error: {e}")
            print(f"  Type: {type(e).__name__}")

    print(f"\n{'=' * 65}")
    print("Day 2 test complete.")
    print("If ✓ on both products, you're ready for Day 3.")
    print("Day 3: MCP server + Community Researcher agent")
    print("=" * 65)


if __name__ == "__main__":
    asyncio.run(test_analyst())
