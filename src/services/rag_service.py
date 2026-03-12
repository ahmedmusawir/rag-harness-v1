from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

from src.services.config_service import (
    GEMINI_API_KEY,
    SUMMARY_REQUIRED,
    UPLOAD_TIMEOUT_SECONDS,
)
from src.services.logging_service import get_logger

SUMMARY_PROMPT = """
Analyze this document and create a STRUCTURED SUMMARY:

1. DOCUMENT TYPE: (What kind of document is this?)

2. MAIN TOPICS: (What are the 3-5 key topics covered?)

3. KEY ENTITIES - LIST ALL:
   - People mentioned (full names)
   - Companies/organizations
   - Products/platforms/tools
   - Dates, numbers, metrics

4. COMPLETE FACT LIST:
   - List the important facts explicitly

5. SEARCH OPTIMIZED TERMS:
   - Keywords, synonyms, acronyms, alternate phrasings

Be EXHAUSTIVE. This summary will be uploaded beside the original
document to improve retrieval for counting, listing, and aggregation questions.
""".strip()

logger = get_logger(__name__)


class RagServiceError(Exception):
    """Base exception for RAG service failures."""


class RagUploadTimeoutError(RagServiceError):
    """Raised when Google indexing exceeds the shared upload budget."""


class RagSummaryError(RagServiceError):
    """Raised when summary generation fails and fallback is disabled."""


