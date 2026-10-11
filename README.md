# AI Research Agent — Bounded, Citation-Grounded

A production-ready AI research agent that takes a complex research question, plans focused sub-tasks, gathers evidence from the web and internal sources, detects conflicts, synthesizes a citation-grounded report, self-evaluates, and streams progress live. Built for free-tier deployment (Render + Supabase + Upstash + Vercel).

**Live:** Frontend `https://ai-research-agent-tau-mauve.vercel.app` → API `https://ai-research-agent-a166.onrender.com` (`GET /health` `200`)

---

## Features

* **Bounded autonomy** — `MAX_LLM_CALLS=50` `MAX_TOOL_CALLS=10` `MAX_RESEARCH_TIME=120` `MAX_AGENT_ITERATIONS=2` `MAX_CONTEXT_SIZE=8192` `app/agents/instrumented_graph.py:33` + `ResearchService.extract_evidence` `content[:6000]` `app/services/research_service.py:134` + `collect_sources()[:10]` + `collect_evidence[:5]` `app/agents/graph.py:164` — no unbounded loops
* **Grounded synthesis** — `Synthesizer` `app/agents/synthesizer.py:28` + `CitationService` `app/services/citation_service.py:8` `citation_ids ⊆ [1..len(evidence)]` + `ReportService` `app/services/report_service.py:10` → `ResearchReport` `app/schemas/research.py:98`
* **Self-evaluation loop** — `ReportEvaluator` `app/agents/evaluator.py:48` `grounded/citation_correct/hallucination/score 1-5` with `route_after_report_evaluation` `app/agents/graph.py:399` `score>=4` or `2` iterations → `finalize_report`
* **Hybrid retrieval** — `pgvector` `pg16` + `BM25` `app/retrieval/bm25.py:59` + `RRF` `app/retrieval/hybrid.py:40` + `Reranker` + `WebFetch` `app/tools/web_fetch.py:13` `validate_url` `app/tools/url_security.py:10`
* **Observability** — `JSONFormatter` `app/observability/logging.py:88` `run_id/trace_id/node_name` + `redact_secrets` + `Prometheus` `app/observability/metrics.py:17` `research_runs_total|llm_tokens_total|limit_violations` + `Tracing` `app/observability/tracing.py:34` `create_span`
* **Multi-LLM fallback** — `GroqProvider` `app/llm/groq.py:30` `openai/gpt-oss-20b` + `GeminiProvider` `app/llm/gemini.py:18` `gemini-3.5-flash-lite` `Interactions API` + `FallbackProvider` `app/llm/fallback.py:12` `tokens per day` → `Gemini` (`Tavily` `app/tools/tavily_provider.py:18` via `httpx`)
* **Atomic persistence** — `ReportRepository.create_with_evaluation` `app/db/repositories.py:343` `pool.acquire()+transaction()` + `ResearchJobRepository` `FOR UPDATE SKIP LOCKED` `app/db/repositories.py:60` + heartbeat `app/workers/research_worker.py:42` `lease_expires_at`
* **Live progress** — `ResearchProgressPublisher` `app/services/progress_publisher.py:8` `Redis Pub/Sub` `app/db/redis.py:25` `research-events:{id}` → `SSE` `GET /research/{id}/stream` `app/api/sse.py:72`
* **Frontend** — `Next.js 16 App Router` `frontend/app/page.js:4` `Tailwind` — `POST /research` `GET /research/{id}` `GET /research/{id}/report` `app/api/research.py:12` with `CORS` `app/sse_app.py:6`, `10/min` rate limit, `In Progress` with ETA + `Grab a coffee ☕` messages, report viewer with citations

## Architecture

```mermaid
flowchart TD
    U[User/Vercel] --> F[Next.js frontend/app/page.js]
    F -->|POST /research| A[FastAPI app/sse_app.py]
    A --> R[ResearchJobRepository → research_jobs]
    A --> S[SSE /research/{id}/stream ← Redis Pub/Sub]
    W[ResearchWorker app/workers/research_worker.py] -->|claim_next_pending FOR UPDATE SKIP LOCKED| R
    W --> G[build_production_research_graph app/agents/production_factory.py]
    G --> P[ResearchPlanner app/agents/planner.py]
    G --> E[Researcher WebSearchTool(Tavily) + WebFetch]
    G --> C[collect_evidence → ResearchService.extract_evidence]
    G --> V[SourceEvaluationService app/services/source_evaluation_service.py]
    G --> Y[Synthesizer app/agents/synthesizer.py]
    G --> I[CitationService app/services/citation_service.py]
    G --> O[ReportService app/services/report_service.py]
    G --> Q[ReportEvaluator app/agents/evaluator.py]
    G -->|FallbackProvider| L[Groq → Gemini app/llm/fallback.py]
    G -->|InstrumentedResearchGraph| T[UsageTracker app/llm/usage.py + ToolCallTracker]
    W -->|create_with_evaluation transaction| D[(Supabase Postgres + pgvector)]
    W -->|publish| Redis[(Upstash Redis)]
```

