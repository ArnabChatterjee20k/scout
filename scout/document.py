from dataclasses import dataclass
from typing import Optional

@dataclass
class Document:
    url: str
    html: str
    markdown: Optional[str]

    def to_markdown(self):
        pass

    def extract(self):
        pass

    def extract_with_llm(self):
        pass