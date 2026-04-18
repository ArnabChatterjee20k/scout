import asyncio
from pathlib import Path

from scout.adapters.browser_manager import BrowserManagerConfig
from scout.agents.browser_agent import BrowserAgentConfig
from scout.scout import Scout

PLAYLIST_OUTPUT_DIR = Path("spotify_playlist_export")


async def main() -> None:
    """Open a Spotify playlist and export tracks via browser agent to JSONL."""
    playlist_url = "https://open.spotify.com/playlist/6z0lE29bRXUYlrGnwxclRN"
    async with Scout(
        browser_config=BrowserManagerConfig(headless=True),
    ).start() as scout:
        await scout.set_timeout(60_000).scrape(playlist_url, actions=[])
        result = await scout.interact(
            "Extract every song from this playlist as (name, album, duration, artists). "
            "scroll the playlist container until no new rows appear, and after each batch call file_tool "
            "(file_type txt, mode append, path playlist/songs.jsonl) to append one JSON object per line. "
            "Do not paste the full list in chat. When done, reply with the file path, approximate row count, and format (JSONL).",
            agent_config=BrowserAgentConfig(output_dir=PLAYLIST_OUTPUT_DIR),
        )
        print(result.output)
        print(f"Files under: {PLAYLIST_OUTPUT_DIR.resolve()}")
        if result.limit_reached:
            print("note: usage limit reached")


if __name__ == "__main__":
    asyncio.run(main())
