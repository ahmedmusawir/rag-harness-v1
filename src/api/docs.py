from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from src.api.dependencies import verify_api_key
from src.services.config_service import config
from src.services.rag_service import (
    RagServiceError,
    RagSummaryError,
    RagUploadTimeoutError,
    rag_service,
)
from src.services.state_service import (
    DocumentNotFoundError,
    ProjectNotFoundError,
    state_service,
)
from src.types.doc import QueryRequest, QueryResponse, UploadResponse

router = APIRouter(dependencies=[Depends(verify_api_key)])

ALLOWED_TYPES = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
}
UPLOADS_DIR = Path("uploads")


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _ensure_project(project_id: str) -> dict[str, object]:
    try:
        return state_service.get_project(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


def _validate_upload(file: UploadFile, file_bytes: bytes, project: dict[str, object]) -> str:
    filename = file.filename or ""
    extension = Path(filename).suffix.lower()
    expected_mime = ALLOWED_TYPES.get(extension)
    if expected_mime is None or file.content_type != expected_mime:
        raise HTTPException(
            status_code=400,
            detail="File type not supported. Accepted: PDF, TXT",
        )

    max_bytes = config.MAX_FILE_SIZE_MB * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Max {config.MAX_FILE_SIZE_MB}MB.",
        )

    if int(project.get("doc_count", 0)) >= 200:
        raise HTTPException(
            status_code=400,
            detail="Project has reached the 200 document limit.",
        )

    display_name = Path(filename).stem
    if not display_name:
        raise HTTPException(
            status_code=400,
            detail="File type not supported. Accepted: PDF, TXT",
        )
    return display_name


def _write_upload_file(doc_id: str, filename: str, file_bytes: bytes) -> Path:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    upload_path = UPLOADS_DIR / f"{doc_id}{Path(filename).suffix.lower()}"
    upload_path.write_bytes(file_bytes)
    return upload_path


def _run_upload_pipeline(
    *,
    upload_path: Path,
    file_bytes: bytes,
    mime_type: str,
    store_id: str,
    display_name: str,
) -> dict[str, str]:
    summary_text = rag_service.generate_summary(
        file_bytes=file_bytes,
        mime_type=mime_type,
    )
    return rag_service.upload_document_pair(
        store_name=store_id,
        original_path=upload_path,
        display_name=display_name,
        summary_text=summary_text,
        summary_filename=f"{display_name}_SUMMARY.txt",
    )


@router.post("/projects/{project_id}/upload", response_model=UploadResponse)
async def upload_document(project_id: str, file: UploadFile = File(...)) -> dict[str, object]:
    project = _ensure_project(project_id)
    if not project.get("store_id"):
        raise HTTPException(status_code=500, detail="Upload failed: Project store is not configured.")

    file_bytes = await file.read()
    display_name = _validate_upload(file, file_bytes, project)

    doc_id = str(uuid4())
    upload_path = _write_upload_file(doc_id, file.filename or "upload", file_bytes)

    try:
        if config.UPLOAD_TIMEOUT_SECONDS <= 0:
            raise asyncio.TimeoutError
        upload_result = _run_upload_pipeline(
            upload_path=upload_path,
            file_bytes=file_bytes,
            mime_type=file.content_type or "",
            store_id=str(project["store_id"]),
            display_name=display_name,
        )
    except asyncio.TimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail="Upload timed out. Google API did not respond within 90 seconds.",
        ) from exc
    except RagUploadTimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail="Upload timed out. Google API did not respond within 90 seconds.",
        ) from exc
    except RagSummaryError as exc:
        raise HTTPException(status_code=500, detail=f"Upload failed: {exc}") from exc
    except RagServiceError as exc:
        raise HTTPException(status_code=500, detail=f"Upload failed: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Upload failed: {exc}") from exc

    uploaded_at = _utc_now_iso()
    document = {
        "id": doc_id,
        "project_id": project_id,
        "original_name": file.filename or "",
        "display_name": display_name,
        "file_size_bytes": len(file_bytes),
        "mime_type": file.content_type or "",
        "store_doc_name": upload_result["store_doc_name"],
        "summary_doc_name": upload_result["summary_doc_name"],
        "status": "indexed",
        "uploaded_at": uploaded_at,
        "error": None,
    }
    state_service.upsert_doc(project_id, document)
    return {
        "doc_id": doc_id,
        "original_name": document["original_name"],
        "display_name": display_name,
        "file_size_bytes": len(file_bytes),
        "status": "indexed",
        "store_doc_name": upload_result["store_doc_name"],
        "summary_doc_name": upload_result["summary_doc_name"],
        "uploaded_at": uploaded_at,
    }


@router.get("/projects/{project_id}/docs")
async def list_documents(project_id: str) -> dict[str, list[dict[str, object]]]:
    _ensure_project(project_id)
    return {"docs": state_service.list_docs(project_id)}


@router.delete("/projects/{project_id}/docs/{doc_id}")
async def delete_document(project_id: str, doc_id: str) -> dict[str, str]:
    try:
        document = state_service.get_doc(project_id, doc_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc

    try:
        if document.get("store_doc_name"):
            rag_service.delete_document(document["store_doc_name"])
        if document.get("summary_doc_name"):
            rag_service.delete_document(document["summary_doc_name"])
        state_service.delete_doc(project_id, doc_id)
    except RagServiceError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"message": "Document deleted successfully", "doc_id": doc_id}


@router.post("/projects/{project_id}/query", response_model=QueryResponse)
async def query_project(project_id: str, payload: QueryRequest) -> dict[str, object]:
    project = _ensure_project(project_id)
    if not project.get("store_id"):
        raise HTTPException(status_code=500, detail="Query failed: Project store is not configured.")

    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    start = time.perf_counter()
    try:
        result = rag_service.query_store(
            store_name=str(project["store_id"]),
            question=question,
            model=payload.model,
        )
    except RagServiceError as exc:
        raise HTTPException(status_code=500, detail=f"Query failed: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Query failed: {exc}") from exc
    latency_ms = int((time.perf_counter() - start) * 1000)

    sources = [
        {
            "doc_name": source.get("doc_name", ""),
            "chunk_text": source.get("chunk_text", ""),
            "relevance_score": source.get("relevance_score"),
        }
        for source in result.get("sources", [])
    ]
    return {
        "answer": result["answer"],
        "sources": sources,
        "model_used": payload.model,
        "project_id": project_id,
        "latency_ms": latency_ms,
    }
