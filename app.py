"""
Audiobookshelf Metadata Exporter — Flask web application.

Reads directly from Audiobookshelf's SQLite database and exports
metadata.json / cover.jpg files to a specified directory.
"""

import os
import threading
import uuid
from flask import Flask, render_template, request, redirect, url_for, flash

import db
import exporter

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(24)

DEFAULT_EXPORT_PATH = os.environ.get("ABS_EXPORT_PATH", "/exported_audiobooks")

# In-memory job store for export progress polling
jobs = {}
jobs_lock = threading.Lock()


@app.route("/")
def index():
    """Landing page — library selector."""
    libraries = db.get_book_libraries()
    return render_template("index.html", libraries=libraries)


@app.route("/browse", methods=["POST"])
def browse():
    """Show items for the selected library."""
    library_id = request.form.get("library_id")
    if not library_id:
        flash("Please select a library.", "warning")
        return redirect(url_for("index"))

    try:
        library_name = db.get_library_name(library_id)
        items = db.get_items_by_library(library_id)
    except Exception as e:
        flash(f"Database error: {e}", "danger")
        return redirect(url_for("index"))

    default_path = os.path.join(DEFAULT_EXPORT_PATH, library_name or "Unknown")

    return render_template(
        "browse.html",
        items=items,
        library_id=library_id,
        library_name=library_name or "Unknown Library",
        default_export_path=default_path,
    )


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
    }


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
