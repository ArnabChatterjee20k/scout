from __future__ import annotations

import re

import pytest

from scout.core import Action, Selector

from tests.e2e.helpers import (
    E2E_TIMEOUT_MS,
    assert_has_main_document_request,
    assert_http_ok,
)

EXPECTED_TIMELINE_TIMES = [
    "09:00",
    "09:15",
    "09:30",
    "09:45",
    "10:00",
    "10:15",
    "10:30",
    "10:45",
    "11:00",
    "11:15",
    "11:30",
    "11:45",
]

_MERGE_TIMELINE_JS = """() => {
  if (!window.__grabbedTimes) window.__grabbedTimes = [];
  document.querySelectorAll(".time-entry").forEach(function (el) {
    var t = el.dataset.time;
    if (window.__grabbedTimes.indexOf(t) === -1) window.__grabbedTimes.push(t);
  });
  document.body.setAttribute("data-grabbed-merged", window.__grabbedTimes.join("|"));
}"""

_COLLECT_TIMELINE_JS = """() => {
  var times = Array.prototype.map.call(document.querySelectorAll(".time-entry"), function (el) {
    return el.dataset.time;
  });
  document.body.setAttribute("data-collected", times.join("|"));
}"""


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_action_goto(scout_instance, e2e_server_url: str) -> None:
    chain = f"{e2e_server_url}/nav_chain.html"
    target = f"{e2e_server_url}/nav_target.html"
    doc = await scout_instance.set_timeout(E2E_TIMEOUT_MS).scrape(
        chain,
        [
            Action(kind="goto", selector=None, value=target),
        ],
    )
    assert_http_ok(doc)
    assert doc.metadata["title"] == "Nav Target Page"
    assert "target-marker-ok" in doc.html
    assert_has_main_document_request(doc)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_action_back_and_forward(scout_instance, e2e_server_url: str) -> None:
    chain = f"{e2e_server_url}/nav_chain.html"
    target = f"{e2e_server_url}/nav_target.html"
    doc = await scout_instance.set_timeout(E2E_TIMEOUT_MS).scrape(
        chain,
        [
            Action(kind="goto", selector=None, value=target),
            Action(kind="back", selector=None, value=None),
            Action(kind="forward", selector=None, value=None),
        ],
    )
    assert_http_ok(doc)
    assert doc.metadata["title"] == "Nav Target Page"
    assert "target-marker-ok" in doc.html


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_action_reload_increments_probe(
    scout_instance, e2e_server_url: str
) -> None:
    url = f"{e2e_server_url}/reload_probe.html?e2e=reload"
    doc = await scout_instance.set_timeout(E2E_TIMEOUT_MS).scrape(
        url,
        [
            Action(kind="reload", selector=None, value=None),
        ],
    )
    assert_http_ok(doc)
    assert 'data-reload-count="2"' in doc.html


