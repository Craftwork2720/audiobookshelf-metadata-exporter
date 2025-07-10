import os
import json
import shutil
import csv

# Define paths for CSV files
CSV_DB_PATH = os.environ.get("ABS_CSV_DB_PATH", "/abs-data/csv_db")
LIBRARIES_CSV = os.path.join(CSV_DB_PATH, "libraries.csv")
LIBRARY_ITEMS_CSV = os.path.join(CSV_DB_PATH, "library_items.csv")

# ABS_MEDIA_ROOT is now the base path where actual audiobook folders (named by ID) reside
ABS_MEDIA_ROOT = os.environ.get("ABS_MEDIA_ROOT", "/media/Audiobooks")

# Helper function to read a CSV file into a list of dictionaries
def read_csv_to_dicts(filepath):
    data = []
    if not os.path.exists(filepath):
        print(f"Błąd: Plik CSV nie istnieje: {filepath}")
        return data
    try:
        with open(filepath, mode='r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                data.append(row)
    except Exception as e:
        print(f"Błąd odczytu pliku CSV '{filepath}': {e}")
    return data

def list_library_names():
    """Reads libraries from CSV and returns their names."""
    libraries = read_csv_to_dicts(LIBRARIES_CSV)
    return [lib['name'] for lib in libraries if 'name' in lib]

def get_library_id_by_name(name):
    """Reads libraries from CSV and returns ID for a given name."""
    libraries = read_csv_to_dicts(LIBRARIES_CSV)
    for lib in libraries:
        if lib.get('name') == name:
            return lib.get('id')
    return None

def get_items_by_library(lib_id):
    """Reads library items from CSV for a given library ID.
    Only extracts ID, path, title, authorNamesFirstLast for display and path construction."""
    all_items = read_csv_to_dicts(LIBRARY_ITEMS_CSV)
    items_for_lib = []
    for item in all_items:
        if (item.get('libraryId') == str(lib_id) and
            item.get('mediaType') == 'book' and
            item.get('isMissing') in ['0', 'false', 'False', False]):
            
            # Zmieniamy 'relPath' na 'path' zgodnie z Twoim życzeniem
            items_for_lib.append((
                item.get('id'),
                item.get('relPath'), # Tutaj wciąż czytamy 'relPath' z CSV, bo tak się nazywa kolumna.
                                     # Ale dalej w kodzie będziemy to nazywać 'path'.
                item.get('title'),
                item.get('authorNamesFirstLast')
            ))
    return items_for_lib

def get_source_item_path(item_id):
    """Constructs the expected source path for an item based on its ID."""
    return os.path.join(ABS_MEDIA_ROOT, str(item_id))

def copy_and_write_metadata(item_id, export_base_path, path, title, author):
    """Copies metadata.json and cover.jpg from ABS_MEDIA_ROOT/item_id to export_base_path/path, IF THEY EXIST.
    Does NOT create destination folder if nothing is to be copied."""
    
    # Source paths for metadata.json and cover.jpg based on ABS_MEDIA_ROOT and item_id
    source_item_folder = get_source_item_path(item_id)
    source_metadata_path = os.path.join(source_item_folder, "metadata.json")
    source_cover_path = os.path.join(source_item_folder, "cover.jpg")

    # Check if there's anything to copy BEFORE creating the destination directory
    has_metadata_source = os.path.exists(source_metadata_path)
    has_cover_source = os.path.exists(source_cover_path)

    if not has_metadata_source and not has_cover_source:
        return False, {
            "metadata_status_text": "Brak w źródle", "metadata_class": "missing",
            "cover_status_text": "Brak w źródle", "cover_class": "missing",
            "overall_message": "Brak plików do skopiowania", "overall_class": "skipped"
        }

    # Destination folder based on user-provided export_base_path and path from CSV
    # Zmieniamy 'rel_path' na 'path'
    dest_folder = os.path.join(export_base_path, path)

    # Now, if we have something to copy, ensure destination folder exists
    if not os.path.isdir(dest_folder):
        try:
            os.makedirs(dest_folder, exist_ok=True)
        except Exception as e:
            return False, {
                "metadata_status_text": "N/A", "metadata_class": "error",
                "cover_status_text": "N/A", "cover_class": "error",
                "overall_message": f"Błąd tworzenia folderu docelowego: {e}", "overall_class": "error",
                "metadata_copied": False, # No actual files copied here
                "cover_copied": False     # No actual files copied here
            }

    result_details = {
        "metadata_status_text": "", "metadata_class": "",
        "cover_status_text": "", "cover_class": "",
        "overall_message": "OK", "overall_class": "success",
        "metadata_copied": False,
        "cover_copied": False
    }
    overall_success = True

    # --- Attempt to copy metadata.json ---
    if has_metadata_source:
        dest_metadata_path = os.path.join(dest_folder, "metadata.json")
        try:
            shutil.copy(source_metadata_path, dest_metadata_path)
            result_details["metadata_status_text"] = "Skopiowano"
            result_details["metadata_class"] = "copied"
            result_details["metadata_copied"] = True
        except shutil.SameFileError:
            result_details["metadata_status_text"] = "Już istnieje"
            result_details["metadata_class"] = "exists"
            result_details["metadata_copied"] = True
        except Exception as e:
            result_details["metadata_status_text"] = f"Błąd: {e}"
            result_details["metadata_class"] = "error"
            overall_success = False
    else:
        result_details["metadata_status_text"] = "Brak w źródle"
        result_details["metadata_class"] = "missing"

    # --- Attempt to copy cover.jpg ---
    if has_cover_source:
        dest_cover_path = os.path.join(dest_folder, "cover.jpg")
        try:
            shutil.copy(source_cover_path, dest_cover_path)
            result_details["cover_status_text"] = "Skopiowano"
            result_details["cover_class"] = "copied"
            result_details["cover_copied"] = True
        except shutil.SameFileError:
            result_details["cover_status_text"] = "Już istnieje"
            result_details["cover_class"] = "exists"
            result_details["cover_copied"] = True
        except Exception as e:
            result_details["cover_status_text"] = f"Błąd: {e}"
            result_details["cover_class"] = "error"
            overall_success = False
    else:
        result_details["cover_status_text"] = "Brak w źródle"
        result_details["cover_class"] = "missing"

    if not overall_success:
        result_details["overall_message"] = "Wystąpiły błędy"
        result_details["overall_class"] = "error"
    elif not (result_details["metadata_class"] == "copied" or result_details["metadata_class"] == "exists" or \
              result_details["cover_class"] == "copied" or result_details["cover_class"] == "exists"):
        result_details["overall_message"] = "Brak plików do skopiowania"
        result_details["overall_class"] = "skipped"
        overall_success = False

    return overall_success, result_details

def export_items(items, export_path):
    """Exports items to the specified export_path, returning detailed results and counts."""
    results = []
    metadata_count = 0
    cover_count = 0

    if not os.path.isdir(export_path):
        try:
            os.makedirs(export_path, exist_ok=True)
            results.append((None, False, {
                "metadata_status_text": "N/A", "metadata_class": "info",
                "cover_status_text": "N/A", "cover_class": "info",
                "overall_message": f"Utworzono główny katalog docelowy: '{export_path}'", "overall_class": "info",
                "metadata_copied": False, "cover_copied": False
            }))
        except Exception as e:
            results.append((None, False, {
                "metadata_status_text": "N/A", "metadata_class": "error",
                "cover_status_text": "N/A", "cover_class": "error",
                "overall_message": f"Błąd: Główny katalog docelowy ('{export_path}') nie istnieje i nie można go utworzyć: {e}", "overall_class": "error",
                "metadata_copied": False, "cover_copied": False
            }))
            return results, {"metadata_total": metadata_count, "cover_total": cover_count}
        
    # Zmieniamy 'rel_path' na 'path'
    for item_id, path, title, author in items:
        success, details = copy_and_write_metadata(item_id, export_path, path, title, author)
        results.append((item_id, success, details))
        
        if details.get("metadata_copied"):
            metadata_count += 1
        if details.get("cover_copied"):
            cover_count += 1
            
    return results, {"metadata_total": metadata_count, "cover_total": cover_count}