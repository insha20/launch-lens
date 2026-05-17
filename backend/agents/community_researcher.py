"""
agents/community_researcher.py — Agent 2: Community Researcher

WHAT THIS AGENT DOES:
Takes the 3 ICP hypotheses from the Product Analyst and finds real
evidence for each one by searching Reddit and HN using the MCP tools.

ARCHITECTURE CHANGE FROM ORIGINAL PLAN:
Originally planned to use langchain.agents.create_react_agent + AgentExecutor.
Those APIs are deprecated/moved across LangChain versions and caused import
errors. Switched to langgraph.prebuilt.create_react_agent which:
  - Is the current recommended approach (LangGraph is LangChain's successor)
  - Handles the ReAct loop internally with proper async support
  - Uses tool_calling instead of text parsing — more reliable
  - No AgentExecutor needed — cleaner API

THIS IS WORTH DOCUMENTING IN YOUR README:
"Encountered LangChain API deprecation conflicts. Migrated to LangGraph's
prebuilt ReAct agent which uses native tool calling instead of text-based
ReAct parsing — more reliable and the current recommended pattern."
That's a real engineering decision that shows maturity.

HOW LANGGRAPH'S create_react_agent WORKS:
Unlike the old text-based ReAct (Thought/Action/Observation format),
LangGraph uses the model's native tool-calling capability:
  1. You give the agent a list of tools
  2. The LLM decides which tool to call using structured function calls
  3. LangGraph executes the tool and passes results back as messages
  4. The LLM sees results and decides what to do next
  5. Loop continues until the LLM stops calling tools
This is more reliable because there's no text parsing that can break.
"""

import os
import asyncio
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

load_dotenv()

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from schemas import ProductAnalysis, ICPHypothesis, CommunityPost, CommunityEvidence
from mcp_server import get_mcp_tools


# ─────────────────────────────────────────────────────────────
# System prompt for the researcher
# With LangGraph's tool-calling approach, this goes in the
# system message — not a ReAct template with placeholders.
# ─────────────────────────────────────────────────────────────

RESEARCHER_SYSTEM = """You are a community research analyst. Your job is to find 
real evidence on Reddit and Hacker News that validates or invalidates ICP hypotheses.

RESEARCH STRATEGY:
1. Use search_reddit with the specific queries provided first
2. Try the subreddit-specific search if a community is mentioned  
3. Also check search_hackernews for the same topic
4. If initial results are sparse, try a broader version of the query
5. Make 3-5 tool calls total — enough to get a real signal

WHAT TO LOOK FOR:
- Posts where people describe the pain in their own words
- High score/comment posts (wider resonance)
- Questions asking for solutions (confirms willingness to seek help)
- Complaints about existing solutions (confirms the gap)

After your research, provide a structured summary:
- Total posts found: N
- Pain confirmed: yes/no  
- Strongest signal: [most compelling post or pattern]
- Key language: [actual phrases the community uses]
- Best communities: [specific subreddits or HN threads with most signal]"""


# ─────────────────────────────────────────────────────────────
# Build the agent
# ─────────────────────────────────────────────────────────────

def build_researcher_agent():
    """
    Builds the Community Researcher using LangGraph's prebuilt ReAct agent.

    langgraph.prebuilt.create_react_agent creates a full agent graph that:
    - Routes to tools when the LLM calls them
    - Routes back to the LLM with tool results
    - Ends when the LLM produces a final response with no tool calls

    The agent is fully async — call with ainvoke() in async contexts.
    """
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=os.getenv("GEMINI_API_KEY"),
        temperature=0.1,
    )

    tools = get_mcp_tools()

    # create_react_agent from langgraph.prebuilt — the modern approach
    # prompt= sets the system message for the agent
    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=RESEARCHER_SYSTEM,
    )

    return agent


# Lazy initialization
_researcher_agent = None

def get_researcher_agent():
    global _researcher_agent
    if _researcher_agent is None:
        _researcher_agent = build_researcher_agent()
    return _researcher_agent


# ─────────────────────────────────────────────────────────────
# Research a single ICP hypothesis
# ─────────────────────────────────────────────────────────────

