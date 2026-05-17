"""
agents/product_analyst.py — Agent 1: Product Analyst

WHAT THIS AGENT DOES:
Takes a plain English product description and returns a structured
ProductAnalysis object with 3 ICP hypotheses, each with communities
and search queries the Community Researcher will use on Day 3.

WHY THIS IS THE FIRST AGENT:
Every downstream agent depends on this output. The Community Researcher
needs the search_queries. The GTM Copywriter needs the personas. If
this agent produces vague or generic output, the entire pipeline
produces vague and generic results. The prompt engineering here
matters more than anywhere else in the system.

KEY TECHNIQUE: Structured output with Pydantic
LangChain's with_structured_output() forces the LLM to return data
that matches your Pydantic schema exactly. If the LLM tries to return
a string where you declared a list, LangChain retries automatically.
This is fundamentally different from asking the LLM to "respond in JSON"
and then trying to parse it yourself — that approach breaks constantly.
"""

import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage

# Load .env file so GEMINI_API_KEY is available via os.getenv
load_dotenv()

# Import our schemas — defined once in schemas.py, used everywhere
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from schemas import ProductAnalysis, ICPHypothesis


# ─────────────────────────────────────────────────────────────
# The system prompt — the most important engineering in this file
# ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a sharp, experienced product strategist who has helped 
hundreds of early-stage founders find their first customers.

Your job is to analyze a product description and identify who would actually 
pay for it — not who the founder thinks will pay, but who genuinely has this 
problem badly enough to open their wallet.

RULES YOU MUST FOLLOW:
1. Generate EXACTLY 3 ICP hypotheses. Not 2, not 4. Exactly 3.
2. Make each hypothesis meaningfully different — different job titles, 
   different company sizes, different pain intensities.
3. pain_intensity must reflect real urgency. Score 8-10 only if this 
   problem costs the persona money or sleep. Score 1-4 for mild annoyances.
4. communities must be specific: "r/freelance" not "Reddit". 
   "Indie Hackers forums" not "online communities".
5. search_queries must be what a frustrated person actually types, 
   not marketing language. "how to chase invoice without being annoying" 
   is good. "freelancer invoicing solution" is bad.
6. red_flags should be honest. If the market is saturated, say so. 
   If the problem isn't painful enough, say so. Founders need truth.
7. problem_being_solved must be from the CUSTOMER's perspective.
   "I forget to follow up with clients and lose deals" not 
   "automated email follow-up solution for freelancers".

Think carefully before responding. Bad ICP analysis wastes weeks of 
a founder's life chasing the wrong customers."""


# ─────────────────────────────────────────────────────────────
# Building the LangChain chain
# ─────────────────────────────────────────────────────────────

def build_analyst_chain():
    """
    Builds and returns the Product Analyst LangChain chain.
    
    Called once when the agent module loads.
    Returns a runnable chain that takes a product description
    and returns a ProductAnalysis object.
    
    HOW with_structured_output WORKS:
    ChatGoogleGenerativeAI supports function calling — it can be told
    to call a specific "function" with arguments that match a schema.
    with_structured_output() uses this under the hood: it converts your
    Pydantic model into a function schema, passes it to Gemini, and
    Gemini returns structured arguments instead of free text.
    LangChain then builds your Pydantic object from those arguments.
    
    Result: you get a real ProductAnalysis Python object back,
    not a string you have to parse.
    """
    
    # Step 1: Initialize the LLM
    # gemini-2.5-flash is fast and cheap for structured extraction.
    # We'll use gemini-3.1-pro-preview for the PMF Scorer (Day 5) which needs
    # deeper reasoning, but flash is fine for structured output tasks.
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        api_key=os.getenv("GEMINI_API_KEY"),
        temperature=0.3,
    )
    
    # Step 2: Attach structured output
    # This is the key line. It wraps the LLM with a layer that:
    # - Converts ProductAnalysis Pydantic model → Gemini function schema
    # - Sends the schema to Gemini with the prompt
    # - Receives structured arguments back from Gemini
    # - Constructs and returns a real ProductAnalysis Python object
    structured_llm = llm.with_structured_output(ProductAnalysis)
    
    # Step 3: Build the prompt template
    # ChatPromptTemplate handles the message formatting.
    # {product_description} is a placeholder replaced at runtime.
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", """Analyze this product and identify the ideal customers:

Product description: {product_description}

Remember: exactly 3 ICP hypotheses, each meaningfully different.
Be specific about communities and search queries.
Be honest about red flags.""")
    ])
    
    # Step 4: Chain prompt → structured LLM using the | operator
    # This is LangChain's pipe syntax — same concept as Unix pipes.
    # prompt | structured_llm means:
    # "take the output of prompt and pass it as input to structured_llm"
    # When you call chain.invoke({"product_description": "..."}),
    # LangChain formats the prompt then passes it to the LLM.
    chain = prompt | structured_llm
    
    return chain


# ─────────────────────────────────────────────────────────────
# Public function — called by main.py and later by the orchestrator
# ─────────────────────────────────────────────────────────────

# Build the chain once at module load time (not on every request)
_analyst_chain = None

def get_analyst_chain():
    """Lazy initialization — build the chain only when first needed."""
    global _analyst_chain
    if _analyst_chain is None:
        _analyst_chain = build_analyst_chain()
    return _analyst_chain


async def analyze_product(product_description: str) -> ProductAnalysis:
    """
    Main entry point for the Product Analyst agent.
    
    Takes a product description string.
    Returns a fully validated ProductAnalysis Pydantic object.
    
    Raises:
        ValueError: if GEMINI_API_KEY is not set
        Exception: if LLM call fails after retries
    """
    if not os.getenv("GEMINI_API_KEY"):
        raise ValueError(
            "GEMINI_API_KEY not found. "
            "Copy .env.example to .env and add your key. "
            "Get a free key at: https://aistudio.google.com/app/apikey"
        )
    
    chain = get_analyst_chain()
    
    # .ainvoke() is the async version of .invoke()
    # Use ainvoke in async contexts (FastAPI routes, async functions)
    # Use invoke in sync contexts (scripts, tests)
    result = await chain.ainvoke({
        "product_description": product_description
    })
    
    # result is already a ProductAnalysis object — not a string, not a dict.
    # Pydantic has already validated every field.
    return result
