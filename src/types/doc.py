from __future__ import annotations

from typing import Any

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
    model: str = "gemini-2.5-pro"


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


class StoreDocumentSummary(BaseModel):
    name: str
    display_name: str


class StoreCheckResponse(BaseModel):
    project_id: str
    project_name: str
    store_id: str
    document_count: int
    documents: list[StoreDocumentSummary]


class StoreDetailsResponse(BaseModel):
    project_id: str
    project_name: str
    store_id: str
    store_display_name: str
    doc_count: int
    raw: dict[str, Any] | None = None


class StoreDocumentsResponse(BaseModel):
    project_id: str
    store_id: str
    document_count: int
    documents: list[StoreDocumentSummary]


class StoreDocumentDetailsResponse(BaseModel):
    name: str
    display_name: str
    raw: dict[str, Any] | None = None


class StoreVerifyItem(BaseModel):
    name: str
    display_name: str
    document_count: int


class StoreVerifyResponse(BaseModel):
    total_stores: int
    stores: list[StoreVerifyItem]


class CleanupRequest(BaseModel):
    confirm: bool = False
    confirmation_text: str = ""


class CleanupPreviewResponse(BaseModel):
    project_id: str
    project_name: str
    store_id: str
    doc_count: int
    docs: list[DocResponse]
    warning: str


class CleanupResponse(BaseModel):
    project_id: str
    store_id: str
    deleted_count: int
    doc_count: int
    message: str


class OperationStatusResponse(BaseModel):
    name: str
    done: bool | None = None
    metadata: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
