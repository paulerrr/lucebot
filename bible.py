import json
import os
import re

import discord
from discord.ui import LayoutView, Container, TextDisplay

KNOX_PATH = os.path.join(os.path.dirname(__file__), "bibles", "knox.json")
DR_PATH = os.path.join(os.path.dirname(__file__), "bibles", "dr.json")
VUL_PATH = os.path.join(os.path.dirname(__file__), "bibles", "vul.tsv")
RSVCE_PATH = os.path.join(os.path.dirname(__file__), "bibles", "rsvce.json")

TRANSLATIONS = {
    "knox": "Knox Bible",
    "dr": "Douay-Rheims",
    "vul": "Clementine Vulgate",
    "rsvce": "RSV Catholic Edition",
}
DEFAULT_TRANSLATION = "knox"

# Latin book names in vul.tsv -> book_id
_VUL_BOOK_MAP = {
    "Genesis": "Gen",
    "Exodus": "Ex",
    "Leviticus": "Lev",
    "Numeri": "Num",
    "Deuteronomium": "Dt",
    "Josue": "Jos",
    "Judicum": "Judg",
    "Ruth": "Ru",
    "Regum I": "1_Kgs",
    "Regum II": "2_Kgs",
    "Regum III": "3_Kgs",
    "Regum IV": "4_Kgs",
    "Paralipomenon I": "1_Par",
    "Paralipomenon II": "2_Par",
    "Esdrae": "Esd",
    "Nehemiae": "Neh",
    "Tobiae": "Tob",
    "Judith": "Jdt",
    "Esther": "Est",
    "Job": "Job",
    "Psalmi": "Ps",
    "Proverbia": "Prov",
    "Ecclesiastes": "Eccl",
    "Canticum Canticorum": "Cant",
    "Sapientia": "Wis",
    "Ecclesiasticus": "Eccle",
    "Isaias": "Isa",
    "Jeremias": "Jer",
    "Lamentationes": "Lam",
    "Baruch": "Bar",
    "Ezechiel": "Eze",
    "Daniel": "Dan",
    "Osee": "Os",
    "Joael": "Jo",
    "Amos": "Am",
    "Abdias": "Abd",
    "Jonas": "Jon",
    "Michaea": "Mic",
    "Nahum": "Nah",
    "Habacuc": "Hab",
    "Sophonias": "Sop",
    "Aggaeus": "Agg",
    "Zacharias": "Zac",
    "Malachias": "Mal",
    "Machabaeorum I": "1_Mac",
    "Machabaeorum II": "2_Mac",
    "Matthaeus": "Mat",
    "Marcus": "Mk",
    "Lucas": "Lk",
    "Joannes": "Jn",
    "Actus Apostolorum": "Act",
    "ad Romanos": "Rom",
    "ad Corinthios I": "1_Cor",
    "ad Corinthios II": "2_Cor",
    "ad Galatas": "Gal",
    "ad Ephesios": "Eph",
    "ad Philippenses": "Phl",
    "ad Colossenses": "Col",
    "ad Thessalonicenses I": "1_Th",
    "ad Thessalonicenses II": "2_Th",
    "ad Timotheum I": "1_Tim",
    "ad Timotheum II": "2_Tim",
    "ad Titum": "Tit",
    "ad Philemonem": "Phm",
    "ad Hebraeos": "Heb",
    "Jacobi": "Jas",
    "Petri I": "1_Pet",
    "Petri II": "2_Pet",
    "Joannis I": "1_Jn",
    "Joannis II": "2_Jn",
    "Joannis III": "3_Jn",
    "Judae": "Jud",
    "Apocalypsis": "Apoc",
}

# Mapping from common user input names to the book_id used in knox.json.
# Includes abbreviations, full names, and alternate names.
BOOK_ALIASES = {}

