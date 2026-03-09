from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio

os.environ.setdefault("GEMINI_API_KEY", "test-key")

from main import app
from src.api import dependencies as dependencies_module
from src.api import docs as docs_module
from src.api import projects as projects_module
from src.services.state_service import StateService


class FakeRagService:
    def __init__(self) -> None:
        self.create_store_result = {"name": "fileSearchStores/demo", "display_name": "Demo"}
        self.query_result = {
            "answer": "Answer",
            "sources": [
                {
                    "doc_name": "Resume",
                    "chunk_text": "Grounded text",
                    "relevance_score": None,
                }
            ],
        }
        self.created_names: list[str] = []
        self.deleted_store_names: list[str] = []
        self.deleted_doc_names: list[str] = []
        self.generate_summary_calls: list[dict[str, object]] = []
        self.upload_document_pair_calls: list[dict[str, object]] = []
        self.query_calls: list[dict[str, object]] = []
        self.raise_on_generate_summary: Exception | None = None
        self.raise_on_upload_pair: Exception | None = None
        self.raise_on_query: Exception | None = None

    def create_store(self, display_name: str) -> dict[str, str]:
        self.created_names.append(display_name)
        return self.create_store_result

    def delete_store(self, store_name: str) -> None:
        self.deleted_store_names.append(store_name)

    def delete_document(self, doc_name: str) -> None:
        self.deleted_doc_names.append(doc_name)

    def generate_summary(self, *, file_bytes: bytes, mime_type: str, **_: object) -> str:
        self.generate_summary_calls.append(
            {"file_bytes": file_bytes, "mime_type": mime_type}
        )
        if self.raise_on_generate_summary is not None:
            raise self.raise_on_generate_summary
        return "summary text"

    def upload_document_pair(self, **kwargs: object) -> dict[str, str]:
        self.upload_document_pair_calls.append(kwargs)
        if self.raise_on_upload_pair is not None:
            raise self.raise_on_upload_pair
        return {
            "store_doc_name": "fileSearchStores/demo/documents/original",
            "summary_doc_name": "fileSearchStores/demo/documents/summary",
        }

    def query_store(self, *, store_name: str, question: str, model: str) -> dict[str, object]:
        self.query_calls.append(
            {"store_name": store_name, "question": question, "model": model}
        )
        if self.raise_on_query is not None:
            raise self.raise_on_query
        return self.query_result


@pytest_asyncio.fixture
async def client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> httpx.AsyncClient:
    state_service = StateService(tmp_path / "projects.json")
    rag_service = FakeRagService()

    monkeypatch.setattr(projects_module, "state_service", state_service)
    monkeypatch.setattr(docs_module, "state_service", state_service)
    monkeypatch.setattr(projects_module, "rag_service", rag_service)
    monkeypatch.setattr(docs_module, "rag_service", rag_service)
    monkeypatch.setattr(dependencies_module.config, "API_KEY", "")
    monkeypatch.setattr(docs_module.config, "MAX_FILE_SIZE_MB", 50)
    monkeypatch.setattr(docs_module.config, "UPLOAD_TIMEOUT_SECONDS", 90)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as async_client:
        yield async_client


@pytest.fixture
def api_state() -> SimpleNamespace:
    return SimpleNamespace(
        dependencies=dependencies_module,
        docs=docs_module,
        projects=projects_module,
    )


async def create_project(client: httpx.AsyncClient) -> str:
    response = await client.post("/projects", json={"name": "Architect Agent"})
    assert response.status_code == 201
    return response.json()["id"]


