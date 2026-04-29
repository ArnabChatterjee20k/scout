from lxml import etree
from lxml import html as lxml_html
from .core import EXTRACTION_SELECTOR_KIND


class HTMLParser:
    def __init__(self, html: str):
        self._tree = lxml_html.fromstring(html)

    def _extract(self, elements, attr: str | None = None):
        results = []

        for el in elements:
            if isinstance(el, etree._Element):
                if attr:
                    results.append(el.get(attr))
                else:
                    results.append(el.text_content().strip())
            else:
                results.append(str(el).strip())

        return results

    def from_css(self, selector: str, attr: str | None = None):
        elements = self._tree.cssselect(selector)
        return self._extract(elements, attr)

    def from_xpath(self, xpath: str, attr: str | None = None):
        elements = self._tree.xpath(xpath)
        return self._extract(elements, attr)

    def from_tag(self, tag: str, attr: str | None = None):
        elements = self._tree.findall(f".//{tag}")
        return self._extract(elements, attr)

    def from_text(self, text: str):
        elements = self._tree.xpath(f"//*[contains(text(), '{text}')]")
        return self._extract(elements)

    def get(self, kind: EXTRACTION_SELECTOR_KIND, value: str, attr: str | None = None):
        if kind == "css":
            return self.from_css(value, attr)
        elif kind == "xpath":
            return self.from_xpath(value, attr)
        elif kind == "tag":
            return self.from_tag(value, attr)
        elif kind == "text":
            return self.from_text(value)
        else:
            raise ValueError(f"Unsupported selector kind: {kind}")

    def remove_tags(self, tags: list[str]) -> str:
        for tag in tags:
            for el in self._tree.findall(f".//{tag}"):
                el.drop_tree()

        return lxml_html.tostring(self._tree, encoding="unicode", pretty_print=True)
