"""
Fuzzy matching of ABS metadata against audiobook folder names.
"""

import re
import unicodedata
import difflib


def normalize(text):
    """Lowercase, strip diacritics, collapse whitespace, remove punctuation."""
    if not text:
        return ""
    # NFD decomposition strips diacritics (ą→a, ę→e, ü→u etc.)
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# Patterns to strip from folder names before matching
_STRIP_PATTERNS = [
    r"\[audiobook[^\]]*\]",        # [audiobook PL], [audiobook EN]
    r"\[ebook[^\]]*\]",            # [ebook PL]
    r"\((?:19|20)\d{2}\)",         # (2024), (1997)
    r"czyta\s+\S+",                # czyta Kowalski
    r"czyta\s+\w+\.\w+",           # czyta M.Kowalik
    r"\b(?:unabridged|mp3|m4b|superprodukcja)\b",
    r"\([\d\s]+kbps\)",            # (320kbps)
    r"pop\b",
    r"tom\s+\d+[-–]\d+",           # tom 1-3
    r"book\s+\d+\s*[-–]?\s*",      # Book 28 -
    r"graphicaudio",
    r"cykl\s+",                    # cykl Do jutra...
    r"\s*\+\s*\[.*?\]",            # + [ebook PL]
]

_STRIP_RE = re.compile("|".join(_STRIP_PATTERNS), re.IGNORECASE)


def _extract_folder_candidate(rel_path):
    """
    Extract the most useful folder segment from rel_path and clean it up.
    Returns (folder_author, folder_title) — either may be None.
    """
    # Use last non-empty segment
    segment = [s for s in rel_path.replace("\\", "/").split("/") if s.strip()][-1]

    # Replace dots used as spaces (Murakami.Haruki-1Q84) but keep decimal numbers
    segment = re.sub(r"(?<=[a-zA-Z])\.(?=[a-zA-Z])", " ", segment)

    # Strip noise patterns
    segment = _STRIP_RE.sub(" ", segment)
    segment = re.sub(r"\s+", " ", segment).strip()

    # Split on " - " → left=author, right=title
    if " - " in segment:
        parts = segment.split(" - ", 1)
        return parts[0].strip(), parts[1].strip()

    # No separator — treat whole thing as title, author unknown
    return None, segment.strip()


def _similarity(a, b):
    """SequenceMatcher ratio on normalized strings."""
    return difflib.SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def _match_authors(meta_authors, folder_author):
    """
    meta_authors: comma-separated string like "Magdalena, Maciej Reputakowscy"
    folder_author: string like "Magdalena i Maciej Reputakowski"
    Returns similarity score 0-1.
    """
    if not meta_authors or not folder_author:
        return None  # can't compare

    # Try full string match first
    score = _similarity(meta_authors, folder_author)
    if score >= 0.65:
        return score

    # Try each individual author against folder_author
    authors = [a.strip() for a in re.split(r"[,;]", meta_authors) if a.strip()]
    best = max((_similarity(a, folder_author) for a in authors), default=0)
    return max(score, best)


def compare(title, authors, rel_path):
    """
    Compare ABS title+authors against folder name derived from rel_path.

    Returns dict:
      {
        "status": "match" | "partial" | "unknown",
        "title_score": float,
        "author_score": float | None,
        "folder_title": str,
        "folder_author": str | None,
      }
    """
    if not rel_path:
        return {"status": "unknown", "title_score": 0, "author_score": None,
                "folder_title": "", "folder_author": None}

    folder_author, folder_title = _extract_folder_candidate(rel_path)

    if not folder_title:
        return {"status": "unknown", "title_score": 0, "author_score": None,
                "folder_title": folder_title or "", "folder_author": folder_author}

    title_score = _similarity(title or "", folder_title)
    author_score = _match_authors(authors, folder_author) if folder_author else None

    # Determine status
    # Title is primary signal; author is secondary (often missing or reformatted)
    if title_score >= 0.72:
        if author_score is None or author_score >= 0.60:
            status = "match"
        else:
            status = "partial"  # title ok but author mismatch
    elif title_score >= 0.45:
        status = "partial"
    else:
        status = "unknown"

    return {
        "status": status,
        "title_score": round(title_score, 2),
        "author_score": round(author_score, 2) if author_score is not None else None,
        "folder_title": folder_title,
        "folder_author": folder_author,
    }
