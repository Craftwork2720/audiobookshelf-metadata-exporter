"""
Audiobookshelf Metadata Exporter — Flask web application.

Reads directly from Audiobookshelf's SQLite database and exports
metadata.json / cover.jpg files to a specified directory.
"""

import os
from flask import Flask, render_template, request, redirect, url_for, flash

import db
import exporter

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(24)

DEFAULT_EXPORT_PATH = os.environ.get("ABS_EXPORT_PATH", "/exported_audiobooks")


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

    return render_template(
        "browse.html",
        items=items,
        library_id=library_id,
        library_name=library_name or "Unknown Library",
        default_export_path=DEFAULT_EXPORT_PATH,
    )


@app.route("/export", methods=["POST"])
def export_items():
    """Export selected items and show results."""
    library_id = request.form.get("library_id")
    export_path = request.form.get("export_path", "").strip()
    item_ids = request.form.getlist("item_ids")

    if not item_ids:
        flash("No items selected.", "warning")
        return redirect(url_for("index"))

    if not export_path:
        flash("Export path is required.", "warning")
        return redirect(url_for("index"))

    # Get full item data for the selected IDs
    try:
        all_items = db.get_items_by_library(library_id)
    except Exception as e:
        flash(f"Database error: {e}", "danger")
        return redirect(url_for("index"))

    selected_items = [item for item in all_items if item["id"] in item_ids]

    # Run export
    results, file_counts = exporter.export_items(selected_items, export_path)

    # Count by status class
    counts = {"success": 0, "skipped": 0, "error": 0}
    for r in results:
        cls = r.get("overall_class", "error")
        if cls in counts:
            counts[cls] += 1

    return render_template(
        "results.html",
        results=results,
        counts=counts,
        file_counts=file_counts,
        library_id=library_id,
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
