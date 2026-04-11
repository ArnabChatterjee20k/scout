from __future__ import annotations

import asyncio, re, subprocess, json, csv, io
from typing import Any, Dict, List, Literal, Union
from dataclasses import dataclass, field, replace
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError
from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import ModelHTTPError, UsageLimitExceeded
from pydantic_ai.usage import RunUsage, UsageLimits

from ..logger import get_logger
from . import model

agent = Agent(
    model=model,
    retries=4,
    system_prompt=(
        "You automate the browser via tools. Use `browser_tool` for page actions and "
        "`file_tool` to persist extracted data under the configured output directory. "
        "For large extractions or long lists, prefer batch `eval` (JavaScript in the page) over many small steps. "
        "Follow the detailed instructions in the dynamic system prompt."
    ),
)
logger = get_logger("AGENT")


def _default_output_dir() -> Path:
    return Path.cwd() / "scout_agent_output"


@dataclass
class Deps:
    cdp_endpoint: str
    page_snapshot: str
    output_dir: Path = field(default_factory=_default_output_dir)


@dataclass
class BrowserAgentResult:
    """Outcome of a browser agent run: final text plus usage metadata."""

    output: str
    usage: RunUsage | None = None
    run_id: str | None = None
    limit_reached: bool = False


@dataclass
class BrowserAgentConfig:
    """Per-run settings for :func:`execute` and :meth:`Scout.interact`."""

    output_dir: Path | str | None = None
    """Where ``file_tool`` writes. If ``None``, uses :attr:`Deps.output_dir` (default ``scout_agent_output``)."""

    max_model_requests: int | None = None
    """Maximum **model API requests** (LLM turns) this run. ``None`` → :data:`DEFAULT_MAX_MODEL_REQUESTS`. Successful tool calls are **not** capped (``UsageLimits.tool_calls_limit`` is left unset)."""

    model_http_max_retries: int = 5
    """Retries after :class:`~pydantic_ai.exceptions.ModelHTTPError` (e.g. rate limits)."""

    model: Any | None = None
    """Optional pydantic-ai model for this run; ``None`` uses the module agent default."""


DEFAULT_MAX_MODEL_REQUESTS = 1000
"""Default for :attr:`BrowserAgentConfig.max_model_requests` when it is left ``None``."""


def _usage_limits_for_config(cfg: BrowserAgentConfig) -> UsageLimits:
    """Build pydantic-ai limits: only **request** count is capped; ``tool_calls_limit`` is unset (no cap)."""
    cap = cfg.max_model_requests
    if cap is None:
        cap = DEFAULT_MAX_MODEL_REQUESTS
    return UsageLimits(
        request_limit=cap,
        tool_calls_limit=None,
    )


# Default HTTP retries; override per run via :class:`BrowserAgentConfig`.
MAX_MODEL_HTTP_RETRIES = 5
_RETRY_IN_MESSAGE = re.compile(
    r"retry\s+in\s+(\d+(?:\.\d+)?)\s*s",
    re.IGNORECASE,
)


def _parse_duration_seconds(s: str) -> float | None:
    s = s.strip()
    m = re.match(r"^(\d+(?:\.\d+)?)s$", s)
    if m:
        return float(m.group(1))
    return None


def _retry_delay_from_google_body(body: object | None) -> float | None:
    """Read ``google.rpc.RetryInfo.retryDelay`` (e.g. ``45s``) from API error JSON."""
    if body is None or not isinstance(body, dict):
        return None
    err = body.get("error")
    if not isinstance(err, dict):
        return None
    details = err.get("details")
    if not isinstance(details, list):
        return None
    for d in details:
        if not isinstance(d, dict):
            continue
        if d.get("@type") != "type.googleapis.com/google.rpc.RetryInfo":
            continue
        rd = d.get("retryDelay")
        if isinstance(rd, str):
            parsed = _parse_duration_seconds(rd)
            if parsed is not None:
                return parsed
    return None


def _retry_delay_seconds_for_model_http_error(
    exc: ModelHTTPError, *, attempt: int
) -> float:
    """
    Prefer server hint (RetryInfo / message); otherwise exponential backoff.
    Capped to avoid sleeping unreasonably long on bad parses.
    """
    delay = _retry_delay_from_google_body(exc.body)
    if delay is None:
        msg = ""
        if isinstance(exc.body, dict):
            err = exc.body.get("error")
            if isinstance(err, dict) and isinstance(err.get("message"), str):
                msg = err["message"]
        if not msg:
            msg = str(exc.message)
        m = _RETRY_IN_MESSAGE.search(msg)
        if m:
            delay = float(m.group(1))
    if delay is None:
        delay = min(2.0**attempt, 120.0)
    return min(max(delay, 1.0), 3600.0)