_BOOK_DEFINITIONS = [
    ("Gen", ["genesis", "gen", "gn"]),
    ("Ex", ["exodus", "ex", "exod"]),
    ("Lev", ["leviticus", "lev", "lv"]),
    ("Num", ["numbers", "num", "nm"]),
    ("Dt", ["deuteronomy", "dt", "deut"]),
    ("Jos", ["josue", "joshua", "jos", "josh"]),
    ("Judg", ["judges", "judg", "jdg", "jgs"]),
    ("Ru", ["ruth", "ru", "rth"]),
    ("1_Kgs", ["1 kings", "1kings", "1 kgs", "1kgs", "1 sam", "1sam", "1 samuel", "1samuel"]),
    ("2_Kgs", ["2 kings", "2kings", "2 kgs", "2kgs", "2 sam", "2sam", "2 samuel", "2samuel"]),
    ("3_Kgs", ["3 kings", "3kings", "3 kgs", "3kgs"]),
    ("4_Kgs", ["4 kings", "4kings", "4 kgs", "4kgs"]),
    ("1_Par", ["1 paralipomena", "1paralipomena", "1 par", "1par",
               "1 chronicles", "1chronicles", "1 chr", "1chr", "1 chron", "1chron"]),
    ("2_Par", ["2 paralipomena", "2paralipomena", "2 par", "2par",
               "2 chronicles", "2chronicles", "2 chr", "2chr", "2 chron", "2chron"]),
    ("Esd", ["1 esdras", "1esdras", "esd", "ezra", "ezr"]),
    ("Neh", ["2 esdras", "2esdras", "nehemias", "nehemiah", "neh"]),
    ("Tob", ["tobias", "tobit", "tob", "tb"]),
    ("Jdt", ["judith", "jdt", "jdth"]),
    ("Est", ["esther", "est"]),
    ("Job", ["job", "jb"]),
    ("Ps", ["psalms", "psalm", "ps", "pss"]),
    ("Prov", ["proverbs", "prov", "prv", "pr"]),
    ("Eccl", ["ecclesiastes", "eccl", "qoh", "qoheleth"]),
    ("Cant", ["song of songs", "song of solomon", "cant", "sg", "sos", "canticles"]),
    ("Wis", ["wisdom", "wis", "ws"]),
    ("Eccle", ["ecclesiasticus", "eccle", "sirach", "sir"]),
    ("Isa", ["isaias", "isaiah", "isa", "is"]),
    ("Jer", ["jeremias", "jeremiah", "jer"]),
    ("Lam", ["lamentations", "lam", "la"]),
    ("Bar", ["baruch", "bar"]),
    ("Eze", ["ezechiel", "ezekiel", "eze", "ezek", "ez"]),
    ("Dan", ["daniel", "dan", "dn"]),
    ("Os", ["osee", "hosea", "os", "hos"]),
    ("Jo", ["joel", "jo", "jl"]),
    ("Am", ["amos", "am"]),
    ("Abd", ["abdias", "obadiah", "abd", "ob", "obad"]),
    ("Jon", ["jonas", "jonah", "jon"]),
    ("Mic", ["michaeas", "micah", "mic", "mi"]),
    ("Nah", ["nahum", "nah", "na"]),
    ("Hab", ["habacuc", "habakkuk", "hab", "hb"]),
    ("Sop", ["sophonias", "zephaniah", "sop", "zeph", "zep"]),
    ("Agg", ["aggaeus", "haggai", "agg", "hag", "hg"]),
    ("Zac", ["zacharias", "zechariah", "zac", "zech", "zec"]),
    ("Mal", ["malachias", "malachi", "mal"]),
    ("1_Mac", ["1 machabees", "1machabees", "1 maccabees", "1maccabees",
               "1 mac", "1mac", "1 macc", "1macc"]),
    ("2_Mac", ["2 machabees", "2machabees", "2 maccabees", "2maccabees",
               "2 mac", "2mac", "2 macc", "2macc"]),
    ("Mat", ["matthew", "mat", "matt", "mt"]),
    ("Mk", ["mark", "mk"]),
    ("Lk", ["luke", "lk"]),
    ("Jn", ["john", "jn"]),
    ("Act", ["acts of apostles", "acts", "act"]),
    ("Rom", ["romans", "rom", "rm"]),
    ("1_Cor", ["1 corinthians", "1corinthians", "1 cor", "1cor"]),
    ("2_Cor", ["2 corinthians", "2corinthians", "2 cor", "2cor"]),
    ("Gal", ["galatians", "gal"]),
    ("Eph", ["ephesians", "eph"]),
    ("Phl", ["philippians", "phl", "phil", "php"]),
    ("Col", ["colossians", "col"]),
    ("1_Th", ["1 thessalonians", "1thessalonians", "1 th", "1th", "1 thess", "1thess"]),
    ("2_Th", ["2 thessalonians", "2thessalonians", "2 th", "2th", "2 thess", "2thess"]),
    ("1_Tim", ["1 timothy", "1timothy", "1 tim", "1tim"]),
    ("2_Tim", ["2 timothy", "2timothy", "2 tim", "2tim"]),
    ("Tit", ["titus", "tit", "ti"]),
    ("Phm", ["philemon", "phm", "phlm"]),
    ("Heb", ["hebrews", "heb"]),
    ("Jas", ["james", "jas"]),
    ("1_Pet", ["1 peter", "1peter", "1 pet", "1pet", "1 pt", "1pt"]),
    ("2_Pet", ["2 peter", "2peter", "2 pet", "2pet", "2 pt", "2pt"]),
    ("1_Jn", ["1 john", "1john", "1 jn", "1jn"]),
    ("2_Jn", ["2 john", "2john", "2 jn", "2jn"]),
    ("3_Jn", ["3 john", "3john", "3 jn", "3jn"]),
    ("Jud", ["jude", "jud"]),
    ("Apoc", ["apocalypse", "revelation", "apoc", "rev", "rv"]),
]

