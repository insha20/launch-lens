"""
mcp_server.py — LaunchLens MCP Server

WHAT IS MCP?
Model Context Protocol is an open standard (by Anthropic) that defines
how AI agents communicate with external tools. Think of it as USB-C for
AI tools — one standard protocol, any tool, any agent.

WHAT THIS FILE DOES:
Defines 4 tools that any MCP-compatible agent can call by name:
  - search_reddit(query, subreddit, limit)
  - search_hackernews(query, limit, search_type)
  - scrape_url(url)
  - search_web(query, limit)  ← stub until Tavily key added

WHY A SEPARATE SERVER vs plain functions:
1. Agents call tools by name through a standard protocol, not by importing
   Python functions. This is how production AI systems work.
2. The MCP server can run as a completely separate process — your agents
   don't need to know how the tools are implemented, just what they're called.
3. It's what interviewers mean when they ask "how did your agents communicate
   with external services?" — this is the professional answer.

HOW IT RUNS:
Two modes:
  - Standalone: `python mcp_server.py` — runs as an MCP server process
  - In-process: import get_mcp_tools() and use tools directly in LangChain

ARCHITECTURE NOTE:
For this project we use in-process mode (get_mcp_tools) because it's
simpler to develop and test. The standalone mode is there to show you
understand the full MCP architecture — and because Claude Desktop can
connect to it directly, which makes a great demo.
"""

import os
import asyncio
import threading
import httpx
from typing import Optional
from dotenv import load_dotenv

# nest_asyncio allows asyncio.run() to work inside a running event loop.
# Needed because LangChain @tool wrappers are sync but our tool implementations
# are async — and tests run inside an existing asyncio event loop.
try:
    import nest_asyncio
    nest_asyncio.apply()
except ImportError:
    pass  # fine in production where tools are called from sync contexts

load_dotenv()

# MCP SDK imports
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

# LangChain tool wrapper — lets MCP tools be used in LangChain agents
from langchain_core.tools import tool as langchain_tool


# ─────────────────────────────────────────────────────────────
# Core tool implementations
# These are plain async functions — the MCP layer wraps them below
# ─────────────────────────────────────────────────────────────

async def _reddit_search(
    query: str,
    subreddit: Optional[str] = None,
    limit: int = 10,
    time_filter: str = "year"
) -> list[dict]:
    """
    Core Reddit search implementation.
    Uses the public Reddit JSON API — no auth required.
    Returns list of dicts (not Pydantic objects) so MCP can serialize them.
    """
    if subreddit:
        url = f"https://www.reddit.com/r/{subreddit}/search.json"
    else:
        url = "https://www.reddit.com/search.json"

    params = {
        "q": query,
        "sort": "relevance",
        "t": time_filter,
        "limit": min(limit, 25),          # Reddit max is 25 per request
        "restrict_sr": "true" if subreddit else "false",
    }
    headers = {"User-Agent": "LaunchLens/0.3 (portfolio project by insha)"}

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()

    posts = []
    for child in data.get("data", {}).get("children", []):
        d = child["data"]
        # Skip removed/deleted posts
        if d.get("removed_by_category") or d.get("title") == "[deleted]":
            continue
        posts.append({
            "source": "reddit",
            "title": d.get("title", ""),
            "subreddit": d.get("subreddit", ""),
            "score": d.get("score", 0),
            "num_comments": d.get("num_comments", 0),
            "url": f"https://reddit.com{d.get('permalink', '')}",
            "body": d.get("selftext", "")[:600] if d.get("selftext") else "",
            "created_utc": d.get("created_utc", 0),
        })

    return posts


