from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class DocResponse(BaseModel):
    id: str
    original_name: str
    display_name: str
    file_size_bytes: int
    mime_type: str
    status: str
    uploaded_at: str
    error: str | None = None


class UploadResponse(BaseModel):
    doc_id: str
    original_name: str
    display_name: str
    file_size_bytes: int
    status: str
    store_doc_name: str
    summary_doc_name: str
    uploaded_at: str


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    model: str = "gemini-2.5-flash"


class QuerySource(BaseModel):
    doc_name: str
    chunk_text: str
    relevance_score: float | None = None


class QueryResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    answer: str
    sources: list[QuerySource]
    model_used: str
    project_id: str
    latency_ms: int