@agent.system_prompt
def get_agent_browser_command(ctx: RunContext[Deps]):
    cdp_endpoint = ctx.deps.cdp_endpoint
    output_dir = ctx.deps.output_dir.resolve()
    return f"""
    You are an autonomous browser automation agent. You complete tasks by interacting with a browser using the browser tool. Be autonomous — break tasks into steps, execute ALL steps without stopping early, and be concise.
    
    You are already on the correct page.
    
    A snapshot of the current page is provided in the USER message. Use it as your starting point.

    Use the browser tool to interact with the page.

    ## File tool (``file_tool``)
    For long-running extractions (e.g. playlists with 1000+ rows), call ``file_tool`` after each scroll batch or eval so data is persisted on disk. Do not rely on the chat context to hold the full list.
    - ``path``: relative path only (e.g. ``playlist/songs.jsonl``), resolved under: ``{output_dir}`` (no ``..`` or absolute paths).
    - ``file_type``: ``txt`` (plain string), ``json`` (object or list, written as JSON text), or ``csv`` (list of objects with consistent keys).
    - ``mode``: ``append`` (default) or ``write`` (overwrite).
    - ``content``: matches ``file_type`` (string for ``txt``; object/list for ``json``; list of dicts for ``csv``).
    - ``add_newline_if_missing``: default true — when appending, ensures a trailing newline if serialized output does not end with one.
    Prefer JSON Lines: use ``file_type`` ``txt`` and pass one JSON object per line as a string, or use ``json`` with a single object per call. For CSV, the first append to a new file includes a header; later appends write rows only.
    In your final reply, summarize what was written and the file path — do not paste the entire list.

    ## Browser Tool — agent-browser commands
    The browser tool runs agent-browser CLI commands. Each tool call should contain a single command or a short chain (joined with &&).

    Commands:
    agent-browser --cdp {cdp_endpoint} snapshot                Get full accessibility tree with clickable refs (@e1, @e2...), prefer using -i
    agent-browser --cdp {cdp_endpoint} snapshot -i             Only interactive elements
    agent-browser --cdp {cdp_endpoint} snapshot -s "#css"      Scope snapshot to a CSS selector
    agent-browser --cdp {cdp_endpoint} click @e1               Click element by ref
    agent-browser --cdp {cdp_endpoint} fill @e2 "text"         Clear field and type text
    agent-browser --cdp {cdp_endpoint} type @e2 "text"         Type without clearing
    agent-browser --cdp {cdp_endpoint} select @e1 "option"     Select dropdown option
    agent-browser --cdp {cdp_endpoint} check @e1               Toggle checkbox
    agent-browser --cdp {cdp_endpoint} press Enter             Press a key
    agent-browser --cdp {cdp_endpoint} keyboard type "text"    Type at current focus
    agent-browser --cdp {cdp_endpoint} hover @e1               Hover element
    agent-browser --cdp {cdp_endpoint} scroll down 500         Scroll down (px)
    agent-browser --cdp {cdp_endpoint} scroll up 500           Scroll up (px)
    agent-browser --cdp {cdp_endpoint} get text @e1            Get text content of element
    agent-browser --cdp {cdp_endpoint} get title               Get page title
    agent-browser --cdp {cdp_endpoint} get url                 Get current URL
    agent-browser --cdp {cdp_endpoint} wait @e1                Wait for element to appear
    agent-browser --cdp {cdp_endpoint} wait --load networkidle Wait for network idle
    agent-browser --cdp {cdp_endpoint} wait --text "Welcome"   Wait for text to appear
    agent-browser --cdp {cdp_endpoint} wait 2000               Wait milliseconds
    agent-browser --cdp {cdp_endpoint} find text "X" click     Find element by text and click
    agent-browser --cdp {cdp_endpoint} find role button click --name "Submit"
    agent-browser --cdp {cdp_endpoint} find placeholder "Q" type "query"
    agent-browser --cdp {cdp_endpoint} frame @e2               Scope to iframe
    agent-browser --cdp {cdp_endpoint} frame main              Return to main frame
    agent-browser --cdp {cdp_endpoint} eval "js code"          Run JavaScript in page
    agent-browser --cdp {cdp_endpoint} back                    Go back

    ## Efficiency — use JavaScript (eval) for larger work
    For **big** tasks (long lists, virtualized / infinite-scroll tables, hundreds of similar elements, repeated scroll-and-read loops), **prefer `eval`** so one tool call does bulk DOM work instead of many tiny steps.
    - Use **snapshot / click / fill** only for what JS cannot do cleanly: locate the right container once, accept cookies, focus inputs, or confirm structure — then drive extraction with **`eval`**.
    - In **`eval`**, query nodes with **`querySelector` / `querySelectorAll`**, walk the virtualized list’s scroll container, **`scrollTop`** in steps, collect rows into an array, and return **`JSON.stringify(...)`** (compact, one line if possible) so the CLI output stays parseable.
    - Prefer **few large `eval`s** (e.g. “scroll N px + collect visible rows + return JSON”) over **many** `scroll` + `get text` + `snapshot` cycles.
    - **Do not** paste huge `eval` results into your final user message — write batches with **`file_tool`** (e.g. JSONL via `file_type` `txt`) and summarize counts/paths only.
    - Escape quotes in shell strings when needed so `eval` snippets are valid.

    ## Workflow
    1. An initial page snapshot is provided — use it immediately, don't re-snapshot.
    2. For **small** interactions, use @refs from the snapshot (click, fill, etc.).
    3. For **large** extractions or repetitive scrolling, switch to **`eval`** early; re-snapshot only when you must re-anchor after navigation or a broken DOM state.
    4. After interactions that change the page (non-eval UI steps), call snapshot to refresh @refs if you still need them.
    5. Repeat until the task is complete.

    ## Rules
    1. You are already on the target page. Do NOT navigate to external sites or search engines.
    2. @refs are invalidated after page changes — snapshot again when you still rely on @refs after UI actions.
    3. Chain independent commands with && to save round-trips.
    4. When extracting **lots** of data, **prefer `eval`** (batch DOM reads + JSON) over many `get text` / per-row commands; use `get text` only for small, one-off reads.
    5. If a command fails, try a different approach (different selector, wait first, use find, etc.).
    6. NEVER open new tabs. Always work in the current tab. Do not use agent-browser tab new or agent-browser open. If you need to navigate within the site, click links directly.

    ## When to stop (critical)
    When the task is complete or you have the information the user asked for:
    - Respond in a single final message with ONLY the answer for the user.
    - Do NOT call the browser_tool in that final message.
    - If you have the answer, stop immediately — do not snapshot or click again.
    - For huge lists already written via file_tool, the final message should confirm path, approximate count, and format — not the full data.

    ## Output Format
    Your final text response is what the user sees. It MUST be a clean, human-readable answer:
    - If asked for a price → respond with the product name and price (e.g. "iPhone 15 Pro Max: $1,199")
    - If asked for a list that was saved to a file → point to the file path and row count; do not dump the whole list
    - If asked for a short list → respond with a clean list of items
    - If asked to perform an action → confirm what was done
    - NEVER dump raw HTML, accessibility trees, or @ref identifiers in your final response
    - Be concise and direct — just the answer the user asked for
    """


