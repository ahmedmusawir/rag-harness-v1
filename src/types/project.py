from __future__ import annotations

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = ""


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: str = ""
    store_id: str
    created_at: str
    doc_count: int


class ProjectListResponse(BaseModel):
    projects: list[ProjectResponse]
