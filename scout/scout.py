from .adapters.Playwright import PlaywrightAdapter, Response, TIMEOUT
from .core import Action, CrawlConfig
from .adapters.browser_manager import BrowserManager, BrowserManagerConfig
from contextlib import asynccontextmanager
import json, subprocess
from asyncio.queues import Queue

from .agents.browser_agent import BrowserAgentConfig, BrowserAgentResult, Deps, execute
from .logger import get_logger


async def get_response(res: Response):
    try:
        # 1. Ensure it's JSON
        content_type = res.request.headers.get("content-type", "")
        if "application/json" not in content_type:
            return None

        # 2. Check operationName from request body
        post_data = res.request.post_data
        if not post_data:
            return None

        payload = json.loads(post_data)

        if payload.get("operationName") != "fetchPlaylistContents":
            return None

        # 3. Now safely parse response body
        body = json.loads((await res.body()).decode())

        items = body["playlistV2"]["content"]["items"]
        tracks = []
        for item in items:
            try:
                track = item["itemV2"]["data"]
                tracks.append(
                    {
                        "name": track["name"],
                        "artists": [
                            a["profile"]["name"] for a in track["artists"]["items"]
                        ],
                        "album": track["albumOfTrack"]["name"],
                        "duration_ms": track["trackDuration"]["totalMilliseconds"],
                        "uri": track["uri"],
                        "added_at": item["addedAt"]["isoString"],
                    }
                )
            except Exception:
                continue

        return tracks

    except Exception as e:
        print(e)
        return None


# self._crawler.set_network_rule(
#         rule = NetworkRule(
#         match_url=re.compile(r"/query(?:/|$)"),
#         on_request=lambda req: ...,
#         on_response=get_response,
#         log_request=False,
#         log_response=False
#     )
# )


class Scout:
    def __init__(self, *, browser_config: BrowserManagerConfig | None = None):
        self._crawler = PlaywrightAdapter()
        self._browser_manager: BrowserManager = BrowserManager(
            browser_config or BrowserManagerConfig()
        )
        self._logger = get_logger("SCOUT")

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

    async def crawl(self, url: str, config: CrawlConfig):
        queue = Queue(config.page_limit * config.max_depth)
        async with self._crawler as crawler:
            doc = await crawler.scrape(url)

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
