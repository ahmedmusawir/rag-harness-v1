from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.dependencies import verify_api_key
from src.services.logging_service import get_logger
from src.services.rag_service import RagServiceError, rag_service
from src.services.state_service import ProjectNotFoundError, state_service
from src.types.project import ProjectCreate, ProjectListResponse, ProjectResponse

router = APIRouter(dependencies=[Depends(verify_api_key)])
logger = get_logger(__name__)


@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(payload: ProjectCreate) -> dict[str, object]:
    try:
        store = rag_service.create_store(payload.name)
        project = state_service.create_project(
            name=payload.name,
            description=payload.description,
            store_id=store["name"],
        )
        logger.info("project created project_id=%s store_id=%s", project["id"], project["store_id"])
        return project
    except RagServiceError as exc:
        logger.exception("project create failed name=%s", payload.name)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("project create failed name=%s", payload.name)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/projects", response_model=ProjectListResponse)
async def list_projects() -> dict[str, list[dict[str, object]]]:
    return {"projects": state_service.list_projects()}


@router.get("/projects/{project_id}")
async def get_project(project_id: str) -> dict[str, object]:
    try:
        return state_service.get_project(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str) -> dict[str, str]:
    try:
        project = state_service.get_project(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc

    try:
        for document in project["docs"].values():
            if document.get("store_doc_name"):
                rag_service.delete_document(document["store_doc_name"])
            if document.get("summary_doc_name"):
                rag_service.delete_document(document["summary_doc_name"])
        if project.get("store_id"):
            rag_service.delete_store(project["store_id"])
        state_service.delete_project(project_id)
    except RagServiceError as exc:
        logger.exception("project delete failed project_id=%s", project_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("project delete failed project_id=%s", project_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    logger.warning("project deleted project_id=%s", project_id)
    return {"message": "Project deleted successfully", "id": project_id}
