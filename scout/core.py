from dataclasses import dataclass
from typing import Optional, Literal, Callable, Any, Awaitable, TypeVar, Union, Pattern
from playwright.async_api import Request, Response
from html_to_markdown import convert

@dataclass
class ResponseModel:
    url: str
    headers: dict
    body: Any
    status: int
    method: str


@dataclass
class RequestModel:
    url: str
    method: str
    headers: dict


@dataclass
class Session:
    """Mainly the cookies, storage, etc"""

    pass

@dataclass
class Result:
    request: list[Request]

T = TypeVar("T")
Handler = Callable[[T],Union[Any, Awaitable[Any]]]
@dataclass
class NetworkRule:
    match_url: Optional[Union[str, Pattern[str]]] = None
    on_request: Optional[Handler[Request]] = None
    on_response: Optional[Handler[Response]] = None
    log_request: bool = False
    log_response: bool = False

    def is_matching(self, target: Optional[Union[str, Pattern[str]]])-> bool:
        if self.match_url is None:
            return True
        
        if isinstance(self.match_url, str):
            return self.match_url == target

        return bool(self.match_url.search(target))


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
    requests: list[RequestModel]
    response: list[ResponseModel]

    def to_markdown(self):
        self.markdown = convert(self.html)['content']
        return self.markdown

    def extract(self):
        pass

    def extract_with_llm(self):
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
