from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

from playwright.async_api import Browser, Playwright, async_playwright

from ..logger import get_logger

# Default configuration constants
DEFAULT_DEBUG_PORT: int = 9092
DEFAULT_DEBUG_HOST: str = "0.0.0.0"
DEFAULT_SESSION_ID: str = "scout-session"


async def _wait_cdp_http(port: int, *, timeout_s: float = 30.0) -> None:
    url = f"http://127.0.0.1:{port}/json/version"
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_s

    def _ping() -> None:
        with urllib.request.urlopen(url, timeout=1.0) as r:
            r.read(64)

    while loop.time() < deadline:
        try:
            await asyncio.to_thread(_ping)
            return
        except urllib.error.URLError, OSError, TimeoutError:
            await asyncio.sleep(0.12)
    raise TimeoutError(f"CDP endpoint did not become ready at 127.0.0.1:{port}")


@dataclass
class BrowserManagerConfig:
    """If ``cdp_endpoint`` is set, the manager only attaches and does not spawn a process."""

    cdp_endpoint: Optional[str] = None
    headless: bool = True
    """If True, Chromium runs with ``--headless=new`` (no UI). If False, a visible (headed) window is used."""
    remote_debugging_port: int = DEFAULT_DEBUG_PORT
    """Port for remote debugging (default: 9092, or pass custom port)."""
    remote_debugging_address: str = DEFAULT_DEBUG_HOST
    """Chromium --remote-debugging-address (default: 127.0.0.1, pass custom host if needed)."""
    kill_launched_browser_on_close: bool = True
    """If we started a subprocess, terminate it on ``stop()``."""
    cdp_ready_timeout_s: float = 30.0
    session_id: str = DEFAULT_SESSION_ID
    """Session/uid for the browser (default: 'scout-session', pass custom id if needed)."""
    user_data_dir: Optional[str] = None
    """Optional custom user data directory. If None, uses temp dir with session_id."""


class BrowserManager:
    def __init__(self, config: Optional[BrowserManagerConfig] = None):
        self.config = config or BrowserManagerConfig()
        self._logger = get_logger("BrowserManager")
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._process: Optional[subprocess.Popen] = None
        self._user_data_temp: Optional[tempfile.TemporaryDirectory] = None
        self._launched_locally: bool = False
        self._connect_url: Optional[str] = None
        # HTTP CDP port (launch mode, or parsed from attach URL when present)
        self._debugging_port: Optional[int] = None
        self._websocket_debugger_url: Optional[str] = None

    @property
    def playwright(self) -> Playwright:
        if self._playwright is None:
            raise RuntimeError("BrowserManager is not started")
        return self._playwright

    @property
    def browser(self) -> Browser:
        if self._browser is None:
            raise RuntimeError("BrowserManager is not started")
        return self._browser

    @property
    def cdp_url(self) -> Optional[str]:
        return self._connect_url

    @property
    def debugging_port(self) -> Optional[int]:
        """Port for ``http://127.0.0.1:<port>/json/version`` style CDP (``None`` if unknown)."""
        return self._debugging_port

    @property
    def websocket_debugger_url(self) -> Optional[str]:
        """Most recently resolved CDP websocket URL, if available."""
        return self._websocket_debugger_url

    @staticmethod
    def _port_from_cdp_http_url(url: str) -> Optional[int]:
        try:
            p = urlparse(url)
            if p.port is not None:
                return int(p.port)
            if p.scheme == "http":
                return 80
            if p.scheme == "https":
                return 443
        except Exception:
            pass
        return None

    async def get_websocket_debugger_url(self) -> Optional[str]:
        """Fetch the live websocket debugger URL from ``/json/version``."""
        port = self._debugging_port
        if port is None:
            return None

        version_url = f"http://127.0.0.1:{port}/json/version"

        def _fetch() -> Optional[str]:
            with urllib.request.urlopen(version_url, timeout=2.0) as r:
                payload = json.load(r)
            value = payload.get("webSocketDebuggerUrl")
            return value if isinstance(value, str) and value else None

        try:
            ws_url = await asyncio.to_thread(_fetch)
        except urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError:
            return None

        self._websocket_debugger_url = ws_url
        return ws_url

    async def start(self) -> Browser:
        if self._browser is not None:
            return self._browser

        self._playwright = await async_playwright().start()

        if self.config.cdp_endpoint:
            url = self.config.cdp_endpoint.rstrip("/")
            self._connect_url = url
            self._debugging_port = self._port_from_cdp_http_url(url)
            if url.startswith("ws://") or url.startswith("wss://"):
                self._websocket_debugger_url = url
            self._launched_locally = False
            self._browser = await self._playwright.chromium.connect_over_cdp(url)
            self._logger.info(f"Connected over CDP {url}", tag="CDP")
            return self._browser

        port = self.config.remote_debugging_port

        # Determine user data directory
        if self.config.user_data_dir:
            user_data_dir = self.config.user_data_dir
            os.makedirs(user_data_dir, exist_ok=True)
            self._user_data_temp = None
        else:
            self._user_data_temp = tempfile.TemporaryDirectory(
                prefix=f"scout-chromium-{self.config.session_id}-"
            )
            user_data_dir = self._user_data_temp.name
        exe = self._playwright.chromium.executable_path

        args = [
            exe,
            f"--remote-debugging-port={port}",
            f"--remote-debugging-address={self.config.remote_debugging_address}",
            "--remote-allow-origins=*",
            f"--user-data-dir={user_data_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-breakpad",
        ]
        if self.config.headless:
            args.append("--headless=new")

        mode = "headless" if self.config.headless else "headed"
        self._logger.info(
            f"Launching Chromium ({mode}) with port={port} host={self.config.remote_debugging_address}",
            tag="CDP",
        )
        self._process = subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._launched_locally = True

        try:
            await _wait_cdp_http(port, timeout_s=self.config.cdp_ready_timeout_s)
        except Exception:
            await self.stop()
            raise

        url = f"http://127.0.0.1:{port}"
        self._connect_url = url
        self._debugging_port = port
        self._browser = await self._playwright.chromium.connect_over_cdp(url)
        await self.get_websocket_debugger_url()
        self._logger.info(f"Connected over CDP {url}", tag="CDP")
        return self._browser

    async def stop(self) -> None:
        if self._browser is not None:
            try:
                await self._browser.close()
            except Exception as e:
                self._logger.info("browser.close failed", tag="CDP", error=str(e))
            self._browser = None

        if self._process is not None and self.config.kill_launched_browser_on_close:
            self._process.terminate()
            try:
                self._process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                self._process.kill()
                try:
                    self._process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    pass
            self._process = None

        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except Exception as e:
                self._logger.info("playwright.stop failed", tag="CDP", error=str(e))
            self._playwright = None

        if self._user_data_temp is not None:
            try:
                self._user_data_temp.cleanup()
            except Exception:
                pass
            self._user_data_temp = None

        self._launched_locally = False
        self._connect_url = None
        self._debugging_port = None
        self._websocket_debugger_url = None

    async def __aenter__(self) -> BrowserManager:
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        await self.stop()
        return False
