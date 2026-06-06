"""
File export logic — copies metadata.json and cover.jpg from
the Audiobookshelf media folder to the export destination.
"""

import os
import shutil

MEDIA_ROOT = os.environ.get("ABS_MEDIA_ROOT", "/media/Audiobooks")


def export_items(items, export_path):
    """
    Export metadata and cover files for a list of items.

    Args:
        items: list of dicts with keys: id, rel_path, title, authors
        export_path: destination root directory

    Returns:
        (results_list, counts_dict)
        Each result: {id, title, rel_path, metadata_status, cover_status, overall_status, overall_class}
    """
    results = []
    metadata_copied = 0
    cover_copied = 0

    # Ensure export root exists
    if not os.path.isdir(export_path):
        try:
            os.makedirs(export_path, exist_ok=True)
        except Exception as e:
            results.append({
                "id": None, "title": "N/A", "rel_path": "N/A",
                "metadata_status": "N/A", "cover_status": "N/A",
                "overall_status": f"Cannot create export directory: {e}",
                "overall_class": "error",
            })
            return results, {"metadata": 0, "cover": 0}

    for item in items:
        result = _export_single_item(item, export_path)
        results.append(result)
        if result.get("metadata_copied"):
            metadata_copied += 1
        if result.get("cover_copied"):
            cover_copied += 1

    return results, {"metadata": metadata_copied, "cover": cover_copied}


def export_items_stream(items, export_path):
    """
    Generator that exports items one by one, yielding progress events.

    Yields dicts with:
      - type: "progress" | "error" | "done"
      - For "progress": current, total, result (single item result)
      - For "error": message
      - For "done": results, counts, file_counts
    """
    total = len(items)

    if not os.path.isdir(export_path):
        try:
            os.makedirs(export_path, exist_ok=True)
        except Exception as e:
            yield {"type": "error", "message": f"Cannot create export directory: {e}"}
            return

    results = []
    metadata_copied = 0
    cover_copied = 0

    for i, item in enumerate(items):
        result = _export_single_item(item, export_path)
        results.append(result)

        if result.get("metadata_copied"):
            metadata_copied += 1
        if result.get("cover_copied"):
            cover_copied += 1

        yield {
            "type": "progress",
            "current": i + 1,
            "total": total,
            "result": result,
        }

        try:
            import gevent
            gevent.sleep(0)
        except ImportError:
            pass

    counts = {"success": 0, "skipped": 0, "error": 0}
    for r in results:
        cls = r.get("overall_class", "error")
        if cls in counts:
            counts[cls] += 1

    yield {
        "type": "done",
        "counts": counts,
        "file_counts": {"metadata": metadata_copied, "cover": cover_copied},
    }


def _export_single_item(item, export_path):
    """Copy metadata.json and cover.jpg for one item."""
    item_id = item["id"]
    rel_path = item["rel_path"]
    title = item.get("title", "")

    source_dir = os.path.join(MEDIA_ROOT, str(item_id))
    source_metadata = os.path.join(source_dir, "metadata.json")
    source_cover = os.path.join(source_dir, "cover.jpg")

    has_metadata = os.path.isfile(source_metadata)
    has_cover = os.path.isfile(source_cover)

    if not has_metadata and not has_cover:
        return {
            "id": item_id, "title": title, "rel_path": rel_path,
            "metadata_status": "Not found", "cover_status": "Not found",
            "overall_status": "Skipped — no source files",
            "overall_class": "skipped",
            "metadata_copied": False, "cover_copied": False,
        }

    dest_dir = os.path.join(export_path, rel_path)

    # Create destination directory
    try:
        os.makedirs(dest_dir, exist_ok=True)
    except Exception as e:
        return {
            "id": item_id, "title": title, "rel_path": rel_path,
            "metadata_status": "N/A", "cover_status": "N/A",
            "overall_status": f"Cannot create directory: {e}",
            "overall_class": "error",
            "metadata_copied": False, "cover_copied": False,
        }

    result = {
        "id": item_id, "title": title, "rel_path": rel_path,
        "metadata_copied": False, "cover_copied": False,
    }

    # Copy metadata.json
    if has_metadata:
        result["metadata_status"], result["metadata_copied"] = _copy_file(
            source_metadata, os.path.join(dest_dir, "metadata.json")
        )
    else:
        result["metadata_status"] = "Not found"

    # Copy cover.jpg
    if has_cover:
        result["cover_status"], result["cover_copied"] = _copy_file(
            source_cover, os.path.join(dest_dir, "cover.jpg")
        )
    else:
        result["cover_status"] = "Not found"

    # Determine overall status
    any_copied = result["metadata_copied"] or result["cover_copied"]
    any_error = "Error" in result.get("metadata_status", "") or "Error" in result.get("cover_status", "")

    if any_error:
        result["overall_status"] = "Completed with errors"
        result["overall_class"] = "error"
    elif any_copied:
        result["overall_status"] = "OK"
        result["overall_class"] = "success"
    else:
        result["overall_status"] = "Skipped"
        result["overall_class"] = "skipped"

    return result


def _copy_file(source, destination):
    """Copy a single file. Returns (status_message, success_bool)."""
    try:
        shutil.copy(source, destination)
        return "Copied", True
    except shutil.SameFileError:
        return "Already exists", True
    except Exception as e:
        return f"Error: {e}", False
