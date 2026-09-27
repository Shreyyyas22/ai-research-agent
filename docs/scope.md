# AI Research Agent — V1 Scope

## Goal

Build a bounded AI research agent that accepts a complex research
question, plans research tasks, gathers evidence from web and
internal sources, detects conflicting evidence, synthesizes a
citation-grounded report, evaluates the report, and exposes the
workflow through a FastAPI backend.

## In Scope

- Complex research questions
- Query analysis
- Research planning
- Web search
- Web page fetching
- Internal document retrieval
- Evidence extraction
- Source evaluation
- Conflict detection
- Citation-grounded synthesis
- Structured research reports
- Report self-evaluation
- PostgreSQL persistence
- Vector retrieval with pgvector
- BM25 retrieval
- Hybrid retrieval with RRF
- FastAPI backend
- Background processing
- Redis coordination
- SSE progress streaming
- Structured logging
- Metrics and tracing
- Automated testing
- Docker deployment

## Out of Scope for V1

- Unlimited autonomous agent behavior
- Arbitrary shell command execution
- Fully autonomous software development
- Unbounded research loops
- Production-scale multi-region deployment
- Complex frontend UX
- Multiple LLM providers initially

## Design Principles

1. Bound agent autonomy.
2. Treat retrieved content as untrusted data.
3. Separate LLM providers from business logic.
4. Prefer structured outputs.
5. Ground generated claims in retrieved evidence.
6. Persist research results.
7. Make failures observable and recoverable.
8. Measure cost, latency, and quality rather than guessing them.