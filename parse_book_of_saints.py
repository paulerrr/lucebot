"""
One-time script to parse The Book of Saints PDF into a JSON lookup file.
Run: python3 parse_book_of_saints.py /path/to/bookofsaintsdict00stau.pdf
Outputs: saints_book.json
"""

import json
import re
import sys

from pdfminer.high_level import extract_text


# Matches entry header lines like:
#   ALEXANDER (St.) M.
#   FRANCIS OF ASSISI (St.) C.
#   ALEXANDER SAULI (St.) Bp.
HEADER_RE = re.compile(
    r'\n\*?([A-Z][A-Za-z ,\'\-]+)\s*\((St\.|Bl\.|SS\.)\)[^\n]*\n'
)

# Running page headers inserted by the PDF layout — strip these
PAGE_HEADER_RE = re.compile(r'[A-Z][A-Z ]+\n\nTHE BOOK OF SAINTS\n\n')

# Date line like "(July 10)" or "(3rd cent.)" at the start of a chunk
DATE_RE = re.compile(r'^\s*\([^\)]{3,40}\)\s*\n?')

# Cross-reference-only entries
CROSS_REF_RE = re.compile(r'^\s*(Otherwise|See SS\.|See Bl\.)', re.IGNORECASE)


def normalize_name(name: str) -> str:
    """Lowercase, collapse whitespace, strip leading titles."""
    name = name.lower().strip()
    name = re.sub(r'\s+', ' ', name)
    name = re.sub(r'^(saint|blessed|st\.?|bl\.?)\s+', '', name)
    return name


def parse_pdf(pdf_path: str) -> dict:
    print(f"Extracting text from {pdf_path} ...")
    text = extract_text(pdf_path)

    # Strip running page headers
    text = PAGE_HEADER_RE.sub(' ', text)
    # Strip page numbers (isolated digits on their own line)
    text = re.sub(r'\n\d+\n', '\n', text)

    # Find all entry headers and their positions
    # Store (name, match_start, content_start) where content_start is right after the header line
    headers = [(m.group(1).strip(), m.start(), m.end()) for m in HEADER_RE.finditer(text)]
    print(f"Found {len(headers)} entry headers")

    entries = {}
    for i, (raw_name, hdr_start, content_start) in enumerate(headers):
        # Content ends where the next header's leading \n begins
        content_end = headers[i + 1][1] if i + 1 < len(headers) else len(text)
        chunk = text[content_start:content_end]

        # Skip cross-reference-only entries
        if CROSS_REF_RE.match(chunk.strip()):
            continue

        # Strip leading date/century lines (not the description)
        chunk = DATE_RE.sub('', chunk.strip())
        chunk = DATE_RE.sub('', chunk.strip())  # sometimes two date-like lines

        # Clean up: fix hyphenated line breaks, collapse whitespace
        chunk = re.sub(r'-\n', '', chunk)
        chunk = re.sub(r'\n+', ' ', chunk)
        chunk = re.sub(r'\s{2,}', ' ', chunk).strip()

        if len(chunk) < 40:
            continue

        key = normalize_name(raw_name)
        # Keep the longest description if there are multiple entries for the same name
        if key not in entries or len(chunk) > len(entries[key]['description']):
            entries[key] = {
                'name': raw_name.title(),
                'description': chunk,
            }

    return entries


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 parse_book_of_saints.py <path-to-pdf>")
        sys.exit(1)

    entries = parse_pdf(sys.argv[1])

    out_path = 'saints_book.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    print(f"Wrote {len(entries)} entries to {out_path}")

    # Print a few samples
    for key in list(entries)[:3]:
        print(f"\n--- {key!r} ---")
        print(entries[key]['description'][:300])


if __name__ == '__main__':
    main()
