"""
LaunchLens — main.py
Day 7: Full pipeline wired into /launch route via LangGraph orchestrator
"""

import os
import asyncio
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import httpx

# Load .env FIRST — before any other imports that might need env vars
load_dotenv()

from schemas import ProductInput, ProductAnalysis, LaunchLensReport
from agents.product_analyst import analyze_product
from graph import run_pipeline

app = FastAPI(title="LaunchLens API", version="0.7.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────
# Reddit / HN response models (move to schemas.py on Day 3)
# ─────────────────────────────────────────────────────────────

class RedditPost(BaseModel):
    title: str
    subreddit: str
    score: int
    url: str
    body: Optional[str] = None
    num_comments: int

class HNPost(BaseModel):
    title: str
    score: int
    url: Optional[str] = None
    author: str
    num_comments: int
    objectID: str


# ─────────────────────────────────────────────────────────────
# MCP tool functions (unchanged from Day 1)
# ─────────────────────────────────────────────────────────────

async def tool_reddit_search(
    query: str,
    subreddit: Optional[str] = None,
    limit: int = 10,
    time_filter: str = "year"
) -> list[RedditPost]:
    if subreddit:
        url = f"https://www.reddit.com/r/{subreddit}/search.json"
    else:
        url = "https://www.reddit.com/search.json"
    params = {
        "q": query, "sort": "relevance", "t": time_filter,
        "limit": limit, "restrict_sr": "true" if subreddit else "false",
    }
    headers = {"User-Agent": "LaunchLens/0.1 (portfolio project)"}
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    posts = []
    for child in data.get("data", {}).get("children", []):
        d = child["data"]
        posts.append(RedditPost(
            title=d.get("title", ""), subreddit=d.get("subreddit", ""),
            score=d.get("score", 0), url=f"https://reddit.com{d.get('permalink', '')}",
            body=d.get("selftext", "")[:500] if d.get("selftext") else None,
            num_comments=d.get("num_comments", 0),
        ))
    return posts


async def tool_hn_search(query: str, limit: int = 10, search_type: str = "story") -> list[HNPost]:
    url = "https://hn.algolia.com/api/v1/search"
    params = {"query": query, "tags": search_type, "hitsPerPage": limit}
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    posts = []
    for hit in data.get("hits", []):
        posts.append(HNPost(
            title=hit.get("title", hit.get("story_title", "")),
            score=hit.get("points", 0) or 0, url=hit.get("url"),
            author=hit.get("author", ""), num_comments=hit.get("num_comments", 0) or 0,
            objectID=hit.get("objectID", ""),
        ))
    return posts


async def tool_url_scrape(url: str) -> dict:
    headers = {"User-Agent": "LaunchLens/0.1 (portfolio project)"}
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers, timeout=10, follow_redirects=True)
        resp.raise_for_status()
    return {"url": url, "status_code": resp.status_code,
            "content_length": len(resp.text), "raw_preview": resp.text[:1000]}


async def tool_web_search(query: str, limit: int = 5) -> list[dict]:
    print(f"[web_search stub] '{query}'")
    return []


async def tool_embed_and_store(texts: list[str], session_id: str) -> dict:
    print(f"[embed_and_store stub] {len(texts)} texts")
    return {"session_id": session_id, "stored": len(texts), "status": "stub"}


# ─────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "0.7.0",
        "day": 7,
        "gemini_configured": bool(os.getenv("GEMINI_API_KEY")),
        "pipeline_agents": [
            "product_analyst",
            "community_researcher",
            "rag_synthesizer",
            "pmf_scorer",
            "gtm_copywriter",
        ],
    }


@app.get("/tools/reddit")
async def reddit_search(query: str, subreddit: Optional[str] = None, limit: int = 10):
    try:
        posts = await tool_reddit_search(query, subreddit, limit)
        return {"source": "reddit", "query": query, "posts": [p.model_dump() for p in posts]}
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Reddit API error: {str(e)}")


@app.get("/tools/hn")
async def hn_search(query: str, limit: int = 10):
    try:
        posts = await tool_hn_search(query, limit)
        return {"source": "hackernews", "query": query, "posts": [p.model_dump() for p in posts]}
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"HN API error: {str(e)}")


@app.post("/analyze")
async def analyze(payload: ProductInput):
    """
    Day 2: runs the Product Analyst agent and returns structured ICP analysis.
    Also fires a preview Reddit + HN search using the first ICP's search query.
    Day 3: Community Researcher agent takes over the search step properly.
    """
    try:
        # Agent 1 — Product Analyst
        analysis: ProductAnalysis = await analyze_product(payload.description)

        # Preview search using first ICP hypothesis's first search query
        first_query = (
            analysis.icp_hypotheses[0].search_queries[0]
            if analysis.icp_hypotheses else payload.description[:80]
        )
        reddit_posts, hn_posts = await asyncio.gather(
            tool_reddit_search(first_query, limit=5),
            tool_hn_search(first_query, limit=5),
        )

        return {
            "analysis": analysis.model_dump(),
            "preview_community_data": {
                "query_used": first_query,
                "reddit": [p.model_dump() for p in reddit_posts],
                "hackernews": [p.model_dump() for p in hn_posts],
                "note": "Day 3: Community Researcher will run all ICP queries properly"
            }
        }

    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.post("/launch", response_model=LaunchLensReport)
async def launch(payload: ProductInput):
    """
    Day 7: Full 5-agent pipeline.

    Runs Product Analyst → Community Researcher → RAG Synthesizer
    → PMF Scorer → (conditional) GTM Copywriter.

    Returns a LaunchLensReport with:
      - product_analysis: 3 ICP hypotheses
      - pmf_score: 1-10 score with chain-of-thought reasoning
      - gtm_pack: cold DM, Reddit angle, landing page (if signal is strong enough)
      - pipeline_status: complete | insufficient_data | error

    Runtime: 30-90 seconds (5 LLM calls + Reddit/HN search + embeddings).
    Tip: test with /docs → POST /launch → paste a product description.
    """
    try:
        report: LaunchLensReport = await run_pipeline(payload.description)
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {str(e)}")
