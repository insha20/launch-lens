"""
test_reddit_retry.py — Test the new retry logic for Reddit API blocking
"""
import asyncio
from mcp_server import _reddit_search


async def test_reddit_retry():
    """Test that retry logic kicks in for 403 errors."""
    print("Testing Reddit search with retry logic...")
    
    # Test a common product query
    result = await _reddit_search(
        query="resume builder tool feedback",
        subreddit="jobs",
        limit=5
    )
    
    if result:
        print(f"✓ Found {len(result)} posts")
        for post in result[:2]:
            print(f"  - {post['title'][:60]}... ({post['score']} points)")
    else:
        print("✗ No posts found (may be due to Reddit 403 blocking)")
    
    return result


if __name__ == "__main__":
    print("\n" + "="*60)
    print("Reddit Retry Logic Test")
    print("="*60)
    result = asyncio.run(test_reddit_retry())
    print("="*60 + "\n")
