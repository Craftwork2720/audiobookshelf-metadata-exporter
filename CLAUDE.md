# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Audiobookshelf metadata exporter — a Flask web app that reads directly from Audiobookshelf's SQLite database (`absdatabase.sqlite`) and exports `metadata.json`/`cover.jpg` files to a user-specified directory. No API calls, no CSV step — just direct SQLite read access.

## Running the App

```bash
# Local (no Docker)
pip install -r requirements.txt
python app.py          # serves on http://localhost:8080

# Docker (dev, local build)
docker compose -f docker-compose-build.yaml up --build

# Docker (production, pre-built image)
docker compose up -d
```

No tests, no linter, no CI are configured.

## Architecture

Four source files:

- **`app.py`** — Flask routes: `/` (library selector), `/browse` (item browser), `/export/start` (background export), `/export/status/<job_id>` (polling). Uses Jinja2 templates in `templates/`.
- **`db.py`** — SQLite database layer. Read-only queries against `absdatabase.sqlite` using Python's built-in `sqlite3`. Functions: `get_book_libraries()`, `get_items_by_library(library_id)`, `get_library_name(library_id)`.
- **`exporter.py`** — File copy logic. Copies `metadata.json` and `cover.jpg` from `ABS_ITEMS_PATH/{item_id}/` to the export destination. Provides both `export_items()` (synchronous) and `export_items_stream()` (generator yielding progress events).
- **`matcher.py`** — Fuzzy matching of ABS metadata (title, authors) against folder names parsed from `rel_path`. Uses normalization (diacritics removal, lowercasing), three similarity strategies (sequence ratio, partial ratio, token overlap), and classifies items as `match`, `partial`, `unknown`, or `no_meta`. Tuned for Polish audiobook folder naming conventions (noise patterns like `czyta`, `[audiobook PL]`, `superprodukcja`). Users can provide a custom `matcher.py` in `/data/` to override the built-in one.

### Export flow

Exports run in background threads via Python's `threading` module. An in-memory job store (`dict` + `threading.Lock`) tracks progress. The frontend polls `/export/status/<job_id>` every 500ms, receiving batches of up to 50 new results per call. Each result has an `overall_class` of `success`, `skipped`, or `error`.

Templates use Bootstrap 5 via CDN. Static CSS in `static/style.css`.

## Database Schema (relevant tables — camelCase names!)

- `libraries` — library definitions (filter to `mediaType='book'`)
- `libraryItems` — central entity, links to `books` via `mediaId`, has `relPath`, `title`, `authorNamesFirstLast`
- `books` — book metadata (title, publishedYear, narrators, etc.)
- `authors` — linked to books via `bookAuthors` junction table
- `series` — linked to books via `bookSeries` junction table (with `sequence`)

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `8080` | Web server port |
| `ABS_DATABASE_PATH` | `/config/absdatabase.sqlite` | Path to Audiobookshelf SQLite database |
| `ABS_ITEMS_PATH` | `/metadata/items` | Path to audiobook metadata/items folder |
| `EXPORT_PATH` | `/data/exported` | Default export destination in UI |
| `MATCHER_ENABLED` | `false` | Enable fuzzy matching of metadata against folder names |
| `SECRET_KEY` | random | Flask secret key |

## Key Design Decisions

- **Direct SQLite access** — reads `absdatabase.sqlite` in read-only mode via `?mode=ro` URI. No CSV exports needed.
- **Read-only source mounts** — database and media volumes are read-only; only the export directory is writable.
- **SQLite version requirement** — Audiobookshelf's DB uses trigger syntax requiring SQLite >= 3.45. The Dockerfile installs `libsqlite3` from Debian trixie to satisfy this (bookworm ships 3.40).
- **No authentication** — the app has no auth layer; it's designed for trusted local/Docker network use.
- **English UI** — all user-facing strings in English.
