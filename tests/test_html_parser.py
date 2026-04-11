"""Unit tests for :mod:`scout.html_parser`."""

from __future__ import annotations

import pytest

from scout.html_parser import HTMLParser

SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head><title>T</title></head>
<body>
  <div id="root">
    <h1 class="title">Hello World</h1>
    <p data-role="note">First paragraph</p>
    <a href="https://example.com/page">Link text</a>
    <span>UniqueMarker</span>
  </div>
</body>
</html>
"""


@pytest.fixture
def parser() -> HTMLParser:
    return HTMLParser(SAMPLE_HTML)


class TestHTMLParserFromCss:
    def test_selects_text_content(self, parser: HTMLParser) -> None:
        assert parser.from_css("h1.title") == ["Hello World"]

    def test_multiple_matches(self, parser: HTMLParser) -> None:
        texts = parser.from_css("div#root p, div#root span")
        assert "First paragraph" in texts
        assert "UniqueMarker" in texts

    def test_no_match_returns_empty_list(self, parser: HTMLParser) -> None:
        assert parser.from_css(".nonexistent") == []

    def test_attr_href(self, parser: HTMLParser) -> None:
        assert parser.from_css("a", attr="href") == ["https://example.com/page"]

    def test_attr_missing_returns_none_in_list(self, parser: HTMLParser) -> None:
        assert parser.from_css("h1", attr="data-missing") == [None]


class TestHTMLParserFromXpath:
    def test_xpath_text(self, parser: HTMLParser) -> None:
        assert parser.from_xpath("//h1") == ["Hello World"]

    def test_attr(self, parser: HTMLParser) -> None:
        assert parser.from_xpath("//p/@data-role") == ["note"]


class TestHTMLParserFromTag:
    def test_find_by_tag(self, parser: HTMLParser) -> None:
        titles = parser.from_tag("h1")
        assert titles == ["Hello World"]


class TestHTMLParserFromText:
    def test_contains_text(self, parser: HTMLParser) -> None:
        out = parser.from_text("UniqueMarker")
        assert len(out) >= 1
        assert any("UniqueMarker" in x for x in out)


class TestHTMLParserGet:
    def test_css_kind(self, parser: HTMLParser) -> None:
        assert parser.get("css", "h1", None) == ["Hello World"]

    def test_xpath_kind(self, parser: HTMLParser) -> None:
        assert parser.get("xpath", "//a", None) == ["Link text"]

    def test_tag_kind(self, parser: HTMLParser) -> None:
        assert parser.get("tag", "h1", None) == ["Hello World"]

    def test_text_kind(self, parser: HTMLParser) -> None:
        out = parser.get("text", "First paragraph", None)
        assert out and "First paragraph" in out[0]

    def test_unsupported_kind_raises(self, parser: HTMLParser) -> None:
        with pytest.raises(ValueError, match="Unsupported selector kind"):
            parser.get("load_state", "x", None)  # type: ignore[arg-type]


class TestHTMLParserEmptyDocument:
    def test_empty_html(self) -> None:
        p = HTMLParser("<html><body></body></html>")
        assert p.from_css("h1") == []
