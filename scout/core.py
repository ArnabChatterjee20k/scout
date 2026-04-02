from dataclasses import dataclass
from typing import Optional, Literal


@dataclass
class Response:
    headers: dict
    body: dict
    response_code: int


@dataclass
class Request:
    url: str
    headers: dict
    response: list[Response]


@dataclass
class Session:
    """Mainly the cookies, storage, etc"""

    pass


@dataclass
class Result:
    request: list[Request]


@dataclass
class Metadata:
    title: str
    url: str
    status: int
    headers: dict
    cookies: list[dict]
    storage: dict


@dataclass
class Document:
    url: str
    html: str
    metadata: dict
    markdown: Optional[str]
    screenshots: list[bytes]

    def to_markdown(self):
        pass

    def extract(self):
        pass

    def extract_with_llm(self):
        pass

    def interact(self):
        pass


SELECTOR_KIND = Literal["css", "xpath", "text", "url", "load_state", "tag"]


@dataclass(frozen=True)
class Selector:
    """
    A generic “thing to match / wait on”.

    Examples:
    - Selector(kind="css", value="button:has-text('Accept')")
    - Selector(kind="xpath", value="//button[contains(., 'Accept')]")
    - Selector(kind="text", value="Sign in")
    - Selector(kind="url", value="**/checkout")
    - Selector(kind="load_state", value="networkidle")
    - Selector(kind="state", value="dom_stable")  # engine-defined state
    """

    kind: SELECTOR_KIND
    value: str


ACTION_TYPE = Literal[
    # Navigation / page control
    "goto",
    "back",
    "forward",
    "reload",
    # Interaction
    "click",
    "type",
    "press",
    "hover",
    "scroll",
    # Extraction / capture
    "screenshot",
    "run_js_code",
]


@dataclass
class Action:
    kind: ACTION_TYPE
    selector: Optional[Selector]
    value: Optional[str]
    timeout: Optional[int] = 30000
    wait_for_load_state: Optional[
        Literal["load", "domcontentloaded", "networkidle"]
    ] = None
