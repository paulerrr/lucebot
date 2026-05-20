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
    search_verses, format_bible_search_view, TRANSLATIONS, DEFAULT_TRANSLATION,
)
import config as cfg
from social_interactions import SocialInteractions

load_dotenv()
cfg.load()

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")
QUOTE_CHANNEL_ID = os.getenv("DISCORD_QUOTE_CHANNEL_ID")
SAINT_CHANNEL_ID = os.getenv("DISCORD_SAINT_CHANNEL_ID")
READINGS_TYPE = os.getenv("READINGS_TYPE", "novus_ordo").lower()
_guild_id_env = os.getenv("DISCORD_GUILD_ID")
GUILD_ID = int(_guild_id_env) if _guild_id_env else None

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN not set in .env")
if not CHANNEL_ID:
    raise RuntimeError("DISCORD_CHANNEL_ID not set in .env")
CHANNEL_ID = int(CHANNEL_ID)
QUOTE_CHANNEL_ID = int(QUOTE_CHANNEL_ID) if QUOTE_CHANNEL_ID else None
SAINT_CHANNEL_ID = int(SAINT_CHANNEL_ID) if SAINT_CHANNEL_ID else None
_purgatory_channel_env = os.getenv("DISCORD_PURGATORY_CHANNEL_ID")
_purgatory_role_env = os.getenv("DISCORD_PURGATORY_ROLE_ID")
PURGATORY_CHANNEL_ID = int(_purgatory_channel_env) if _purgatory_channel_env else None
PURGATORY_ROLE_ID = int(_purgatory_role_env) if _purgatory_role_env else None
_log_channel_env = os.getenv("DISCORD_LOG_CHANNEL_ID")
LOG_CHANNEL_ID = int(_log_channel_env) if _log_channel_env else None

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("lucebot")

social = SocialInteractions()

EST = datetime.timezone(datetime.timedelta(hours=-5))

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)


async def post_readings(channel):
    """Fetch readings and send them to the given channel."""
    mass = await get_daily_readings()
    if mass is None:
        await channel.send("Could not fetch today's readings.")
        return

    embeds = format_for_discord(mass)

    for embed in embeds:
        await channel.send(embed=embed)


async def post_latin_readings(channel):
    """Fetch TLM propers and send them to the given channel."""
    data = await get_latin_readings()
    if data is None:
        await channel.send("Could not fetch today's Traditional Latin Mass readings.")
        return

    embeds = format_latin_for_discord(data)

    for embed in embeds:
        await channel.send(embed=embed)


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


@tree.command(name="set-translation", description="Set your preferred Bible translation")
@discord.app_commands.describe(translation="The translation to use for your Bible verse lookups")
@discord.app_commands.choices(translation=[
    discord.app_commands.Choice(name="Knox Bible", value="knox"),
    discord.app_commands.Choice(name="Douay-Rheims", value="dr"),
    discord.app_commands.Choice(name="Clementine Vulgate (Latin)", value="vul"),
    discord.app_commands.Choice(name="RSV Catholic Edition", value="rsvce"),
    discord.app_commands.Choice(name="New American Bible Revised Edition", value="nabre"),
])
async def set_translation_command(interaction: discord.Interaction, translation: str):
    cfg.set_user(interaction.user.id, "translation", translation)
    label = TRANSLATIONS.get(translation, translation)
    await interaction.response.send_message(
        f"Your Bible translation has been set to **{label}**.", ephemeral=True
    )
    log.info("User %s set translation to %s", interaction.user, translation)


@tree.command(name="search", description="Search the Bible for a word or phrase")
@discord.app_commands.describe(query="The word or phrase to search for")
async def search_command(interaction: discord.Interaction, query: str):
    log.info("Bible search from %s: %s", interaction.user, query)
    translation = cfg.get_user(interaction.user.id, "translation", DEFAULT_TRANSLATION)
    results = search_verses(query, translation=translation)
    view = format_bible_search_view(query, results, translation=translation)
    await interaction.response.send_message(view=view)


@tree.command(name="translations", description="List available Bible translations and your current preference")
async def translations_command(interaction: discord.Interaction):
    current = cfg.get_user(interaction.user.id, "translation", DEFAULT_TRANSLATION)
    lines = [f"**Available Bible translations** (default: `{DEFAULT_TRANSLATION}`)\n"]
    for key, label in TRANSLATIONS.items():
        marker = " ← yours" if key == current else ""
        lines.append(f"- `[{key}]`  {label}{marker}")
    lines.append("\nUse `/set-translation` to change your preference, or append `[key]` inline (e.g. `John 3:16 [nabre]`).")
    await interaction.response.send_message("\n".join(lines), ephemeral=True)


