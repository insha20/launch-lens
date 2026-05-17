"""
test_rag.py — Day 4 test script

Tests in three stages:
  Stage 1: Embedding pipeline — can we embed text into Chroma?
  Stage 2: Semantic search — does retrieval find relevant chunks?
  Stage 3: RAG Synthesizer agent — full synthesis on mock evidence

Run from backend/ folder:
    python test_rag.py

What to look for:
  Stage 1: "Stored N chunks in Chroma" — confirms embedding works
  Stage 2: Retrieved chunks should be thematically relevant to queries
  Stage 3: Synthesis should cite specific evidence, not hallucinate
"""

import asyncio
import os
import uuid
import sys
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


async def test_stage1_embedding():
    """Test that text gets embedded and stored in Chroma correctly."""
    print("=" * 65)
    print("STAGE 1: Embedding Pipeline")
    print("=" * 65)

    from rag_pipeline import embed_and_store, get_store
    from schemas import CommunityEvidence, CommunityPost

    # Mock evidence — simulates what the Community Researcher returns
    mock_evidence = [
        CommunityEvidence(
            hypothesis_persona="Solo freelance developer billing 5-15 clients",
            posts=[
                CommunityPost(
                    source="reddit",
                    title="Client ghosted me twice then used my whole proposal",
                    url="https://reddit.com/r/freelance/comments/abc123",
                    score=469,
                ),
                CommunityPost(
                    source="reddit",
                    title="How do I follow up on an invoice without being annoying?",
                    url="https://reddit.com/r/freelance/comments/def456",
                    score=312,
                ),
                CommunityPost(
                    source="hackernews",
                    title="Ask HN: How do you handle late-paying clients?",
                    url="https://news.ycombinator.com/item?id=12345",
                    score=87,
                ),
            ],
            total_posts_found=3,
            strongest_signal=(
                "Strong evidence of pain. Multiple posts with 300+ upvotes "
                "about clients ghosting after proposals and not paying invoices. "
                "Key language: 'chasing payment', 'client ghosted', 'follow up "
                "without being annoying'. Community clearly feels this pain acutely."
            ),
        ),
        CommunityEvidence(
            hypothesis_persona="Growing freelancer scaling to 10+ clients",
            posts=[
                CommunityPost(
                    source="reddit",
                    title="My manual follow-up system is breaking down at scale",
                    url="https://reddit.com/r/freelance/comments/ghi789",
                    score=156,
                ),
            ],
            total_posts_found=1,
            strongest_signal=(
                "Moderate evidence. Some posts about scaling pain but fewer "
                "than the first hypothesis. Pain is real but less acute."
            ),
        ),
    ]

    session_id = str(uuid.uuid4())
    print(f"\nSession ID: {session_id[:8]}...")
    print("Embedding mock community evidence...")

    try:
        store = embed_and_store(mock_evidence, session_id)
        print(f"✓ Vector store created")

        # Verify retrieval from cache
        cached = get_store(session_id)
        assert cached is not None, "Store not cached"
        print(f"✓ Store cached and retrievable by session ID")

        return store, session_id

    except Exception as e:
        print(f"✗ Embedding failed: {e}")
        import traceback
        traceback.print_exc()
        return None, None


async def test_stage2_semantic_search(store, session_id):
    """Test that semantic search returns relevant results."""
    print("\n" + "=" * 65)
    print("STAGE 2: Semantic Search")
    print("=" * 65)

    if store is None:
        print("✗ Skipping — Stage 1 failed")
        return

    from rag_pipeline import semantic_search, format_retrieved_docs

    test_queries = [
        "client not paying invoice",
        "follow up email without being pushy",
        "freelancer scaling problems",
        "proposal ignored by client",
    ]

    for query in test_queries:
        print(f"\nQuery: '{query}'")
        try:
            docs = semantic_search(store, query, k=2)
            print(f"  ✓ Retrieved {len(docs)} chunks")
            for doc in docs:
                source = doc.metadata.get("source", "?")
                preview = doc.page_content[:80].replace("\n", " ")
                print(f"  • [{source}] {preview}...")
        except Exception as e:
            print(f"  ✗ Search failed: {e}")

    # Test formatted output
    print("\n--- Formatted retrieval output (what the LLM sees) ---")
    docs = semantic_search(store, "invoice payment freelancer", k=3)
    formatted = format_retrieved_docs(docs)
    print(formatted[:500] + "..." if len(formatted) > 500 else formatted)


async def test_stage3_rag_synthesizer(store, session_id):
    """Test the full RAG Synthesizer agent."""
    print("\n" + "=" * 65)
    print("STAGE 3: RAG Synthesizer Agent")
    print("=" * 65)

    if store is None:
        print("✗ Skipping — Stage 1 failed")
        return

    if not os.getenv("GEMINI_API_KEY"):
        print("✗ GEMINI_API_KEY not set — skipping LLM test")
        return

    from schemas import ICPHypothesis
    from agents.rag_synthesizer import synthesize_hypothesis

    test_hypothesis = ICPHypothesis(
        persona="Solo freelance developer billing 5-15 clients monthly",
        pain_intensity=8,
        why_they_pay="To stop losing deals from missed follow-ups and recover unpaid invoices faster",
        communities=["r/freelance", "r/webdev"],
        search_queries=[
            "client not responding to proposal",
            "how to follow up invoice politely",
            "freelancer chasing payment",
        ]
    )

    print(f"\nSynthesizing hypothesis: {test_hypothesis.persona[:50]}...")
    print("(LLM will only answer from retrieved evidence — not from memory)")

    try:
        result = await synthesize_hypothesis(test_hypothesis, store)

        print(f"\n✓ Synthesis complete")
        print(f"\nPain confirmed: {result.pain_confirmed}")
        print(f"Confidence score: {result.confidence_score:.2f}")
        print(f"\nSupporting quotes:")
        for q in result.supporting_quotes:
            print(f"  • {q[:120]}")

        # Validate output
        assert 0.0 <= result.confidence_score <= 1.0
        assert isinstance(result.pain_confirmed, bool)
        assert len(result.supporting_quotes) > 0
        print(f"\n✓ Schema validation passed")

    except Exception as e:
        print(f"✗ Synthesis error: {e}")
        import traceback
        traceback.print_exc()


async def main():
    store, session_id = await test_stage1_embedding()
    await test_stage2_semantic_search(store, session_id)
    await test_stage3_rag_synthesizer(store, session_id)

    print("\n" + "=" * 65)
    print("Day 4 tests complete.")
    print("If all 3 stages ✓, you're ready for Day 5.")
    print("Day 5: PMF Scorer + GTM Copywriter agents")
    print("=" * 65)


if __name__ == "__main__":
    asyncio.run(main())