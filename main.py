"""
Manual tests from repo root: `python main.py`

Requires Playwright browsers: `playwright install chromium`

Complex sites (SPAs, heavy JS, infinite polling) usually need:
- Waits after load: use an Action whose ``selector`` is
  ``Selector(kind="load_state", value="networkidle")`` (or ``load`` / ``domcontentloaded``).
- Waiting for navigation or URL: ``Selector(kind="url", value="**/path/**")`` with
  ``page.wait_for_url`` semantics in the adapter.
- Targeting content: prefer concrete CSS / text selectors once the shell has rendered.

Those behaviors are expressed as ``Action`` lists below; anything like viewport, user
agent, or ``goto(wait_until=...)`` belongs in the adapter when you add it.
"""

import asyncio

from scout.core import Action, Selector
from scout.scout import Scout


async def run_example_com() -> None:
    """Minimal page: good for sanity-checking clicks and ``run_js_code``."""
    url = "https://example.com"
    actions = [
        Action(
            kind="click",
            selector=Selector(kind="css", value="a"),
            value=None,
        ),
        Action(
            kind="run_js_code",
            selector=None,
            value="() => document.documentElement.outerHTML.length",
        ),
    ]
    doc = await Scout().scrape(url, actions)
    _print_doc_summary(doc, label="example.com")


async def run_heavier_page() -> None:
    """
    More DOM + network than example.com; still static enough for a smoke test.
    Tune the ``load_state`` action if the site is chatty (networkidle can time out).
    """
    url = "https://news.ycombinator.com"
    actions = [
        # Wait until network is quiet (useful before asserting on dynamic UIs).
        Action(
            kind="run_js_code",
            selector=Selector(kind="load_state", value="networkidle"),
            value="() => null",
        ),
        Action(
            kind="run_js_code",
            selector=None,
            value="() => ({ title: document.title, links: document.links.length })",
        ),
    ]
    doc = await Scout().scrape(url, actions)
    _print_doc_summary(doc, label="news.ycombinator.com")


def _print_doc_summary(doc, *, label: str) -> None:
    print(f"\n--- {label} ---")
    print("title:", doc.metadata.get("title"))
    print("http status:", doc.metadata.get("status"))
    print("html length:", len(doc.html))
    print("screenshot count:", len(doc.screenshots))
    print("metadata keys:", sorted(doc.metadata.keys()))


async def main() -> None:
    await run_example_com()
    await run_heavier_page()


if __name__ == "__main__":
    asyncio.run(main())
