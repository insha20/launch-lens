"""
Day 1 test script — run this to verify Reddit and HN APIs work
before touching any LLM code.

Usage:
    python test_tools.py
"""

import asyncio
from main import tool_reddit_search, tool_hn_search, tool_url_scrape


async def test_all():
    print("=" * 60)
    print("LaunchLens — Day 1 Tool Tests")
    print("=" * 60)

    # ── Test 1: Reddit search ──────────────────────────────────
    print("\n[1] Reddit search: 'no-code tool too expensive'")
    try:
        posts = await tool_reddit_search("no-code tool too expensive", limit=3)
        print(f"    ✓ Found {len(posts)} posts")
        for p in posts[:2]:
            print(f"    • r/{p.subreddit}: {p.title[:60]}... ({p.score} pts)")
    except Exception as e:
        print(f"    ✗ Error: {e}")

    # ── Test 2: Reddit search in specific subreddit ────────────
    print("\n[2] Reddit search in r/indiehackers: 'finding customers'")
    try:
        posts = await tool_reddit_search("finding customers", subreddit="indiehackers", limit=3)
        print(f"    ✓ Found {len(posts)} posts")
        for p in posts[:2]:
            print(f"    • {p.title[:60]}... ({p.num_comments} comments)")
    except Exception as e:
        print(f"    ✗ Error: {e}")

    # ── Test 3: HN search ──────────────────────────────────────
    print("\n[3] HN search: 'validate startup idea'")
    try:
        posts = await tool_hn_search("validate startup idea", limit=3)
        print(f"    ✓ Found {len(posts)} posts")
        for p in posts[:2]:
            print(f"    • {p.title[:60]}... ({p.score} pts)")
    except Exception as e:
        print(f"    ✗ Error: {e}")

    # ── Test 4: HN Show HN search ──────────────────────────────
    print("\n[4] HN 'Show HN' search: 'product market fit'")
    try:
        posts = await tool_hn_search("product market fit", search_type="show_hn", limit=3)
        print(f"    ✓ Found {len(posts)} posts")
        for p in posts[:2]:
            print(f"    • {p.title[:60]}...")
    except Exception as e:
        print(f"    ✗ Error: {e}")

    # ── Test 5: URL scrape ─────────────────────────────────────
    print("\n[5] URL scrape: indiehackers.com")
    try:
        result = await tool_url_scrape("https://www.indiehackers.com")
        print(f"    ✓ Status {result['status_code']}, {result['content_length']} chars fetched")
    except Exception as e:
        print(f"    ✗ Error: {e}")

    print("\n" + "=" * 60)
    print("All tests done. If ✓ on Reddit + HN, you're ready for Day 2.")
    print("Day 2: wire LangChain + Gemini to analyze this data.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_all())