@agent.tool
async def browser_tool(ctx: RunContext[Deps], command: str) -> str:
    """Run an agent-browser CLI command in the browser. Each call should be one command or a short && chain."""
    logger.info(msg=command, tag="COMMAND")
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        out = (result.stdout or "").rstrip()
        err = (result.stderr or "").rstrip()
        if result.returncode != 0:
            msg = f"[exit {result.returncode}]"
            if out:
                msg += f"\n{out}"
            if err:
                msg += f"\n{err}"
            return msg
        return out or err or "(no output)"
    except Exception as e:
        return str(e)


# file tool helpers
class FileInput(BaseModel):
    path: str = Field(
        ...,
        description="Relative path under the agent output directory (e.g. playlist/songs.jsonl).",
    )
    file_type: Literal["txt", "json", "csv"] = Field(
        default="txt",
        description="txt: plain string; json: object or list serialized to JSON; csv: list of dict rows.",
    )
    mode: Literal["append", "write"] = Field(
        default="append",
        description="append: add to file; write: overwrite file.",
    )
    content: Union[str, Dict[str, Any], List[Dict[str, Any]]] = Field(
        ...,
        description="Must match file_type: str for txt; dict/list for json; list[dict] for csv.",
    )
    add_newline_if_missing: bool = Field(
        default=True,
        description="If true and mode is append, append a newline when serialized content lacks a trailing newline.",
    )


def _safe_output_file_path(output_dir: Path, rel: str) -> Path:
    rel = rel.strip().replace("\\", "/")
    if not rel or rel.startswith("/") or ".." in Path(rel).parts:
        raise ValueError(
            "path must be a relative path under the output directory (no .. or absolute paths)"
        )
    base = output_dir.resolve()
    full = (base / rel).resolve()
    try:
        full.relative_to(base)
    except ValueError:
        raise ValueError("path must stay under the output directory") from None
    return full