# Build alias lookup
for book_id, aliases in _BOOK_DEFINITIONS:
    for alias in aliases:
        BOOK_ALIASES[alias] = book_id

# Book ID -> display name
BOOK_DISPLAY = {}


def _load_knox():
    """Load Knox Bible from NDJSON into {book_id: {chapter: {verse: text}}}."""
    bible = {}
    with open(KNOX_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            bid = obj["book_id"]
            ch = obj["chapter"]
            vs = obj["verse"]
            text = obj["text"]
            if bid not in BOOK_DISPLAY:
                BOOK_DISPLAY[bid] = obj["book_name"]
            bible.setdefault(bid, {}).setdefault(ch, {})[vs] = text
    return bible


def _load_dr():
    """Load DR Bible from {BookName: {chapter_str: {verse_str: text}}} into the same shape as Knox."""
    with open(DR_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    bible = {}
    # Build a reverse map: lowercase book name -> book_id
    name_to_id = {alias: bid for alias, bid in BOOK_ALIASES.items()}
    for book_name, chapters in raw.items():
        bid = name_to_id.get(book_name.lower())
        if bid is None:
            continue
        for ch_str, verses in chapters.items():
            ch = int(ch_str)
            for vs_str, text in verses.items():
                vs = int(vs_str)
                bible.setdefault(bid, {}).setdefault(ch, {})[vs] = text
    return bible


def _load_vul():
    """Load Vulgate from TSV (BookName, Abbrev, BookNum, Chapter, Verse, Text)."""
    bible = {}
    with open(VUL_PATH, encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 6:
                continue
            book_name, _, _, ch_str, vs_str, text = parts[0], parts[1], parts[2], parts[3], parts[4], parts[5]
            bid = _VUL_BOOK_MAP.get(book_name)
            if bid is None:
                continue
            bible.setdefault(bid, {}).setdefault(int(ch_str), {})[int(vs_str)] = text
    return bible


_BIBLES = {}


def _load_rsvce():
    """Load RSVCE from {book_id: {chapter_int: {verse_int: text}}}."""
    with open(RSVCE_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    bible = {}
    for bid, chapters in raw.items():
        for ch_str, verses in chapters.items():
            ch = int(ch_str)
            for vs_str, text in verses.items():
                bible.setdefault(bid, {}).setdefault(ch, {})[int(vs_str)] = text
    return bible


def _get_bible(translation):
    if translation not in _BIBLES:
        if translation == "knox":
            _BIBLES["knox"] = _load_knox()
        elif translation == "dr":
            _BIBLES["dr"] = _load_dr()
        elif translation == "vul":
            _BIBLES["vul"] = _load_vul()
        elif translation == "rsvce":
            _BIBLES["rsvce"] = _load_rsvce()
    return _BIBLES.get(translation, _BIBLES.get("knox"))


# Pre-load Knox at startup
_BIBLES["knox"] = _load_knox()
BIBLE = _BIBLES["knox"]

# Regex to match bible verse references like:
#   John 3:16
#   1 Cor 13:4-7
#   Genesis 1:1-3
#   Ps 23
#   Rom 8:28,31
_VERSE_PATTERN = re.compile(
    r"(?<!\w)"                        # not preceded by a word char
    r"((?:[123]\s*)?[A-Za-z]+)"       # book name (optional leading number)
    r"\s+"                            # space
    r"(\d+)"                          # chapter
    r"(?:\s*:\s*(\d+)"                # optional :verse_start
    r"(?:\s*[-–]\s*(\d+))?"           # optional -verse_end
    r")?"
    r"(?!\w)"                         # not followed by a word char
    r"(?:\s*[\[(](\w+)[\])])?"        # optional [translation] or (translation)
    ,
    re.IGNORECASE,
)


def parse_verse_reference(text):
    """Parse a verse reference and return (book_id, chapter, verse_start, verse_end, translation_override) or None.
    translation_override is None if no inline tag was given."""
    m = _VERSE_PATTERN.search(text)
    if not m:
        return None

    raw_book = m.group(1).strip().lower()
    raw_book = re.sub(r"^([123])\s+", r"\1 ", raw_book)

    book_id = BOOK_ALIASES.get(raw_book)
    if book_id is None:
        return None

    chapter = int(m.group(2))
    verse_start = int(m.group(3)) if m.group(3) else None
    verse_end = int(m.group(4)) if m.group(4) else None

    if verse_end is not None and verse_start is not None and verse_end < verse_start:
        return None

    raw_translation = m.group(5)
    translation_override = raw_translation.lower() if raw_translation and raw_translation.lower() in TRANSLATIONS else None

    return book_id, chapter, verse_start, verse_end, translation_override


def lookup_verses(book_id, chapter, verse_start=None, verse_end=None, translation=DEFAULT_TRANSLATION):
    """Look up verses from the requested translation. Returns list of (verse_num, text) or None."""
    bible = _get_bible(translation)
    book = bible.get(book_id)
    if not book:
        return None
    ch_data = book.get(chapter)
    if not ch_data:
        return None

    if verse_start is None:
        return sorted(ch_data.items())

    if verse_end is None:
        verse_end = verse_start

    verses = []
    for v in range(verse_start, verse_end + 1):
        if v in ch_data:
            verses.append((v, ch_data[v]))
    return verses if verses else None


def format_bible_view(book_id, chapter, verse_start, verse_end, verses, translation=DEFAULT_TRANSLATION):
    """Format looked-up verses as a Components V2 LayoutView."""
    display_name = BOOK_DISPLAY.get(book_id, book_id)
    translation_label = TRANSLATIONS.get(translation, translation)

    if verse_start is None:
        title = f"{display_name} {chapter}"
    elif verse_end is None or verse_end == verse_start:
        title = f"{display_name} {chapter}:{verse_start}"
    else:
        title = f"{display_name} {chapter}:{verse_start}-{verse_end}"

    body = "\n".join(f"**{v}.** {text}" for v, text in verses)

    if len(body) > 4000:
        body = body[:3997] + "..."

    view = LayoutView()
    container = Container(accent_colour=0x3E621B)
    container.add_item(TextDisplay(f"### {title} - {translation_label}"))
    container.add_item(TextDisplay(body))
    container.add_item(TextDisplay(f"-# {translation_label}"))
    view.add_item(container)
    return view


def search_verses(query, limit=5, translation=DEFAULT_TRANSLATION):
    """Search the Bible for verses containing the query string (case-insensitive).

    Returns a list of (book_id, chapter, verse, text) tuples, up to `limit` results.
    """
    bible = _get_bible(translation)
    query_lower = query.lower()
    results = []
    for book_id, chapters in bible.items():
        for chapter, verses in chapters.items():
            for verse, text in verses.items():
                if query_lower in text.lower():
                    results.append((book_id, chapter, verse, text))
                    if len(results) >= limit:
                        return results
    return results


def format_bible_search_view(query, results, translation=DEFAULT_TRANSLATION):
    """Format search results as a Components V2 LayoutView."""
    translation_label = TRANSLATIONS.get(translation, translation)
    view = LayoutView()
    container = Container(accent_colour=0x3E621B)
    container.add_item(TextDisplay(f'### Bible Search: "{query}"'))

    if not results:
        container.add_item(TextDisplay("No matching verses found."))
    else:
        lines = []
        for book_id, chapter, verse, text in results:
            display_name = BOOK_DISPLAY.get(book_id, book_id)
            ref = f"{display_name} {chapter}:{verse}"
            display_text = text if len(text) <= 200 else text[:197] + "..."
            lines.append(f"**{ref}** — {display_text}")
        body = "\n\n".join(lines)
        if len(body) > 4000:
            body = body[:3997] + "..."
        container.add_item(TextDisplay(body))

    container.add_item(TextDisplay(f"-# {translation_label}"))
    view.add_item(container)
    return view
