import logging
import os

import aiohttp
import discord

log = logging.getLogger("lucebot")

API_URL = "https://the-collection-of-catholic-prayers-api.vercel.app/v1/today_saint"
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"


async def _generate_saint_summary(name: str, session: aiohttp.ClientSession) -> str | None:
    """Use OpenRouter to generate a brief biography of the saint."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        log.warning("OPENROUTER_API_KEY not set — skipping saint summary")
        return None

    prompt = (
        f"Write a 1-2 paragraph biography of {name}, "
        f"including what they are the patron saint of (if applicable). "
        f"Be factual and concise."
    )

    payload = {
        "model": "openrouter/free",
        "messages": [{"role": "user", "content": prompt}],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with session.post(OPENROUTER_API_URL, json=payload, headers=headers) as resp:
            if resp.status != 200:
                log.error("OpenRouter request failed (HTTP %s)", resp.status)
                return None
            data = await resp.json()
            return data["choices"][0]["message"]["content"].strip()
    except Exception:
        log.exception("Failed to generate saint summary")
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

            if not data:
                return "no_feast"

            saint = data[0]
            name = saint.get("saint_name", "Unknown Saint")
            saint_date = saint.get("saint_date", "")

            summary = await _generate_saint_summary(name, session)

            embed = discord.Embed(title=name, color=discord.Color.gold())
            if summary:
                embed.description = summary
            if saint_date:
                embed.set_footer(text=saint_date)

            return [embed]
    except Exception:
        log.exception("Failed to fetch saint")
        return None
