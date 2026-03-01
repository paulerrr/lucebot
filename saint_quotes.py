"""Reusable saint quotes query module.

Copy this file (and saint_quotes.db) into any project to query quotes.

Usage:
    from saint_quotes import SaintQuotes

    sq = SaintQuotes()              # uses default DB path
    sq = SaintQuotes("path/to.db")  # or specify a path

    sq.random()                     # one random quote
    sq.random(topic="PRAYER")       # random quote on a topic
    sq.random(author="Augustine")   # random quote by an author (substring match)

    sq.search("love")              # full-text search in quote body
    sq.by_author("Thomas Aquinas") # all quotes by author (substring match)
    sq.by_topic("HUMILITY")       # all quotes under a topic (exact match)
    sq.topics()                    # list all topics
    sq.authors()                   # list all authors
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional


DEFAULT_DB = Path(__file__).resolve().parent / "saint_quotes.db"


class Quote:
    __slots__ = ("id", "topic", "quote", "author", "page", "source_id")

    def __init__(self, row: tuple) -> None:
        self.id, self.topic, self.quote, self.author, self.page, self.source_id = row

    def __repr__(self) -> str:
        return f"Quote({self.id}, {self.author!r}, {self.quote[:50]!r}...)"

    def __str__(self) -> str:
        return f'"{self.quote}"\n  — {self.author} (on {self.topic})'

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "topic": self.topic,
            "quote": self.quote,
            "author": self.author,
            "page": self.page,
            "source_id": self.source_id,
        }


class SaintQuotes:
    def __init__(self, db_path: str | Path = DEFAULT_DB) -> None:
        self._con = sqlite3.connect(str(db_path))
        self._con.row_factory = None

    def close(self) -> None:
        self._con.close()

    def __enter__(self) -> "SaintQuotes":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # --- queries ---

    _COLS = "id, topic, quote, author, page, source_id"

    def random(
        self,
        topic: Optional[str] = None,
        author: Optional[str] = None,
    ) -> Quote | None:
        """Return one random quote, optionally filtered by topic or author."""
        clauses, params = [], []
        if topic:
            clauses.append("topic = ?")
            params.append(topic.upper())
        if author:
            clauses.append("author LIKE ?")
            params.append(f"%{author}%")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        row = self._con.execute(
            f"SELECT {self._COLS} FROM saint_quotes {where} ORDER BY RANDOM() LIMIT 1",
            params,
        ).fetchone()
        return Quote(row) if row else None

    def search(self, term: str, limit: int = 20) -> list[Quote]:
        """Search quote text (case-insensitive substring)."""
        rows = self._con.execute(
            f"SELECT {self._COLS} FROM saint_quotes WHERE quote LIKE ? LIMIT ?",
            (f"%{term}%", limit),
        ).fetchall()
        return [Quote(r) for r in rows]

    def by_author(self, author: str) -> list[Quote]:
        """All quotes by author (substring match)."""
        rows = self._con.execute(
            f"SELECT {self._COLS} FROM saint_quotes WHERE author LIKE ? ORDER BY topic",
            (f"%{author}%",),
        ).fetchall()
        return [Quote(r) for r in rows]

    def by_topic(self, topic: str) -> list[Quote]:
        """All quotes under a topic (exact match, case-insensitive)."""
        rows = self._con.execute(
            f"SELECT {self._COLS} FROM saint_quotes WHERE topic = ? ORDER BY id",
            (topic.upper(),),
        ).fetchall()
        return [Quote(r) for r in rows]

    def topics(self) -> list[str]:
        """List all distinct topics."""
        return [
            r[0] for r in self._con.execute(
                "SELECT DISTINCT topic FROM saint_quotes ORDER BY topic"
            ).fetchall()
        ]

    def authors(self) -> list[str]:
        """List all distinct authors."""
        return [
            r[0] for r in self._con.execute(
                "SELECT DISTINCT author FROM saint_quotes ORDER BY author"
            ).fetchall()
        ]

    def sources(self) -> list[dict]:
        """List all sources."""
        rows = self._con.execute(
            "SELECT id, title, author, publisher, year, isbn FROM sources ORDER BY id"
        ).fetchall()
        keys = ("id", "title", "author", "publisher", "year", "isbn")
        return [dict(zip(keys, r)) for r in rows]

    def by_source(self, source_id: int) -> list[Quote]:
        """All quotes from a given source."""
        rows = self._con.execute(
            f"SELECT {self._COLS} FROM saint_quotes WHERE source_id = ? ORDER BY id",
            (source_id,),
        ).fetchall()
        return [Quote(r) for r in rows]

    def count(self) -> int:
        return self._con.execute("SELECT COUNT(*) FROM saint_quotes").fetchone()[0]
