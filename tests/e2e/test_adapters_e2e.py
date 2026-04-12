from __future__ import annotations

import pytest

from scout.adapters.Playwright import PlaywrightAdapter
from scout.adapters.browser_manager import BrowserManager, BrowserManagerConfig
from scout.core import Action, Selector


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_browser_manager_exposes_cdp_endpoints() -> None:
    config = BrowserManagerConfig(cdp_ready_timeout_s=20.0)

    async with BrowserManager(config) as manager:
        assert manager.cdp_url is not None
        assert manager.cdp_url.startswith("http://127.0.0.1:")
        assert isinstance(manager.debugging_port, int)

        ws_url = await manager.get_websocket_debugger_url()
        assert ws_url is not None
        assert ws_url.startswith("ws://")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_playwright_adapter_can_scrape_with_cdp(e2e_server_url: str) -> None:
    config = BrowserManagerConfig(cdp_ready_timeout_s=20.0)

    async with BrowserManager(config) as manager:
        endpoint = await manager.get_websocket_debugger_url() or manager.cdp_url
        assert endpoint is not None

        adapter = PlaywrightAdapter()
        adapter.set_cdp_endpoint(endpoint)
        adapter.set_timeout(1200)

        hooks: list[tuple[str, object, str]] = []

        async with adapter:
            doc = await adapter.scrape(
                f"{e2e_server_url}/index.html",
                actions=[
                    Action(
                        kind="screenshot",
                        selector=None,
                        value=None,
                        on_complete=lambda r, u: hooks.append(("screenshot", r, u)),
                    ),
                    Action(
                        kind="run_js_code",
                        selector=None,
                        value="() => document.title",
                        on_complete=lambda r, u: hooks.append(("run_js", r, u)),
                    ),
                ],
            )

    assert doc.metadata["title"] == "Scout E2E"
    assert "screenshots" not in doc.metadata
    assert "action_results" not in doc.metadata
    assert len(hooks) == 2
    assert hooks[0][0] == "screenshot"
    assert hooks[1][0] == "run_js"
    assert hooks[1][1] == "Scout E2E"
    assert all(h[2].rstrip("/").endswith("index.html") for h in hooks)
    assert doc.metadata["status"] == 200
    assert isinstance(hooks[0][1], bytes) and len(hooks[0][1]) > 0
    assert doc.screenshots == []
    assert 'id="title"' in doc.html
