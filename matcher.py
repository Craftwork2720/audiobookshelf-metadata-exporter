"""
Fuzzy matching of ABS metadata against audiobook folder names.
"""

import re
import unicodedata
import difflib


# ── Normalization ──────────────────────────────────────────────────────────────

def normalize(text):
    """Lowercase, strip diacritics, collapse whitespace, remove punctuation."""
    if not text:
        return ""
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ── Folder name cleaning ───────────────────────────────────────────────────────

_NOISE = re.compile(r"""
    \[audiobook[^\]]*\]
  | \[ebook[^\]]*\]
  | \[unabridged[^\]]*\]
  | \bunabridged\b
  | \bmp3\b | \bm4b\b | \bflac\b
  | \d+kbps
  | \bbook\s+\d+\s*
  | \((?:19|20)\d{2}\)
  | \[.*?\]
  | \(.*?\)
""", re.IGNORECASE | re.VERBOSE)

_COLLECTION_SEGMENT = re.compile(
    r"(collection|trilogy|box|series\s+\d|saga)",
    re.IGNORECASE
)


def _dots_to_spaces(text):
    """Brandon.Sanderson → Brandon Sanderson, M.Kowalik → M.Kowalik."""
    return re.sub(
        r"([a-zA-Z]{2,})\.(?=[a-zA-Z])",
        r"\1 ",
        text
    )


def _clean_segment(segment):
    """Remove noise from a folder segment."""
    segment = _dots_to_spaces(segment)
    segment = re.sub(r"_", " ", segment)
    segment = _NOISE.sub(" ", segment)
    segment = re.sub(r"\s*-\s*", " - ", segment)   # normalize dashes
    segment = re.sub(r"(\s*-\s*){2,}", " - ", segment)  # collapse multiples
    segment = re.sub(r"^\s*-\s*", "", segment)     # leading dash
    segment = re.sub(r"\s*-\s*$", "", segment)     # trailing dash
    segment = re.sub(r"\s+", " ", segment).strip()
    return segment


def _pick_best_segment(segments):
    """Pick the best segment from a path, working from leaf upward."""
    for seg in reversed(segments):
        seg = seg.strip()
        if not seg:
            continue
        cleaned = _clean_segment(seg)
        if _COLLECTION_SEGMENT.search(cleaned) and len(cleaned.split()) <= 5:
            continue
        if len(cleaned) < 3:
            continue
        return seg
    return segments[-1] if segments else ""


def _extract_candidate(rel_path):
    """Parse rel_path into (folder_author, folder_title)."""
    segments = [s for s in rel_path.replace("\\", "/").split("/") if s.strip()]
    if not segments:
        return None, ""

    raw = _pick_best_segment(segments)
    cleaned = _clean_segment(raw)

    # "Title by Author" — split on last " by "
    if " by " in cleaned.lower():
        idx = cleaned.lower().rfind(" by ")
        title_part = cleaned[:idx].strip()
        author_part = cleaned[idx + 4:].strip()
        if title_part and author_part:
            return author_part, title_part

    if " - " in cleaned:
        parts = cleaned.split(" - ")
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()
        if len(parts) >= 3:
            title = parts[-1].strip()
            author = parts[0].strip()
            if re.match(r"^(?:\d{4}|book\s+\d+|\d+)$", parts[1].strip(), re.IGNORECASE):
                return author, title
            return author, " - ".join(parts[1:]).strip()

    return None, cleaned.strip()


# ── Similarity ─────────────────────────────────────────────────────────────────

def _ratio(a, b):
    na, nb = normalize(a), normalize(b)
    if not na or not nb:
        return 0.0
    return difflib.SequenceMatcher(None, na, nb).ratio()


def _partial_ratio(a, b):
    na, nb = normalize(a), normalize(b)
    if not na or not nb:
        return 0.0
    shorter, longer = (na, nb) if len(na) <= len(nb) else (nb, na)
    matcher = difflib.SequenceMatcher(None, shorter, longer)
    match = matcher.find_longest_match(0, len(shorter), 0, len(longer))
    return match.size / len(shorter) if match.size else 0.0


def _token_overlap(a, b):
    na, nb = normalize(a), normalize(b)
    ta = set(t for t in na.split() if len(t) > 2)
    tb = set(t for t in nb.split() if len(t) > 2)
    if not ta:
        return 0.0
    return len(ta & tb) / len(ta)


def _title_score(meta_title, folder_title):
    if not meta_title or not folder_title:
        return 0.0
    return max(
        _ratio(meta_title, folder_title),
        _partial_ratio(meta_title, folder_title),
        _token_overlap(meta_title, folder_title),
    )


def _author_score(meta_authors, folder_author):
    if not meta_authors or not folder_author:
        return None
    best = _ratio(meta_authors, folder_author)
    for author in re.split(r"[,;]", meta_authors):
        author = author.strip()
        if len(author) < 3:
            continue
        best = max(best, _ratio(author, folder_author))
        parts = author.split()
        if len(parts) == 2:
            best = max(best, _ratio(f"{parts[1]} {parts[0]}", folder_author))
    return best


# ── No-metadata detection ──────────────────────────────────────────────────────

def _is_no_metadata(title, rel_path):
    """Detect items where ABS used the folder name as the title."""
    if not title:
        return False
    if re.search(r"\[audiobook|\(\d{4}\)", title, re.IGNORECASE):
        return True
    if re.search(r".+ - .+ \(\d{4}\)", title):
        return True
    segments = [s for s in rel_path.replace("\\", "/").split("/") if s.strip()]
    if segments and _ratio(title, segments[-1]) > 0.85:
        return True
    return False


# ── Public API ─────────────────────────────────────────────────────────────────

def compare(title, authors, rel_path):
    """
    Compare ABS metadata against folder name.

    Returns dict:
      status: "match" | "partial" | "unknown" | "no_meta"
      title_score: float
      author_score: float | None
      folder_title: str
      folder_author: str | None
    """
    if not rel_path:
        return _result("unknown", 0.0, None, "", None)

    if _is_no_metadata(title, rel_path):
        return _result("no_meta", 1.0, None, "", None)

    folder_author, folder_title = _extract_candidate(rel_path)

    if not folder_title:
        return _result("unknown", 0.0, None, folder_title, folder_author)

    t_score = _title_score(title or "", folder_title)
    a_score = _author_score(authors, folder_author)

    if t_score >= 0.85:
        status = "match"  # high confidence title match — author not needed
    elif t_score >= 0.68:
        status = "match" if (a_score is None or a_score >= 0.55) else "partial"
    elif t_score >= 0.42:
        status = "partial"
    else:
        status = "unknown"

    return _result(status, t_score, a_score, folder_title, folder_author)


def _result(status, t_score, a_score, folder_title, folder_author):
    return {
        "status": status,
        "title_score": round(t_score, 2),
        "author_score": round(a_score, 2) if a_score is not None else None,
        "folder_title": folder_title,
        "folder_author": folder_author,
    }
