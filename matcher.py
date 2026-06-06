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
    \[audiobook[^\]]*\]         # [audiobook PL]
  | \[ebook[^\]]*\]             # [ebook PL]
  | \((?:19|20)\d{2}\)          # (2024)
  | czyta\s+[\w.]+(?:\s+[\w.]+)?  # czyta Kowalski / czyta M.Kowalik
  | czyta:\s*[\w.]+(?:\s+[\w.]+)?
  | \bczyta\b
  | \bunabridged\b
  | \bmp3\b | \bm4b\b | \bflac\b
  | superprodukcja
  | \([\d\s]+kbps\)
  | \bpop\b
  | tom\s+\d+[-–]\d+            # tom 1-3 (range, not single)
  | book\s+\d+\s*[-–]\s*        # Book 28 -
  | graphicaudio
  | cykl\s+
  | \s*\+\s*\[.*?\]             # + [ebook PL]
  | \b(?:czesc|część|part|vol|volume)\b\.?\s*\d+
  | serial\s+oryginalny
  | \d+kbps
  | \[.*?\]                     # any remaining [...]
  | \(.*?\)                     # any remaining (...)
""", re.IGNORECASE | re.VERBOSE)

# Segments that look like collection/series folders — skip them, use parent
_COLLECTION_SEGMENT = re.compile(
    r"(cykl|serie|tom\s+\d+[-–]\d+|book\s+\d+[-–]\d+|komplet|collection|trilogy|box)",
    re.IGNORECASE
)

# Lektor/narrator patterns in authors field
_LEKTOR_RE = re.compile(r"czyta[:\s]", re.IGNORECASE)


def _dots_to_spaces(text):
    """Convert dots used as word separators to spaces (Murakami.Haruki→Murakami Haruki).
    Preserve decimal numbers and abbreviations like M.Kowalik."""
    return re.sub(r"(?<=[a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ])\.(?=[a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ]{2,})", " ", text)


def _clean_segment(segment):
    """Clean a single folder segment — remove noise, return core text."""
    segment = _dots_to_spaces(segment)
    segment = re.sub(r"_", " ", segment)          # underscores → spaces
    segment = _NOISE.sub(" ", segment)
    segment = re.sub(r"\s+", " ", segment).strip()
    return segment


def _pick_best_segment(segments):
    """
    From a list of path segments (root→leaf order), pick the most useful one.
    Prefers the last segment unless it looks like a collection folder,
    in which case tries the second-to-last.
    """
    # Work from leaf upward
    for seg in reversed(segments):
        seg = seg.strip()
        if not seg:
            continue
        cleaned = _clean_segment(seg)
        # Skip segments that are just collection descriptors
        if _COLLECTION_SEGMENT.search(cleaned) and len(cleaned.split()) <= 5:
            continue
        if len(cleaned) < 3:
            continue
        return seg
    return segments[-1] if segments else ""


def _extract_candidate(rel_path):
    """
    Parse rel_path into (folder_author, folder_title).
    Returns (None, title) when author can't be determined.
    """
    segments = [s for s in rel_path.replace("\\", "/").split("/") if s.strip()]
    if not segments:
        return None, ""

    raw = _pick_best_segment(segments)
    cleaned = _clean_segment(raw)

    # Split on " - " → author / title
    if " - " in cleaned:
        author_part, title_part = cleaned.split(" - ", 1)
        return author_part.strip(), title_part.strip()

    return None, cleaned.strip()


# ── Similarity functions ───────────────────────────────────────────────────────

def _ratio(a, b):
    """SequenceMatcher ratio on normalized strings."""
    na, nb = normalize(a), normalize(b)
    if not na or not nb:
        return 0.0
    return difflib.SequenceMatcher(None, na, nb).ratio()


def _partial_ratio(a, b):
    """
    Best ratio when one string is a prefix/substring of the other.
    Handles: 'Eszelon' vs 'Eszelon. Stacja Zło. Tom 4'
    """
    na, nb = normalize(a), normalize(b)
    if not na or not nb:
        return 0.0
    shorter, longer = (na, nb) if len(na) <= len(nb) else (nb, na)
    # Find best matching window of len(shorter) in longer
    matcher = difflib.SequenceMatcher(None, shorter, longer)
    match = matcher.find_longest_match(0, len(shorter), 0, len(longer))
    if match.size == 0:
        return 0.0
    # Score = how much of the shorter string is covered
    return match.size / len(shorter)


def _token_overlap(a, b):
    """
    Fraction of tokens from the shorter string found in the longer.
    Handles reordered titles: 'Księżycowy Sztylet. Wilkozacy' vs 'Wilkozacy. Tom 3. Księżycowy Sztylet'
    """
    na, nb = normalize(a), normalize(b)
    ta = set(t for t in na.split() if len(t) > 2)  # skip short words
    tb = set(t for t in nb.split() if len(t) > 2)
    if not ta:
        return 0.0
    overlap = ta & tb
    return len(overlap) / len(ta)


def _title_score(meta_title, folder_title):
    """Combined title similarity — max of three strategies."""
    if not meta_title or not folder_title:
        return 0.0
    return max(
        _ratio(meta_title, folder_title),
        _partial_ratio(meta_title, folder_title),
        _token_overlap(meta_title, folder_title),
    )


def _author_score(meta_authors, folder_author):
    """
    Compare authors string against folder author segment.
    Returns score 0-1 or None if comparison not possible.
    """
    if not meta_authors or not folder_author:
        return None

    # If meta_authors looks like a lektor entry, skip author comparison
    if _LEKTOR_RE.search(meta_authors):
        return None

    # Try full string
    best = _ratio(meta_authors, folder_author)

    # Try individual authors (comma/semicolon separated)
    for author in re.split(r"[,;]", meta_authors):
        author = author.strip()
        if len(author) < 3:
            continue
        best = max(best, _ratio(author, folder_author))
        # Also try lastname-firstname swap
        parts = author.split()
        if len(parts) == 2:
            swapped = f"{parts[1]} {parts[0]}"
            best = max(best, _ratio(swapped, folder_author))

    return best


# ── No-metadata detection ──────────────────────────────────────────────────────

def _is_no_metadata(title, rel_path):
    """
    Detect items where ABS used the folder name as the title
    (no proper metadata was ever set).
    Heuristics:
    - title contains '[audiobook' or year pattern (YYYY)
    - title closely matches the last path segment (>0.85)
    - title contains ' - ' and author pattern
    """
    if not title:
        return False

    # Direct markers in title
    if re.search(r"\[audiobook|\(\d{4}\)|\bczyta\b", title, re.IGNORECASE):
        return True

    # Title looks like "Autor - Tytuł (rok)" pattern
    if re.search(r".+ - .+ \(\d{4}\)", title):
        return True

    # Title closely matches folder segment
    segments = [s for s in rel_path.replace("\\", "/").split("/") if s.strip()]
    if segments:
        last = segments[-1]
        if _ratio(title, last) > 0.85:
            return True

    return False


# ── Public API ─────────────────────────────────────────────────────────────────

def compare(title, authors, rel_path):
    """
    Compare ABS title+authors against folder name from rel_path.

    Returns dict:
      status: "match" | "partial" | "unknown" | "no_meta"
      title_score: float
      author_score: float | None
      folder_title: str
      folder_author: str | None
      lektor_author: bool  — True when authors field contains a narrator name
    """
    if not rel_path:
        return _result("unknown", 0.0, None, "", None, False)

    # Detect no-metadata items first
    if _is_no_metadata(title, rel_path):
        return _result("no_meta", 1.0, None, "", None, False)

    folder_author, folder_title = _extract_candidate(rel_path)
    lektor = bool(_LEKTOR_RE.search(authors or ""))

    if not folder_title:
        return _result("unknown", 0.0, None, folder_title, folder_author, lektor)

    t_score = _title_score(title or "", folder_title)
    a_score = _author_score(authors, folder_author) if not lektor else None

    # Classification
    # Title is primary; author is secondary and optional
    if t_score >= 0.68:
        if a_score is None or a_score >= 0.55:
            status = "match"
        elif a_score >= 0.35:
            status = "partial"   # title good, author borderline
        else:
            status = "partial"   # title good, author mismatch — still partial not unknown
    elif t_score >= 0.42:
        status = "partial"
    else:
        status = "unknown"

    return _result(status, t_score, a_score, folder_title, folder_author, lektor)


def _result(status, t_score, a_score, folder_title, folder_author, lektor):
    return {
        "status": status,
        "title_score": round(t_score, 2),
        "author_score": round(a_score, 2) if a_score is not None else None,
        "folder_title": folder_title,
        "folder_author": folder_author,
        "lektor_author": lektor,
    }
