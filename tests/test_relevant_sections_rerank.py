from __future__ import annotations

from scout.core import Document

CONTENT_HTML = """
<html><body>
  <h2>Networking</h2>
  <p>HTTP server security best practices and TLS termination.</p>
  <p>Completely unrelated cooking recipe about pasta and tomatoes.</p>
</body></html>
"""


def _document(html: str) -> Document:
    return Document(
        url="https://example.test/doc",
        html=html,
        metadata={},
        markdown=None,
        screenshots=[],
        requests=[],
        response=[],
    )


def _keyword_reranker(keywords: list[str]):
    def _rerank(query: str, heading: str, candidates: list[str]) -> list[float]:
        return [
            float(sum(candidate.lower().count(word) for word in keywords))
            for candidate in candidates
        ]

    return _rerank


def test_get_relevant_sections_uses_injected_reranker():
    document = _document(CONTENT_HTML)

    result = document.get_relevant_sections(
        "http server security",
        top_k=5,
        reranker=_keyword_reranker(["http", "server", "security", "tls"]),
    )

    joined = " ".join(result).lower()
    assert "http server" in joined
    assert all(isinstance(chunk, str) for chunk in result)


def test_get_relevant_sections_defaults_to_embedding_path():
    # No reranker and use_laya=False: the method must still run via the default
    # bi-encoder path and return a list (quality is covered in domdistill).
    document = _document(CONTENT_HTML)
    result = document.get_relevant_sections("http server security", top_k=5)
    assert isinstance(result, list)
