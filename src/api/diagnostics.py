from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import verify_api_key
from src.services.logging_service import get_logger
from src.services.rag_service import RagServiceError, rag_service
from src.services.state_service import ProjectNotFoundError, state_service
from src.types.doc import (
    CleanupRequest,
    CleanupResponse,
    CleanupPreviewResponse,
    OperationStatusResponse,
    StoreCheckResponse,
    StoreDetailsResponse,
    StoreDocumentDetailsResponse,
    StoreDocumentsResponse,
    StoreVerifyResponse,
)

router = APIRouter(dependencies=[Depends(verify_api_key)])
logger = get_logger(__name__)


def _ensure_project(project_id: str) -> dict[str, object]:
    try:
        return state_service.get_project(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@router.get("/projects/{project_id}/store/check", response_model=StoreCheckResponse)
async def check_store(project_id: str) -> dict[str, object]:
    project = _ensure_project(project_id)
    store_id = str(project.get("store_id", ""))
    try:
        documents = rag_service.list_documents(store_id)
    except RagServiceError as exc:
        logger.exception("store check failed project_id=%s store_id=%s", project_id, store_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    logger.info("store check project_id=%s store_id=%s document_count=%s", project_id, store_id, len(documents))
    return {
        "project_id": project_id,
        "project_name": project.get("name", ""),
        "store_id": store_id,
        "document_count": len(documents),
        "documents": documents,
    }


@router.get("/projects/{project_id}/store/details", response_model=StoreDetailsResponse)
async def get_store_details(project_id: str) -> dict[str, object]:
    project = _ensure_project(project_id)
    store_id = str(project.get("store_id", ""))
    try:
        remote = rag_service.get_store_details(store_id)
    except RagServiceError as exc:
        logger.exception("store details failed project_id=%s store_id=%s", project_id, store_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    logger.info("store details project_id=%s store_id=%s", project_id, store_id)
    return {
        "project_id": project_id,
        "project_name": project.get("name", ""),
        "store_id": store_id,
        "store_display_name": remote.get("display_name", ""),
        "doc_count": int(project.get("doc_count", 0)),
    }


@router.get("/projects/{project_id}/store/documents", response_model=StoreDocumentsResponse)
async def list_store_documents(project_id: str) -> dict[str, object]:
    project = _ensure_project(project_id)
    store_id = str(project.get("store_id", ""))
    try:
        documents = rag_service.list_documents(store_id)
    except RagServiceError as exc:
        logger.exception("store document list failed project_id=%s store_id=%s", project_id, store_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    logger.info("store documents listed project_id=%s store_id=%s count=%s", project_id, store_id, len(documents))
    return {
        "project_id": project_id,
        "store_id": store_id,
        "document_count": len(documents),
        "documents": documents,
    }


@router.get(
    "/projects/{project_id}/store/documents/{document_name:path}",
    response_model=StoreDocumentDetailsResponse,
)
async def get_store_document_details(project_id: str, document_name: str) -> dict[str, object]:
    _ensure_project(project_id)
    try:
        document = rag_service.get_document_details(document_name)
    except RagServiceError as exc:
        logger.exception("store document details failed project_id=%s document_name=%s", project_id, document_name)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    logger.info("store document details project_id=%s document_name=%s", project_id, document_name)
    return document


@router.get("/stores/verify", response_model=StoreVerifyResponse)
async def verify_stores() -> dict[str, object]:
    try:
        stores = rag_service.verify_stores()
    except RagServiceError as exc:
        logger.exception("store verify failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    logger.info("store verify total_stores=%s", len(stores))
    return {"total_stores": len(stores), "stores": stores}


@router.post(
    "/projects/{project_id}/store/cleanup-preview",
    response_model=CleanupPreviewResponse,
)
async def cleanup_preview(project_id: str) -> dict[str, object]:
    project = _ensure_project(project_id)
    docs = state_service.list_docs(project_id)
    logger.warning("cleanup preview project_id=%s store_id=%s doc_count=%s", project_id, project.get("store_id", ""), len(docs))
    return {
        "project_id": project_id,
        "project_name": project.get("name", ""),
        "store_id": project.get("store_id", ""),
        "doc_count": len(docs),
        "docs": docs,
        "warning": "This will delete all documents from the Google store and leave the store empty.",
    }


@router.post("/projects/{project_id}/store/cleanup", response_model=CleanupResponse)
async def cleanup_store(project_id: str, payload: CleanupRequest) -> dict[str, object]:
    project = _ensure_project(project_id)
    if not payload.confirm or payload.confirmation_text != "EMPTY STORE":
        raise HTTPException(
            status_code=400,
            detail="Cleanup requires confirm=true and confirmation_text='EMPTY STORE'.",
        )

    store_id = str(project.get("store_id", ""))
    try:
        deleted_documents = rag_service.cleanup_store(store_id)
        state_service.clear_docs(project_id)
    except RagServiceError as exc:
        logger.exception("cleanup failed project_id=%s store_id=%s", project_id, store_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    logger.warning(
        "cleanup executed project_id=%s store_id=%s deleted_count=%s",
        project_id,
        store_id,
        len(deleted_documents),
    )
    return {
        "project_id": project_id,
        "store_id": store_id,
        "deleted_count": len(deleted_documents),
        "doc_count": 0,
        "message": "Store cleaned successfully. The project remains, but the store is now empty.",
    }


@router.get("/operations/{operation_name:path}", response_model=OperationStatusResponse)
async def get_operation_status(operation_name: str) -> dict[str, object]:
    try:
        status_payload = rag_service.get_operation_status(operation_name)
    except RagServiceError as exc:
        logger.exception("operation status failed operation_name=%s", operation_name)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("operation status failed operation_name=%s", operation_name)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    logger.info("operation status operation_name=%s done=%s", operation_name, status_payload.get("done"))
    return status_payload
