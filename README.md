# AI Research Agent

An AI-powered research system that autonomously investigates questions, searches the web, gathers and evaluates evidence, generates citation-grounded research reports, and evaluates the quality of its output.

The project combines LLM orchestration, web search, evidence processing, retrieval infrastructure, PostgreSQL persistence, asynchronous job execution, and a Next.js dashboard to deliver an end-to-end research experience.

## Live Demo

- **Frontend:** https://ai-research-agent-tau-mauve.vercel.app/
- **Backend API:** https://ai-research-agent-a166.onrender.com
- **Health Check:** https://ai-research-agent-a166.onrender.com/health
- **Metrics:** https://ai-research-agent-a166.onrender.com/metrics

> Note: The backend runs on Render's free tier and may sleep after inactivity. The first request after an idle period can take longer while the service wakes up.

## Features

### Autonomous Research Workflow

- Accepts natural-language research questions through a REST API.
- Generates structured research plans using LLMs.
- Executes research tasks and gathers web sources through Tavily.
- Extracts, limits, and deduplicates source content.
- Processes evidence to support research findings.
- Evaluates sources and synthesizes citation-grounded findings.
- Generates structured research reports with key findings and citation references.
- Evaluates completed reports for quality, grounding, and citation correctness.

### LLM Integration and Provider Resilience

- Supports Groq and Google Gemini providers.
- Implements a shared fallback provider to switch from Groq to Gemini when appropriate.
- Handles retryable rate-limit and service-unavailable errors with bounded retries.
- Fails fast for recognized daily-quota exhaustion so unnecessary retries are avoided.
- Supports provider selection through the `LLM_PROVIDER` configuration.
- Tracks LLM calls, token usage, duration, and estimated cost where usage information is available.

### Retrieval and Evidence Processing

- PostgreSQL-backed research persistence.
- pgvector support for embedding storage and vector similarity search.
- HNSW indexing support for vector retrieval.
- Hybrid retrieval infrastructure using vector search and BM25/RRF techniques.
- Bounded source collection and evidence processing to control context size.
- Prompt-injection and URL-security protections in the web-fetching pipeline.

### Asynchronous Job Processing

- Separates API request handling from research execution.
- Tracks jobs through pending, running, completed, and failed states.
- Uses PostgreSQL transactions for atomic report and evaluation persistence.
- Claims pending jobs atomically using `FOR UPDATE SKIP LOCKED`.
- Implements worker leases and heartbeats to support abandoned-job recovery.
- Prioritizes pending work over expired running jobs.
- Supports progress reporting and server-sent events (SSE).
- Prevents multiple workers from claiming the same pending job in the tested concurrent-claiming scenario.

### Observability and Operational Reliability

- Structured JSON logging.
- Prometheus metrics.
- Trace and run-context instrumentation.
- LLM and tool-call tracking.
- Configurable execution timeouts and call limits.
- Bounded retries and explicit provider-failure handling.
- Worker supervision and graceful shutdown.
- API request validation and IP-based request throttling.

### Web Dashboard

The Next.js frontend provides an interface for interacting with the research backend.

- Submit research questions.
- Receive a research job ID.
- Track job status and progress.
- Stream progress events through SSE.
- Retrieve completed reports.
- Display key findings and citation references.

## Architecture

```text
                  User
                   |
                   v
          Next.js Research UI
                   |
                   v
             FastAPI API
                   |
           POST /research
                   |
                   v
          PostgreSQL Job Queue
                   |
                   v
          Research Worker
                   |
                   v
          LangGraph Workflow
                   |
        +----------+----------+
        |          |          |
        v          v          v
   Research     Tavily      Evidence
    Planner     Search      Processing
        |          |          |
        +----------+----------+
                   |
                   v
          Source Evaluation
                   |
                   v
          Citation-Grounded
             Synthesis
                   |
                   v
          Report Evaluation
                   |
                   v
       Atomic Report Persistence
                   |
           +-------+-------+
           |               |
           v               v
       PostgreSQL        Redis
           |               |
           v               v
      Report API       Live Progress
           |
           v
       Next.js UI
```

LLM requests are routed through the configured provider abstraction, with Groq-to-Gemini fallback. PostgreSQL stores research jobs and persisted results, while Redis supports progress-related functionality.

## Technology Stack

| Layer | Technologies |
|---|---|
| Language | Python 3.12, JavaScript |
| Backend | FastAPI, Pydantic, async Python |
| Agent orchestration | LangGraph, LangChain components |
| LLM providers | Groq, Google Gemini |
| Web search | Tavily |
| Database | PostgreSQL, asyncpg, SQLAlchemy/Alembic where applicable |
| Vector search | pgvector, HNSW |
| Retrieval | Embeddings, BM25, Reciprocal Rank Fusion (RRF) |
| Progress and caching infrastructure | Redis, Server-Sent Events |
| Frontend | Next.js App Router, React |
| Monitoring | Prometheus, structured logging, tracing |
| Testing | pytest, FastAPI TestClient, integration and acceptance tests |
| Deployment | Render, Vercel |

## API Reference

Base URL:

```text
https://ai-research-agent-a166.onrender.com
```

### 1. Create a Research Job

`POST /research`

Request:

```json
{
  "question": "What is pgvector HNSW indexing?"
}
```

The question must contain between 1 and 2,000 characters.

Successful response: `201 Created`

```json
{
  "id": "YOUR_RESEARCH_JOB_ID",
  "question": "What is pgvector HNSW indexing?",
  "status": "pending"
}
```

### 2. Retrieve Job Status

`GET /research/{id}`

Returns the job information and its current status.

Possible lifecycle states:

- `pending`
- `running`
- `completed`
- `failed`

Invalid UUIDs return `400 Bad Request`, while unknown jobs return `404 Not Found`.

