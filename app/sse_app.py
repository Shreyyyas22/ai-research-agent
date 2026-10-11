from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.metrics import router as metrics_router
from app.api.research import router as research_router
from app.api.sse import router
from app.observability.logging import configure_logging

configure_logging()


app = FastAPI(
    title="AI Research Agent - SSE",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(metrics_router)
app.include_router(research_router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
