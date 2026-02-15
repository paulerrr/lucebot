import datetime
import logging
import os

import discord
from discord.ext import tasks
from dotenv import load_dotenv

from readings import get_daily_readings, format_for_discord
from latin_readings import get_latin_readings, format_latin_for_discord
from quotes import get_daily_quote, format_quote_for_discord
from saints import get_daily_saint
from bible import (
    parse_verse_reference, lookup_verses, format_bible_view,
    search_verses, format_bible_search_view,
)

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")
QUOTE_CHANNEL_ID = os.getenv("DISCORD_QUOTE_CHANNEL_ID")
SAINT_CHANNEL_ID = os.getenv("DISCORD_SAINT_CHANNEL_ID")
READINGS_TYPE = os.getenv("READINGS_TYPE", "novus_ordo").lower()

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN not set in .env")
if not CHANNEL_ID:
    raise RuntimeError("DISCORD_CHANNEL_ID not set in .env")
CHANNEL_ID = int(CHANNEL_ID)
QUOTE_CHANNEL_ID = int(QUOTE_CHANNEL_ID) if QUOTE_CHANNEL_ID else None
SAINT_CHANNEL_ID = int(SAINT_CHANNEL_ID) if SAINT_CHANNEL_ID else None

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("lucebot")

EST = datetime.timezone(datetime.timedelta(hours=-5))

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)


async def post_readings(channel):
    """Fetch readings and send them to the given channel."""
    mass = await get_daily_readings()
    if mass is None:
        await channel.send("Could not fetch today's readings.")
        return

    embeds = format_for_discord(mass)

    # Discord allows max 10 embeds per message; batch if needed
    for i in range(0, len(embeds), 10):
        await channel.send(embeds=embeds[i : i + 10])


async def post_latin_readings(channel):
    """Fetch TLM propers and send them to the given channel."""
    data = await get_latin_readings()
    if data is None:
        await channel.send("Could not fetch today's Traditional Latin Mass readings.")
        return

    embeds = format_latin_for_discord(data)

    for i in range(0, len(embeds), 10):
        await channel.send(embeds=embeds[i : i + 10])


async def post_quote(channel):
    """Fetch a random saint quote and send it to the given channel."""
    quote = get_daily_quote()
    embed = format_quote_for_discord(quote)
    await channel.send(embed=embed)


async def post_saint(channel, *, manual=False):
    """Fetch the saint of the day and send it to the given channel."""
    result = await get_daily_saint()
    if result is None:
        if manual:
            await channel.send("Could not fetch saint data.")
        return
    if result == "no_feast":
        if manual:
            await channel.send("No saint feast today.")
        return
    await channel.send(embeds=result)


@tasks.loop(time=datetime.time(hour=7, minute=0, tzinfo=EST))
async def daily_readings():
    """Post readings and quote every day at 7:00 AM EST."""
    channel = client.get_channel(CHANNEL_ID)
    if channel is None:
        log.error("Channel %s not found", CHANNEL_ID)
    else:
        log.info("Posting daily readings (type=%s)", READINGS_TYPE)
        try:
            if READINGS_TYPE == "latin":
                await post_latin_readings(channel)
            else:
                await post_readings(channel)
        except Exception:
            log.exception("Failed to post daily readings")

    if QUOTE_CHANNEL_ID:
        quote_channel = client.get_channel(QUOTE_CHANNEL_ID)
        if quote_channel is None:
            log.error("Quote channel %s not found", QUOTE_CHANNEL_ID)
        else:
            log.info("Posting daily quote")
            try:
                await post_quote(quote_channel)
            except Exception:
                log.exception("Failed to post daily quote")

    if SAINT_CHANNEL_ID:
        saint_channel = client.get_channel(SAINT_CHANNEL_ID)
        if saint_channel is None:
            log.error("Saint channel %s not found", SAINT_CHANNEL_ID)
        else:
            log.info("Posting daily saint")
            try:
                await post_saint(saint_channel)
            except Exception:
                log.exception("Failed to post daily saint")


@tree.command(name="search", description="Search the Knox Bible for a word or phrase")
@discord.app_commands.describe(query="The word or phrase to search for")
async def search_command(interaction: discord.Interaction, query: str):
    log.info("Bible search from %s: %s", interaction.user, query)
    results = search_verses(query)
    view = format_bible_search_view(query, results)
    await interaction.response.send_message(view=view)


@client.event
async def on_ready():
    log.info("Logged in as %s", client.user)
    await tree.sync()
    log.info("Slash commands synced")
    if not daily_readings.is_running():
        daily_readings.start()


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.strip() == "!readings":
        log.info("Manual readings request from %s", message.author)
        await post_readings(message.channel)

    if message.content.strip() == "!quote":
        log.info("Manual quote request from %s", message.author)
        await post_quote(message.channel)

    if message.content.strip() == "!latin":
        log.info("Manual TLM readings request from %s", message.author)
        await post_latin_readings(message.channel)

    if message.content.strip() == "!saint":
        log.info("Manual saint request from %s", message.author)
        await post_saint(message.channel, manual=True)

    # Bible verse lookup — check if the message contains a verse reference
    if not message.content.startswith("!"):
        parsed = parse_verse_reference(message.content)
        if parsed:
            book_id, chapter, verse_start, verse_end = parsed
            verses = lookup_verses(book_id, chapter, verse_start, verse_end)
            if verses:
                view = format_bible_view(book_id, chapter, verse_start, verse_end, verses)
                await message.channel.send(view=view)


client.run(TOKEN)