### 3. Retrieve the Research Report

`GET /research/{id}/report`

Returns the completed report, including its title, key findings, and citation references.

A report that is not yet available returns `404 Not Found`.

### 4. Stream Research Progress

`GET /research/{id}/stream`

Uses Server-Sent Events to deliver research progress to connected clients.

### 5. Health Check

`GET /health`

Provides a health response for service monitoring.

### 6. Prometheus Metrics

`GET /metrics`

Exposes application metrics, including research-run metrics.

## Development Setup

### Prerequisites

- Python 3.12
- Node.js and npm
- PostgreSQL with pgvector support
- Redis
- API credentials for the configured LLM and search providers

### Backend Setup

From the repository root:

```bash
git clone https://github.com/Shreyyyas22/ai-research-agent.git
cd ai-research-agent
```

Create and activate a virtual environment:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

Install project dependencies using the repository's existing dependency manager and lockfile.

Configure the required environment variables in `.env`, using `.env.example` as the reference.

Start the backend using the repository's configured ASGI application entry point.

### Frontend Setup

```bash
cd frontend
npm install
```

Create a frontend environment file with:

```env
NEXT_PUBLIC_API_URL=https://ai-research-agent-a166.onrender.com
```

Start the development server:

```bash
npm run dev
```

Open the local URL printed by Next.js in your terminal.

> Use the existing project scripts and dependency lockfiles. The exact backend startup command and optional services should be confirmed against the current repository configuration.

## Environment Configuration

Configure the following variables according to your deployment:

| Variable | Purpose |
|---|---|
| `GROQ_API_KEY` | Groq API authentication |
| `GEMINI_API_KEY` | Google Gemini API authentication |
| `TAVILY_API_KEY` | Tavily web-search authentication |
| `LLM_PROVIDER` | Selects the configured LLM provider mode |
| `DATABASE_URL` | PostgreSQL connection configuration |
| Redis configuration | Connection settings for Redis |

The application also uses configuration for execution limits, retries, database connections, and other operational settings.

Never commit `.env` files, API keys, database passwords, or Redis credentials to source control.

## Testing

Run the backend test suite using the repository's configured environment:

```bash
uv run pytest -q
```

Run a compilation check:

```bash
uv run python -m compileall -q app
```

Check the Git diff for whitespace errors:

```bash
git diff --check
```

The test suite includes unit, integration, and API acceptance coverage for areas such as:

- LLM usage tracking and provider fallback.
- Gemini retry and quota handling.
- Research workflow instrumentation and execution limits.
- URL validation and web-fetch security.
- Atomic report and evaluation persistence.
- Concurrent job claiming.
- Lease creation, heartbeat refresh, and expired-job recovery.
- API request validation and HTTP response contracts.
- Health, metrics, and stream endpoint contracts.

Test totals have varied across development checkpoints as tests and implementation changed. Run the commands above against the current checkout to establish the definitive release result.

## Development Milestones

The project evolved through foundational research-agent implementation, reliability work, production deployment, and frontend integration.

| Phase | Milestone | Outcome |
|---|---|---|
| 0–23 | Research-agent foundation and core workflow | Agent orchestration, retrieval, persistence, instrumentation, and execution controls developed incrementally |
| 24 | Observability | Structured logging, metrics, and tracing |
| 25 | Failure recovery and resilience | Provider fallback, retry behavior, concurrent job claiming, and duplicate-prevention tests |
| 26 | API contract and acceptance | Research creation, status, report, health, metrics, and stream contracts |
| 27 | Security and operational hardening | Input validation, SSRF protections, secret redaction, timeouts, and operational checks |
| 28 | Deployment and load validation | IP-based rate limiting, concurrent submission validation, and live deployment checks |
| 29 | Job lease and recovery | Worker ownership metadata, heartbeat renewal, lease expiry, and abandoned-job reclamation |
| 30 | Frontend dashboard | Next.js scaffold, Vercel deployment, and a successful real end-to-end research report |

The phase descriptions above summarize the recorded development checkpoints; not every possible production failure scenario has been exhaustively tested.

## Deployment

### Frontend

- Platform: Vercel
- Live URL: https://ai-research-agent-tau-mauve.vercel.app/
- Root directory: `frontend`
- Environment variable: `NEXT_PUBLIC_API_URL`

### Backend

- Platform: Render
- Live URL: https://ai-research-agent-a166.onrender.com
- Application API and worker are supervised within the deployed service.
- PostgreSQL and Redis provide persistence and progress-related infrastructure.

The first real end-to-end research report was successfully generated through the deployed frontend, backend, Tavily search, LLM provider fallback, database persistence, and report retrieval.

## Known Limitations

- Research endpoints are currently public; authentication has not been enabled.
- IP-based rate limiting uses an in-memory limiter. Its counters are not shared across multiple application processes or instances, so it is not a distributed rate-limiting solution.
- Render's free tier may sleep during inactivity, increasing the latency of the first request.
- Groq and Gemini quotas, service availability, and response latency depend on their respective providers.
- Lease-based recovery has been implemented, but stale-worker fencing across every database write must be verified before claiming complete protection against outdated workers.
- Multi-worker recovery and the full range of provider and infrastructure failure scenarios have not all been validated in live production.
- Cost estimates depend on the usage information and pricing assumptions available to the application.

## Future Improvements

Potential improvements include:

- API authentication and user-level access control.
- Distributed rate limiting.
- Strong stale-worker fencing and bounded retry policies.
- Additional multi-worker and fault-injection tests.
- Persistent research history and filtering in the dashboard.
- More detailed report exports and citation presentation.
- Usage and cost summaries in the frontend.
- Further performance and concurrency benchmarking.

## License

Add the project's chosen license before distributing or reusing the code publicly.
