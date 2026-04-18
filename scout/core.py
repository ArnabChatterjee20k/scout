from dataclasses import dataclass, field
from typing import (
    Optional,
    Literal,
    Callable,
    Any,
    Awaitable,
    Type,
    TypeVar,
    Union,
    Pattern,
)
from playwright.async_api import Request, Response
from html_to_markdown import convert
from pydantic import BaseModel


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
Handler = Callable[[T], Union[Any, Awaitable[Any]]]


@dataclass
class NetworkRule:
    match_url: Optional[Union[str, Pattern[str]]] = None
    on_request: Optional[Handler[Request]] = None
    on_response: Optional[Handler[Response]] = None
    log_request: bool = False
    log_response: bool = False

    def is_matching(self, target: Optional[Union[str, Pattern[str]]]) -> bool:
        if self.match_url is None:
            return True

        if isinstance(self.match_url, str):
            return self.match_url == target

        return bool(self.match_url.search(target))


@dataclass
class VirtualScrollConfig:
    """
    Configuration for container-based virtualized scrolling (e.g. feed UIs).
    """

    container_selector: str
    scroll_count: int = 20
    wait_after_scroll: float = 0.25
    scroll_by: Union[int, Literal["page_height", "container_height"]] = (
        "container_height"
    )
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "container_selector": self.container_selector,
            "scroll_count": self.scroll_count,
            "wait_after_scroll": self.wait_after_scroll,
            "scroll_by": self.scroll_by,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "VirtualScrollConfig":
        return cls(
            container_selector=value["container_selector"],
            scroll_count=int(value.get("scroll_count", 20)),
            wait_after_scroll=float(value.get("wait_after_scroll", 0.25)),
            scroll_by=value.get("scroll_by", "container_height"),
            enabled=bool(value.get("enabled", True)),
        )


@dataclass
class ScrollingRule:
    """
    Optional scrolling behavior to help load dynamic content before extraction.

    If `full_page_scan` is True, the adapter performs a viewport-step scroll down
    (optionally capped) before extracting page HTML.
    """

    full_page_scan: bool = False
    scroll_delay: float = 0.1
    # Use an explicit cap by default to avoid hangs on infinite-scroll pages.
    # Set to None for unlimited scrolling.
    max_scroll_steps: Optional[int] = 10
    virtual_scroll: Optional[Union[VirtualScrollConfig, dict[str, Any]]] = None

    def __post_init__(self) -> None:
        if isinstance(self.virtual_scroll, dict):
            self.virtual_scroll = VirtualScrollConfig.from_dict(self.virtual_scroll)


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
        self.markdown = convert(self.html)["content"]
        return self.markdown

    def extract(self, schema: list[ExtractionSchema]) -> list[ExtractionResult]:
        from .html_parser import HTMLParser

        parser = HTMLParser(self.html)
        result: list[ExtractionResult] = []
        for extraction_schema in schema:
            value = parser.get(
                kind=extraction_schema.selector.kind,
                value=extraction_schema.selector.value,
                attr=extraction_schema.attr,
            )
            result.append(
                ExtractionResult(
                    field=extraction_schema.field,
                    selector=extraction_schema.selector,
                    attr=extraction_schema.attr,
                    value=value,
                )
            )
        return result

    async def extract_with_agent(self, query: str, schema: Type[BaseModel]):
        from .agents.extraction_agent import extract

        md = self.markdown
        if md is None:
            md = self.to_markdown()
        return await extract(md, schema, query)


SELECTOR_KIND = Literal["css", "xpath", "text", "url", "load_state", "tag"]
EXTRACTION_SELECTOR_KIND = Literal["css", "xpath", "text", "tag"]


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


@dataclass(frozen=True)
class ExtractionSelector:
    kind: EXTRACTION_SELECTOR_KIND
    value: str


@dataclass(frozen=True)
class ExtractionSchema:
    field: str
    selector: ExtractionSelector
    attr: Optional[str] = None


@dataclass(frozen=True, kw_only=True)
class ExtractionResult(ExtractionSchema):
    """Result of :meth:`Document.extract`; ``value`` holds parser output (e.g. list of strings)."""

    value: Any


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
    # (result, page_url) after a successful execute(); may return an awaitable.
    on_complete: Optional[Callable[[Any, str], Any]] = None
    # (error, page_url) when execute() raises; may return an awaitable. Errors are still logged.
    on_error: Optional[Callable[[BaseException, str], Any]] = None


@dataclass
class Include:
    actions: list[Action] = field(default_factory=list)
    pattern: Optional[Union[str, Pattern[str]]] = None


@dataclass
class CrawlConfig:
    include: Optional[list[Union[Include, dict, str, Pattern[str]]]] = field(
        default_factory=list
    )
    exclude: Optional[list[Union[str, Pattern[str]]]] = field(default_factory=list)
    page_limit: int = 5
    max_depth: int = 10
    concurrency: int = 1
    page_transition_delay: int = 0
    scrolling: Optional[ScrollingRule] = None

    # just for caching the included list post init
    _normalized_include: list["Include"] = field(
        init=False, repr=False, default_factory=list
    )

    def __post_init__(self):
        self._normalized_include = [
            self._normalize_include(i) for i in (self.include or [])
        ]

    def _normalize_include(
        self, value: Union[Include, dict, str, Pattern[str]]
    ) -> "Include":
        if isinstance(value, Include):
            return value
        if isinstance(value, str):
            return Include(pattern=value)
        # regex
        if hasattr(value, "search"):
            return Include(pattern=value)
        return Include(**value)

    def is_included(self, target: str):
        for exclude in self.exclude:
            if isinstance(exclude, str) and exclude == target:
                return False

            if hasattr(exclude, "search") and exclude.search(target):
                return False

        if not self._normalized_include:
            return True

        for include in self._normalized_include:
            pattern = include.pattern

            if isinstance(pattern, str) and pattern == target:
                return True

            if hasattr(pattern, "search") and pattern.search(target):
                return True

        return False