def _get_log_channel():
    log_channel_id = LOG_CHANNEL_ID or cfg.get("log_channel_id")
    if log_channel_id:
        return client.get_channel(log_channel_id)
    return None


@tree.command(name="set-log-channel", description="Set the channel where member join/leave events are logged")
@discord.app_commands.describe(channel="The channel to log joins and leaves in")
@discord.app_commands.default_permissions(manage_guild=True)
async def set_log_channel_command(interaction: discord.Interaction, channel: discord.TextChannel):
    cfg.set("log_channel_id", channel.id)
    await interaction.response.send_message(
        f"Member join/leave events will now be logged in {channel.mention}.", ephemeral=True
    )
    log.info("Log channel set to %s by %s", channel.id, interaction.user)


@tree.command(name="purgatory-setup", description="Set up the purgatory verification system")
@discord.app_commands.describe(
    channel="Existing purgatory channel (creates #purgatory if not specified)",
    role="Existing purgatory role (creates Purgatory role if not specified)",
)
@discord.app_commands.default_permissions(manage_guild=True)
async def purgatory_setup_command(
    interaction: discord.Interaction,
    channel: discord.TextChannel = None,
    role: discord.Role = None,
):
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild

    # Resolve or create role
    if role is None:
        role = discord.utils.get(guild.roles, name="Purgatory")
        if role is None:
            role = await guild.create_role(
                name="Purgatory",
                color=discord.Color.dark_grey(),
                reason="Purgatory verification setup",
            )
            role_status = f"Created new role {role.mention}"
        else:
            role_status = f"Found existing role {role.mention}"
    else:
        role_status = f"Using role {role.mention}"

    # Resolve or create channel
    if channel is None:
        channel = discord.utils.get(guild.text_channels, name="purgatory")
        if channel is None:
            channel = await guild.create_text_channel(
                name="purgatory",
                reason="Purgatory verification setup",
            )
            channel_status = f"Created new channel {channel.mention}"
        else:
            channel_status = f"Found existing channel {channel.mention}"
    else:
        channel_status = f"Using channel {channel.mention}"

    # Allow purgatory role in the purgatory channel
    await channel.set_permissions(
        role, view_channel=True, send_messages=True, read_message_history=True
    )

    # Deny purgatory role access to all other channels
    denied = 0
    for ch in guild.channels:
        if ch.id == channel.id or isinstance(ch, discord.CategoryChannel):
            continue
        try:
            await ch.set_permissions(role, view_channel=False)
            denied += 1
        except discord.Forbidden:
            log.warning("Could not set permissions on channel %s", ch)

    # Save to persistent config
    cfg.set("purgatory_channel_id", channel.id)
    cfg.set("purgatory_role_id", role.id)

    await interaction.followup.send(
        f"Purgatory setup complete!\n"
        f"- {role_status}\n"
        f"- {channel_status}\n"
        f"- Denied access to {denied} other channel(s)\n\n"
        f"New members will be assigned {role.mention} and directed to {channel.mention} for verification.",
        ephemeral=True,
    )
    log.info(
        "Purgatory setup by %s: role=%s channel=%s denied=%d",
        interaction.user, role.id, channel.id, denied,
    )


@tree.command(name="verify", description="Remove the Purgatory role from a member to grant server access")
@discord.app_commands.describe(member="The member to verify")
@discord.app_commands.default_permissions(manage_roles=True)
async def verify_command(interaction: discord.Interaction, member: discord.Member):
    purgatory_role_id = PURGATORY_ROLE_ID or cfg.get("purgatory_role_id")
    if not purgatory_role_id:
        await interaction.response.send_message("Purgatory role not configured. Run /purgatory-setup first.", ephemeral=True)
        return

    role = interaction.guild.get_role(purgatory_role_id)
    if role is None:
        await interaction.response.send_message("Purgatory role not found in this server.", ephemeral=True)
        return

    if role not in member.roles:
        await interaction.response.send_message(f"{member.mention} does not have the Purgatory role.", ephemeral=True)
        return

    try:
        await member.remove_roles(role, reason=f"Verified by {interaction.user}")
    except discord.Forbidden:
        await interaction.response.send_message("Missing permissions to remove the Purgatory role.", ephemeral=True)
        return

    await interaction.response.send_message(f"{member.mention} has been verified and granted access.", ephemeral=True)
    log.info("Verified %s (Purgatory role removed by %s)", member, interaction.user)