## Quick Start

```bash
# 1. Env
cp .env.example .env  # set GROQ_API_KEY, GEMINI_API_KEY, TAVILY_API_KEY, DATABASE_URL, REDIS_URL
# 2. Infra (local)
docker compose up -d postgres redis
uv run alembic upgrade head
# 3. Run
uv run python -m app.workers.research_worker &  # or via supervisor app/supervisor.py
uv run uvicorn app.sse_app:app --reload --port 8000
# 4. Frontend
cd frontend && npm install && NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
# 5. Test
uv run pytest -q  # 248 passed
```

## Environment

| Variable | Required | Default | Description |
|---|---|---|---|
| `GROQ_API_KEY` | For Groq | — | `gsk_...` |
| `GEMINI_API_KEY` | For Gemini fallback | — | `AIza...` |
| `TAVILY_API_KEY` | Yes | — | `tvly-dev-...` |
| `DATABASE_URL` | Yes | `postgresql://...@localhost:5433/research_agent` | Supabase `postgresql://...pooler.supabase.com:5432/postgres` |
| `REDIS_URL` | Yes | `redis://localhost:6379/0` | Upstash `rediss://...` |
| `LLM_PROVIDER` | No | `groq` | `groq`/`gemini`/`auto` (auto = Groq→Gemini on daily quota) |
| `MAX_LLM_CALLS` | No | `50` | Per-job LLM cap |
| `MAX_TOOL_CALLS` | No | `10` | Per-job web_search cap |
| `MAX_RESEARCH_TIME` | No | `120` | Seconds, `ResearchRunTimeoutError` |
| `MAX_CONTEXT_SIZE` | No | `8192` | Tokens, `ContextWindowExceededError` |

## API

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | `{"status":"ok"}` |
| `GET` | `/metrics` | Prometheus `research_runs_total` |
| `POST` | `/research` | `{question: string 1-2000}` → `201 {id, question, status:pending}` (10/min IP) |
| `GET` | `/research/{id}` | `{status: pending|running|completed|failed}` |
| `GET` | `/research/{id}/report` | `ResearchReport` + `sources` (404 if not completed) |
| `GET` | `/research/{id}/stream` | `text/event-stream` SSE `research-events:{id}` |

## Deployment

* **Backend:** `Dockerfile:26` `python -m app.supervisor` (uvicorn + worker) on **Render** (`PORT` env, `healthCheck /health`), `docker-compose.yml:3` `pgvector/pgvector:pg16` + `redis:7-alpine` for local
* **DB:** **Supabase** `pgvector 0.8.2` (`alembic upgrade head` via `migrate` service)
* **Cache:** **Upstash Redis** `socket_connect_timeout 10` `app/db/redis.py:29`
* **Frontend:** **Vercel** `frontend/` `Next.js 16` `Root Directory: frontend` `NEXT_PUBLIC_API_URL`

## Testing & Evaluation

```bash
uv run pytest -q --cov=app  # 248 passed, 87% cov
uv run pytest tests/integration/test_report_transaction.py -q  # atomic rollback: grounded=None → NotNullViolation → report None
uv run python scripts/smoke_test_live_graph.py  # live Groq→Gemini with Tavily (needs keys, ~60-90s)
```

* **Eval dataset** `app/eval/dataset.json:1` 10 items (`expected_claims`/`must_contain_keywords`) + `app/eval/metrics.py:26` `citation/coverage/grounding/relevance` → `QualityMetrics` + `app/eval/runner.py:28` `EvaluationRunner` JSONL + `app/eval/report.py:28` comparison

## Known Limitations (frozen at `e0d4a1b` → `76217f7`)

* Free-tier `Groq` `TPD 200k` daily quota → `FallbackProvider` to `Gemini` (verified `bd9637f9 completed score:5` after `429`), but burst `10× POST` can still exhaust — no Redis `slowapi` yet
* `running` jobs stuck >5m need manual `UPDATE status='failed'` — `lease_expires_at` `app/db/models/research.py:33` + `heartbeat` `app/workers/research_worker.py:42` is in `6241c8c` but live 2-worker fencing not yet proven on Render
* `Research History` `frontend/app/page.js:15` is `useState` session-only — no `GET /research?limit` persistence
* Full 65-source graph can exceed `MAX_RESEARCH_TIME 120` — narrow `What is pgvector?` works, broad `Explain pgvector...` needs `300` or `MAX_TOOL_CALLS=3`

## Roadmap

* 24-29 Observability, resilience, API, deployment, recovery ✅
* 30 Frontend dashboard ✅ `73899f5`
* 31 Stale-worker fencing live test (2 workers) — pending
* 32 End-to-end acceptance `Vercel`→`Render`→`report` — live `3c1ed733 completed` proved once

## License

MIT — see `pyproject.toml:1`
