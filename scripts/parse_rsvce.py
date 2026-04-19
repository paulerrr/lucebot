#!/usr/bin/env python3
"""Convert obsidian-holy-bible Markdown files to rsvce.json."""
import json
import os
import re
import sys

SOURCE = os.path.expanduser("~/projects/obsidian-holy-bible/Holy Bible")
OUT = os.path.join(os.path.dirname(__file__), "bibles", "rsvce.json")

# Directory name prefix number -> book_id
BOOK_DIR_MAP = {
    # Old Testament
    "Book of Genesis": "Gen",
    "Book of Exodus": "Ex",
    "Book of Leviticus": "Lev",
    "Book of Numbers": "Num",
    "Book of Deuteronomy": "Dt",
    "Book of Joshua": "Jos",
    "Book of Judges": "Judg",
    "Book of Ruth": "Ru",
    "First Book of Samuel": "1_Kgs",
    "Second Book of Samuel": "2_Kgs",
    "First Book of Kings": "3_Kgs",
    "Second Book of Kings": "4_Kgs",
    "First Book of Chronicles": "1_Par",
    "Second Book of Chronicles": "2_Par",
    "Book of Ezra": "Esd",
    "Book of Nehemiah": "Neh",
    "Book of Tobit": "Tob",
    "Book of Judith": "Jdt",
    "Book of Esther": "Est",
    "First Book of Maccabees": "1_Mac",
    "Second Book of Maccabees": "2_Mac",
    "Book of Job": "Job",
    "Book of Psalms": "Ps",
    "Book of Proverbs": "Prov",
    "Book of Ecclesiastes": "Eccl",
    "Song of Solomon": "Cant",
    "Book of Wisdom": "Wis",
    "Book of Sirach": "Eccle",
    "Book of Isaiah": "Isa",
    "Book of Jeremiah": "Jer",
    "Book of Lamentations": "Lam",
    "Book of Baruch": "Bar",
    "Book of Ezekiel": "Eze",
    "Book of Daniel": "Dan",
    "Book of Hosea": "Os",
    "Book of Joel": "Jo",
    "Book of Amos": "Am",
    "Book of Obadiah": "Abd",
    "Book of Jonah": "Jon",
    "Book of Micah": "Mic",
    "Book of Nahum": "Nah",
    "Book of Habakkuk": "Hab",
    "Book of Zephaniah": "Sop",
    "Book of Haggai": "Agg",
    "Book of Zechariah": "Zac",
    "Book of Malachi": "Mal",
    # New Testament
    "Gospel of Matthew": "Mat",
    "Gospel According to Saint Matthew": "Mat",
    "Gospel of Mark": "Mk",
    "Gospel According to Saint Mark": "Mk",
    "Gospel of Luke": "Lk",
    "Gospel According to Saint Luke": "Lk",
    "Gospel of John": "Jn",
    "Gospel According to Saint John": "Jn",
    "Acts of the Apostles": "Act",
    "Letter to the Romans": "Rom",
    "Epistle to the Romans": "Rom",
    "First Letter to the Corinthians": "1_Cor",
    "First Epistle to the Corinthians": "1_Cor",
    "Second Letter to the Corinthians": "2_Cor",
    "Second Epistle to the Corinthians": "2_Cor",
    "Letter to the Galatians": "Gal",
    "Epistle to the Galatians": "Gal",
    "Letter to the Ephesians": "Eph",
    "Epistle to the Ephesians": "Eph",
    "Letter to the Philippians": "Phl",
    "Epistle to the Philippians": "Phl",
    "Letter to the Colossians": "Col",
    "Epistle to the Colossians": "Col",
    "First Letter to the Thessalonians": "1_Th",
    "First Epistle to the Thessalonians": "1_Th",
    "Second Letter to the Thessalonians": "2_Th",
    "Second Epistle to the Thessalonians": "2_Th",
    "First Letter to Timothy": "1_Tim",
    "First Epistle to Timothy": "1_Tim",
    "Second Letter to Timothy": "2_Tim",
    "Second Epistle to Timothy": "2_Tim",
    "Letter to Titus": "Tit",
    "Epistle to Titus": "Tit",
    "Letter to Philemon": "Phm",
    "Epistle to Philemon": "Phm",
    "Letter to the Hebrews": "Heb",
    "Epistle to the Hebrews": "Heb",
    "Letter of James": "Jas",
    "Epistle of James": "Jas",
    "First Letter of Peter": "1_Pet",
    "First Epistle of Peter": "1_Pet",
    "Second Letter of Peter": "2_Pet",
    "Second Epistle of Peter": "2_Pet",
    "First Letter of John": "1_Jn",
    "First Epistle of John": "1_Jn",
    "Second Letter of John": "2_Jn",
    "Second Epistle of John": "2_Jn",
    "Third Letter of John": "3_Jn",
    "Third Epistle of John": "3_Jn",
    "Letter of Jude": "Jud",
    "Epistle of Jude": "Jud",
    "Book of Revelation": "Apoc",
    "Revelation to John": "Apoc",
}

_VERSE_RE = re.compile(r"^(\d+)\s+(.+)$")
_CHAPTER_RE = re.compile(r"(\d+)\.md$")


def dir_to_book_id(dir_name):
    # Strip leading "N, " prefix
    name = re.sub(r"^\d+,\s*", "", dir_name)
    return BOOK_DIR_MAP.get(name)


def parse_chapter(path):
    verses = {}
    seen_first_heading = False
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip()
            if line.startswith("# ") and not line.startswith("### "):
                if seen_first_heading:
                    break  # second translation starts here — stop
                seen_first_heading = True
                continue
            m = _VERSE_RE.match(line)
            if m:
                verses[int(m.group(1))] = m.group(2)
    return verses


def main():
    bible = {}
    skipped_books = []

    for testament in ("Old Testament", "New Testament"):
        testament_path = os.path.join(SOURCE, testament)
        if not os.path.isdir(testament_path):
            print(f"Missing: {testament_path}", file=sys.stderr)
            continue

        for book_dir in sorted(os.listdir(testament_path)):
            if book_dir.endswith(".md"):
                continue
            book_id = dir_to_book_id(book_dir)
            if book_id is None:
                skipped_books.append(book_dir)
                continue

            book_path = os.path.join(testament_path, book_dir)
            for fname in os.listdir(book_path):
                cm = _CHAPTER_RE.search(fname)
                if not cm or "," in fname:
                    continue
                ch = int(cm.group(1))
                verses = parse_chapter(os.path.join(book_path, fname))
                if verses:
                    bible.setdefault(book_id, {})[ch] = verses

    if skipped_books:
        print(f"Skipped (unmapped): {skipped_books}", file=sys.stderr)

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(bible, f, ensure_ascii=False)

    total_verses = sum(
        len(vs) for bk in bible.values() for vs in bk.values()
    )
    print(f"Wrote {OUT}: {len(bible)} books, {total_verses} verses")


if __name__ == "__main__":
    main()