class RagService:
    def __init__(self, client: Any | None = None) -> None:
        self._client = client

    @property
    def client(self) -> Any:
        if self._client is None:
            self._client = genai.Client(api_key=GEMINI_API_KEY)
        return self._client

    def create_store(self, display_name: str) -> dict[str, str]:
        store = self.client.file_search_stores.create(
            config={"display_name": display_name}
        )
        logger.info("created store display_name=%s store_id=%s", display_name, store.name)
        return {
            "name": store.name,
            "display_name": getattr(store, "display_name", display_name),
        }

    def delete_store(self, store_name: str) -> None:
        self.client.file_search_stores.delete(name=store_name)
        logger.info("deleted store store_id=%s", store_name)

    def list_documents(self, store_name: str) -> list[dict[str, str]]:
        documents = list(self.client.file_search_stores.documents.list(parent=store_name))
        return [
            {
                "name": doc.name,
                "display_name": getattr(doc, "display_name", ""),
            }
            for doc in documents
        ]

    def get_store_details(self, store_name: str) -> dict[str, Any]:
        store = self.client.file_search_stores.get(name=store_name)
        return {
            "name": getattr(store, "name", store_name),
            "display_name": getattr(store, "display_name", ""),
            "raw": self._to_jsonable(store),
        }

    def verify_stores(self) -> list[dict[str, Any]]:
        stores = list(self.client.file_search_stores.list())
        verified: list[dict[str, Any]] = []
        for store in stores:
            documents = list(self.client.file_search_stores.documents.list(parent=store.name))
            verified.append(
                {
                    "name": getattr(store, "name", ""),
                    "display_name": getattr(store, "display_name", ""),
                    "document_count": len(documents),
                }
            )
        return verified

    def get_document_details(self, document_name: str) -> dict[str, Any]:
        document = self.client.file_search_stores.documents.get(name=document_name)
        return {
            "name": getattr(document, "name", document_name),
            "display_name": getattr(document, "display_name", ""),
            "raw": self._to_jsonable(document),
        }

    def get_operation_status(self, operation_name: str) -> dict[str, Any]:
        operation = types.UploadToFileSearchStoreOperation(name=operation_name)
        refreshed = self.client.operations.get(operation)
        return {
            "name": getattr(refreshed, "name", operation_name),
            "done": getattr(refreshed, "done", None),
            "metadata": self._to_jsonable(getattr(refreshed, "metadata", None)),
            "error": self._to_jsonable(getattr(refreshed, "error", None)),
        }

    def generate_summary(
        self,
        *,
        file_bytes: bytes,
        mime_type: str,
        prompt: str = SUMMARY_PROMPT,
        model: str = "gemini-2.5-flash",
    ) -> str:
        response = self.client.models.generate_content(
            model=model,
            contents=[
                types.Part.from_bytes(data=file_bytes, mime_type=mime_type),
                prompt,
            ],
        )
        logger.info("generated summary mime_type=%s model=%s", mime_type, model)
        return response.text

    def upload_document_pair(
        self,
        *,
        store_name: str,
        original_path: str | Path,
        display_name: str,
        summary_text: str | None,
        summary_filename: str,
    ) -> dict[str, str]:
        if summary_text is None:
            if SUMMARY_REQUIRED:
                raise RagSummaryError(
                    "Summary generation failed and SUMMARY_REQUIRED=true."
                )
            logger.warning(
                "Summary generation unavailable; falling back to original-only upload."
            )

        start = time.perf_counter()
        original_doc = self._upload_and_wait(
            file_path=original_path,
            store_name=store_name,
            display_name=display_name,
            deadline=self._deadline_from_start(start),
        )

        summary_doc_name = ""
        if summary_text is not None:
            summary_path = self._write_summary_file(summary_text, summary_filename)
            summary_doc = self._upload_and_wait(
                file_path=summary_path,
                store_name=store_name,
                display_name=Path(summary_filename).stem,
                deadline=self._deadline_from_start(start),
            )
            summary_doc_name = summary_doc["name"]

        return {
            "store_doc_name": original_doc["name"],
            "summary_doc_name": summary_doc_name,
        }

    def cleanup_store(self, store_name: str) -> list[dict[str, str]]:
        documents = self.list_documents(store_name)
        for document in documents:
            self.delete_document(document["name"])
        logger.warning(
            "cleanup store executed store_id=%s deleted_count=%s",
            store_name,
            len(documents),
        )
        return documents

    def delete_document(self, doc_name: str) -> None:
        self.client.file_search_stores.documents.delete(
            name=doc_name,
            config={"force": True},
        )
        logger.info("deleted document resource_name=%s", doc_name)

    def query_store(
        self,
        *,
        store_name: str,
        question: str,
        model: str = "gemini-2.5-flash",
    ) -> dict[str, Any]:
        response = self.client.models.generate_content(
            model=model,
            contents=question,
            config=types.GenerateContentConfig(
                tools=[
                    types.Tool(
                        file_search=types.FileSearch(
                            file_search_store_names=[store_name]
                        )
                    )
                ]
            ),
        )
        logger.info("query executed store_id=%s model=%s", store_name, model)
        return {
            "answer": response.text,
            "sources": self._parse_grounding_metadata(response),
        }

    def _upload_and_wait(
        self,
        *,
        file_path: str | Path,
        store_name: str,
        display_name: str,
        deadline: float,
    ) -> dict[str, str]:
        operation = self.client.file_search_stores.upload_to_file_search_store(
            file=str(file_path),
            file_search_store_name=store_name,
            config={"display_name": display_name},
        )

        while not operation.done:
            if time.perf_counter() >= deadline:
                raise RagUploadTimeoutError(
                    "Upload timed out. Google API did not respond within 90 seconds."
                )
            time.sleep(1)
            operation = self.client.operations.get(operation)

        documents = list(self.client.file_search_stores.documents.list(parent=store_name))
        for document in documents:
            if getattr(document, "display_name", "") == display_name:
                return {
                    "name": document.name,
                    "display_name": document.display_name,
                }

        raise RagServiceError(f"Uploaded document '{display_name}' not found in store.")

    def _deadline_from_start(self, start: float) -> float:
        return start + UPLOAD_TIMEOUT_SECONDS

    def _write_summary_file(self, summary_text: str, summary_filename: str) -> Path:
        summary_path = Path("uploads") / summary_filename
        summary_path.write_text(summary_text, encoding="utf-8")
        return summary_path

    def _parse_grounding_metadata(self, response: Any) -> list[dict[str, str]]:
        try:
            candidate = response.candidates[0]
        except (AttributeError, IndexError, TypeError):
            return []

        metadata = getattr(candidate, "grounding_metadata", None)
        if metadata is None:
            return []

        chunks = getattr(metadata, "grounding_chunks", None) or []
        supports = getattr(metadata, "grounding_supports", None) or []

        support_by_chunk: dict[int, list[str]] = {}
        for support in supports:
            indices = getattr(support, "grounding_chunk_indices", None) or []
            text = getattr(getattr(support, "segment", None), "text", "") or ""
            for index in indices:
                if text:
                    support_by_chunk.setdefault(index, []).append(text)

        sources: list[dict[str, str]] = []
        for index, chunk in enumerate(chunks):
            web_info = getattr(chunk, "web", None)
            retrieved_context = getattr(chunk, "retrieved_context", None)
            title = (
                getattr(retrieved_context, "title", None)
                or getattr(web_info, "title", None)
                or "Unknown source"
            )
            snippets = support_by_chunk.get(index, [])
            sources.append(
                {
                    "doc_name": title,
                    "chunk_text": snippets[0] if snippets else "",
                    "relevance_score": None,
                }
            )
        return sources

    def _to_jsonable(self, value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, list):
            return [self._to_jsonable(item) for item in value]
        if isinstance(value, dict):
            return {str(key): self._to_jsonable(item) for key, item in value.items()}
        if hasattr(value, "model_dump"):
            return self._to_jsonable(value.model_dump())
        if hasattr(value, "__dict__"):
            return {
                key: self._to_jsonable(item)
                for key, item in vars(value).items()
                if not key.startswith("_")
            }
        return str(value)


rag_service = RagService()
