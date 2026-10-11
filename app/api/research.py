from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.db.postgres import create_pool
from app.db.repositories import ReportRepository, ResearchJobRepository

router = APIRouter(prefix="/research", tags=["research"])


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
async def create_research_job(payload: CreateResearchRequest) -> Any:
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