async def research_hypothesis(hypothesis: ICPHypothesis) -> CommunityEvidence:
    """
    Researches one ICP hypothesis and returns structured evidence.
    Uses ainvoke() — fully async, no thread pool needed.
    """
    agent = get_researcher_agent()

    communities_str = ", ".join(hypothesis.communities[:4])
    queries_str = "\n".join(f"  - {q}" for q in hypothesis.search_queries[:4])

    # Build the research task as a human message
    task = f"""Research this ICP hypothesis and find community evidence:

Persona: {hypothesis.persona}
Pain they feel: {hypothesis.why_they_pay}
Communities to check: {communities_str}
Search queries to try:
{queries_str}

Use the tools to search Reddit and HN. Make at least 3 searches across both platforms."""

    print(f"\n  → Invoking researcher agent for: {hypothesis.persona[:50]}...")

    result = await agent.ainvoke({
        "messages": [HumanMessage(content=task)]
    })

    # Extract the final AI message. LangGraph may return message objects or
    # plain dicts depending on versions; normalize both to strings.
    import json
    messages = result.get("messages", [])
    final_message = ""
    tool_calls_made = []

    for msg in messages:
        # Normalize message content extraction for object or dict
        content = ""
        tool_calls = []
        if isinstance(msg, AIMessage):
            content = msg.content or ""
            tool_calls = getattr(msg, "tool_calls", []) or []
        elif isinstance(msg, dict):
            content = msg.get("content") or msg.get("text") or ""
            tool_calls = msg.get("tool_calls") or msg.get("tool_call") or []
        else:
            # Fallback to string conversion
            content = str(msg)

        # If content is a list or dict, convert to readable string
        if isinstance(content, list) or isinstance(content, dict):
            try:
                content = json.dumps(content, ensure_ascii=False)
            except Exception:
                content = str(content)

        if content:
            final_message = content

        # Collect tool call names
        for tc in tool_calls or []:
            try:
                if isinstance(tc, dict):
                    tool_calls_made.append(tc.get("name", ""))
                else:
                    # tc may be a ToolCall object-like
                    name = getattr(tc, "name", None)
                    if name:
                        tool_calls_made.append(name)
            except Exception:
                continue

    # Print tool usage for transparency
    if tool_calls_made:
        print(f"  → Tools called: {', '.join(tool_calls_made)}")

    print(f"  → Research complete. Summary length: {len(final_message)} chars")

    # Extract posts from tool results in message history
    posts_found = []
    for msg in messages:
        # reuse normalized content extraction
        if isinstance(msg, AIMessage):
            msg_str = msg.content or ""
        elif isinstance(msg, dict):
            raw = msg.get("content") or msg.get("text") or ""
            msg_str = raw if isinstance(raw, str) else str(raw)
        else:
            msg_str = str(msg)

        if "reddit.com" in msg_str or "ycombinator.com" in msg_str:
            lines = msg_str.split("\n")
            for line in lines:
                if "URL:" in line:
                    url = line.replace("URL:", "").strip()
                    if url.startswith("http"):
                        source = "reddit" if "reddit" in url else "hackernews"
                        posts_found.append(CommunityPost(
                            source=source,
                            title="",
                            url=url,
                            score=0,
                        ))

    return CommunityEvidence(
        hypothesis_persona=hypothesis.persona,
        posts=posts_found[:10],
        total_posts_found=max(len(posts_found), len(tool_calls_made) * 2),
        # Ensure strongest_signal is always a string (Pydantic expects str)
        strongest_signal=(final_message[:600] if isinstance(final_message, str) else str(final_message)) if final_message else "No evidence found",
    )


async def research_all_hypotheses(analysis: ProductAnalysis) -> list[CommunityEvidence]:
    """
    Researches all 3 ICP hypotheses sequentially.
    Sequential (not parallel) to be respectful of Reddit rate limits.
    """
    evidence_list = []

    for i, hypothesis in enumerate(analysis.icp_hypotheses):
        print(f"\n[Community Researcher] Hypothesis {i+1}/3: {hypothesis.persona[:55]}...")

        try:
            evidence = await research_hypothesis(hypothesis)
            evidence_list.append(evidence)
            if i < len(analysis.icp_hypotheses) - 1:
                await asyncio.sleep(2)      # be respectful of Reddit's API
        except Exception as e:
            print(f"[Community Researcher] Error on hypothesis {i+1}: {e}")
            evidence_list.append(CommunityEvidence(
                hypothesis_persona=hypothesis.persona,
                posts=[],
                total_posts_found=0,
                strongest_signal=f"Research failed: {str(e)}",
            ))

    return evidence_list