@pytest.mark.asyncio
async def test_health_endpoint_is_public(
    client: httpx.AsyncClient,
    api_state: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(api_state.dependencies.config, "API_KEY", "secret")

    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_requests_require_matching_api_key_when_configured(
    client: httpx.AsyncClient,
    api_state: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(api_state.dependencies.config, "API_KEY", "secret")

    rejected = await client.post("/projects", json={"name": "Architect Agent"})
    accepted = await client.post(
        "/projects",
        json={"name": "Architect Agent"},
        headers={"X-API-Key": "secret"},
    )

    assert rejected.status_code == 403
    assert rejected.json() == {"detail": "Invalid API key"}
    assert accepted.status_code == 201


@pytest.mark.asyncio
async def test_missing_api_key_config_bypasses_auth(client: httpx.AsyncClient) -> None:
    response = await client.post("/projects", json={"name": "Architect Agent"})

    assert response.status_code == 201


@pytest.mark.asyncio
async def test_project_crud_routes_work(
    client: httpx.AsyncClient, api_state: SimpleNamespace
) -> None:
    project_id = await create_project(client)

    listed = await client.get("/projects")
    fetched = await client.get(f"/projects/{project_id}")
    deleted = await client.delete(f"/projects/{project_id}")

    assert listed.status_code == 200
    assert listed.json()["projects"][0]["id"] == project_id
    assert fetched.status_code == 200
    assert fetched.json()["id"] == project_id
    assert deleted.status_code == 200
    assert deleted.json() == {
        "message": "Project deleted successfully",
        "id": project_id,
    }
    assert api_state.projects.rag_service.deleted_store_names == ["fileSearchStores/demo"]


@pytest.mark.asyncio
async def test_upload_rejects_extension_mime_mismatch(client: httpx.AsyncClient) -> None:
    project_id = await create_project(client)

    response = await client.post(
        f"/projects/{project_id}/upload",
        files={"file": ("resume.pdf", b"hello", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "File type not supported. Accepted: PDF, TXT"}


@pytest.mark.asyncio
async def test_upload_rejects_oversized_files(
    client: httpx.AsyncClient,
    api_state: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_id = await create_project(client)
    monkeypatch.setattr(api_state.docs.config, "MAX_FILE_SIZE_MB", 0)

    response = await client.post(
        f"/projects/{project_id}/upload",
        files={"file": ("resume.txt", b"a", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "File too large. Max 0MB."}


@pytest.mark.asyncio
async def test_upload_rejects_when_project_doc_cap_reached(
    client: httpx.AsyncClient, api_state: SimpleNamespace
) -> None:
    project_id = await create_project(client)
    for index in range(200):
        api_state.docs.state_service.upsert_doc(
            project_id,
            {
                "id": f"doc-{index}",
                "project_id": project_id,
                "original_name": f"doc-{index}.txt",
                "display_name": f"doc-{index}",
                "file_size_bytes": 1,
                "mime_type": "text/plain",
                "store_doc_name": f"store/doc-{index}",
                "summary_doc_name": f"store/doc-{index}-summary",
                "status": "indexed",
                "uploaded_at": "2026-03-08T00:00:00Z",
                "error": None,
            },
        )

    response = await client.post(
        f"/projects/{project_id}/upload",
        files={"file": ("resume.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Project has reached the 200 document limit."}


@pytest.mark.asyncio
async def test_upload_returns_504_on_timeout(
    client: httpx.AsyncClient,
    api_state: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_id = await create_project(client)
    monkeypatch.setattr(api_state.docs.config, "UPLOAD_TIMEOUT_SECONDS", 0)

    response = await client.post(
        f"/projects/{project_id}/upload",
        files={"file": ("resume.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 504
    assert response.json() == {
        "detail": "Upload timed out. Google API did not respond within 90 seconds."
    }


@pytest.mark.asyncio
async def test_upload_returns_500_when_summary_generation_fails(
    client: httpx.AsyncClient,
    api_state: SimpleNamespace,
) -> None:
    project_id = await create_project(client)
    api_state.docs.rag_service.raise_on_generate_summary = RuntimeError("boom")

    response = await client.post(
        f"/projects/{project_id}/upload",
        files={"file": ("resume.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Upload failed: boom"}
    assert api_state.docs.rag_service.upload_document_pair_calls == []


@pytest.mark.asyncio
async def test_successful_upload_persists_doc_and_returns_contract_shape(
    client: httpx.AsyncClient,
    api_state: SimpleNamespace,
) -> None:
    project_id = await create_project(client)

    response = await client.post(
        f"/projects/{project_id}/upload",
        files={"file": ("resume.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["display_name"] == "resume"
    assert body["status"] == "indexed"
    docs_response = await client.get(f"/projects/{project_id}/docs")
    assert docs_response.status_code == 200
    assert len(docs_response.json()["docs"]) == 1


@pytest.mark.asyncio
async def test_delete_document_removes_original_and_summary(
    client: httpx.AsyncClient, api_state: SimpleNamespace
) -> None:
    project_id = await create_project(client)
    upload = await client.post(
        f"/projects/{project_id}/upload",
        files={"file": ("resume.txt", b"hello", "text/plain")},
    )
    doc_id = upload.json()["doc_id"]

    response = await client.delete(f"/projects/{project_id}/docs/{doc_id}")

    assert response.status_code == 200
    assert response.json() == {
        "message": "Document deleted successfully",
        "doc_id": doc_id,
    }
    assert api_state.docs.rag_service.deleted_doc_names == [
        "fileSearchStores/demo/documents/original",
        "fileSearchStores/demo/documents/summary",
    ]


@pytest.mark.asyncio
async def test_query_route_returns_contract_shape(
    client: httpx.AsyncClient,
    api_state: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_id = await create_project(client)
    times = iter([100.0, 100.25, 100.25, 100.25])
    monkeypatch.setattr(docs_module.time, "perf_counter", lambda: next(times))

    response = await client.post(
        f"/projects/{project_id}/query",
        json={"question": "What is in the doc?", "model": "gemini-2.5-flash"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "answer": "Answer",
        "sources": [
            {
                "doc_name": "Resume",
                "chunk_text": "Grounded text",
                "relevance_score": None,
            }
        ],
        "model_used": "gemini-2.5-flash",
        "project_id": project_id,
        "latency_ms": body["latency_ms"],
    }
    assert isinstance(body["latency_ms"], int)
    assert body["latency_ms"] >= 0
    assert api_state.docs.rag_service.query_calls == [
        {
            "store_name": "fileSearchStores/demo",
            "question": "What is in the doc?",
            "model": "gemini-2.5-flash",
        }
    ]


@pytest.mark.asyncio
async def test_query_rejects_blank_question(client: httpx.AsyncClient) -> None:
    project_id = await create_project(client)

    response = await client.post(
        f"/projects/{project_id}/query",
        json={"question": "   ", "model": "gemini-2.5-flash"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Question cannot be empty"}