async def _apply_reaction_role(payload, *, add: bool):
    reaction_roles = cfg.get("reaction_roles", {})
    mapping = reaction_roles.get(str(payload.message_id))
    if not mapping:
        return
    role_id = mapping.get(str(payload.emoji))
    if role_id is None:
        return
    guild = client.get_guild(payload.guild_id)
    if guild is None:
        return
    member = guild.get_member(payload.user_id)
    if member is None or member.bot:
        return
    role = guild.get_role(role_id)
    if role is None:
        return
    if add:
        await member.add_roles(role, reason="Reaction role")
        log.info("Added role %s to %s via reaction", role, member)
    else:
        await member.remove_roles(role, reason="Reaction role removed")
        log.info("Removed role %s from %s via reaction", role, member)


@client.event
async def on_raw_reaction_add(payload):
    if payload.guild_id is None or payload.user_id == client.user.id:
        return
    await _apply_reaction_role(payload, add=True)


@client.event
async def on_raw_reaction_remove(payload):
    if payload.guild_id is None:
        return
    await _apply_reaction_role(payload, add=False)


@tree.command(name="reaction-role-setup", description="Post a reaction role message in a channel")
@discord.app_commands.describe(
    channel="Channel to post the message in",
    title="Title shown on the embed",
    emoji1="First emoji", role1="Role for first emoji",
    emoji2="Second emoji", role2="Role for second emoji",
    emoji3="Third emoji", role3="Role for third emoji",
    emoji4="Fourth emoji", role4="Role for fourth emoji",
    emoji5="Fifth emoji", role5="Role for fifth emoji",
)
@discord.app_commands.default_permissions(manage_roles=True)
async def reaction_role_setup_command(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    title: str,
    emoji1: str, role1: discord.Role,
    emoji2: str = None, role2: discord.Role = None,
    emoji3: str = None, role3: discord.Role = None,
    emoji4: str = None, role4: discord.Role = None,
    emoji5: str = None, role5: discord.Role = None,
):
    await interaction.response.defer(ephemeral=True)

    pairs = [(e, r) for e, r in [
        (emoji1, role1), (emoji2, role2), (emoji3, role3),
        (emoji4, role4), (emoji5, role5),
    ] if e and r]

    description = "\n".join(f"{e}  →  {r.mention}" for e, r in pairs)
    embed = discord.Embed(title=title, description=description, color=discord.Color.blurple())
    embed.set_footer(text="React to receive a role. Remove your reaction to remove the role.")

    msg = await channel.send(embed=embed)

    reaction_roles = cfg.get("reaction_roles", {})
    reaction_roles[str(msg.id)] = {e: r.id for e, r in pairs}
    cfg.set("reaction_roles", reaction_roles)

    for emoji, _ in pairs:
        try:
            await msg.add_reaction(emoji)
        except discord.HTTPException:
            log.warning("Could not add reaction %s to message %s", emoji, msg.id)

    await interaction.followup.send(
        f"Reaction role message posted in {channel.mention} with {len(pairs)} role(s).",
        ephemeral=True,
    )
    log.info("Reaction role message %s created by %s", msg.id, interaction.user)


