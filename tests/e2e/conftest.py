from __future__ import annotations

import os

# Resolve Chromium from the Playwright package inside this venv (not the global cache).
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "0")

import socket
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from scout.adapters.browser_manager import BrowserManagerConfig
from scout.scout import Scout

_FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="session")
def e2e_site_dir() -> Path:
    """Static HTML under ``tests/e2e/fixtures`` (see that directory)."""
    return _FIXTURES


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture(scope="session")
def e2e_server_url(e2e_site_dir: Path) -> str:
    port = _free_port()
    handler = partial(SimpleHTTPRequestHandler, directory=str(e2e_site_dir))
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture
async def scout_instance() -> Scout:
    async with Scout(
        browser_config=BrowserManagerConfig(headless=True),
    ).start() as scout:
        yield scout
