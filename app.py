"""
Audiobookshelf Metadata Exporter — Flask web application.

Reads directly from Audiobookshelf's SQLite database and exports
metadata.json / cover.jpg files to a specified directory.
"""

import importlib.util
import os
import threading
import uuid
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash

import db
import exporter

# Load custom matcher.py from /data if present, otherwise use built-in
_custom_matcher_path = "/data/matcher.py"
if os.path.isfile(_custom_matcher_path):
    spec = importlib.util.spec_from_file_location("matcher", _custom_matcher_path)
    matcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(matcher)
else:
    import matcher

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(24)

DEFAULT_EXPORT_PATH = os.environ.get("EXPORT_PATH", "/exported")
MATCHER_ENABLED = os.environ.get("MATCHER_ENABLED", "false").lower() in ("true", "1", "yes")

# Per-library export paths: LIBRARY_EXPORT_PATHS="Audiobooki:/data/Polskie,Angielskie:/data/English"
_LIBRARY_PATHS_RAW = os.environ.get("LIBRARY_EXPORT_PATHS", "")
LIBRARY_EXPORT_PATHS = {}
for entry in _LIBRARY_PATHS_RAW.split(","):
    entry = entry.strip()
    if ":" in entry:
        name, path = entry.split(":", 1)
        LIBRARY_EXPORT_PATHS[name.strip()] = path.strip()

# In-memory job store for export progress polling
jobs = {}
jobs_lock = threading.Lock()


@app.route("/")
def index():
    """Landing page — library selector."""
    try:
        libraries = db.get_book_libraries()
    except Exception as e:
        return render_template(
            "error.html",
            error_title="Database Not Found",
            error_message=(
                f"Could not connect to the Audiobookshelf database. "
                f"Check that the file exists and is mounted correctly. ({e})"
            ),
        ), 500
    return render_template("index.html", libraries=libraries)


@app.route("/browse", methods=["GET", "POST"])
def browse():
    """Show items for the selected library."""
    library_id = request.form.get("library_id") or request.args.get("library_id")
    if not library_id:
        flash("Please select a library.", "warning")
        return redirect(url_for("index"))

    # UI toggle overrides env var default
    matcher_param = request.args.get("matcher")
    if matcher_param is not None:
        matcher_enabled = matcher_param.lower() in ("true", "1", "yes")
    else:
        matcher_enabled = MATCHER_ENABLED

    try:
        library_name = db.get_library_name(library_id)
        items = db.get_items_by_library(library_id)
    except Exception as e:
        flash(f"Database error: {e}", "danger")
        return redirect(url_for("index"))

    if matcher_enabled:
        for item in items:
            item["match"] = matcher.compare(
                item.get("title", ""),
                item.get("authors", ""),
                item.get("rel_path", ""),
            )

    # Per-library path overrides default
    if library_name and library_name in LIBRARY_EXPORT_PATHS:
        default_path = LIBRARY_EXPORT_PATHS[library_name]
    else:
        default_path = os.path.join(DEFAULT_EXPORT_PATH, library_name or "Unknown")

    return render_template(
        "browse.html",
        items=items,
        library_id=library_id,
        library_name=library_name or "Unknown Library",
        default_export_path=default_path,
        matcher_enabled=matcher_enabled,
    )


@app.route("/export/zip", methods=["POST"])
def export_zip():
    """Start ZIP export in background thread, return job_id."""
    library_id = request.form.get("library_id")
    export_path = request.form.get("export_path", "").strip()
    select_all = request.form.get("select_all") == "true"
    item_ids = request.form.getlist("item_ids")

    if not select_all and not item_ids:
        return {"error": "No items selected"}, 400
    if not export_path:
        return {"error": "Export path required"}, 400

    try:
        library_name = db.get_library_name(library_id)
        all_items = db.get_items_by_library(library_id)
    except Exception as e:
        return {"error": str(e)}, 500

    if select_all:
        selected_items = all_items
    else:
        id_set = set(item_ids)
        selected_items = [item for item in all_items if item["id"] in id_set]

    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{library_name or 'export'}_{date_str}.zip"
    zip_path = os.path.join(export_path, filename)

    job_id = str(uuid.uuid4())
    job = {
        "status": "running",
        "current": 0,
        "total": len(selected_items),
        "results": [],
        "results_offset": 0,
        "counts": {"success": 0, "skipped": 0, "error": 0},
        "file_counts": {"metadata": 0, "cover": 0},
        "zip_path": zip_path,
    }
    with jobs_lock:
        jobs[job_id] = job

    def run():
        for event in exporter.export_to_zip_stream(selected_items, zip_path):
            with jobs_lock:
                if event["type"] == "progress":
                    job["current"] = event["current"]
                    job["total"] = event["total"]
                    job["results"].append(event["result"])
                elif event["type"] == "done":
                    job["counts"] = event["counts"]
                    job["file_counts"] = event["file_counts"]
                    job["zip_path"] = event["zip_path"]
                    job["status"] = "done"
                elif event["type"] == "error":
                    job["status"] = "error"
                    job["error"] = event["message"]

    threading.Thread(target=run, daemon=True).start()
    return {"job_id": job_id, "zip": True}


@app.route("/export/start", methods=["POST"])
def export_start():
    """Start export in background thread, return job_id."""
    library_id = request.form.get("library_id")
    export_path = request.form.get("export_path", "").strip()
    select_all = request.form.get("select_all") == "true"
    item_ids = request.form.getlist("item_ids")

    if (not select_all and not item_ids) or not export_path:
        return {"error": "Missing items or path"}, 400

    try:
        library_name = db.get_library_name(library_id)
        all_items = db.get_items_by_library(library_id)
    except Exception as e:
        return {"error": str(e)}, 500

    if select_all:
        selected_items = all_items
    else:
        id_set = set(item_ids)
        selected_items = [item for item in all_items if item["id"] in id_set]

    job_id = str(uuid.uuid4())
    job = {
        "status": "running",
        "current": 0,
        "total": len(selected_items),
        "results": [],
        "results_offset": 0,
        "counts": {"success": 0, "skipped": 0, "error": 0},
        "file_counts": {"metadata": 0, "cover": 0},
    }
    with jobs_lock:
        jobs[job_id] = job

    def run():
        for event in exporter.export_items_stream(selected_items, export_path):
            with jobs_lock:
                if event["type"] == "progress":
                    job["current"] = event["current"]
                    job["total"] = event["total"]
                    job["results"].append(event["result"])
                elif event["type"] == "done":
                    job["counts"] = event["counts"]
                    job["file_counts"] = event["file_counts"]
                    job["status"] = "done"
                elif event["type"] == "error":
                    job["status"] = "error"
                    job["error"] = event["message"]

    threading.Thread(target=run, daemon=True).start()
    return {"job_id": job_id}


@app.route("/export/status/<job_id>")
def export_status(job_id):
    """Poll export progress — returns a batch of new results each call."""
    with jobs_lock:
        job = jobs.get(job_id)
    if not job:
        return {"error": "Job not found"}, 404

    offset = job["results_offset"]
    batch = job["results"][offset:offset + 50]
    job["results_offset"] = offset + len(batch)

    return {
        "status": job["status"],
        "current": job["current"],
        "total": job["total"],
        "counts": job["counts"],
        "file_counts": job["file_counts"],
        "new_results": batch,
        "error": job.get("error"),
        "zip_path": job.get("zip_path"),
    }


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
