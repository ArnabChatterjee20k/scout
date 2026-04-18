"""Unit tests for :class:`scout.core.Document` extraction and markdown."""

from __future__ import annotations

import re
from unittest.mock import patch

from scout.core import (
    CrawlConfig,
    Document,
    ExtractionSchema,
    ExtractionSelector,
    Include,
)


def _minimal_document(html: str) -> Document:
    return Document(
        url="https://example.test/",
        html=html,
        metadata={},
        markdown=None,
        screenshots=[],
        requests=[],
        response=[],
    )


class TestDocumentExtract:
    def test_css_extracts_text(self) -> None:
        doc = _minimal_document("<html><body><h1>Hi</h1></body></html>")
        schema = [
            ExtractionSchema(
                field="heading",
                selector=ExtractionSelector(kind="css", value="h1"),
                attr=None,
            )
        ]
        results = doc.extract(schema)
        assert len(results) == 1
        assert results[0].field == "heading"
        assert results[0].value == ["Hi"]

    def test_multiple_schemas(self) -> None:
        doc = _minimal_document(
            "<html><body><h1>T</h1><p class='x'>Body</p></body></html>"
        )
        schema = [
            ExtractionSchema(
                field="h",
                selector=ExtractionSelector(kind="css", value="h1"),
                attr=None,
            ),
            ExtractionSchema(
                field="p",
                selector=ExtractionSelector(kind="css", value="p.x"),
                attr=None,
            ),
        ]
        results = doc.extract(schema)
        assert [r.field for r in results] == ["h", "p"]
        assert results[0].value == ["T"]
        assert results[1].value == ["Body"]

    def test_attr_extraction(self) -> None:
        doc = _minimal_document(
            '<html><body><a id="l" href="https://a.test">go</a></body></html>'
        )
        schema = [
            ExtractionSchema(
                field="link",
                selector=ExtractionSelector(kind="css", value="a#l"),
                attr="href",
            )
        ]
        results = doc.extract(schema)
        assert results[0].value == ["https://a.test"]

    def test_empty_schema(self) -> None:
        doc = _minimal_document("<html><body></body></html>")
        assert doc.extract([]) == []

    def test_xpath_kind(self) -> None:
        doc = _minimal_document("<html><body><span>xx</span></body></html>")
        schema = [
            ExtractionSchema(
                field="s",
                selector=ExtractionSelector(kind="xpath", value="//span"),
                attr=None,
            )
        ]
        assert doc.extract(schema)[0].value == ["xx"]


class TestDocumentToMarkdown:
    def test_to_markdown_sets_and_returns_content(self) -> None:
        doc = _minimal_document("<html><body><p>Hello</p></body></html>")
        with patch("scout.core.convert") as mock_convert:
            mock_convert.return_value = {"content": "# md\n"}
            md = doc.to_markdown()
        assert md == "# md\n"
        assert doc.markdown == "# md\n"
        mock_convert.assert_called_once_with(doc.html)


class TestCrawlConfig:
    def test_includes_everything_when_include_list_is_empty(self) -> None:
        config = CrawlConfig()
        assert config.is_included("https://example.test/a")
        assert config.is_included("https://example.test/b")

    def test_exact_string_include_and_exclude(self) -> None:
        target = "https://example.test/keep"
        blocked = "https://example.test/skip"
        config = CrawlConfig(include=[target], exclude=[blocked])

        assert config.is_included(target) is True
        assert config.is_included(blocked) is False

    def test_regex_include_and_exclude(self) -> None:
        config = CrawlConfig(
            include=[re.compile(r"^https://example\.test/blog/")],
            exclude=[re.compile(r"/drafts/")],
        )

        assert config.is_included("https://example.test/blog/post-1") is True
        assert config.is_included("https://example.test/blog/drafts/post-2") is False
        assert config.is_included("https://example.test/docs/page") is False

    def test_supports_include_dataclass_and_dict_forms(self) -> None:
        keep_with_dataclass = Include(pattern="https://example.test/from-dataclass")
        keep_with_dict = {"pattern": "https://example.test/from-dict"}
        config = CrawlConfig(include=[keep_with_dataclass, keep_with_dict])

        assert config.is_included("https://example.test/from-dataclass") is True
        assert config.is_included("https://example.test/from-dict") is True
        assert config.is_included("https://example.test/other") is False