def _serialize_csv_rows(rows: list[dict[str, Any]], *, include_header: bool) -> str:
    output = io.StringIO()
    fieldnames = list(rows[0].keys())
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    if include_header:
        writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def _prepare_file_payload(file: FileInput, full_path: Path) -> str:
    if file.file_type == "txt":
        if not isinstance(file.content, str):
            raise ValueError("txt requires string content")
        return file.content
    if file.file_type == "json":
        return json.dumps(file.content, ensure_ascii=False)
    if file.file_type == "csv":
        if not isinstance(file.content, list) or not file.content:
            raise ValueError("csv requires a non-empty list of dicts")
        if not all(isinstance(row, dict) for row in file.content):
            raise ValueError("csv requires a list of objects (dicts)")
        include_header = (
            file.mode == "write"
            or not full_path.exists()
            or full_path.stat().st_size == 0
        )
        return _serialize_csv_rows(file.content, include_header=include_header)
    raise ValueError(f"Unsupported file_type: {file.file_type}")


def _write_to_file(file: FileInput, output_dir: Path) -> str:
    full_path = _safe_output_file_path(output_dir, file.path)
    full_path.parent.mkdir(parents=True, exist_ok=True)
    data = _prepare_file_payload(file, full_path)
    write_mode = "a" if file.mode == "append" else "w"
    if (
        file.mode == "append"
        and file.add_newline_if_missing
        and data
        and not data.endswith("\n")
    ):
        data += "\n"
    with open(full_path, write_mode, encoding="utf-8") as f:
        f.write(data)
    return f"Wrote {len(data)} bytes to {full_path}"


@agent.tool
async def file_tool(ctx: RunContext[Deps], file: FileInput) -> str:
    """Write or append under the agent output directory. Use for TXT/JSON/CSV (or JSONL via txt) while scrolling."""
    logger.info(
        msg=f"path={file.path} mode={file.mode} file_type={file.file_type}",
        tag="FILE",
    )
    try:
        return await asyncio.to_thread(_write_to_file, file, ctx.deps.output_dir)
    except Exception as e:
        return str(e)


async def execute(
    query: str,
    deps: Deps,
    *,
    config: BrowserAgentConfig | None = None,
) -> BrowserAgentResult:
    """
    Run the agent until the model returns a final text answer (no more tool calls),
    or until usage limits are exceeded (then ``UsageLimitExceeded`` is handled).

    ``file_tool`` writes under :attr:`BrowserAgentConfig.output_dir` when set; otherwise
    :attr:`Deps.output_dir` (default ``./scout_agent_output``). Use :class:`BrowserAgentConfig`
    for output path, ``max_model_requests``, HTTP retries, or a different model.

    Returns a :class:`BrowserAgentResult` with ``output`` set to the model's final string.
    """
    cfg = config or BrowserAgentConfig()
    if cfg.output_dir is not None:
        deps = replace(
            deps, output_dir=Path(cfg.output_dir).expanduser().resolve()
        )
    deps.output_dir.mkdir(parents=True, exist_ok=True)

    prompt = f"""
            ## Task
            {query}

            ## Current Page Snapshot
            {deps.page_snapshot}

            ## Instructions
            - Use the snapshot to understand the page
            - Use @refs from the snapshot
            - Do NOT re-snapshot unless needed
    """

    limits = _usage_limits_for_config(cfg)
    max_http_retries = cfg.model_http_max_retries
    attempt = 0
    result = None
    run_kw: dict[str, Any] = {"deps": deps, "usage_limits": limits}
    if cfg.model is not None:
        run_kw["model"] = cfg.model
    while attempt < max_http_retries:
        try:
            result = await agent.run(prompt, **run_kw)
            break
        except ModelHTTPError as exc:
            attempt += 1
            if attempt >= max_http_retries:
                logger.error(msg=str(exc), tag="MODEL_HTTP", error=str(exc))
                return BrowserAgentResult(
                    output=(
                        f"Failed after {attempt} attempts due to model API errors: {exc}"
                    ),
                    limit_reached=True,
                )
            delay = _retry_delay_seconds_for_model_http_error(exc, attempt=attempt)
            logger.warning(
                msg=f"Model HTTP {exc.status_code}; sleeping {delay:.2f}s before retry {attempt}/{max_http_retries}",
                tag="MODEL_RETRY",
                error=str(exc),
            )
            await asyncio.sleep(delay)
        except UsageLimitExceeded as exc:
            logger.error(msg=str(exc), tag="USAGE_LIMIT", error=str(exc))
            return BrowserAgentResult(
                output=(
                    "The browser agent stopped because the run hit its model/tool usage limit. "
                    "Raise ``BrowserAgentConfig.max_model_requests`` or simplify the task. "
                    f"Details: {exc}"
                ),
                limit_reached=True,
            )

    if result is None:
        return BrowserAgentResult(
            output="Agent run finished without a result.",
            limit_reached=True,
        )

    usage = result.usage()
    run_id = result.run_id
    return BrowserAgentResult(output=result.output, usage=usage, run_id=run_id)
