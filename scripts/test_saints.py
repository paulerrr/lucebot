"""Live test of saints.get_daily_saint against Vatican News.

Usage: python scripts/test_saints.py [MM-DD]
"""
import asyncio
import datetime
import logging
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
logging.basicConfig(level=logging.INFO)

import saints


async def main() -> None:
    date_arg = sys.argv[1] if len(sys.argv) > 1 else None
    if date_arg:
        month, day = (int(x) for x in date_arg.split("-"))

        class FakeDT(datetime.datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, month, day, tzinfo=tz)

        saints.datetime.datetime = FakeDT

    result = await saints.get_daily_saint()
    if result is None:
        print("RESULT: None (fetch error)")
        return
    if result == "no_feast":
        print("RESULT: no_feast")
        return
    print(f"RESULT: {len(result)} embed(s)")
    for i, e in enumerate(result):
        desc = e.description or ""
        print(f"\n--- Embed {i}: title={e.title!r} url={e.url!r}")
        print(f"    thumbnail={e.thumbnail.url if e.thumbnail else None!r}")
        print(f"    desc len={len(desc)}")
        print("    " + desc[:400].replace("\n", "\n    "))
        if len(desc) > 400:
            print("    [...]")
            print("    " + desc[-200:].replace("\n", "\n    "))
        for f in e.fields:
            print(f"    FIELD {f.name!r}: {f.value!r}")
        if e.footer and e.footer.text:
            print(f"    footer: {e.footer.text}")


asyncio.run(main())
