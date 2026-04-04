### About
Its a suprise

### Requirements
* For LLM based operations
[Agent-browser](https://agent-browser.dev/installation)
No chromium, just the agent-browser cli tool

* Chromium (browsers live under the Playwright package in the active venv when using):

```bash
PLAYWRIGHT_BROWSERS_PATH=0 python3 main.py
```

### E2E Testing

Run end-to-end tests for adapters, Scout, and action execution using a local deterministic test site.

[`tests/e2e/conftest.py`](tests/e2e/conftest.py) sets `PLAYWRIGHT_BROWSERS_PATH=0` by default so Chromium is resolved from the virtualenv’s Playwright install. You can still pass the same variable explicitly when installing browsers or running pytest.

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