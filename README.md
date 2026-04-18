# Scout

Scout is a Python toolkit for browser-backed scraping, crawling, interaction, and LLM-assisted extraction.

## What Scout can do

- Scrape a single page and return a `Document` with HTML and metadata.
- Run action chains (`click`, `type`, `scroll`, `press`, `run_js_code`, etc.).
- Crawl links from a starting URL with include/exclude/depth/limit controls.
- Convert HTML to markdown with `Document.to_markdown()`.
- Run schema-based extraction with `Document.extract(...)`.
- Run agent-driven browser interaction with `Scout.interact(...)`.

## Setup

### 1) Install dependencies

```bash
uv sync --dev
```

### 2) Install Playwright Chromium

```bash
PLAYWRIGHT_BROWSERS_PATH=0 uv run playwright install chromium
```

### 3) Optional `.env` for API keys and agent model

Create a `.env` in the project root:

```env
# Comma-separated Gemini keys are supported.
GOOGLE_API_KEY=your_gemini_key_1,your_gemini_key_2

# Optional: defaults to gemini-flash-latest when unset.
SCOUT_GEMINI_MODEL=gemini-2.5-flash
```

Notes:
- `GOOGLE_API_KEY` is used by Scout agent flows.
- `SCOUT_GEMINI_MODEL` is now read from env and used for `GoogleModel(...)`.
- If `SCOUT_GEMINI_MODEL` is not set, Scout uses `gemini-flash-latest`.

### 4) Optional: install agent-browser CLI

`Scout.interact(...)` expects `agent-browser` in PATH.
Install guide: [agent-browser.dev/installation](https://agent-browser.dev/installation)

## Quick start

```python
import asyncio
from scout.scout import Scout

async def main():
    async with Scout().start() as scout:
        doc = await scout.scrape("https://example.com")
        print(doc.metadata["title"])
        print(doc.metadata["status"])
        print(doc.url)

asyncio.run(main())
```

## Examples

### Scrape with actions

```python
import asyncio
from scout.scout import Scout
from scout.core import Action, Selector

async def main():
    async with Scout().start() as scout:
        doc = await scout.scrape(
            "https://example.com/form",
            actions=[
                Action(kind="type", selector=Selector(kind="css", value="#name"), value="Scout"),
                Action(kind="click", selector=Selector(kind="css", value="#submit"), value=None),
                Action(kind="run_js_code", selector=None, value="() => document.title = 'Done'"),
            ],
        )
        print(doc.metadata["title"])

asyncio.run(main())
```

### Selector kinds

```python
Selector(kind="css", value="#submit")
Selector(kind="xpath", value="//button[@id='submit']")
Selector(kind="text", value="Submit")
Selector(kind="tag", value="button")
Selector(kind="load_state", value="networkidle")  # wait selector
Selector(kind="url", value="**/checkout")         # wait selector
```

### Crawl a site

```python
import asyncio
import re
from scout.scout import Scout
from scout.core import CrawlConfig

async def main():
    async with Scout().start() as scout:
        docs = await scout.crawl(
            "https://example.com/docs",
            CrawlConfig(
                page_limit=20,
                max_depth=2,
                concurrency=3,
                include=[re.compile(r"^https://example.com/docs")],
                exclude=[re.compile(r"/changelog")],
                page_transition_delay=0,
            ),
        )
        print(len(docs))
        print([d.url for d in docs[:5]])

asyncio.run(main())
```

### Crawl with scrolling rule

```python
import asyncio
from scout.scout import Scout
from scout.core import CrawlConfig, ScrollingRule, VirtualScrollConfig

async def main():
    async with Scout().start() as scout:
        docs = await scout.crawl(
            "https://example.com/feed",
            CrawlConfig(
                page_limit=5,
                max_depth=1,
                scrolling=ScrollingRule(
                    virtual_scroll=VirtualScrollConfig(
                        container_selector="#feed",
                        scroll_count=12,
                        wait_after_scroll=0.1,
                        scroll_by="container_height",
                    )
                ),
            ),
        )
        print(len(docs))

asyncio.run(main())
```

### Convert to markdown

```python
md = doc.to_markdown()
print(md[:300])
```

### Structured extraction

```python
from scout.core import ExtractionSchema, ExtractionSelector

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
rows = doc.extract(schema)
for row in rows:
    print(row.field, row.value)
```

### Agent interaction (Gemini-backed)

```python
import asyncio
from scout.scout import Scout
from scout.agents.browser_agent import BrowserAgentConfig

async def main():
    async with Scout().start() as scout:
        result = await scout.interact(
            "Extract the visible product name and price from the current page.",
            agent_config=BrowserAgentConfig(
                output_dir="./agent_output",
                max_model_requests=30,
            ),
        )
        print(result.output)

asyncio.run(main())
```

## E2E testing

Run all e2e tests:

```bash
PLAYWRIGHT_BROWSERS_PATH=0 uv run pytest tests/e2e -m e2e
```

Run one file:

```bash
PLAYWRIGHT_BROWSERS_PATH=0 uv run pytest tests/e2e/test_scout_e2e.py -m e2e
```