async def _hn_search(
    query: str,
    limit: int = 10,
    search_type: str = "story"
) -> list[dict]:
    """
    Core HN search via Algolia API.
    Completely free, no auth, no rate limits worth worrying about.

    search_type options:
      story     — regular HN posts
      show_hn   — "Show HN:" posts (products people launched)
      ask_hn    — "Ask HN:" posts (questions and discussions)
      comment   — search within comments (good for finding pain language)
    """
    url = "https://hn.algolia.com/api/v1/search"
    params = {
        "query": query,
        "tags": search_type,
        "hitsPerPage": min(limit, 50),
    }

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

    posts = []
    for hit in data.get("hits", []):
        title = hit.get("title") or hit.get("story_title") or ""
        if not title:
            continue
        posts.append({
            "source": "hackernews",
            "title": title,
            "score": hit.get("points", 0) or 0,
            "num_comments": hit.get("num_comments", 0) or 0,
            "url": hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
            "author": hit.get("author", ""),
            "objectID": hit.get("objectID", ""),
        })

    return posts


async def _scrape_url(url: str) -> dict:
    """
    Fetches a URL and returns clean text content.
    Day 3: returns raw preview.
    Day 4+: add BeautifulSoup for proper HTML → text extraction.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; LaunchLens/0.3)",
        "Accept": "text/html,application/xhtml+xml",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            url, headers=headers, timeout=15, follow_redirects=True
        )
        resp.raise_for_status()

    # TODO Day 4: use BeautifulSoup to extract clean text
    # from bs4 import BeautifulSoup
    # soup = BeautifulSoup(resp.text, "html.parser")
    # clean_text = soup.get_text(separator=" ", strip=True)[:3000]

    return {
        "url": str(resp.url),
        "status_code": resp.status_code,
        "content_length": len(resp.text),
        "raw_preview": resp.text[:2000],
    }


async def _web_search(query: str, limit: int = 5) -> list[dict]:
    """
    Web search via Tavily API.
    Stub until TAVILY_API_KEY is added to .env.
    Free tier: 1000 searches/month at tavily.com
    """
    tavily_key = os.getenv("TAVILY_API_KEY")

    if not tavily_key:
        print(f"[web_search] TAVILY_API_KEY not set — returning empty. "
              f"Get free key at tavily.com")
        return []

    # TODO: implement Tavily when key is available
    # from tavily import TavilyClient
    # client = TavilyClient(api_key=tavily_key)
    # results = client.search(query, max_results=limit)
    return []


# ─────────────────────────────────────────────────────────────
# LangChain tool wrappers
# These let LangChain agents call the tools by name.
# The @langchain_tool decorator adds the metadata LangChain needs
# to include these in an agent's tool list.
# ─────────────────────────────────────────────────────────────

@langchain_tool
def search_reddit(query: str, subreddit: str = "", limit: int = 8) -> str:
    """
    Search Reddit for posts matching a query.
    Use this to find real community discussions about a problem or product category.
    Returns post titles, scores, comment counts, and URLs.

    Args:
        query: Search query — use frustrated customer language, not marketing terms
        subreddit: Optional specific subreddit to search within (without r/ prefix)
        limit: Number of posts to return (max 25)
    """
    # LangChain tools must be sync — run the async function safely whether or
    # not an event loop is already running.
    result = _run_async(_reddit_search(
        query=query,
        subreddit=subreddit if subreddit else None,
        limit=limit
    ))

    if not result:
        return f"No Reddit posts found for query: '{query}'"

    # Format as readable text for the LLM
    lines = [f"Reddit search results for '{query}':\n"]
    for i, post in enumerate(result, 1):
        lines.append(
            f"{i}. [{post['subreddit']}] {post['title']}\n"
            f"   Score: {post['score']} | Comments: {post['num_comments']}\n"
            f"   URL: {post['url']}\n"
            f"   {post['body'][:200] + '...' if len(post['body']) > 200 else post['body']}\n"
        )
    return "\n".join(lines)


@langchain_tool
def search_hackernews(query: str, search_type: str = "story", limit: int = 8) -> str:
    """
    Search Hacker News for posts matching a query.
    Use 'show_hn' search_type to find products people have launched.
    Use 'story' for general discussions.
    Use 'ask_hn' for questions and pain point discussions.

    Args:
        query: Search query string
        search_type: One of 'story', 'show_hn', 'ask_hn', 'comment'
        limit: Number of results to return
    """
    result = _run_async(_hn_search(query=query, limit=limit, search_type=search_type))

    if not result:
        return f"No Hacker News posts found for query: '{query}'"

    lines = [f"Hacker News search results for '{query}' (type: {search_type}):\n"]
    for i, post in enumerate(result, 1):
        lines.append(
            f"{i}. {post['title']}\n"
            f"   Score: {post['score']} | Comments: {post['num_comments']}\n"
            f"   URL: {post['url']}\n"
        )
    return "\n".join(lines)


@langchain_tool
def scrape_url(url: str) -> str:
    """
    Fetch and return the text content of a URL.
    Use this to read a product's landing page or documentation.

    Args:
        url: Full URL to fetch (must include https://)
    """
    try:
        result = _run_async(_scrape_url(url))
        return (
            f"Content from {result['url']}:\n"
            f"Length: {result['content_length']} chars\n\n"
            f"{result['raw_preview']}"
        )
    except Exception as e:
        return f"Failed to scrape {url}: {str(e)}"


@langchain_tool
def search_web(query: str, limit: int = 5) -> str:
    """
    Search the web for current information.
    Requires TAVILY_API_KEY in .env (free at tavily.com).

    Args:
        query: Search query
        limit: Number of results
    """
    result = _run_async(_web_search(query=query, limit=limit))
    if not result:
        return "Web search not available — add TAVILY_API_KEY to .env"
    return str(result)


def _run_async(coro):
    """Run an async coroutine from sync code even when an event loop is already active."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result = {}

    def _target():
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            result["value"] = loop.run_until_complete(coro)
        except Exception as exc:
            result["error"] = exc
        finally:
            loop.close()

    thread = threading.Thread(target=_target)
    thread.start()
    thread.join()
    if "error" in result:
        raise result["error"]
    return result.get("value")


# ─────────────────────────────────────────────────────────────
# Public interface — used by LangChain agents
# ─────────────────────────────────────────────────────────────

def get_mcp_tools() -> list:
    """
    Returns all MCP tools as a LangChain-compatible list.

    Usage in a LangChain agent:
        from mcp_server import get_mcp_tools
        tools = get_mcp_tools()
        agent = create_react_agent(llm, tools, prompt)

    The agent can then call tools by name:
        search_reddit, search_hackernews, scrape_url, search_web
    """
    return [search_reddit, search_hackernews, scrape_url, search_web]


# ─────────────────────────────────────────────────────────────
# Standalone MCP server mode
# Run: python mcp_server.py
# Connect from Claude Desktop or any MCP client
# ─────────────────────────────────────────────────────────────

server = Server("launchlens-tools")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    """Register tools with the MCP server."""
    return [
        types.Tool(
            name="search_reddit",
            description="Search Reddit for community discussions about a topic",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "subreddit": {"type": "string", "description": "Optional subreddit (without r/)"},
                    "limit": {"type": "integer", "description": "Number of results", "default": 8},
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="search_hackernews",
            description="Search Hacker News for posts and discussions",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "search_type": {
                        "type": "string",
                        "enum": ["story", "show_hn", "ask_hn", "comment"],
                        "default": "story"
                    },
                    "limit": {"type": "integer", "default": 8},
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="scrape_url",
            description="Fetch content from a URL",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Full URL to fetch"},
                },
                "required": ["url"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Handle tool calls from MCP clients."""
    if name == "search_reddit":
        result = await _reddit_search(
            query=arguments["query"],
            subreddit=arguments.get("subreddit"),
            limit=arguments.get("limit", 8),
        )
        return [types.TextContent(type="text", text=str(result))]

    elif name == "search_hackernews":
        result = await _hn_search(
            query=arguments["query"],
            limit=arguments.get("limit", 8),
            search_type=arguments.get("search_type", "story"),
        )
        return [types.TextContent(type="text", text=str(result))]

    elif name == "scrape_url":
        result = await _scrape_url(url=arguments["url"])
        return [types.TextContent(type="text", text=str(result))]

    else:
        return [types.TextContent(type="text", text=f"Unknown tool: {name}")]


async def run_server():
    """Run as standalone MCP server (for Claude Desktop integration)."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    print("Starting LaunchLens MCP server...")
    print("Connect from Claude Desktop or any MCP client")
    asyncio.run(run_server())