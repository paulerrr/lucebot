import datetime
import logging

import aiohttp
import discord

log = logging.getLogger("lucebot")

API_BASE = "https://cpbjr.github.io/catholic-readings-api/liturgical-calendar"


FEAST_TYPES = {"memorial", "feast", "solemnity", "optional memorial"}


async def get_daily_saint() -> list[discord.Embed] | None | str:
    """Fetch the saint/celebration of the day from the liturgical calendar API.

    Returns a list of embeds for a saint feast, the string ``"no_feast"`` when
    the day is an ordinary weekday (FERIA), or ``None`` on fetch errors.
    """
    today = datetime.date.today()
    url = f"{API_BASE}/{today.year}/{today.strftime('%m-%d')}.json"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    log.info("No saint data for %s (HTTP %s)", today, resp.status)
                    return None
                data = await resp.json()
    except Exception:
        log.exception("Failed to fetch saint data")
        return None

    celebration = data.get("celebration")
    if not celebration:
        return "no_feast"

    cel_type = celebration.get("type", "")
    if cel_type.lower() not in FEAST_TYPES:
        return "no_feast"

    name = celebration.get("name", "Unknown Celebration")
    quote = celebration.get("quote", "")
    description = celebration.get("description", "")
    wiki_link = data.get("wikipediaLink", "")

    embed = discord.Embed(
        title=name,
        url=wiki_link or None,
        description=description or None,
        color=discord.Color.red(),
    )

    if cel_type:
        embed.add_field(name="Type", value=cel_type, inline=True)

    if quote:
        embed.set_footer(text=quote)

    return [embed]
