"""
test_researcher.py — Day 3 test script

Tests in two stages:
  Stage 1: MCP tools directly (no LLM) — verify data flows correctly
  Stage 2: Community Researcher agent — verify the ReAct loop works

Run from backend/ folder:
    python test_researcher.py

What to watch in the output:
- Stage 1: real Reddit/HN posts coming back with titles and scores
- Stage 2: the agent's reasoning chain (Thought/Action/Observation)
  This is the most interesting part — you'll see the LLM decide
  which tool to call and why, then react to what it finds.
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


async def test_stage1_mcp_tools():
    """Test MCP tools directly — no LLM involved."""
    print("=" * 65)
    print("STAGE 1: MCP Tools Direct Test")
    print("=" * 65)

    from mcp_server import _reddit_search, _hn_search, get_mcp_tools

    # ── Test 1: Reddit search ──────────────────────────────────
    print("\n[1] Reddit: 'how to chase invoice without being annoying'")
    try:
        posts = await _reddit_search(
            "how to chase invoice without being annoying",
            limit=3
        )
        print(f"    ✓ {len(posts)} posts found")
        for p in posts[:2]:
            print(f"    • r/{p['subreddit']} ({p['score']} pts): {p['title'][:55]}...")
    except Exception as e:
        print(f"    ✗ {e}")

    # ── Test 2: Subreddit-specific search ─────────────────────
    print("\n[2] Reddit r/freelance: 'client ghosting proposal'")
    try:
        posts = await _reddit_search(
            "client ghosting proposal",
            subreddit="freelance",
            limit=3
        )
        print(f"    ✓ {len(posts)} posts found")
        for p in posts[:2]:
            print(f"    • {p['score']} pts | {p['num_comments']} comments: {p['title'][:55]}...")
    except Exception as e:
        print(f"    ✗ {e}")

    # ── Test 3: HN story search ────────────────────────────────
    print("\n[3] HN stories: 'getting first customers saas'")
    try:
        posts = await _hn_search("getting first customers saas", limit=3)
        print(f"    ✓ {len(posts)} posts found")
        for p in posts[:2]:
            print(f"    • {p['score']} pts: {p['title'][:55]}...")
    except Exception as e:
        print(f"    ✗ {e}")

    # ── Test 4: HN Show HN search ─────────────────────────────
    print("\n[4] HN Show HN: 'freelancer invoice'")
    try:
        posts = await _hn_search("freelancer invoice", search_type="show_hn", limit=3)
        print(f"    ✓ {len(posts)} posts found")
        for p in posts[:2]:
            print(f"    • {p['score']} pts: {p['title'][:55]}...")
    except Exception as e:
        print(f"    ✗ {e}")

    # ── Test 5: LangChain tool wrappers ───────────────────────
    print("\n[5] LangChain tool wrappers (what agents actually call)")
    try:
        tools = get_mcp_tools()
        tool_names = [t.name for t in tools]
        print(f"    ✓ {len(tools)} tools registered: {tool_names}")

        # Call one tool directly to verify the wrapper works
        reddit_tool = next(t for t in tools if t.name == "search_reddit")
        result = reddit_tool.invoke({
            "query": "my saas has no users",
            "limit": 2
        })
        print(f"    ✓ Tool invocation works")
        print(f"    Preview: {result[:150]}...")
    except Exception as e:
        print(f"    ✗ {e}")

    print("\n✓ Stage 1 complete — MCP tools working")


async def test_stage2_researcher_agent():
    """Test the Community Researcher ReAct agent."""
    print("\n" + "=" * 65)
    print("STAGE 2: Community Researcher Agent Test")
    print("(Watch the Thought/Action/Observation loop below)")
    print("=" * 65)

    if not os.getenv("GEMINI_API_KEY"):
        print("✗ GEMINI_API_KEY not set — skipping agent test")
        return

    from schemas import ICPHypothesis
    from agents.community_researcher import research_hypothesis

    # Test with one hypothesis (full pipeline is 3 — too slow for a test)
    test_hypothesis = ICPHypothesis(
        persona="Solo freelance developer billing 5-15 clients monthly",
        pain_intensity=8,
        why_they_pay="To stop losing deals from missed follow-ups and recover unpaid invoices faster",
        communities=["r/freelance", "r/webdev"],
        search_queries=[
            "client not responding to proposal",
            "how to follow up invoice politely",
            "freelancer chasing payment reddit",
        ]
    )

    print(f"\nResearching: {test_hypothesis.persona}")
    print("(The agent's reasoning chain will print below — read it carefully)")
    print("-" * 65)

    try:
        evidence = await research_hypothesis(test_hypothesis)
        print("\n" + "-" * 65)
        print("✓ Research complete")
        print(f"\nPersona: {evidence.hypothesis_persona[:60]}...")
        print(f"Posts found: {evidence.total_posts_found}")
        print(f"\nStrongest signal:\n{evidence.strongest_signal[:400]}")
    except Exception as e:
        print(f"\n✗ Agent error: {e}")
        print(f"Type: {type(e).__name__}")

    print("\n✓ Stage 2 complete")


async def main():
    await test_stage1_mcp_tools()
    await test_stage2_researcher_agent()

    print("\n" + "=" * 65)
    print("Day 3 tests complete.")
    print("If Stage 1 ✓ and Stage 2 ✓, you're ready for Day 4.")
    print("Day 4: RAG pipeline — embed community posts into Chroma")
    print("=" * 65)


if __name__ == "__main__":
    asyncio.run(main())
