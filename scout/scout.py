from .adapters.Playwright import PlaywrightAdapter, Response, TIMEOUT
from .core import Action
from .adapters.browser_manager import BrowserManager, BrowserManagerConfig
from contextlib import asynccontextmanager


class Scout:
    def __init__(self):
        self._crawler = PlaywrightAdapter()
        self._browser_manager: BrowserManager = BrowserManager(BrowserManagerConfig())

    @asynccontextmanager
    async def start(self):
        await self._browser_manager.start()
        self._crawler.set_cdp_endpoint(
            await self._browser_manager.get_websocket_debugger_url()
        )
        try:
            yield self
        finally:
            await self.stop()

    async def stop(self):
        await self._browser_manager.stop()

    async def __aenter__(self):
        await self._browser_manager.start()
        self._crawler.set_cdp_endpoint(
            await self._browser_manager.get_websocket_debugger_url()
        )
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.stop()
        # Do not suppress exceptions from inside `async with`.
        # Returning a truthy value would swallow errors and make `scrape()` look like it returned None.
        return False

    def set_timeout(self, timeout: int = TIMEOUT):
        self._crawler.set_timeout(timeout)
        return self

    async def scrape(self, url: str, actions: list[Action] | None = None):
        actions = actions or []
        async with self._crawler as crawler:
            return await crawler.scrape(url, actions)

    def crawl(self):
        pass

    def interact(self):
        pass
