from __future__ import annotations

import pytest

from scout.core import Action, CrawlConfig, ScrollingRule, Selector, VirtualScrollConfig


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_scout_executes_actions_end_to_end(
    scout_instance,
    e2e_server_url: str,
) -> None:
    shots: list[bytes] = []

    actions = [
        Action(
            kind="type", selector=Selector(kind="css", value="#name"), value="Scout"
        ),
        Action(
            kind="click", selector=Selector(kind="css", value="#submit"), value=None
        ),
        Action(
            kind="screenshot",
            selector=None,
            value=None,
            on_complete=lambda png, _url: shots.append(png),
        ),
    ]

    doc = await scout_instance.set_timeout(1200).scrape(
        f"{e2e_server_url}/index.html",
        actions,
    )

    assert doc.metadata["title"] == "Scout E2E"
    assert doc.metadata["status"] == 200
    assert "Hello Scout" in doc.html
    assert doc.screenshots == []
    assert len(shots) == 1
    assert isinstance(shots[0], bytes)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_scout_crawls_linked_pages_end_to_end(
    scout_instance,
    e2e_server_url: str,
) -> None:
    start_url = f"{e2e_server_url}/nav_chain.html"
    target_url = f"{e2e_server_url}/nav_target.html"

    docs = await scout_instance.crawl(
        start_url,
        CrawlConfig(
            page_limit=5,
            max_depth=2,
            concurrency=1,
        ),
    )

    assert [doc.url for doc in docs] == [start_url, target_url]
    assert docs[0].metadata["title"] == "Nav Chain Start"
    assert docs[1].metadata["title"] == "Nav Target Page"
    assert "chain-marker" in docs[0].html
    assert "target-marker-ok" in docs[1].html


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_scout_crawl_respects_max_depth_edge_case(
    scout_instance,
    e2e_server_url: str,
) -> None:
    start_url = f"{e2e_server_url}/nav_chain.html"
    docs = await scout_instance.crawl(
        start_url,
        CrawlConfig(
            page_limit=5,
            max_depth=1,
            concurrency=1,
        ),
    )

    assert [doc.url for doc in docs] == [start_url]
    assert docs[0].metadata["title"] == "Nav Chain Start"
    assert "chain-marker" in docs[0].html


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_scout_crawl_respects_page_limit_edge_case(
    scout_instance,
    e2e_server_url: str,
) -> None:
    start_url = f"{e2e_server_url}/nav_chain.html"
    docs = await scout_instance.crawl(
        start_url,
        CrawlConfig(
            page_limit=1,
            max_depth=5,
            concurrency=1,
        ),
    )

    assert [doc.url for doc in docs] == [start_url]
    assert docs[0].metadata["title"] == "Nav Chain Start"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_scout_crawl_respects_exclude_edge_case(
    scout_instance,
    e2e_server_url: str,
) -> None:
    start_url = f"{e2e_server_url}/nav_chain.html"
    target_url = f"{e2e_server_url}/nav_target.html"
    docs = await scout_instance.crawl(
        start_url,
        CrawlConfig(
            exclude=[target_url],
            page_limit=5,
            max_depth=5,
            concurrency=1,
        ),
    )

    assert [doc.url for doc in docs] == [start_url]
    assert docs[0].metadata["title"] == "Nav Chain Start"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_scout_crawl_without_scrolling_loads_timeline_page(
    scout_instance,
    e2e_server_url: str,
) -> None:
    timeline_url = f"{e2e_server_url}/scroll_timeline.html"
    docs = await scout_instance.crawl(
        timeline_url,
        CrawlConfig(
            page_limit=1,
            max_depth=1,
            concurrency=1,
        ),
    )

    assert len(docs) == 1
    html = docs[0].html
    assert docs[0].metadata["title"] == "Scroll Timeline Layouts"
    assert 'id="feed"' in html
    assert "09:00" in html
    assert "09:30" in html


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_scout_crawl_virtual_scroll_loads_full_timeline(
    scout_instance,
    e2e_server_url: str,
) -> None:
    timeline_url = f"{e2e_server_url}/scroll_timeline.html"
    docs = await scout_instance.crawl(
        timeline_url,
        CrawlConfig(
            page_limit=1,
            max_depth=1,
            concurrency=1,
            scrolling=ScrollingRule(
                virtual_scroll=VirtualScrollConfig(
                    container_selector="#feed",
                    scroll_count=10,
                    wait_after_scroll=0.05,
                    scroll_by="container_height",
                )
            ),
        ),
    )

    assert len(docs) == 1
    html = docs[0].html
    assert "09:00" in html
    assert "11:45" in html
