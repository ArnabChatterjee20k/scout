from __future__ import annotations

import pytest

from scout.core import Action, Selector


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_scout_executes_actions_end_to_end(
    scout_instance,
    e2e_server_url: str,
) -> None:
    actions = [
        Action(
            kind="type", selector=Selector(kind="css", value="#name"), value="Scout"
        ),
        Action(
            kind="click", selector=Selector(kind="css", value="#submit"), value=None
        ),
        Action(kind="screenshot", selector=None, value=None),
    ]

    doc = await scout_instance.set_timeout(1200).scrape(
        f"{e2e_server_url}/index.html",
        actions,
    )

    assert doc.metadata["title"] == "Scout E2E"
    assert doc.metadata["status"] == 200
    assert "Hello Scout" in doc.html
    assert len(doc.screenshots) == 1
    assert isinstance(doc.screenshots[0], bytes)
