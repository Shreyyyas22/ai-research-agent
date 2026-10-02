from pydantic import BaseModel, ConfigDict, Field


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