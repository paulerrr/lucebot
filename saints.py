import datetime
import logging
import sqlite3

import aiohttp
import discord

log = logging.getLogger("lucebot")

API_URL = "https://the-collection-of-catholic-prayers-api.vercel.app/v1/today_saint"

_PREFIXES = ("SAINT ", "ST. ", "ST ", "BLESSED ", "BL. ", "BL ", "BD. ", "BD ")


def _normalize(name):
    n = name.upper().strip()
    for p in _PREFIXES:
        if n.startswith(p):
            return n[len(p):].strip()
    return n


def lookup_saint_bio(saint_name, month_name, day):
    try:
        con = sqlite3.connect("saints.db")
    except Exception:
        log.exception("Failed to open saints.db")
        return None

    try:
        cur = con.execute(
            "SELECT name, body_text FROM saints WHERE feast_month = ? AND feast_day = ?",
            (month_name, day),
        )
        rows = cur.fetchall()
    except Exception:
        log.exception("Failed to query saints.db")
        return None
    finally:
        con.close()

    if not rows:
        return None

    if len(rows) == 1:
        return rows[0][1]

    normalized_api = _normalize(saint_name)
    # Exact match
    for db_name, body_text in rows:
        if _normalize(db_name) == normalized_api:
            return body_text
    # Substring match (handles "DAVID" vs "DAVID OF WALES", etc.)
    for db_name, body_text in rows:
        norm_db = _normalize(db_name)
        if norm_db in normalized_api or normalized_api in norm_db:
            return body_text

    return None


async def get_daily_saint() -> list[discord.Embed] | None | str:
    """Fetch today's saint from the Catholic Prayers API.

    Returns a list with one embed, the string ``"no_feast"`` when no saint
    is found, or ``None`` on fetch errors.
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(API_URL) as resp:
                if resp.status != 200:
                    log.error("Failed to fetch saint (HTTP %s)", resp.status)
                    return None
                data = await resp.json()
    except Exception:
        log.exception("Failed to fetch saint")
        return None

    if not data:
        return "no_feast"

    saint = data[0]
    name = saint.get("saint_name", "Unknown Saint")
    saint_date = saint.get("saint_date", "")

    embed = discord.Embed(title=name, color=discord.Color.gold())

    today = datetime.date.today()
    month_name = today.strftime("%B")
    day = today.day
    bio = lookup_saint_bio(name, month_name, day)

    if bio:
        if len(bio) > 2000:
            bio = bio[:2000] + "…"
        embed.description = bio
        footer = f"{saint_date} · Butler's Lives of the Saints" if saint_date else "Butler's Lives of the Saints"
    else:
        footer = saint_date

    if footer:
        embed.set_footer(text=footer)

    return [embed]