@pytest.mark.e2e
@pytest.mark.parametrize(
    "submit_selector",
    [
        Selector(kind="css", value="#submit"),
        Selector(kind="tag", value="button"),
        Selector(kind="xpath", value="//button[@id='submit']"),
        Selector(kind="text", value="Submit"),
    ],
)
@pytest.mark.asyncio
async def test_action_click_with_selector_kinds(
    scout_instance,
    e2e_server_url: str,
    submit_selector: Selector,
) -> None:
    doc = await scout_instance.set_timeout(E2E_TIMEOUT_MS).scrape(
        f"{e2e_server_url}/index.html",
        [
            Action(
                kind="type", selector=Selector(kind="css", value="#name"), value="Scout"
            ),
            Action(kind="click", selector=submit_selector, value=None),
        ],
    )
    assert_http_ok(doc)
    assert "Hello Scout" in doc.html


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_action_type_and_screenshot(scout_instance, e2e_server_url: str) -> None:
    shots: list[bytes] = []
    doc = await scout_instance.set_timeout(E2E_TIMEOUT_MS).scrape(
        f"{e2e_server_url}/index.html",
        [
            Action(
                kind="type", selector=Selector(kind="css", value="#name"), value="Ada"
            ),
            Action(
                kind="screenshot",
                selector=None,
                value=None,
                on_complete=lambda png, _url: shots.append(png),
            ),
        ],
    )
    assert_http_ok(doc)
    assert "Ada" in doc.html or "ready" in doc.html
    assert doc.screenshots == []
    assert len(shots) == 1
    assert isinstance(shots[0], bytes)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_action_press_enter_submits_complex(
    scout_instance, e2e_server_url: str
) -> None:
    doc = await scout_instance.set_timeout(E2E_TIMEOUT_MS).scrape(
        f"{e2e_server_url}/complex.html",
        [
            Action(
                kind="click", selector=Selector(kind="css", value="#commit"), value=None
            ),
            Action(
                kind="press",
                selector=Selector(kind="css", value="#commit"),
                value="Enter",
            ),
        ],
    )
    assert_http_ok(doc)
    assert "submitted-enter" in doc.html


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_action_hover_sets_data_hovered(
    scout_instance, e2e_server_url: str
) -> None:
    doc = await scout_instance.set_timeout(E2E_TIMEOUT_MS).scrape(
        f"{e2e_server_url}/complex.html",
        [
            Action(
                kind="hover",
                selector=Selector(kind="css", value="#hover-zone"),
                value=None,
            ),
        ],
    )
    assert_http_ok(doc)
    assert 'data-hovered="true"' in doc.html


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_action_scroll_then_run_js_scroll_y(
    scout_instance, e2e_server_url: str
) -> None:
    doc = await scout_instance.set_timeout(E2E_TIMEOUT_MS).scrape(
        f"{e2e_server_url}/complex.html",
        [
            Action(kind="scroll", selector=None, value="2400"),
            Action(
                kind="run_js_code",
                selector=None,
                value="() => document.body.setAttribute('data-scroll-y', String(window.scrollY))",
            ),
        ],
    )
    assert_http_ok(doc)
    assert "data-scroll-y=" in doc.html
    assert 'data-scroll-y="0"' not in doc.html


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_action_screenshot_twice(scout_instance, e2e_server_url: str) -> None:
    shots: list[bytes] = []
    doc = await scout_instance.set_timeout(E2E_TIMEOUT_MS).scrape(
        f"{e2e_server_url}/index.html",
        [
            Action(
                kind="screenshot",
                selector=None,
                value=None,
                on_complete=lambda png, _url: shots.append(png),
            ),
            Action(
                kind="screenshot",
                selector=None,
                value=None,
                on_complete=lambda png, _url: shots.append(png),
            ),
        ],
    )
    assert doc.screenshots == []
    assert len(shots) == 2
    assert all(isinstance(s, bytes) for s in shots)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_action_run_js_changes_title(scout_instance, e2e_server_url: str) -> None:
    doc = await scout_instance.set_timeout(E2E_TIMEOUT_MS).scrape(
        f"{e2e_server_url}/index.html",
        [
            Action(
                kind="run_js_code",
                selector=None,
                value="() => { document.title = 'E2E JS Title'; }",
            ),
        ],
    )
    assert doc.metadata["title"] == "E2E JS Title"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_selector_load_state_wait_then_click(
    scout_instance, e2e_server_url: str
) -> None:
    doc = await scout_instance.set_timeout(E2E_TIMEOUT_MS).scrape(
        f"{e2e_server_url}/index.html",
        [
            Action(
                kind="click",
                selector=Selector(kind="load_state", value="load"),
                value=None,
            ),
            Action(
                kind="type", selector=Selector(kind="css", value="#name"), value="LS"
            ),
            Action(
                kind="click", selector=Selector(kind="css", value="#submit"), value=None
            ),
        ],
    )
    assert_http_ok(doc)
    assert "Hello LS" in doc.html


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_selector_url_wait_matches_current_page(
    scout_instance, e2e_server_url: str
) -> None:
    target = f"{e2e_server_url}/nav_target.html"
    doc = await scout_instance.set_timeout(E2E_TIMEOUT_MS).scrape(
        target,
        [
            Action(
                kind="click",
                selector=Selector(kind="url", value="**/nav_target.html"),
                value=None,
            ),
        ],
    )
    assert_http_ok(doc)
    assert "target-marker-ok" in doc.html


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_nested_layouts_scroll_feed_collect_times(
    scout_instance,
    e2e_server_url: str,
) -> None:
    """
    Nested layout regions (app → sidebar/main → inner) with a short inner #feed.
    Time rows load in batches as the feed is scrolled toward the bottom; actions
    hover the feed, issue repeated scroll deltas, merge seen times into
    data-grabbed-merged, then snapshot data-collected.
    """
    url = f"{e2e_server_url}/scroll_timeline.html"
    actions: list[Action] = [
        Action(kind="hover", selector=Selector(kind="css", value="#feed"), value=None),
    ]
    actions.extend(Action(kind="scroll", selector=None, value="140") for _ in range(22))
    actions.append(Action(kind="run_js_code", selector=None, value=_MERGE_TIMELINE_JS))
    actions.extend(Action(kind="scroll", selector=None, value="140") for _ in range(14))
    actions.append(
        Action(kind="run_js_code", selector=None, value=_COLLECT_TIMELINE_JS)
    )

    doc = await scout_instance.set_timeout(E2E_TIMEOUT_MS).scrape(url, actions)
    assert_http_ok(doc)
    assert "layout-sidebar-main" in doc.html
    assert "layout-main-inner" in doc.html
    assert 'data-grabbed-merged="' in doc.html
    assert 'data-collected="' in doc.html

    collected_m = re.search(r'data-collected="([^"]*)"', doc.html)
    assert collected_m is not None
    collected = [x for x in collected_m.group(1).split("|") if x]
    assert collected == EXPECTED_TIMELINE_TIMES
    merged_m = re.search(r'data-grabbed-merged="([^"]*)"', doc.html)
    assert merged_m is not None
    merged = [x for x in merged_m.group(1).split("|") if x]
    assert merged == EXPECTED_TIMELINE_TIMES


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_complex_consent_and_main_app(
    scout_instance, e2e_server_url: str
) -> None:
    doc = await scout_instance.set_timeout(E2E_TIMEOUT_MS).scrape(
        f"{e2e_server_url}/complex.html",
        [],
    )
    assert_http_ok(doc)
    assert 'data-consent="accepted"' in doc.html
    assert "Complex fixture" in doc.html
