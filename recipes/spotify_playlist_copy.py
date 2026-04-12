#!/usr/bin/env python3
"""
Export a Spotify playlist to disk using Scout's browser agent.

Prerequisites
-------------
- ``uv sync`` (or your env) with Scout dependencies installed.
- ``agent-browser`` on your ``PATH`` (see Agent-browser install docs).
- ``GOOGLE_API_KEY`` in ``.env`` at the repo root (or exported) for the LLM.
- A normal Spotify **web** session: open the playlist in Chromium once if the agent
  must be logged in (headless may still need cookies depending on your setup).

Run
---
From the repository root::

    uv run python recipes/spotify_playlist_copy.py \\
        --playlist-url "https://open.spotify.com/playlist/YOUR_ID"

Output defaults to ``./spotify_playlist_export/playlist/songs.jsonl`` (JSON Lines).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Running this file adds ``recipes/`` to sys.path first; ensure the repo root is importable.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scout.adapters.browser_manager import BrowserManagerConfig
from scout.agents.browser_agent import BrowserAgentConfig
from scout.scout import Scout

DEFAULT_PLAYLIST = "https://open.spotify.com/playlist/6z0lE29bRXUYlrGnwxclRN"
DEFAULT_OUTPUT_DIR = Path("spotify_playlist_export")
DEFAULT_REL_FILE = "playlist/songs.jsonl"


def build_prompt(rel_file: str) -> str:
    return (
        "Extract every track from this Spotify playlist. "
        "For each song capture: name, album, duration, artists (as a list or comma-separated string). "
        "The list may be long and virtualized: scroll the playlist until no new rows load, "
        "and use batch JavaScript (eval) where possible instead of one click per row. "
        "After each batch, append to disk with file_tool: "
        f"file_type txt, mode append, path {rel_file} — "
        "one JSON object per line (JSON Lines). "
        "Do not paste the full track list in chat. "
        "When finished, reply with the file path, approximate track count, and format (JSONL)."
    )


async def run(
    *,
    playlist_url: str,
    output_dir: Path,
    rel_file: str,
    headless: bool,
    timeout_ms: int,
) -> None:
    output_dir = output_dir.expanduser().resolve()
    prompt = build_prompt(rel_file)

    async with Scout(
        browser_config=BrowserManagerConfig(headless=headless),
    ).start() as scout:
        await scout.set_timeout(timeout_ms).scrape(playlist_url, actions=[])
        result = await scout.interact(
            prompt,
            agent_config=BrowserAgentConfig(output_dir=output_dir),
        )
        print(result.output)
        print(f"Output directory: {output_dir}")
        if result.limit_reached:
            print(
                "Warning: run hit the model/tool usage limit — increase BrowserAgentConfig if needed."
            )


def main() -> None:
    p = argparse.ArgumentParser(
        description="Copy a Spotify playlist to JSONL via Scout."
    )
    p.add_argument(
        "--playlist-url",
        default=DEFAULT_PLAYLIST,
        help="Spotify playlist URL (default: built-in example playlist)",
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for file_tool writes (default: {DEFAULT_OUTPUT_DIR})",
    )
    p.add_argument(
        "--rel-file",
        default=DEFAULT_REL_FILE,
        help=f"Path under output-dir for JSONL (default: {DEFAULT_REL_FILE})",
    )
    p.add_argument(
        "--headed",
        action="store_true",
        help="Show a visible browser window (default: headless)",
    )
    p.add_argument(
        "--timeout-ms",
        type=int,
        default=60_000,
        help="Page navigation / scrape timeout in ms (default: 60000)",
    )
    args = p.parse_args()

    asyncio.run(
        run(
            playlist_url=args.playlist_url,
            output_dir=args.output_dir,
            rel_file=args.rel_file,
            headless=not args.headed,
            timeout_ms=args.timeout_ms,
        )
    )


if __name__ == "__main__":
    main()
