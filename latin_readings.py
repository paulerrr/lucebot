import datetime
import logging

import aiohttp
import discord

log = logging.getLogger("lucebot")

API_URL = "https://www.missalemeum.com/en/api/v5/proper"
SITE_URL = "https://www.missalemeum.com/en"

# Sections to include in the Discord post (by id)
INCLUDE_SECTIONS = {
    "Introitus",
    "Oratio",
    "Lectio",
    "Graduale",
    "Tractus",
    "Sequentia",
    "Evangelium",
    "Offertorium",
    "Secreta",
    "Communio",
    "Postcommunio",
}

COLOR_MAP = {
    "w": "White",
    "r": "Red",
    "g": "Green",
    "v": "Violet",
    "b": "Black",
    "p": "Rose",
}


async def get_latin_readings():
    """Fetch today's TLM propers from the Missale Meum API."""
    today = datetime.date.today().isoformat()
    url = f"{API_URL}/{today}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    log.error("Missale Meum API returned %s", resp.status)
                    return None
                return await resp.json()
    except Exception:
        log.exception("Failed to fetch TLM propers")
        return None


def format_latin_for_discord(data):
    """Convert Missale Meum API response into a list of Discord Embeds."""
    # API returns a list of propers; use the first one
    if isinstance(data, list):
        data = data[0]

    embeds = []
    info = data.get("info", {})

    date_str = info.get("date", datetime.date.today().isoformat())
    title = info.get("title", "Traditional Latin Mass")
    colors = info.get("colors", [])
    rank = info.get("rank", "")
    tempora = info.get("tempora", "")

    # Build description from rank/color/tempora info
    desc_parts = []
    if tempora:
        desc_parts.append(tempora)
    color_names = [COLOR_MAP.get(c, c) for c in colors]
    if color_names:
        desc_parts.append(f"Color: {', '.join(color_names)}")
    if rank:
        desc_parts.append(f"Rank: {rank}")

    title_embed = discord.Embed(
        title=title,
        url=f"{SITE_URL}/{date_str}",
        description="\n".join(desc_parts) if desc_parts else None,
        color=discord.Color.dark_gold(),
    )
    embeds.append(title_embed)

    for section in data.get("sections", []):
        section_id = section.get("id", "")
        if section_id not in INCLUDE_SECTIONS:
            continue

        label = section.get("label", section_id)
        body = section.get("body", [])

        # Extract English text (first element of each pair)
        lines = []
        for pair in body:
            if isinstance(pair, list) and len(pair) >= 1:
                lines.append(pair[0])
            elif isinstance(pair, str):
                lines.append(pair)

        text = "\n\n".join(lines).strip()
        if not text:
            continue

        if len(text) > 4096:
            text = text[:4093] + "..."

        embed = discord.Embed(
            title=label,
            description=text,
            color=discord.Color.dark_gold(),
        )
        embeds.append(embed)

    return embeds
