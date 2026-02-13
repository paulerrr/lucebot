import discord

from saint_quotes import SaintQuotes

sq = SaintQuotes("saint_quotes.db")


def get_daily_quote():
    """Return a random saint quote."""
    return sq.random()


def format_quote_for_discord(quote):
    """Format a saint quote as a Discord embed."""
    embed = discord.Embed(
        description=f"*\"{quote.quote}\"*",
        color=discord.Color.purple(),
    )
    embed.set_footer(text=f"— {quote.author}")
    return embed
