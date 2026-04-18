# Scout Examples

Detailed, practical examples for common Scout workflows.

All examples assume:
- you already ran `uv sync --dev`
- Playwright Chromium is installed (`PLAYWRIGHT_BROWSERS_PATH=0 uv run playwright install chromium`)
- examples are run from the repository root

---

## 1) Basic page scrape

Use this when you only need final HTML + metadata for one URL.

```python
import asyncio
from scout.scout import Scout


async def main() -> None:
    async with Scout().start() as scout:
        doc = await scout.scrape("https://example.com")
        print("URL:", doc.url)
        print("Title:", doc.metadata["title"])
        print("Status:", doc.metadata["status"])
        print("HTML length:", len(doc.html))


asyncio.run(main())
```

---

## 2) Set timeout and browser mode

Use `set_timeout(...)` to control action/page waits, and `set_headless(...)` before startup.

```python
import asyncio
from scout.scout import Scout


async def main() -> None:
    scout = Scout().set_headless(True).set_timeout(2000)
    async with scout.start():
        doc = await scout.scrape("https://example.com")
        print(doc.metadata["title"])


asyncio.run(main())
```

---

## 3) Actions: form fill + click + JS

This is the core "interact then capture" pattern.

```python
import asyncio
from scout.scout import Scout
from scout.core import Action, Selector


async def main() -> None:
    actions = [
        Action(
            kind="type",
            selector=Selector(kind="css", value="#name"),
            value="Scout",
        ),
        Action(
            kind="click",
            selector=Selector(kind="css", value="#submit"),
            value=None,
        ),
        Action(
            kind="run_js_code",
            selector=None,
            value="() => document.body.setAttribute('data-ran', 'yes')",
        ),
    ]

    async with Scout().start() as scout:
        doc = await scout.scrape("https://example.com/form", actions=actions)
        print("Ran JS:", 'data-ran="yes"' in doc.html)


asyncio.run(main())
```

---

## 4) Selector kinds cheat sheet

```python
from scout.core import Selector

selectors = [
    Selector(kind="css", value="#submit"),
    Selector(kind="xpath", value="//button[@id='submit']"),
    Selector(kind="text", value="Submit"),
    Selector(kind="tag", value="button"),
    Selector(kind="load_state", value="networkidle"),  # wait until page state
    Selector(kind="url", value="**/checkout"),         # wait for URL pattern
]
```

---

## 5) Capture screenshots via action callback

`Document.screenshots` is not auto-populated by screenshot actions; use `on_complete`.

```python
import asyncio
from scout.scout import Scout
from scout.core import Action


async def main() -> None:
    shots: list[bytes] = []

    async with Scout().start() as scout:
        await scout.scrape(
            "https://example.com",
            actions=[
                Action(
                    kind="screenshot",
                    selector=None,
                    value=None,
                    on_complete=lambda png, _url: shots.append(png),
                )
            ],
        )

    print("Captured screenshots:", len(shots))


asyncio.run(main())
```

---

## 6) Convert HTML to markdown

```python
import asyncio
from scout.scout import Scout


async def main() -> None:
    async with Scout().start() as scout:
        doc = await scout.scrape("https://example.com")
        markdown = doc.to_markdown()
        print(markdown[:500])


asyncio.run(main())
```

---

## 7) Structured extraction with schema

Use this for deterministic fields (titles, links, prices in known selectors).

```python
import asyncio
from scout.scout import Scout
from scout.core import ExtractionSchema, ExtractionSelector


async def main() -> None:
    schema = [
        ExtractionSchema(
            field="title",
            selector=ExtractionSelector(kind="css", value="h1"),
        ),
        ExtractionSchema(
            field="links",
            selector=ExtractionSelector(kind="css", value="a"),
            attr="href",
        ),
    ]

    async with Scout().start() as scout:
        doc = await scout.scrape("https://example.com")
        rows = doc.extract(schema)
        for row in rows:
            print(row.field, "=>", row.value[:3])


asyncio.run(main())
```

---

## 8) Crawl a docs section with include/exclude

Use regex filters to keep crawl focused.

```python
import asyncio
import re
from scout.scout import Scout
from scout.core import CrawlConfig


async def main() -> None:
    cfg = CrawlConfig(
        page_limit=30,
        max_depth=2,
        concurrency=3,
        include=[re.compile(r"^https://example.com/docs")],
        exclude=[re.compile(r"/changelog"), re.compile(r"/privacy")],
        page_transition_delay=0,
    )

    async with Scout().start() as scout:
        docs = await scout.crawl("https://example.com/docs", cfg)

    print("Pages:", len(docs))
    for d in docs[:10]:
        print("-", d.url)


asyncio.run(main())
```

---

## 9) Crawl with virtual scroll container

Use this when content appears inside a scrollable container instead of full page scroll.

```python
import asyncio
from scout.scout import Scout
from scout.core import CrawlConfig, ScrollingRule, VirtualScrollConfig


async def main() -> None:
    cfg = CrawlConfig(
        page_limit=5,
        max_depth=1,
        concurrency=1,
        scrolling=ScrollingRule(
            virtual_scroll=VirtualScrollConfig(
                container_selector="#feed",
                scroll_count=12,
                wait_after_scroll=0.1,
                scroll_by="container_height",
            )
        ),
    )

    async with Scout().start() as scout:
        docs = await scout.crawl("https://example.com/feed", cfg)

    print("Crawled:", len(docs))


asyncio.run(main())
```

---

## 10) Agent interaction (Gemini + agent-browser)

This is useful for harder tasks that require exploratory, multi-step interaction.

`.env` example:

```env
GOOGLE_API_KEY=your_key
SCOUT_GEMINI_MODEL=gemini-2.5-flash
```

Script:

```python
import asyncio
from scout.scout import Scout
from scout.agents.browser_agent import BrowserAgentConfig


async def main() -> None:
    async with Scout().start() as scout:
        result = await scout.interact(
            "Collect product names and prices visible on this page, then summarize.",
            agent_config=BrowserAgentConfig(
                output_dir="./scout_agent_output",
                max_model_requests=30,
            ),
        )
        print(result.output)
        print("Run ID:", result.run_id)


asyncio.run(main())
```

---

## 11) Error handling pattern

A production-safe shape you can wrap around any workflow.

```python
import asyncio
from scout.scout import Scout


async def main() -> None:
    try:
        async with Scout().start() as scout:
            doc = await scout.scrape("https://example.com")
            print(doc.metadata["status"])
    except Exception as exc:
        print("Scout run failed:", exc)


asyncio.run(main())
```

---

## 12) Where to look next

- `README.md`: setup and broad feature overview
- `tests/e2e/test_scout_e2e.py`: realistic end-to-end usage patterns
- `tests/test_core_document.py`: extraction and config behavior in unit tests
- `recipes/`: longer, task-specific scripts (for example Spotify playlist export)
