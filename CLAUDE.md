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
docker compose -f docker-compose-dev.yaml up --build

# Docker (production, pre-built image)
docker compose up -d
```

No tests, no linter, no CI are configured.

## Architecture

Three source files:

- **`app.py`** — Flask routes (`/`, `/browse`, `/export`). Thin controller layer; delegates to `db` and `exporter` modules. Uses Jinja2 templates in `templates/`.
- **`db.py`** — SQLite database layer. Read-only queries against `absdatabase.sqlite` using Python's built-in `sqlite3`. Functions: `get_book_libraries()`, `get_items_by_library(library_id)`, `get_library_name(library_id)`.
- **`exporter.py`** — File copy logic. Copies `metadata.json` and `cover.jpg` from `ABS_MEDIA_ROOT/{item_id}/` to the export destination.

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
| `ABS_MEDIA_ROOT` | `/media/Audiobooks` | Path to audiobook metadata/items folder |
| `ABS_EXPORT_PATH` | `/exported_audiobooks` | Default export destination in UI |
| `SECRET_KEY` | random | Flask secret key |

## Key Design Decisions

- **Direct SQLite access** — reads `absdatabase.sqlite` in read-only mode via `?mode=ro` URI. No CSV exports needed.
- **Read-only source mounts** — database and media volumes are read-only; only the export directory is writable.
- **Separate templates** — Jinja2 templates in `templates/`, Bootstrap 5 for styling.
- **English UI** — all user-facing strings in English.
