import discord
from catholic_mass_readings import USCCB


async def get_daily_readings():
    """Fetch today's mass readings from the USCCB website."""
    async with USCCB() as usccb:
        return await usccb.get_today_mass()


def format_for_discord(mass):
    """Format a Mass object into a list of Discord Embeds.

    Returns a list of embeds: one title embed + one per section.
    Discord allows up to 10 embeds per message.
    """
    embeds = []

    # Title embed with mass info and link
    title_embed = discord.Embed(
        title=mass.title,
        url=mass.url,
        description=mass.date_str,
        color=discord.Color.gold(),
    )
    embeds.append(title_embed)

    # One embed per section
    for section in mass.sections:
        header = section.display_header

        for i, reading in enumerate(section.readings):
            # Build the embed title: header + verse reference
            verse_ref = reading.header if reading.header else ""
            if len(section.readings) > 1:
                label = "Long Form" if i == 0 else "Short Form"
                embed_title = f"{header} ({label}) — {verse_ref}" if verse_ref else f"{header} ({label})"
            else:
                embed_title = f"{header} — {verse_ref}" if verse_ref else header

            # The reading text; truncate if over embed description limit
            text = reading.text.strip()
            if len(text) > 4096:
                text = text[:4093] + "..."

            embed = discord.Embed(
                title=embed_title,
                description=text,
                color=discord.Color.blue(),
            )

            # Add verse link if available
            if reading.verses:
                embed.url = reading.verses[0].link

            # Add footer for readings/gospel
            if section.footer:
                embed.set_footer(text=section.footer)

            embeds.append(embed)

    return embeds
