from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("GEMINI_API_KEY", "test-key")

from src.services.rag_service import (
    RagService,
    RagServiceError,
    RagSummaryError,
    RagUploadTimeoutError,
)


class FakeOperation:
    def __init__(self, done: bool) -> None:
        self.done = done


class FakeOperations:
    def __init__(self, operations: list[FakeOperation]) -> None:
        self.operations = operations
        self.calls = 0

    def get(self, _operation: FakeOperation) -> FakeOperation:
        operation = self.operations[self.calls]
        self.calls += 1
        return operation


class FakeDocumentAPI:
    def __init__(self, documents: list[SimpleNamespace]) -> None:
        self.documents = documents
        self.deleted: list[dict[str, object]] = []

    def list(self, parent: str) -> list[SimpleNamespace]:
        self.last_parent = parent
        return self.documents

    def delete(self, *, name: str, config: dict[str, object]) -> None:
        self.deleted.append({"name": name, "config": config})


class FakeFileSearchStores:
    def __init__(
        self,
        *,
        store: SimpleNamespace | None = None,
        documents: list[SimpleNamespace] | None = None,
        operation: FakeOperation | None = None,
    ) -> None:
        self.store = store or SimpleNamespace(
            name="fileSearchStores/demo", display_name="Demo"
        )
        self.documents = FakeDocumentAPI(documents or [])
        self.operation = operation or FakeOperation(done=True)
        self.upload_calls: list[dict[str, object]] = []
        self.deleted: list[str] = []

    def create(self, *, config: dict[str, object]) -> SimpleNamespace:
        self.last_create_config = config
        return self.store

    def delete(self, *, name: str) -> None:
        self.deleted.append(name)

    def upload_to_file_search_store(
        self,
        *,
        file: str,
        file_search_store_name: str,
        config: dict[str, object],
    ) -> FakeOperation:
        self.upload_calls.append(
            {
                "file": file,
                "file_search_store_name": file_search_store_name,
                "config": config,
            }
        )
        return self.operation


class FakeModels:
    def __init__(self, response: SimpleNamespace) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def make_client(
    *,
    create_store: SimpleNamespace | None = None,
    documents: list[SimpleNamespace] | None = None,
    operation: FakeOperation | None = None,
    follow_up_operations: list[FakeOperation] | None = None,
    model_response: SimpleNamespace | None = None,
):
    file_search_stores = FakeFileSearchStores(
        store=create_store,
        documents=documents,
        operation=operation,
    )
    operations = FakeOperations(follow_up_operations or [])
    models = FakeModels(model_response or SimpleNamespace(text="ok", candidates=[]))
    return SimpleNamespace(
        file_search_stores=file_search_stores,
        operations=operations,
        models=models,
    )


def test_create_store_uses_display_name() -> None:
    client = make_client()
    service = RagService(client=client)

    result = service.create_store("Architect Agent")

    assert client.file_search_stores.last_create_config == {
        "display_name": "Architect Agent"
    }
    assert result["name"] == "fileSearchStores/demo"


def test_delete_store_forwards_name() -> None:
    client = make_client()
    service = RagService(client=client)

    service.delete_store("fileSearchStores/demo")

    assert client.file_search_stores.deleted == ["fileSearchStores/demo"]


def test_list_documents_returns_plain_dicts() -> None:
    documents = [
        SimpleNamespace(name="doc-1", display_name="Resume"),
        SimpleNamespace(name="doc-2", display_name="Summary"),
    ]
    client = make_client(documents=documents)
    service = RagService(client=client)

    result = service.list_documents("fileSearchStores/demo")

    assert result == [
        {"name": "doc-1", "display_name": "Resume"},
        {"name": "doc-2", "display_name": "Summary"},
    ]


def test_generate_summary_uses_pdf_part_and_prompt() -> None:
    response = SimpleNamespace(text="Structured summary", candidates=[])
    client = make_client(model_response=response)
    service = RagService(client=client)

    result = service.generate_summary(
        file_bytes=b"pdf-bytes",
        mime_type="application/pdf",
        prompt="Prompt",
    )

    assert result == "Structured summary"
    call = client.models.calls[0]
    assert call["model"] == "gemini-2.5-flash"
    assert call["contents"][1] == "Prompt"


def test_upload_document_pair_uploads_original_and_summary(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "uploads").mkdir()
    original = tmp_path / "resume.pdf"
    original.write_bytes(b"pdf")

    documents = [
        SimpleNamespace(name="doc-original", display_name="resume"),
        SimpleNamespace(name="doc-summary", display_name="resume_SUMMARY"),
    ]
    client = make_client(documents=documents)
    service = RagService(client=client)

    result = service.upload_document_pair(
        store_name="fileSearchStores/demo",
        original_path=original,
        display_name="resume",
        summary_text="summary text",
        summary_filename="resume_SUMMARY.txt",
    )

    assert len(client.file_search_stores.upload_calls) == 2
    assert result == {
        "store_doc_name": "doc-original",
        "summary_doc_name": "doc-summary",
    }
    assert (tmp_path / "uploads" / "resume_SUMMARY.txt").read_text(encoding="utf-8") == "summary text"


