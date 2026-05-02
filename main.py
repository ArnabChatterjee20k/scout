import asyncio
from pathlib import Path

from scout.core import Action, Selector
from scout.scout import Scout
from scout.agents.browser_agent import BrowserAgentConfig
from scout.adapters.browser_manager import BrowserManagerConfig

# Where ``file_tool`` writes (set ``BrowserAgentConfig.output_dir`` for ``interact``).
PLAYLIST_OUTPUT_DIR = Path("spotify_playlist_export")


async def run_example_com() -> None:
    """Open a Spotify playlist, then run the browser agent to scroll and append rows to disk (JSONL)."""
    url = "https://open.spotify.com/playlist/6z0lE29bRXUYlrGnwxclRN"
    actions = []
    async with Scout().start() as scout:
        await scout.set_timeout(60_000).scrape(url, actions)
        agent_result = await scout.interact(
            "Extract every song from this playlist as (name, album, duration, artists). "
            "scroll the playlist container until no new rows appear, and after each batch call file_tool "
            "(file_type txt, mode append, path playlist/softy.csv) to append one csv row per line "
            "(fields: name, album, duration, artists). "
            "Do not paste the full list in chat. When done, reply with the file path, approximate row count, and format (csv).",
            agent_config=BrowserAgentConfig(output_dir=PLAYLIST_OUTPUT_DIR),
        )
        print(agent_result.output)
        print(f"Files under: {PLAYLIST_OUTPUT_DIR.resolve()}")
        if agent_result.limit_reached:
            print("note: usage limit reached")


async def run_heavier_page() -> None:
    """
    More DOM + network than example.com; still static enough for a smoke test.
    Tune the ``load_state`` action if the site is chatty (networkidle can time out).
    """
    url = "https://github.com/xhluca/bm25s"
    actions = [
        # Wait until network is quiet (useful before asserting on dynamic UIs).s
    ]
    from pydantic import BaseModel

    class Features(BaseModel):
        name: str
        feature: str

    class Feedbacks(BaseModel):
        features: list[Features]
        images: list[str]

    # ``headless`` must be set on the config before ``start()`` — the browser is already running after that.
    async with Scout(
        browser_config=BrowserManagerConfig(headless=False),
    ).start() as scout:
        doc = await scout.set_timeout(30000).scrape(url, actions)
        # ``scrape`` leaves ``markdown=None`` until ``to_markdown()``; ``extract_with_agent`` fills it if needed.
        # print(doc.to_markdown())
        query = f"""
                title: {doc.metadata.get('title')}
                url: {doc.metadata.get("url")}
                """
        print(doc.metadata)
        # print(doc.get_relevant_sections(query, top_k=10))


def _print_doc_summary(doc, *, label: str) -> None:
    print(f"\n--- {label} ---")
    if doc is None:
        print("scrape returned None")
        return
    print("responses:", len(getattr(doc, "response", []) or []))
    print("screenshots:", len(getattr(doc, "screenshots", []) or []))
    if getattr(doc, "metadata", None):
        print("title:", doc.metadata.get("title"))
        print("http status:", doc.metadata.get("status"))
    # with open('test.md','w') as f:
    #     f.write(doc.to_markdown())

    for response in doc.response:
        print(response.url, "->", response.body)
    print("title:", doc.metadata.get("title"))
    print("http status:", doc.metadata.get("status"))
    print("html length:", len(doc.html))
    print("screenshot count:", len(doc.screenshots))
    print("metadata keys:", sorted(doc.metadata.keys()))


async def main() -> None:
    # await run_example_com()
    await run_heavier_page()


if __name__ == "__main__":
    asyncio.run(main())
