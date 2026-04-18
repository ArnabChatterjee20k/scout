import asyncio
import re

from scout.core import CrawlConfig
from scout.scout import Scout

START_URL = "https://docs.python.org/3/library/asyncio.html"


async def main() -> None:
    config = CrawlConfig(
        page_limit=10,
        max_depth=2,
        concurrency=2,
        include=[re.compile(r"^https://docs\.python\.org/3/library/")],
    )

    async with Scout().set_headless(True).start() as scout:
        docs = await scout.crawl(START_URL, config)

    print(f"Crawled {len(docs)} pages")
    for i, doc in enumerate(docs, start=1):
        print(f"{i}. {doc.url} | {doc.metadata.get('title')}")


if __name__ == "__main__":
    asyncio.run(main())
