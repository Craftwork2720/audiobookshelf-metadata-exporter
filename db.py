"""
Database layer for reading Audiobookshelf's SQLite database.

Provides read-only access to absdatabase.sqlite for querying
libraries, items, authors, and series.
"""

import sqlite3
import os

DATABASE_PATH = os.environ.get("ABS_DATABASE_PATH", "/config/absdatabase.sqlite")


def _get_connection():
    """Open a read-only SQLite connection with Row factory."""
    uri = f"file:{DATABASE_PATH}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def get_book_libraries():
    """Return all libraries with mediaType='book'."""
    with _get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name FROM libraries WHERE mediaType = 'book' ORDER BY displayOrder, name"
        ).fetchall()
    return [dict(row) for row in rows]


def get_items_by_library(library_id):
    """
    Return book items for a library with authors and series info.

    Each item: {id, rel_path, title, authors, series, series_sequence}
    """
    query = """
        SELECT
            li.id,
            li.relPath       AS rel_path,
            li.title         AS title,
            b.title          AS book_title,
            b.publishedYear  AS published_year,
            b.narrators      AS narrators,
            li.authorNamesFirstLast AS authors,
            GROUP_CONCAT(
                CASE WHEN s.name IS NOT NULL
                    THEN s.name || ' #' || COALESCE(bs.sequence, '?')
                    ELSE NULL
                END, ', '
            ) AS series
        FROM libraryItems li
        JOIN books b ON b.id = li.mediaId
        LEFT JOIN bookAuthors ba ON ba.bookId = b.id
        LEFT JOIN authors a ON a.id = ba.authorId
        LEFT JOIN bookSeries bs ON bs.bookId = b.id
        LEFT JOIN series s ON s.id = bs.seriesId
        WHERE li.libraryId = ?
          AND li.mediaType = 'book'
          AND li.isMissing = 0
        GROUP BY li.id
        ORDER BY li.titleIgnorePrefix
    """
    with _get_connection() as conn:
        rows = conn.execute(query, (library_id,)).fetchall()
    return [dict(row) for row in rows]


def get_library_name(library_id):
    """Return the name of a library by its ID."""
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT name FROM libraries WHERE id = ?", (library_id,)
        ).fetchone()
    return row["name"] if row else None
