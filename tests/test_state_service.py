from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.services.state_service import (
    DocumentNotFoundError,
    InvalidStateError,
    ProjectNotFoundError,
    StateService,
)


def build_document(doc_id: str, project_id: str, status: str = "indexed") -> dict[str, object]:
    return {
        "id": doc_id,
        "project_id": project_id,
        "original_name": "doc.pdf",
        "display_name": "doc",
        "file_size_bytes": 123,
        "mime_type": "application/pdf",
        "store_doc_name": "fileSearchStores/demo/documents/doc-1",
        "summary_doc_name": "fileSearchStores/demo/documents/doc-1-summary",
        "status": status,
        "uploaded_at": "2026-03-07T14:35:00Z",
        "error": None,
    }


def make_service(tmp_path: Path) -> StateService:
    return StateService(tmp_path / "projects.json")


def test_auto_creates_missing_projects_file(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    state = service.load_state()

    assert state == {"projects": {}}
    assert (tmp_path / "projects.json").exists()


def test_create_and_list_projects(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    created = service.create_project(
        name="Architect Agent",
        description="Docs",
        store_id="fileSearchStores/demo",
        project_id="project-1",
        created_at="2026-03-07T14:31:00Z",
    )

    projects = service.list_projects()

    assert created["doc_count"] == 0
    assert projects == [
        {
            "id": "project-1",
            "name": "Architect Agent",
            "description": "Docs",
            "store_id": "fileSearchStores/demo",
            "created_at": "2026-03-07T14:31:00Z",
            "doc_count": 0,
        }
    ]


def test_get_project_raises_for_missing_id(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    with pytest.raises(ProjectNotFoundError, match="Project not found"):
        service.get_project("missing")


def test_upsert_doc_recalculates_doc_count(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    service.create_project(
        name="Architect Agent",
        store_id="fileSearchStores/demo",
        project_id="project-1",
        created_at="2026-03-07T14:31:00Z",
    )

    service.upsert_doc("project-1", build_document("doc-1", "project-1"))
    service.upsert_doc("project-1", build_document("doc-2", "project-1", status="processing"))

    project = service.get_project("project-1")

    assert project["doc_count"] == 2
    assert set(project["docs"]) == {"doc-1", "doc-2"}


def test_delete_doc_recalculates_doc_count(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    service.create_project(
        name="Architect Agent",
        store_id="fileSearchStores/demo",
        project_id="project-1",
    )
    service.upsert_doc("project-1", build_document("doc-1", "project-1"))

    removed = service.delete_doc("project-1", "doc-1")
    project = service.get_project("project-1")

    assert removed["id"] == "doc-1"
    assert project["doc_count"] == 0
    assert project["docs"] == {}


def test_delete_doc_raises_for_missing_doc(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    service.create_project(
        name="Architect Agent",
        store_id="fileSearchStores/demo",
        project_id="project-1",
    )

    with pytest.raises(DocumentNotFoundError, match="Document not found"):
        service.delete_doc("project-1", "missing-doc")


def test_delete_project_removes_project(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    service.create_project(
        name="Architect Agent",
        store_id="fileSearchStores/demo",
        project_id="project-1",
    )

    removed = service.delete_project("project-1")

    assert removed["id"] == "project-1"
    assert service.list_projects() == []


def test_invalid_document_status_is_rejected(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    service.create_project(
        name="Architect Agent",
        store_id="fileSearchStores/demo",
        project_id="project-1",
    )

    with pytest.raises(InvalidStateError, match="Document status"):
        service.upsert_doc("project-1", build_document("doc-1", "project-1", status="done"))


def test_load_state_recalculates_doc_count_from_docs(tmp_path: Path) -> None:
    state_file = tmp_path / "projects.json"
    state_file.write_text(
        json.dumps(
            {
                "projects": {
                    "project-1": {
                        "id": "project-1",
                        "name": "Architect Agent",
                        "description": "",
                        "store_id": "fileSearchStores/demo",
                        "created_at": "2026-03-07T14:31:00Z",
                        "doc_count": 999,
                        "docs": {
                            "doc-1": build_document("doc-1", "project-1"),
                            "doc-2": build_document("doc-2", "project-1"),
                        },
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    service = StateService(state_file)
    project = service.get_project("project-1")

    assert project["doc_count"] == 2


def test_state_file_is_written_as_valid_json(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    service.create_project(
        name="Architect Agent",
        store_id="fileSearchStores/demo",
        project_id="project-1",
    )

    raw = json.loads((tmp_path / "projects.json").read_text(encoding="utf-8"))

    assert raw["projects"]["project-1"]["name"] == "Architect Agent"