def test_upload_document_pair_can_fallback_when_summary_missing(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "uploads").mkdir()
    original = tmp_path / "resume.pdf"
    original.write_bytes(b"pdf")

    documents = [SimpleNamespace(name="doc-original", display_name="resume")]
    client = make_client(documents=documents)
    service = RagService(client=client)
    monkeypatch.setattr("src.services.rag_service.SUMMARY_REQUIRED", False)

    result = service.upload_document_pair(
        store_name="fileSearchStores/demo",
        original_path=original,
        display_name="resume",
        summary_text=None,
        summary_filename="resume_SUMMARY.txt",
    )

    assert len(client.file_search_stores.upload_calls) == 1
    assert result["summary_doc_name"] == ""


def test_upload_document_pair_raises_when_summary_required_missing(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "uploads").mkdir()
    original = tmp_path / "resume.pdf"
    original.write_bytes(b"pdf")

    service = RagService(client=make_client())
    monkeypatch.setattr("src.services.rag_service.SUMMARY_REQUIRED", True)

    with pytest.raises(RagSummaryError, match="SUMMARY_REQUIRED=true"):
        service.upload_document_pair(
            store_name="fileSearchStores/demo",
            original_path=original,
            display_name="resume",
            summary_text=None,
            summary_filename="resume_SUMMARY.txt",
        )


def test_upload_uses_shared_timeout_budget(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "uploads").mkdir()
    original = tmp_path / "resume.pdf"
    original.write_bytes(b"pdf")

    operation = FakeOperation(done=False)
    follow_up = [FakeOperation(done=False)]
    documents = [SimpleNamespace(name="doc-original", display_name="resume")]
    client = make_client(
        documents=documents,
        operation=operation,
        follow_up_operations=follow_up,
    )
    service = RagService(client=client)

    time_values = iter([100.0, 189.0, 191.0])
    monkeypatch.setattr("src.services.rag_service.time.perf_counter", lambda: next(time_values))
    monkeypatch.setattr("src.services.rag_service.time.sleep", lambda _seconds: None)

    with pytest.raises(
        RagUploadTimeoutError,
        match="Upload timed out. Google API did not respond within 90 seconds.",
    ):
        service.upload_document_pair(
            store_name="fileSearchStores/demo",
            original_path=original,
            display_name="resume",
            summary_text="summary text",
            summary_filename="resume_SUMMARY.txt",
        )


def test_delete_document_uses_force_flag() -> None:
    client = make_client()
    service = RagService(client=client)

    service.delete_document("fileSearchStores/demo/documents/doc-1")

    assert client.file_search_stores.documents.deleted == [
        {
            "name": "fileSearchStores/demo/documents/doc-1",
            "config": {"force": True},
        }
    ]


def test_query_store_returns_answer_and_sources() -> None:
    metadata = SimpleNamespace(
        grounding_chunks=[
            SimpleNamespace(retrieved_context=SimpleNamespace(title="Resume")),
        ],
        grounding_supports=[
            SimpleNamespace(
                grounding_chunk_indices=[0],
                segment=SimpleNamespace(text="Moose worked on RAG systems."),
            )
        ],
    )
    response = SimpleNamespace(
        text="Answer",
        candidates=[SimpleNamespace(grounding_metadata=metadata)],
    )
    client = make_client(model_response=response)
    service = RagService(client=client)

    result = service.query_store(
        store_name="fileSearchStores/demo",
        question="What did Moose work on?",
    )

    assert result["answer"] == "Answer"
    assert result["sources"] == [
        {
            "doc_name": "Resume",
            "chunk_text": "Moose worked on RAG systems.",
            "relevance_score": None,
        }
    ]
    call = client.models.calls[0]
    assert call["contents"] == "What did Moose work on?"


def test_query_store_handles_missing_grounding_metadata() -> None:
    response = SimpleNamespace(text="Answer", candidates=[SimpleNamespace()])
    client = make_client(model_response=response)
    service = RagService(client=client)

    result = service.query_store(
        store_name="fileSearchStores/demo",
        question="Question",
    )

    assert result == {"answer": "Answer", "sources": []}


def test_upload_raises_if_indexed_document_not_found(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "uploads").mkdir()
    original = tmp_path / "resume.pdf"
    original.write_bytes(b"pdf")

    client = make_client(documents=[])
    service = RagService(client=client)
    monkeypatch.setattr("src.services.rag_service.SUMMARY_REQUIRED", False)

    with pytest.raises(RagServiceError, match="Uploaded document 'resume' not found"):
        service.upload_document_pair(
            store_name="fileSearchStores/demo",
            original_path=original,
            display_name="resume",
            summary_text=None,
            summary_filename="resume_SUMMARY.txt",
        )
