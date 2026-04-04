from __future__ import annotations

from scout.core import Document

E2E_TIMEOUT_MS = 1200


def assert_http_ok(doc: Document) -> None:
    assert doc.metadata.get("status") == 200


def assert_has_main_document_request(doc: Document) -> None:
    assert len(doc.requests) >= 1
