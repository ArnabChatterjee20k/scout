# Recipes

Small, copy-paste-friendly examples for common Scout workflows.

## Spotify playlist → JSON Lines on disk

Large Spotify playlists use a virtualized list; the **browser agent** scrolls and appends rows with **`file_tool`** so tracks are not held only in the chat context.

### Requirements

- Repo dependencies: `uv sync`
- **Agent-browser** CLI available on your `PATH`
- **`GOOGLE_API_KEY`** (or your configured provider keys) in `.env` — see `scout/agents/__init__.py`
- Spotify may require you to be logged in on the web player; use **`--headed`** once to sign in if headless fails

### Run

From the **repository root**:

```bash
uv run python recipes/spotify_playlist_copy.py \
  --playlist-url "https://open.spotify.com/playlist/YOUR_PLAYLIST_ID"
```

Use a visible browser (useful for login or debugging):

```bash
uv run python recipes/spotify_playlist_copy.py --headed --playlist-url "https://open.spotify.com/playlist/..."
```

Custom output folder and relative file path:

```bash
uv run python recipes/spotify_playlist_copy.py \
  --output-dir ./my_export \
  --rel-file playlist/tracks.jsonl \
  --playlist-url "https://open.spotify.com/playlist/..."
```

### Output

By default, tracks are appended under `spotify_playlist_export/playlist/songs.jsonl` (one JSON object per line). Adjust `--output-dir` and `--rel-file` as needed.

Respect Spotify’s terms of service and only export playlists you’re allowed to access.
