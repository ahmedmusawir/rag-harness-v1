from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from uuid import uuid4

PROJECTS_FILE = Path("projects.json")
EMPTY_STATE = {"projects": {}}
VALID_DOC_STATUSES = {"processing", "indexed", "failed"}


class StateServiceError(Exception):
    """Base exception for state service failures."""


class ProjectNotFoundError(StateServiceError):
    """Raised when a project cannot be found."""


class DocumentNotFoundError(StateServiceError):
    """Raised when a document cannot be found."""


class InvalidStateError(StateServiceError):
    """Raised when projects.json contains invalid data."""


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class StateService:
    def __init__(self, state_file: Path | str = PROJECTS_FILE) -> None:
        self.state_file = Path(state_file)

    def ensure_state_file(self) -> None:
        if self.state_file.exists():
            return
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self._write_state(EMPTY_STATE)

    def load_state(self) -> dict[str, Any]:
        self.ensure_state_file()
        with self.state_file.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return self._validate_state(data)

    def list_projects(self) -> list[dict[str, Any]]:
        state = self.load_state()
        projects = state["projects"].values()
        return [self._project_summary(project) for project in projects]

    def get_project(self, project_id: str) -> dict[str, Any]:
        state = self.load_state()
        project = state["projects"].get(project_id)
        if project is None:
            raise ProjectNotFoundError("Project not found")
        return deepcopy(project)

    def create_project(
        self,
        *,
        name: str,
        description: str = "",
        store_id: str,
        created_at: str | None = None,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        state = self.load_state()
        new_project_id = project_id or str(uuid4())
        project = {
            "id": new_project_id,
            "name": name,
            "description": description,
            "store_id": store_id,
            "created_at": created_at or _utc_now_iso(),
            "doc_count": 0,
            "docs": {},
        }
        state["projects"][new_project_id] = project
        self._write_state(state)
        return deepcopy(project)

    def delete_project(self, project_id: str) -> dict[str, Any]:
        state = self.load_state()
        project = state["projects"].pop(project_id, None)
        if project is None:
            raise ProjectNotFoundError("Project not found")
        self._write_state(state)
        return deepcopy(project)

    def list_docs(self, project_id: str) -> list[dict[str, Any]]:
        project = self.get_project(project_id)
        return list(project["docs"].values())

    def get_doc(self, project_id: str, doc_id: str) -> dict[str, Any]:
        project = self.get_project(project_id)
        document = project["docs"].get(doc_id)
        if document is None:
            raise DocumentNotFoundError("Document not found")
        return deepcopy(document)

    def upsert_doc(self, project_id: str, document: dict[str, Any]) -> dict[str, Any]:
        state = self.load_state()
        project = state["projects"].get(project_id)
        if project is None:
            raise ProjectNotFoundError("Project not found")

        validated_document = self._validate_document(document, project_id=project_id)
        project["docs"][validated_document["id"]] = validated_document
        self._recalculate_doc_count(project)
        self._write_state(state)
        return deepcopy(validated_document)

    def delete_doc(self, project_id: str, doc_id: str) -> dict[str, Any]:
        state = self.load_state()
        project = state["projects"].get(project_id)
        if project is None:
            raise ProjectNotFoundError("Project not found")

        document = project["docs"].pop(doc_id, None)
        if document is None:
            raise DocumentNotFoundError("Document not found")

        self._recalculate_doc_count(project)
        self._write_state(state)
        return deepcopy(document)

    def clear_docs(self, project_id: str) -> int:
        state = self.load_state()
        project = state["projects"].get(project_id)
        if project is None:
            raise ProjectNotFoundError("Project not found")

        removed_count = len(project["docs"])
        project["docs"] = {}
        self._recalculate_doc_count(project)
        self._write_state(state)
        return removed_count

    def _write_state(self, state: dict[str, Any]) -> None:
        validated_state = self._validate_state(state)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            delete=False,
            dir=self.state_file.parent,
        ) as handle:
            json.dump(validated_state, handle, indent=2)
            handle.write("\n")
            temp_path = Path(handle.name)
        temp_path.replace(self.state_file)

    def _validate_state(self, state: Any) -> dict[str, Any]:
        if not isinstance(state, dict):
            raise InvalidStateError("State must be a JSON object")

        projects = state.get("projects")
        if projects is None:
            state = {"projects": {}}
            projects = state["projects"]
        if not isinstance(projects, dict):
            raise InvalidStateError("State 'projects' must be an object")

        validated_projects: dict[str, Any] = {}
        for project_id, project in projects.items():
            if not isinstance(project, dict):
                raise InvalidStateError("Each project must be an object")
            docs = project.get("docs") or {}
            if not isinstance(docs, dict):
                raise InvalidStateError("Project 'docs' must be an object")

            validated_docs: dict[str, Any] = {}
            for doc_id, document in docs.items():
                validated_docs[doc_id] = self._validate_document(
                    document,
                    project_id=project.get("id", project_id),
                )

            validated_project = {
                "id": project.get("id", project_id),
                "name": project.get("name", ""),
                "description": project.get("description", ""),
                "store_id": project.get("store_id", ""),
                "created_at": project.get("created_at", ""),
                "doc_count": 0,
                "docs": validated_docs,
            }
            self._recalculate_doc_count(validated_project)
            validated_projects[validated_project["id"]] = validated_project

        return {"projects": validated_projects}

    def _validate_document(
        self, document: dict[str, Any], *, project_id: str
    ) -> dict[str, Any]:
        if not isinstance(document, dict):
            raise InvalidStateError("Document must be an object")

        status = document.get("status")
        if status not in VALID_DOC_STATUSES:
            raise InvalidStateError(f"Document status must be one of {VALID_DOC_STATUSES}")

        doc_id = str(document.get("id") or "")
        if not doc_id:
            raise InvalidStateError("Document id is required")

        return {
            "id": doc_id,
            "project_id": document.get("project_id", project_id),
            "original_name": document.get("original_name", ""),
            "display_name": document.get("display_name", ""),
            "file_size_bytes": int(document.get("file_size_bytes", 0)),
            "mime_type": document.get("mime_type", ""),
            "store_doc_name": document.get("store_doc_name", ""),
            "summary_doc_name": document.get("summary_doc_name", ""),
            "status": status,
            "uploaded_at": document.get("uploaded_at", ""),
            "error": document.get("error"),
        }

    def _recalculate_doc_count(self, project: dict[str, Any]) -> None:
        project["doc_count"] = len(project["docs"])

    def _project_summary(self, project: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": project["id"],
            "name": project["name"],
            "description": project["description"],
            "store_id": project["store_id"],
            "created_at": project["created_at"],
            "doc_count": project["doc_count"],
        }


state_service = StateService()
