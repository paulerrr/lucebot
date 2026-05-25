import logging
from pathlib import Path

import aiosqlite
import discord

log = logging.getLogger("lucebot.msgstore")

DB_PATH = Path("data/messages.db")
_db: aiosqlite.Connection = None


async def init():
    global _db
    if _db is not None:
        return
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    _db = await aiosqlite.connect(DB_PATH)
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            message_id  INTEGER PRIMARY KEY,
            guild_id    INTEGER NOT NULL,
            channel_id  INTEGER NOT NULL,
            author_id   INTEGER NOT NULL,
            author_name TEXT    NOT NULL,
            author_avatar TEXT,
            content     TEXT,
            created_at  REAL    NOT NULL
        )
    """)
    await _db.commit()
    log.info("Message store initialised at %s", DB_PATH)


async def store(message: discord.Message):
    await _db.execute(
        "INSERT OR REPLACE INTO messages VALUES (?,?,?,?,?,?,?,?)",
        (
            message.id,
            message.guild.id,
            message.channel.id,
            message.author.id,
            str(message.author),
            str(message.author.display_avatar.url),
            message.content,
            message.created_at.timestamp(),
        ),
    )
    await _db.commit()


async def get(message_id: int) -> dict | None:
    async with _db.execute(
        "SELECT * FROM messages WHERE message_id = ?", (message_id,)
    ) as cursor:
        row = await cursor.fetchone()
    return _row(row) if row else None


async def get_many(message_ids: list[int]) -> list[dict]:
    if not message_ids:
        return []
    placeholders = ",".join("?" * len(message_ids))
    async with _db.execute(
        f"SELECT * FROM messages WHERE message_id IN ({placeholders})", message_ids
    ) as cursor:
        rows = await cursor.fetchall()
    return [_row(r) for r in rows]


async def update_content(message_id: int, new_content: str):
    await _db.execute(
        "UPDATE messages SET content = ? WHERE message_id = ?", (new_content, message_id)
    )
    await _db.commit()


async def delete(message_id: int):
    await _db.execute("DELETE FROM messages WHERE message_id = ?", (message_id,))
    await _db.commit()


async def delete_many(message_ids: list[int]):
    if not message_ids:
        return
    placeholders = ",".join("?" * len(message_ids))
    await _db.execute(
        f"DELETE FROM messages WHERE message_id IN ({placeholders})", message_ids
    )
    await _db.commit()



def _row(row) -> dict:
    return {
        "message_id":   row[0],
        "guild_id":     row[1],
        "channel_id":   row[2],
        "author_id":    row[3],
        "author_name":  row[4],
        "author_avatar": row[5],
        "content":      row[6],
        "created_at":   row[7],
    }
