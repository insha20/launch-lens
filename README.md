# LaunchLens

> Multi-agent AI system that validates product-market fit by researching real community conversations on Reddit and Hacker News.

---

## What it does

Paste a product description → LaunchLens runs a 5-agent research pipeline:

1. **Product Analyst** — extracts ICP hypotheses from your description
2. **Community Researcher** — searches Reddit + HN for real pain point conversations
3. **RAG Synthesizer** — embeds posts, retrieves evidence against each ICP hypothesis
4. **PMF Scorer** — scores product-market fit with chain-of-thought reasoning
5. **GTM Copywriter** — writes cold DM, Reddit post angle, landing page copy in the customer's own words

---

## Tech stack

| Layer | Technology | Why |
|---|---|---|
| Agent orchestration | LangGraph | Native tool calling, async support, no AgentExecutor needed |
| Agent chains | LangChain | Prompt templates, structured output, Pydantic integration |
| LLM | Gemini 2.5 Flash | Best free-tier structured output quality during development |
| MCP tools | Model Context Protocol Python SDK | Standard tool protocol — agents call tools by name, not by importing functions |
| Data validation | Pydantic v2 | Strict schema enforcement across all agent inputs/outputs |
| Community data | Reddit JSON API + HN Algolia API | No auth required, free, real community signal |
| Vector store | Chroma | In-memory embeddings for RAG pipeline |
| Backend | FastAPI + uvicorn | Async-first, auto docs, Pydantic integration |
| Frontend | Next.js 14 + Tailwind CSS | React server components, TypeScript, fast iteration |
| Runtime | Node.js ≥ 22 | Required by Tailwind v4 native bindings |

---

## Prerequisites

