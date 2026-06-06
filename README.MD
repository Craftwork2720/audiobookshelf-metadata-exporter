# Audiobookshelf Metadata Exporter

A web tool to export `metadata.json` and `cover.jpg` files from your Audiobookshelf library to a chosen directory. Reads directly from Audiobookshelf's SQLite database — no CSV export step needed.

## Prerequisites

- Docker and Docker Compose
- A running Audiobookshelf instance with its `absdatabase.sqlite` file accessible

## Quick Start

### 1. Set up volume mounts

Edit `docker-compose.yaml` and update the paths to match your Audiobookshelf installation:

```yaml
volumes:
  - "./config:/config:ro"
  - "./metadata:/metadata:ro"
  - "./data/exported:/exported:rw"
```

- **config** — your Audiobookshelf config directory containing `absdatabase.sqlite` (same as your ABS `./config:/config` mount)
- **metadata** — your Audiobookshelf metadata directory (same as your ABS `./metadata:/metadata` mount)
- **exported** — where exported files will be written

### 2. Create directories

```bash
mkdir -p data/exported
```

### 3. Start the container

```bash
docker compose up -d
```

### 4. Open the web interface

Navigate to [http://localhost:8080](http://localhost:8080).

## Usage

1. **Select a library** from the dropdown on the home page
2. **Browse items** — the table shows title, authors, series, published year, and path
3. **Filter** using the search box or select/deselect all buttons
4. **Set the export path** (defaults to `/exported`)
5. **Click Export** — results show per-item status for `metadata.json` and `cover.jpg`

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `PORT` | `8080` | Web server port |
| `ABS_DATABASE_PATH` | `/config/absdatabase.sqlite` | Path to Audiobookshelf SQLite database |
| `ABS_ITEMS_PATH` | `/metadata/items` | Path to audiobook metadata/items folder |
| `EXPORT_PATH` | `/exported` | Default export destination shown in UI |
| `MATCHER_ENABLED` | `false` | Enable fuzzy matching of metadata against folder names |
| `SECRET_KEY` | random | Flask secret key for session security |

## Local Development (no Docker)

```bash
pip install -r requirements.txt

# Set paths to your local data
export ABS_DATABASE_PATH="./data/absdatabase.sqlite"
export ABS_ITEMS_PATH="./data/items"
export EXPORT_PATH="./data/exported"

python app.py
```

## Building the Docker Image

```bash
docker compose -f docker-compose-build.yaml up --build
```
