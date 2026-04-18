# Scout

Scout is a Python toolkit for **real-browser capture and interaction**: it drives Chromium through Playwright (Chrome DevTools Protocol), loads pages, simulates a human briefly, clears common consent surfaces, runs a **sequence of actions** you define, and returns structured **content** plus **metadata** and optional **network captures**. It sits in the same problem space as modern “scrape-to-LLM” pipelines—while **gathering learnings** from projects like [Firecrawl](https://github.com/mendableai/firecrawl) and [Crawl4AI](https://github.com/unclecode/crawl4ai)—but focuses on a small, composable core you control in code.

It was started for the **same recurring problem** that shows up across scraping work: **targeting** the right content, **parsing** it, orchestrating **interactions**, **reacting** to **requests** and **responses**, **extractions**, and **smart removals** (consent banners, overlays, and other noise)—without reinventing that whole stack on every new project.

---

## Content, metadata, branding, and Markdown

- **Content**: Each run yields a `Document` with the final **HTML** string after navigation and actions.
- **Metadata**: Includes page **title**, navigation **URL**, HTTP **status**, response **headers**, **cookies**, **storage state** (local/session as exposed by Playwright), and **screenshots** collected during the run.
- **Branding**: Treat page chrome, favicons, and third-party widgets as part of the captured HTML; downstream steps (or your own filters) decide what counts as “brand” vs body content.
- **Markdown**: `Document.to_markdown()` converts HTML to Markdown via `html-to-markdown`, suitable for LLM prompts or storage side by side with raw HTML.

---

## Human simulation

Before your scripted actions run, Scout performs light **human-like activity**: pseudo-random mouse moves, wheel events, and small scripted scrolls. The goal is to avoid looking like a static, instant bot hit and to nudge lazy-loaded UI the way a user might. This is **simulation**, not a full behavioral model—it complements, not replaces, explicit actions.

---

## Executions

**Actions** are a ordered list of steps the engine executes on the page after load (e.g. `goto`, `click`, `type`, `press`, `hover`, `scroll`, `screenshot`, `run_js_code`). Selectors support CSS, XPath, text, tag, plus **wait-only** paths for load state and URL patterns. Actions can include per-step timeouts. The `Scout` API wraps a `PlaywrightAdapter` that connects to a managed Chromium instance over CDP.

---

## LLM-driven steps

The codebase is shaped for **LLM-assisted workflows**: Markdown output, rich metadata, and commented patterns for hooking **response bodies** (e.g. JSON APIs) via `NetworkRule` handlers. `Document.extract_with_llm()` is reserved for higher-level extraction pipelines where an LLM interprets page content or structured captures—you wire the model and prompts to your environment.

For agent-style control outside this library, some setups use tools like [Agent-browser](https://agent-browser.dev/installation) alongside or instead of direct Playwright automation.

---

## Popup removal and consent banners

After the document is ready, Scout runs an injected script (`remove_popup`) aimed at **dismissing common CMP/cookie consent UIs** (OneTrust, Cookiebot, IAB-style flows, and similar patterns) so the main document is easier to interact with and scrape. This is **best-effort**; sites vary, and you should still treat legal/consent requirements as your responsibility.

---

## Request and response capture, filtering

`NetworkRule` controls which URLs are recorded and can attach **handlers** to requests/responses. Matching supports string equality or regex; when no filter is set, traffic can be recorded broadly. Captured data is stored as structured **request** and **response** models (URL, method, headers, status, body when available) for debugging, API mining, or feeding extractors.

---

## Extractions with smart waiting

The pipeline **waits for `body`**, checks basic visibility, applies consent handling and human simulation, then runs actions. Individual actions can wait via **load state** or **URL** selectors before interactions. Combined with Playwright’s own timeouts and optional `wait_for_load_state`-style behavior, this gives you **layered waiting**—from coarse page readiness to fine-grained steps—without a separate DSL.

---

## Prior art: Firecrawl and Crawl4AI

**Firecrawl** and **Crawl4AI** have popularized solid patterns: crawl/scrape at scale, clean content for LLMs, and integrate with AI stacks. Scout **does not replicate those products**; it **borrows the spirit**—reliable browser-backed capture, content usable for AI, and operational concern for real pages—and concentrates on a minimal, hackable Python layer. Comparisons and ideas from those ecosystems continue to inform Scout’s direction.

---

## Requirements

- Python 3.14+ (see `pyproject.toml`).
- **Chromium** via Playwright. With browsers installed next to the Playwright package in your virtualenv:

```bash
PLAYWRIGHT_BROWSERS_PATH=0 python3 main.py
```

- Optional: [Agent-browser](https://agent-browser.dev/installation) or other agents for LLM-driven control flows that sit outside or beside Scout.

---

## E2E testing

End-to-end tests exercise adapters, `Scout`, and action execution against a local static site under [`tests/e2e/fixtures/`](tests/e2e/fixtures/).

[`tests/e2e/conftest.py`](tests/e2e/conftest.py) sets `PLAYWRIGHT_BROWSERS_PATH=0` by default so Chromium is resolved from the virtualenv’s Playwright install. You can still export the same variable explicitly when installing browsers or running pytest.

1. Install project dependencies:

```bash
uv sync --dev
```

2. Install Playwright Chromium once (into the venv-local Playwright path):

```bash
PLAYWRIGHT_BROWSERS_PATH=0 uv run playwright install chromium
```

3. Run all E2E tests:

```bash
PLAYWRIGHT_BROWSERS_PATH=0 uv run pytest tests/e2e -m e2e
```

4. Run a single E2E file:

```bash
PLAYWRIGHT_BROWSERS_PATH=0 uv run pytest tests/e2e/test_scout_e2e.py -m e2e
```

### Future easier interface
```py
result = await scout.run(
    "https://example.com",
    mode="crawl",
    config=RunConfig(
        limits=Limits(pages=20, depth=2),
        scrolling=Scrolling.virtual("#feed"),
        outputs=Outputs(html=True, markdown=True),
    ),
    steps=[
        click("#accept"),
        type("#search", "pricing"),
    ],
    extract=Schema(ProductSchema),
)
```