from .adapters.Playwright import PlaywrightAdapter, Response, TIMEOUT
from .core import Action, CrawlConfig, ScrollingRule
from .adapters.browser_manager import BrowserManager, BrowserManagerConfig
from contextlib import asynccontextmanager
import json, subprocess, asyncio
from asyncio.queues import Queue
from typing import Any, Optional

from .agents.browser_agent import BrowserAgentConfig, BrowserAgentResult, Deps, execute
from .logger import get_logger

from domdistill.embedding import SentenceTransformerEmbedder


class Scout:
    def __init__(self, *, browser_config: BrowserManagerConfig | None = None):
        self._crawler = PlaywrightAdapter()
        self._browser_manager: BrowserManager = BrowserManager(
            browser_config or BrowserManagerConfig()
        )
        self._logger = get_logger("SCOUT")

    @staticmethod
    def load_chunking_models(save_dir: str = "./models/embeddings"):
        embedder = SentenceTransformerEmbedder(save_dir)
        embedder._load()

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

    def set_headless(self, headless: bool = True) -> "Scout":
        if self._browser_manager.started:
            raise RuntimeError(
                "set_headless() has no effect after the browser started; "
                "call it before start() or before `async with Scout()`."
            )
        self._browser_manager.config.headless = headless
        return self

    def set_scrolling_rule(self, rule: Optional[ScrollingRule]) -> "Scout":
        self._crawler.set_scrolling_rule(rule)
        return self

    async def scrape(
        self,
        url: str,
        actions: list[Action] | None = None,
    ):
        actions = actions or []
        async with self._crawler as crawler:
            return await crawler.scrape(url, actions)

    async def crawl(self, url: str, config: CrawlConfig) -> list[Any]:
        # Feature idea -> adding the nodes of the url to a graph db and visualize it
        queue: Queue[tuple[str, int]] = Queue()
        await queue.put((url, 1))
        result: list[Any] = []
        visited: set[str] = {url}
        visited_lock = asyncio.Lock()
        result_lock = asyncio.Lock()

        collect_urls_js = f"""() => {{
            const urls = new Set();
            for (const a of document.querySelectorAll('a[href]')) {{
                try {{ urls.add(new URL(a.href, document.baseURI).href); }} catch (e) {{}}
            }}
            return Array.from(urls);
        }}"""

        async def enqueue_urls(js_result: Any, depth: int) -> None:
            if not isinstance(js_result, list):
                return
            if depth > config.max_depth:
                return

            for item in js_result:
                if isinstance(item, str):
                    if not config.is_included(item):
                        continue
                    async with visited_lock:
                        if item in visited:
                            continue
                        visited.add(item)
                    await queue.put((item, depth))

        async def worker() -> None:
            while True:
                current_url, depth = await queue.get()
                try:
                    if len(result) >= config.page_limit:
                        continue
                    if depth > config.max_depth:
                        continue

                    async with self._crawler as crawler:
                        crawler.set_scrolling_rule(config.scrolling)
                        doc = await crawler.scrape(
                            current_url,
                            actions=[
                                Action(
                                    kind="run_js_code",
                                    selector=None,
                                    value=collect_urls_js,
                                    on_complete=lambda js_result, _page_url: enqueue_urls(
                                        js_result, depth + 1
                                    ),
                                )
                            ],
                        )
                    async with result_lock:
                        if len(result) < config.page_limit:
                            result.append(doc)
                finally:
                    queue.task_done()
                if config.page_transition_delay > 0:
                    await asyncio.sleep(config.page_transition_delay)

        worker_count = max(1, config.concurrency)
        workers = [asyncio.create_task(worker()) for _ in range(worker_count)]
        await queue.join()
        for w in workers:
            w.cancel()
        await asyncio.gather(*workers, return_exceptions=True)
        return result

    async def interact(
        self,
        query: str,
        *,
        agent_config: BrowserAgentConfig | None = None,
    ) -> BrowserAgentResult:
        cdp_endpoint = await self._browser_manager.get_websocket_debugger_url()
        command = f"agent-browser --cdp {cdp_endpoint} snapshot"
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            self._logger.error(
                msg="Pre snapshot failed",
                tag="INTERACT PRE SNAPSHOT",
                error=result.stderr or result.stdout,
            )
            raise RuntimeError(
                f"snapshot error (exit {result.returncode}): {result.stderr or result.stdout}"
            )

        snapshot = result.stdout

        return await execute(
            query=query,
            deps=Deps(cdp_endpoint=cdp_endpoint, page_snapshot=snapshot),
            config=agent_config,
        )
