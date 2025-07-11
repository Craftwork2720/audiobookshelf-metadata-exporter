# Audiobookshelf Meta Exporter

Export metadata and cover images from your Audiobookshelf instance using Docker.

## Prerequisites

- Docker and Docker Compose installed
- Running Audiobookshelf instance
- DB Browser for SQLite (or similar SQLite tool)

## Setup Instructions

### 1. Export Database Tables to CSV

Using DB Browser for SQLite (or your preferred SQLite tool):

1. Open your Audiobookshelf database file
2. Export the following tables to CSV format:
   - `libraries` → save as `libraries.csv`
   - `libraryitems` → save as `libraryitems.csv`
3. Place both CSV files in the `data/csv_db/` directory

### 2. Copy Metadata Items Folder

Copy the `/items` folder from your Audiobookshelf Docker container:
```bash
cp -r /path/to/audiobookshelf/metadata/items ./data/items
```

### 3. Create Required Directories

Create the following directory structure:

```
├── data/
│   ├── csv_db/
│   │   ├── libraries.csv
│   │   └── libraryitems.csv
│   ├── items/
│   │   └── [copied from audiobookshelf]
│   └── exported/
│       └── [exports will be placed here]
├── docker-compose.yml
└── README.md
```

Create the directories:
```bash
mkdir -p data/csv_db data/items data/exported
```

### 4. Docker Compose Configuration

Create a `docker-compose.yml` file with the following content:

```yaml
services:
  audiobookshelf-exporter:
    image: ghcr.io/craftwork2720/audiobookshelf-meta-exporter:latest
    container_name: audiobookshelf-exporter
    ports:
      - "8080:8080"
    volumes:
      - "./data/csv_db:/abs-data/csv_db:ro"
      - "./data/items:/media/Audiobooks:ro"
      - "./data/exported:/exported_audiobooks:rw"
    environment:
      PORT: 8080
      # You can override default export path here if you want a different default in the UI
      # ABS_EXPORT_DEFAULT_PATH: "/exported_audiobooks"
    restart: unless-stopped
```

### 5. Access the Web Interface

Open your browser and navigate to:
```
http://localhost:8080
```

From the web interface, you can:
- Browse your audiobook library
- Select items to export
- Configure export settings
- Download exported files

## Usage

1. **Access the interface**: Navigate to `http://localhost:8080`
2. **Select library**: Choose a library from the dropdown menu
3. **Enable folder comparison** (optional): Check the "Porównaj metadane z nazwami folderów" box to compare metadata with folder names
4. **Browse and filter**: 
   - Use the search box to filter audiobooks by title or author
   - When folder comparison is enabled, use match filters to show only specific types of matches
5. **Select items**: Choose which audiobooks you want to export using checkboxes
6. **Set export path**: Specify the destination directory for exported files
7. **Export**: Click "Eksportuj zaznaczone" to export selected audiobooks
8. **Review results**: Check the export results table for any errors or issues

## Features

### Folder Name Comparison
The application can compare metadata from your Audiobookshelf database with actual folder names to help identify mismatches:

- **Full Match**: Both title and author match the folder name
- **Title Only**: Only the title matches
- **Authors Only**: Only the author matches  
- **No Match**: Neither title nor author match
- **Parse Error**: Unable to parse the folder name

### Folder Name Format Support
The parser supports various folder naming conventions:
- `Author - Title`
- `Author - Title (Year)`
- `Author - Title [audiobook]`
- `Author - Title czyta Narrator`
- `Author - Title tom 1`
- `Author - Title cykl Series`

## File Structure

```
project-root/
├── docker-compose.yml
├── README.md
└── data/
    ├── csv_db/
    │   ├── libraries.csv        # Exported from Audiobookshelf DB
    │   └── libraryitems.csv     # Exported from Audiobookshelf DB
    ├── items/                   # Copied from Audiobookshelf container
    │   └── [metadata files]
    └── exported/                # Export destination
        └── [exported audiobooks will appear here]
```