@tree.command(name="reaction-role-add", description="Add more emoji→role pairs to an existing reaction role message")
@discord.app_commands.describe(
    message_id="ID of the reaction role message to extend",
    emoji1="First emoji", role1="Role for first emoji",
    emoji2="Second emoji", role2="Role for second emoji",
    emoji3="Third emoji", role3="Role for third emoji",
    emoji4="Fourth emoji", role4="Role for fourth emoji",
    emoji5="Fifth emoji", role5="Role for fifth emoji",
)
@discord.app_commands.default_permissions(manage_roles=True)
async def reaction_role_add_command(
    interaction: discord.Interaction,
    message_id: str,
    emoji1: str, role1: discord.Role,
    emoji2: str = None, role2: discord.Role = None,
    emoji3: str = None, role3: discord.Role = None,
    emoji4: str = None, role4: discord.Role = None,
    emoji5: str = None, role5: discord.Role = None,
):
    await interaction.response.defer(ephemeral=True)

    reaction_roles = cfg.get("reaction_roles", {})
    if message_id not in reaction_roles:
        await interaction.followup.send("No reaction role message found with that ID.", ephemeral=True)
        return

    pairs = [(e, r) for e, r in [
        (emoji1, role1), (emoji2, role2), (emoji3, role3),
        (emoji4, role4), (emoji5, role5),
    ] if e and r]

    reaction_roles[message_id].update({e: r.id for e, r in pairs})
    cfg.set("reaction_roles", reaction_roles)

    # Find the message across all channels to add reactions
    msg = None
    for ch in interaction.guild.text_channels:
        try:
            msg = await ch.fetch_message(int(message_id))
            break
        except (discord.NotFound, discord.Forbidden):
            continue

    if msg:
        for emoji, _ in pairs:
            try:
                await msg.add_reaction(emoji)
            except discord.HTTPException:
                log.warning("Could not add reaction %s to message %s", emoji, message_id)

        # Rebuild embed description from the full updated mapping
        full_mapping = reaction_roles[message_id]
        lines = []
        for emoji, role_id in full_mapping.items():
            role = interaction.guild.get_role(role_id)
            role_str = role.mention if role else f"(unknown role)"
            lines.append(f"{emoji}  →  {role_str}")
        if msg.embeds:
            embed = msg.embeds[0]
            embed.description = "\n".join(lines)
            await msg.edit(embed=embed)

    await interaction.followup.send(
        f"Added {len(pairs)} emoji→role pair(s) to message `{message_id}`.",
        ephemeral=True,
    )
    log.info("Reaction role message %s updated by %s", message_id, interaction.user)


@tree.command(name="reaction-role-list", description="List all configured reaction role messages")
@discord.app_commands.default_permissions(manage_roles=True)
async def reaction_role_list_command(interaction: discord.Interaction):
    reaction_roles = cfg.get("reaction_roles", {})
    if not reaction_roles:
        await interaction.response.send_message("No reaction role messages configured.", ephemeral=True)
        return

    lines = []
    for msg_id, mapping in reaction_roles.items():
        pairs = []
        for emoji, role_id in mapping.items():
            role = interaction.guild.get_role(role_id)
            role_str = role.mention if role else f"(deleted role {role_id})"
            pairs.append(f"{emoji} → {role_str}")
        lines.append(f"**Message `{msg_id}`**\n" + "\n".join(pairs))

    await interaction.response.send_message("\n\n".join(lines), ephemeral=True)


@tree.command(name="reaction-role-remove", description="Delete a reaction role message and remove its configuration")
@discord.app_commands.describe(message_id="ID of the reaction role message to remove")
@discord.app_commands.default_permissions(manage_roles=True)
async def reaction_role_remove_command(interaction: discord.Interaction, message_id: str):
    await interaction.response.defer(ephemeral=True)

    reaction_roles = cfg.get("reaction_roles", {})
    if message_id not in reaction_roles:
        await interaction.followup.send("No reaction role message found with that ID.", ephemeral=True)
        return

    del reaction_roles[message_id]
    cfg.set("reaction_roles", reaction_roles)

    # Try to delete the actual message
    deleted = False
    for ch in interaction.guild.text_channels:
        try:
            msg = await ch.fetch_message(int(message_id))
            await msg.delete()
            deleted = True
            break
        except (discord.NotFound, discord.Forbidden):
            continue

    status = "Message deleted and config removed." if deleted else "Config removed (message was already deleted or not found)."
    await interaction.followup.send(status, ephemeral=True)
    log.info("Reaction role message %s removed by %s", message_id, interaction.user)


@client.event
async def on_ready():
    log.info("Logged in as %s", client.user)
    await tree.sync()
    if GUILD_ID:
        guild_obj = discord.Object(id=GUILD_ID)
        await tree.sync(guild=guild_obj)
        log.info("Slash commands synced (global + guild %s)", GUILD_ID)
    else:
        log.info("Slash commands synced (global only — may take up to 1 hour)")
    if not daily_readings.is_running():
        daily_readings.start()