Before you start, make sure you have the following installed:

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.11+ | [python.org](https://www.python.org/downloads/) |
| Node.js | **22+** | `brew install node@22` (Mac) or [nodejs.org](https://nodejs.org/) |
| npm | 10+ | Comes with Node.js |
| Git | any | `brew install git` or [git-scm.com](https://git-scm.com/) |

> **Why Node 22?** Tailwind CSS v4 uses native Rust bindings (`@tailwindcss/oxide`) that require Node ≥ 20. Node 22 LTS is recommended.

---

## Getting a Gemini API key (free)

1. Go to [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
2. Sign in with a Google account
3. Click **Create API key**
4. Copy the key — you'll paste it into `.env` below

> **Free tier limit:** 20 requests/day per model. A full pipeline run uses ~8–12 requests. If you hit the limit, the backend will automatically retry after the cooldown window (shown in the UI).

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/your-username/launch-lens.git
cd launch-lens
```

### 2. Backend setup

```bash
# Create and activate a Python virtual environment
python -m venv .venv
source .venv/bin/activate        # Mac / Linux
# .venv\Scripts\activate         # Windows

# Install Python dependencies
pip install -r backend/requirements.txt

# Copy the example env file and add your Gemini API key
cp backend/env.example backend/.env
```

Open `backend/.env` and set:
```
GEMINI_API_KEY=your_key_here
```

### 3. Frontend setup

```bash
cd frontend
npm install
cd ..
```

---

## Running the app

You need **two terminals** — one for the backend, one for the frontend.

### Terminal 1 — Backend

```bash
# From the project root
source .venv/bin/activate
cd backend
uvicorn main:app --reload --port 8000
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

✅ API docs available at: http://localhost:8000/docs  
✅ Health check: http://localhost:8000/health

### Terminal 2 — Frontend

```bash
# From the project root
cd frontend
npm run dev
```

You should see:
```
▲ Next.js 14.x.x
- Local: http://localhost:3000
✓ Ready in Xs
```

✅ Open http://localhost:3000 in your browser

---

## Running tests

Run these from `backend/` with the virtual environment activated:

```bash
cd backend
source ../.venv/bin/activate   # if not already active

python test_tools.py           # Day 1 — Reddit + HN API tools
python test_analyst.py         # Day 2 — Product Analyst agent
python test_researcher.py      # Day 3 — MCP tools + Community Researcher
python test_rag.py             # Day 4 — Chroma embeddings + RAG Synthesizer
python test_pmf_and_gtm.py     # Day 5 — PMF Scorer + GTM Copywriter
python test_pipeline.py        # Day 6 — full end-to-end pipeline (30–90s)
```

> ⚠️ Tests make real Gemini API calls. Each test file consumes 1–5 of your 20 daily requests.

---

## Project structure

```
launch-lens/
├── backend/
│   ├── main.py                     ← FastAPI app + all routes
│   ├── schemas.py                  ← Single source of truth for all data shapes
│   ├── graph.py                    ← LangGraph 5-agent state machine
│   ├── rag_pipeline.py             ← Chroma embeddings + semantic search
│   ├── mcp_server.py               ← MCP server (Reddit/HN tools)
│   ├── agents/
│   │   ├── product_analyst.py      ← Agent 1: ICP extraction
│   │   ├── community_researcher.py ← Agent 2: Reddit + HN research
│   │   ├── rag_synthesizer.py      ← Agent 3: RAG synthesis
│   │   ├── pmf_scorer.py           ← Agent 4: PMF scoring
│   │   └── gtm_copywriter.py       ← Agent 5: GTM copy generation
│   ├── env.example                 ← Copy to .env and fill in API key
│   ├── requirements.txt
│   ├── test_tools.py
│   ├── test_analyst.py
│   ├── test_researcher.py
│   ├── test_rag.py
│   ├── test_pmf_and_gtm.py
│   └── test_pipeline.py
└── frontend/
    ├── src/
    │   ├── app/
    │   │   ├── page.tsx            ← Main UI (input form + progress + report)
    │   │   ├── layout.tsx          ← Root layout + fonts
    │   │   └── globals.css         ← Tailwind base styles
    │   ├── components/
    │   │   ├── PipelineProgress.tsx ← 5-stage animated progress indicator
    │   │   └── ReportView.tsx      ← Full report renderer (PMF score + GTM pack)
    │   ├── lib/
    │   │   └── api.ts              ← Typed fetch wrapper for backend
    │   └── types/
    │       └── pipeline.ts         ← TypeScript types mirroring backend schemas
    ├── package.json
    └── next.config.mjs
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `GEMINI_API_KEY not set` | Make sure `backend/.env` exists and contains the key |
| `429 RESOURCE_EXHAUSTED` | You've hit the 20 req/day free tier. The UI shows a banner and the backend retries automatically. Wait for quota to reset (daily at midnight Pacific) or add billing at [ai.dev/rate-limit](https://ai.dev/rate-limit) |
| `Cannot find native binding` (Tailwind) | You're on Node < 20. Run `brew install node@22 && brew link node@22 --force`, then `rm -rf frontend/node_modules && npm install` in `frontend/` |
| `next.config.ts` error | Next.js 14 doesn't support `.ts` config. Rename to `next.config.mjs` |
| Port 8000 already in use | `lsof -ti:8000 \| xargs kill -9` |
| Port 3000 already in use | `lsof -ti:3000 \| xargs kill -9` |
| Reddit returning 403 | Known issue with Reddit's public JSON API. HN Algolia still works. Reddit OAuth support planned. |

---

## Development log

| Day | What was built | Key decisions |
|-----|----------------|---------------|
| **1** | FastAPI scaffold, Reddit JSON API, HN Algolia API, MCP tool stubs | Used public Reddit JSON API — no auth needed for read-only access. Defined all 5 MCP tools as named stubs from Day 1 so the orchestrator can be built against a stable interface before each implementation is complete. `asyncio.gather()` runs Reddit + HN in parallel — halves latency vs sequential calls. |
| **2** | Product Analyst agent, Pydantic schemas, LangChain + Gemini integration | Used `with_structured_output()` instead of parsing JSON strings — LangChain uses Gemini's native function-calling to populate a Pydantic schema directly, eliminating regex parsing failures. All schemas centralised in `schemas.py`. |
| **3** | MCP server (standalone + in-process), Community Researcher agent | Migrated from deprecated `langchain.agents.create_react_agent + AgentExecutor` to `langgraph.prebuilt.create_react_agent` — uses native tool calling instead of text-based ReAct parsing. Replaced `nest_asyncio` with thread-based `_run_async()` helper. |
| **4** | RAG pipeline + RAG Synthesizer | Google `gemini-embedding-001`. Chroma in-memory per session. Synthesizer retrieves evidence, LLM grounds answers in retrieved posts. |
| **5** | PMF Scorer + GTM Copywriter | PMF: chain-of-thought scoring with verdict routing. GTM: cold DM, Reddit angle, landing page with customer language. |
| **6** | LangGraph orchestrator — 5-agent state machine | `PipelineState` TypedDict as shared whiteboard. Conditional edge `should_write_copy()` gates GTM Copywriter on PMF verdict. Rate-limit retry with backoff on every LLM-calling node. |
| **7** | FastAPI `/launch` route | Wired `run_pipeline()` into `POST /launch`. FastAPI auto-validates Pydantic output. Health check surfaces all 5 agent names + `gemini_configured` flag. |
| **8–9** | Next.js frontend | Input form, 5-stage animated progress bar, rate-limit retry banner with elapsed timer, full report view (PMF score + ICP cards + GTM copy with copy buttons). |
| **10** | *(coming)* Docker + Railway deployment | |
| **11–12** | *(coming)* Architecture diagram, portfolio write-up | |
| **13–14** | *(coming)* Blog post + Show HN launch | |

---

## Architecture

### Why MCP instead of plain function calls?

The MCP (Model Context Protocol) server exposes tools through a standard open protocol rather than direct Python imports. This means:

- Agents call tools by name (`search_reddit`) through a protocol — not by importing a function
- The MCP server can run as a completely separate process
- Any MCP-compatible client (Claude Desktop, other agents) can connect to the same tool server
- Swapping a tool's implementation requires no change to agent code

### Why LangGraph over LangChain AgentExecutor?

LangChain's `AgentExecutor` uses text-based ReAct parsing — the LLM outputs `Thought/Action/Observation` as literal text which LangChain parses with regex. This breaks when the LLM formats output slightly differently across versions.

LangGraph's `create_react_agent` uses the model's native tool-calling capability — the LLM returns structured function calls, not text. More reliable, fully async, and the direction the entire ecosystem is moving.

### Data flow

```
User input: product description
        │
        ▼
┌─────────────────────┐
│   Product Analyst   │  LangChain + Gemini 2.5 Flash
│   (Agent 1)         │  with_structured_output → Pydantic
└────────┬────────────┘
         │ ProductAnalysis (3 ICP hypotheses + search queries)
         ▼
┌─────────────────────┐
│ Community Researcher│  LangGraph prebuilt ReAct agent
│   (Agent 2)         │  calls MCP tools in a loop
└────────┬────────────┘
         │ CommunityEvidence per hypothesis
         ▼
┌─────────────────────┐
│  RAG Synthesizer    │  Chroma + Google embeddings
│  (Agent 3)          │  semantic search → grounded synthesis
└────────┬────────────┘
         │ SynthesisResult (pain_confirmed, confidence_score)
         ▼
┌─────────────────────┐
│   PMF Scorer        │  Chain-of-thought reasoning
│   (Agent 4)         │  score 1–10 + verdict routing
└────────┬────────────┘
         │
   should_write_copy()
         │
   ┌─────┴──────────────────────────┐
   │ verdict: moderate/strong       │ verdict: weak/insufficient
   ▼                                ▼
┌──────────────┐           return early report
│ GTM          │           "need more research"
│ Copywriter   │
│ (Agent 5)    │
└──────┬───────┘
       │ cold DM, Reddit angle, landing page
       ▼
  LaunchLensReport → FastAPI → Next.js UI
```

---

## What I learned

- **LangChain version conflicts are real.** The ecosystem moves fast — APIs deprecated in `0.x` are removed in `1.x`, imports moved between packages. Pinning versions in `requirements.txt` is not optional.
- **Test tools before agents.** If the Reddit search returns garbage, the LLM will confidently analyze that garbage. Isolating tool tests from agent tests makes debugging significantly faster.
- **Pydantic as a reliability layer.** `with_structured_output()` + Pydantic schemas catches LLM output issues at the agent boundary before malformed data propagates through 5 agents downstream.
- **Reddit's public API is fragile.** Started returning 403 on some queries without warning. Production AI systems need resilient data sources with OAuth or fallback strategies.
- **`nest_asyncio` is a footgun.** It patches the global event loop and conflicts with production ASGI servers. Thread-based async isolation is cleaner.

---

## Resume bullets

```
• Architected a multi-agent AI system using LangGraph with 5 specialized agents
  (product analyst, community researcher, RAG synthesizer, PMF scorer, GTM
  copywriter) and conditional state routing

• Built a custom MCP server exposing Reddit, Hacker News, and web search as
  structured tools consumed by LangChain agents via the Model Context Protocol

• Implemented structured LLM output using Pydantic v2 schema validation and
  Gemini's native function-calling — eliminating string parsing failures across
  all agent boundaries

• Migrated from deprecated LangChain AgentExecutor to LangGraph prebuilt ReAct
  agent with native tool calling — improved reliability and aligned with current
  ecosystem direction

• Engineered thread-based async bridge (_run_async) for sync/async tool wrapper
  interop, replacing nest_asyncio patching that conflicted with FastAPI's
  event loop in production
```


---

## What it does

Paste a product description → LaunchLens runs a 5-agent research pipeline:

1. **Product Analyst** — extracts ICP hypotheses from your description
2. **Community Researcher** — searches Reddit + HN for real pain point conversations
3. **RAG Synthesizer** — embeds posts, retrieves evidence against each ICP hypothesis *(Day 4)*
4. **PMF Scorer** — scores product-market fit with chain-of-thought reasoning *(Day 5)*
5. **GTM Copywriter** — writes cold DM, Reddit post angle, landing page copy in the customer's own words *(Day 5)*

---

## Tech stack

| Layer | Technology | Why |
|---|---|---|
| Agent orchestration | LangGraph (prebuilt ReAct agent) | Native tool calling, async support, no AgentExecutor needed |
| Agent chains | LangChain | Prompt templates, structured output, Pydantic integration |
| LLM | Gemini 2.5 Flash | Best free-tier structured output quality during development |
| MCP tools | Model Context Protocol Python SDK | Standard tool protocol — agents call tools by name, not by importing functions |
| Data validation | Pydantic v2 | Strict schema enforcement across all agent inputs/outputs |
| Community data | Reddit JSON API + HN Algolia API | No auth required, free, real community signal |
| Vector store | Chroma *(Day 4)* | In-memory embeddings for RAG pipeline |
| Backend | FastAPI + uvicorn | Async-first, auto docs, Pydantic integration |
| Deployment | Docker + Railway *(Day 10)* | Containerized, one-command deploy |

---

## Project structure

```
launchlens/
├── backend/
│   ├── main.py                        ← FastAPI app + routes
│   ├── schemas.py                     ← Single source of truth for all data shapes
│   ├── mcp_server.py                  ← MCP server exposing Reddit/HN/web as tools
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── product_analyst.py         ← Agent 1: ICP extraction
│   │   └── community_researcher.py   ← Agent 2: Reddit + HN research
│   ├── graph.py                       ← LangGraph orchestrator (Day 6)
│   ├── requirements.txt
│   ├── .env.example
│   ├── test_tools.py                  ← Day 1 tests
│   ├── test_analyst.py                ← Day 2 tests
│   └── test_researcher.py             ← Day 3 tests
@@│   ├── rag_pipeline.py                ← Chroma embeddings + semantic search (Day 4)
│   ├── graph.py                       ← LangGraph orchestrator — 5-agent state machine (Day 6)
│   ├── agents/rag_synthesizer.py      ← Agent 3: RAG synthesis (Day 4)
│   ├── agents/pmf_scorer.py           ← Agent 4: PMF scoring (Day 5)
│   ├── agents/gtm_copywriter.py       ← Agent 5: GTM copy (Day 5)
│   ├── test_rag.py                    ← Day 4 tests
│   ├── test_pmf_and_gtm.py            ← Day 5 tests
│   └── test_pipeline.py               ← Day 6 end-to-end test
└── frontend/                          ← Next.js app (Day 8-9)
```

---

## Setup

```bash
# 1. Navigate to backend
cd launchlens/backend

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate       # Mac/Linux
# .venv\Scripts\activate        # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env — add GEMINI_API_KEY
# Free key at: https://aistudio.google.com/app/apikey

# 5. Start the server
uvicorn main:app --reload

# 6. Open API docs — try POST /launch with a product description
open http://localhost:8000/docs
```

---

## Running tests

```bash
python test_tools.py       # Day 1 — Reddit + HN APIs
python test_analyst.py     # Day 2 — Product Analyst agent
python test_researcher.py  # Day 3 — MCP tools + Community Researcher
@@python test_rag.py             # Day 4 — Chroma embeddings + RAG Synthesizer
@@python test_pmf_and_gtm.py     # Day 5 — PMF Scorer + GTM Copywriterpython test_pipeline.py        # Day 6 — full end-to-end pipeline (30-90s)
python test_pipeline.py --product dev_tool   # run on second test product```

---

## Development log

| Day | What was built | Key decisions |
|-----|----------------|---------------|
| **1** | FastAPI scaffold, Reddit JSON API, HN Algolia API, MCP tool stubs | Used public Reddit JSON API — no auth needed for read-only access. Defined all 5 MCP tools as named stubs from Day 1 so the orchestrator can be built against a stable interface before each implementation is complete (programming to an interface). `asyncio.gather()` runs Reddit + HN in parallel — halves latency vs sequential calls. |
| **2** | Product Analyst agent, Pydantic schemas, LangChain + Gemini integration | Used `with_structured_output()` instead of parsing JSON strings — LangChain uses Gemini's native function-calling to populate a Pydantic schema directly, eliminating regex parsing failures. All schemas centralised in `schemas.py` — one file to update, no circular imports between agents. Switched from `gemini-2.0-flash` (free tier quota = 0 on new projects) to `gemini-2.5-flash` which works on free tier. |
| **3** | MCP server (standalone + in-process), Community Researcher agent | Migrated from deprecated `langchain.agents.create_react_agent + AgentExecutor` to `langgraph.prebuilt.create_react_agent` — uses native tool calling instead of text-based ReAct parsing, more reliable and the current recommended pattern. Replaced `nest_asyncio` with thread-based `_run_async()` helper — `nest_asyncio` patches the event loop globally which conflicts with FastAPI/uvicorn in production. Added defensive message content normalization to handle Gemini returning list-type content blocks (LangGraph version-dependent behaviour). Reddit public JSON API returning 403 on some queries — HN Algolia continues to work. Will add Reddit OAuth in a future iteration. |
| **4** | *(coming)* RAG pipeline — Chroma + embeddings | |
 | **4** | RAG pipeline + RAG Synthesizer | Google embedding-004. Chroma in-memory. Synthesizer retrieves evidence, LLM grounds in retrieved posts. No hallucination. |
 | **5** | PMF Scorer + GTM Copywriter | PMF: chain-of-thought scoring with verdict routing. GTM: cold DM, Reddit angle, landing page with customer language. |
| **6** | LangGraph orchestrator — 5-agent state machine | `PipelineState` TypedDict as shared whiteboard across all nodes. Conditional edge `should_write_copy()` gates GTM Copywriter on PMF verdict — system refuses to generate marketing copy if evidence is weak/insufficient. Rate-limit retry logic with backoff in PMF Scorer node. Single `run_pipeline()` entry point for FastAPI. |
| **7** | FastAPI `/launch` route — full pipeline over HTTP | Wired `run_pipeline()` into `POST /launch` with `LaunchLensReport` as response model. FastAPI auto-validates the Pydantic output — if any agent returns a malformed schema, the API returns a 422 before the client sees it. Health check updated to surface all 5 agent names and `gemini_configured` flag for deployment diagnostics. |
| **8–9** | *(coming)* Next.js frontend with SSE streaming | |
| **10** | *(coming)* Docker + Railway deployment | |
| **11–12** | *(coming)* Architecture diagram, portfolio write-up | |
| **13–14** | *(coming)* Blog post + Show HN launch | |

---

## Architecture

### Why MCP instead of plain function calls?

The MCP (Model Context Protocol) server exposes tools through a standard open protocol rather than direct Python imports. This means:

- Agents call tools by name (`search_reddit`) through a protocol — not by importing a function
- The MCP server can run as a completely separate process; agents don't need to know how tools are implemented
- Any MCP-compatible client (Claude Desktop, other agents) can connect to the same tool server
- Swapping a tool's implementation requires no change to agent code

This project uses in-process mode (`get_mcp_tools()`) during development for simplicity. The standalone mode (`python mcp_server.py`) is production-ready and connectable from Claude Desktop directly.

### Why LangGraph over LangChain AgentExecutor?

LangChain's `AgentExecutor` uses text-based ReAct parsing — the LLM outputs `Thought/Action/Observation` as literal text which LangChain parses with regex. This breaks when the LLM formats output slightly differently across versions.

LangGraph's `create_react_agent` uses the model's native tool-calling capability — the LLM returns structured function calls, not text. More reliable, fully async, and the direction the entire ecosystem is moving.

### Data flow (Days 1–6)

```
User input: product description
        │
        ▼
┌─────────────────────┐
│   Product Analyst   │  LangChain + Gemini 2.5 Flash
│   (Agent 1)         │  with_structured_output → Pydantic
└────────┬────────────┘
         │ ProductAnalysis
         │ (3 ICP hypotheses + search queries)
         ▼
┌─────────────────────┐
│ Community Researcher│  LangGraph prebuilt ReAct agent
│   (Agent 2)         │  calls MCP tools in a loop
└────────┬────────────┘
         │ calls → search_reddit()
         │ calls → search_hackernews()
         │ CommunityEvidence per hypothesis
         ▼
┌─────────────────────┐
│  RAG Synthesizer    │  Chroma vector DB + Google embeddings
│  (Agent 3)          │  semantic search → grounded synthesis
└────────┬────────────┘
         │ SynthesisResult (pain_confirmed, confidence_score)
         ▼
┌─────────────────────┐
│   PMF Scorer        │  Chain-of-thought reasoning
│   (Agent 4)         │  score 1-10 + verdict routing
└────────┬────────────┘
         │
   should_write_copy()
         │
   ┌─────┴──────────────────────────┐
   │ verdict: moderate/strong       │ verdict: weak/insufficient
   ▼                                ▼
┌──────────────┐           return early report
│ GTM          │           "need more research"
│ Copywriter   │
│ (Agent 5)    │
└──────┬───────┘
       │ cold DM, Reddit angle, landing page
       ▼
  LaunchLensReport (final output to user)
```

---

## What I learned

- **LangChain version conflicts are real.** The ecosystem moves fast — APIs deprecated in `0.x` are removed in `1.x`, imports moved between packages. Pinning versions in `requirements.txt` is not optional, and reading changelogs before upgrading saves hours.
- **Test tools before agents.** If the Reddit search returns garbage, the LLM will confidently analyze that garbage. Isolating tool tests from agent tests makes debugging significantly faster.
- **Pydantic as a reliability layer.** `with_structured_output()` + Pydantic schemas catches LLM output issues at the agent boundary before malformed data propagates through 5 agents downstream.
- **Reddit's public API is fragile.** Started returning 403 on some queries without warning. Production AI systems need resilient data sources with OAuth or fallback strategies.
- **`nest_asyncio` is a footgun.** It patches the global event loop and conflicts with production ASGI servers. Thread-based async isolation is cleaner for tool wrappers that must be sync.

---

## Resume bullets

```
• Architected a multi-agent AI system using LangGraph with 5 specialized agents
  (product analyst, community researcher, RAG synthesizer, PMF scorer, GTM
  copywriter) and conditional state routing

• Built a custom MCP server exposing Reddit, Hacker News, and web search as
  structured tools consumed by LangChain agents via the Model Context Protocol

• Implemented structured LLM output using Pydantic v2 schema validation and
  Gemini's native function-calling — eliminating string parsing failures across
  all agent boundaries

• Migrated from deprecated LangChain AgentExecutor to LangGraph prebuilt ReAct
  agent with native tool calling after encountering API deprecation conflicts —
  improved reliability and aligned with current ecosystem direction

• Engineered thread-based async bridge (_run_async) for sync/async tool wrapper
  interop, replacing nest_asyncio patching that conflicted with FastAPI's
  event loop in production
```