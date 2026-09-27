# AI Research Agent Architecture

```mermaid
flowchart TD
    A[User] --> B[FastAPI]
    B --> C[Research Service]
    C --> D[LangGraph Agent]

    D --> E[Query Analysis]
    E --> F[Research Planner]
    F --> G[Task Execution]

    G --> H[Web Search]
    G --> I[Web Fetch]
    G --> J[Internal RAG]

    J --> K[PostgreSQL + pgvector]
    H --> L[Evidence]
    I --> L
    J --> L

    L --> M[Source Evaluation]
    M --> N{Enough Evidence?}

    N -->|No| G
    N -->|Yes| O[Synthesis]

    O --> P[Citation Generation]
    P --> Q[Report Evaluation]

    Q --> R{Pass?}
    R -->|No| G
    R -->|Yes| S[Final Report]

    S --> K
    S --> B