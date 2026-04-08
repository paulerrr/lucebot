import logging

import aiohttp
import discord

log = logging.getLogger("lucebot")

API_URL = "https://the-collection-of-catholic-prayers-api.vercel.app/v1/today_saint"


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

    if saint_date:
        embed.set_footer(text=saint_date)

    return [embed]
