from .adapters.Playwright import PlaywrightAdapter
from .core import Action


class Scout:
    def __init__(self):
        self._crawler = PlaywrightAdapter()

    async def scrape(self, url: str, actions: list[Action] | None = None):
        actions = actions or []
        async with self._crawler as crawler:
            return await crawler.scrape(url, actions)

    def crawl(self):
        pass

    def interact(self):
        pass
