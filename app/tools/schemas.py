from pydantic import BaseModel, ConfigDict, Field

class SearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    url: str
    snippet: str

class SearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool
    results: list[SearchResult] = Field(default_factory=list)
    error: str | None = None

class FetchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool
    url: str
    title: str | None = None
    content: str = ""
    error: str | None = None