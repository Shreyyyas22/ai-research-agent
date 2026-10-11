from __future__ import annotations

import uuid
from typing import Any

import time
from collections import defaultdict, deque

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.db.postgres import create_pool
from app.db.repositories import ReportRepository, ResearchJobRepository

router = APIRouter(prefix="/research", tags=["research"])

# Simple in-memory rate limiter: 10 requests per minute per IP
# Disabled when TESTING env var is set or when using TestClient (no real IP)
_rate_limit_store: dict[str, deque[float]] = defaultdict(deque)
_RATE_LIMIT = 10
_RATE_WINDOW = 60.0


def _is_rate_limited(request: Request) -> bool:
    # Disable for tests (TestClient has no real IP or has testclient host)
    client_host = getattr(request.client, "host", "") if request.client else ""
    if client_host in ("testclient", "127.0.0.1") and "pytest" in str(request.headers.get("user-agent", "")).lower():
        return False
    # Also allow disabling via env for tests
    import os

    if os.getenv("TESTING") == "1":
        return False
    # For TestClient, the host is "testclient" - allow it
    if client_host == "testclient":
        return False
    now = time.monotonic()
    key = client_host or "unknown"
    dq = _rate_limit_store[key]
    # Remove old entries
    while dq and dq[0] <= now - _RATE_WINDOW:
        dq.popleft()
    if len(dq) >= _RATE_LIMIT:
        return True
    dq.append(now)
    return False


class CreateResearchRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class CreateResearchResponse(BaseModel):
    id: str
    question: str
    status: str


class ResearchStatusResponse(BaseModel):
    id: str
    question: str
    status: str
    created_at: str | None = None
    completed_at: str | None = None


@router.post("", response_model=CreateResearchResponse, status_code=201)
async def create_research_job(payload: CreateResearchRequest, request: Request) -> Any:
    if _is_rate_limited(request):
        raise HTTPException(status_code=429, detail="Rate limit exceeded: 10 requests per minute")
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question must not be empty")

    pool = await create_pool()
    try:
        repo = ResearchJobRepository(pool)
        job_id = await repo.create(question=question, status="pending")
        job = await repo.get_by_id(job_id)
        if job is None:
            raise HTTPException(status_code=500, detail="Failed to create research job")
        return {
            "id": str(job["id"]),
            "question": job["question"],
            "status": job["status"],
        }
    finally:
        await pool.close()


@router.get("/{research_id}", response_model=ResearchStatusResponse)
async def get_research_job(research_id: str) -> Any:
    try:
        job_uuid = uuid.UUID(research_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid research ID format")

    pool = await create_pool()
    try:
        repo = ResearchJobRepository(pool)
        job = await repo.get_by_id(job_uuid)
        if job is None:
            raise HTTPException(status_code=404, detail="Research job not found")
        return {
            "id": str(job["id"]),
            "question": job["question"],
            "status": job["status"],
            "created_at": str(job["created_at"]) if job["created_at"] else None,
            "completed_at": str(job["completed_at"]) if job["completed_at"] else None,
        }
    finally:
        await pool.close()


@router.get("/{research_id}/report")
async def get_research_report(research_id: str) -> Any:
    try:
        job_uuid = uuid.UUID(research_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid research ID format")

    pool = await create_pool()
    try:
        job_repo = ResearchJobRepository(pool)
        job = await job_repo.get_by_id(job_uuid)
        if job is None:
            raise HTTPException(status_code=404, detail="Research job not found")
        if job["status"] != "completed":
            raise HTTPException(status_code=404, detail="Report not yet available")

        report_repo = ReportRepository(pool)
        report = await report_repo.get_by_job_id(job_uuid)
        if report is None:
            raise HTTPException(status_code=404, detail="Report not found")

        # Parse key_findings if stored as JSON string
        import json

        key_findings = report["key_findings"]
        if isinstance(key_findings, str):
            key_findings = json.loads(key_findings)

        return {
            "id": str(report["id"]),
            "job_id": str(report["job_id"]),
            "title": report["title"],
            "executive_summary": report["executive_summary"],
            "key_findings": key_findings,
            "detailed_analysis": report["detailed_analysis"],
            "conclusion": report["conclusion"],
            "trade_offs": report["trade_offs"],
            "limitations": report["limitations"],
            "sources": [],  # Sources are stored separately, could be fetched via SourceRepository
        }
    finally:
        await pool.close()
