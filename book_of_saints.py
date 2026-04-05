"""
Lookup saint biographies from The Book of Saints (Benedictine Monks of St. Augustine's Abbey, Ramsgate, 1921).
The saints_book.json file is pre-generated from the PDF by parse_book_of_saints.py.
"""

import json
import logging
import os
import re

log = logging.getLogger("lucebot")

_db: dict | None = None

_DB_PATH = os.path.join(os.path.dirname(__file__), "saints_book.json")


def _load():
    global _db
    if _db is not None:
        return
    try:
        with open(_DB_PATH, encoding="utf-8") as f:
            _db = json.load(f)
        log.info("Loaded %d saint entries from Book of Saints", len(_db))
    except FileNotFoundError:
        log.warning("saints_book.json not found — Book of Saints lookup disabled")
        _db = {}
    except Exception:
        log.exception("Failed to load saints_book.json")
        _db = {}


def _normalize(name: str) -> str:
    """Lowercase, collapse whitespace, strip leading title words."""
    name = name.lower().strip()
    name = re.sub(r"\s+", " ", name)
    name = re.sub(r"^(saint|blessed|st\.?|bl\.?)\s+", "", name)
    return name


def lookup(saint_name: str) -> str | None:
    """Return the biography text for a saint, or None if not found."""
    _load()
    if not _db or not saint_name:
        return None

    key = _normalize(saint_name)

    # 1. Exact match
    entry = _db.get(key)
    if entry:
        return entry["description"]

    # 2. The API name may include extra qualifiers after a comma — try just the base name
    base = key.split(",")[0].strip()
    if base != key:
        entry = _db.get(base)
        if entry:
            return entry["description"]

    # 3. Try progressively shorter versions (drop last word) down to 2 words
    parts = base.split()
    while len(parts) >= 2:
        parts.pop()
        candidate = " ".join(parts)
        entry = _db.get(candidate)
        if entry:
            return entry["description"]

    return None
