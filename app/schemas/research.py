from pydantic import BaseModel, ConfigDict, Field
from typing import Literal

class ResearchTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str
    search_queries: list[str]
    priority: int = Field(ge=1, le=5)


class ResearchPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tasks: list[ResearchTask] = Field(
        min_length=1,
        max_length=5,
    )


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    url: str


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Source
    claim: str
    excerpt: str


class ExtractedEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim: str
    excerpt: str


class EvidenceExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence: list[ExtractedEvidence] = Field(
        min_length=0,
        max_length=10,
    )

class Conflict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_a: str
    claim_b: str
    possible_explanation: str
    confidence: Literal["low", "medium", "high"]


class EvidenceSufficiency(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sufficient: bool
    reasoning: str
    missing_information: list[str] = Field(
        default_factory=list,
        max_length=10,
    )


class SourceEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sufficiency: EvidenceSufficiency
    conflicts: list[Conflict] = Field(
        default_factory=list,
        max_length=10,
    )

class SynthesizedClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim: str
    citation_ids: list[int] = Field(
        min_length=1,
        max_length=5,
    )


class SynthesisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claims: list[SynthesizedClaim] = Field(
        min_length=1,
        max_length=20,
    )

class ResearchReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    executive_summary: str

    key_findings: list[SynthesizedClaim] = Field(
        min_length=1,
        max_length=20,
    )

    detailed_analysis: str

    trade_offs: list[str] = Field(
        default_factory=list,
        max_length=10,
    )

    evidence: list[Evidence] = Field(
        default_factory=list,
        max_length=50,
    )

    limitations: list[str] = Field(
        default_factory=list,
        max_length=10,
    )

    conclusion: str

    sources: list[Source] = Field(
        min_length=1,
        max_length=50,
    )