@client.event
async def on_member_join(member):
    purgatory_channel_id = PURGATORY_CHANNEL_ID or cfg.get("purgatory_channel_id")
    purgatory_role_id = PURGATORY_ROLE_ID or cfg.get("purgatory_role_id")
    if purgatory_channel_id and purgatory_role_id:
        guild = member.guild
        role = guild.get_role(purgatory_role_id)
        if role is None:
            log.error("Purgatory role %s not found in guild", purgatory_role_id)
        else:
            try:
                await member.add_roles(role, reason="New member — awaiting verification")
            except discord.Forbidden:
                log.error("Missing permissions to assign purgatory role to %s", member)
            else:
                channel = client.get_channel(purgatory_channel_id)
                if channel is None:
                    log.error("Purgatory channel %s not found", purgatory_channel_id)
                else:
                    await channel.send(
                        f"Welcome, {member.mention}! Before you can access the server, please answer "
                        f"the following questions here:\n\n"
                        f"1. Are you Catholic or enquiring? If not, what denomination or religion?\n"
                        f"2. Are you 18 years old or older?\n"
                        f"3. Do you disagree with any traditional Church teachings?\n"
                        f"4. Are you sedevacantist?\n"
                        f"5. Do you want a rosary or prayer ping?\n\n"
                        f"Once you've answered, please ping a mod so they can verify you and grant you access."
                    )
                    log.info("Assigned purgatory role and posted verification prompt for %s", member)

    log_channel = _get_log_channel()
    if log_channel:
        created = discord.utils.format_dt(member.created_at, style="D")
        embed = discord.Embed(
            title="Member Joined",
            description=f"{member.mention} ({member})",
            color=discord.Color.green(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Account Created", value=created)
        embed.add_field(name="Member Count", value=str(member.guild.member_count))
        embed.set_footer(text=f"ID: {member.id}")
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        await log_channel.send(embed=embed)


@client.event
async def on_member_remove(member):
    log_channel = _get_log_channel()
    if not log_channel:
        return
    roles = [r.mention for r in member.roles if r.name != "@everyone"]
    embed = discord.Embed(
        title="Member Left",
        description=f"{member.mention} ({member})",
        color=discord.Color.red(),
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    if roles:
        embed.add_field(name="Roles", value=" ".join(roles), inline=False)
    embed.add_field(name="Member Count", value=str(member.guild.member_count))
    embed.set_footer(text=f"ID: {member.id}")
    embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
    await log_channel.send(embed=embed)


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

    if message.content.startswith("!verify "):
        if not message.author.guild_permissions.manage_roles:
            await message.channel.send("You don't have permission to verify members.")
            return
        args = message.content.split()
        if len(args) < 2 or not message.mentions:
            await message.channel.send("Usage: `!verify @member`")
            return
        member = message.mentions[0]
        purgatory_role_id = PURGATORY_ROLE_ID or cfg.get("purgatory_role_id")
        if not purgatory_role_id:
            await message.channel.send("Purgatory role not configured.")
            return
        role = message.guild.get_role(purgatory_role_id)
        if role is None:
            await message.channel.send("Purgatory role not found.")
            return
        if role not in member.roles:
            await message.channel.send(f"{member.mention} does not have the Purgatory role.")
            return
        await member.remove_roles(role, reason=f"Verified by {message.author}")
        await message.channel.send(f"{member.mention} has been verified and granted access.")
        log.info("Verified %s (Purgatory role removed by %s)", member, message.author)

    if message.content.startswith("!compliment"):
        await social.handle_compliment(message, client.user)

    if message.content.startswith("!insult"):
        await social.handle_insult(message, client.user)

    if message.content.startswith("!blockuser "):
        await social.handle_blockuser(message)

    if message.content.startswith("!unblockuser "):
        await social.handle_unblockuser(message)

    if message.content.strip() == "!listblockedusers":
        await social.handle_listblockedusers(message, client)

    if message.content.strip() == "!reload_messages":
        await social.handle_reload(message)

    if message.content.strip() == "!translations":
        current = cfg.get_user(message.author.id, "translation", DEFAULT_TRANSLATION)
        lines = [f"**Available Bible translations** (default: `{DEFAULT_TRANSLATION}`)\n"]
        for key, label in TRANSLATIONS.items():
            marker = " ← yours" if key == current else ""
            lines.append(f"- `[{key}]`  {label}{marker}")
        lines.append("\nUse `/set-translation` to change your preference, or append `[key]` inline (e.g. `John 3:16 [nabre]`).")
        await message.channel.send("\n".join(lines))

    # Bible verse lookup — check if the message contains a verse reference
    if not message.content.startswith("!"):
        parsed = parse_verse_reference(message.content)
        if parsed:
            book_id, chapter, verse_start, verse_end, translation_override = parsed
            translation = translation_override or cfg.get_user(message.author.id, "translation", DEFAULT_TRANSLATION)
            verses = lookup_verses(book_id, chapter, verse_start, verse_end, translation=translation)
            if verses:
                view = format_bible_view(book_id, chapter, verse_start, verse_end, verses, translation=translation)
                await message.channel.send(view=view)


client.run(TOKEN)
