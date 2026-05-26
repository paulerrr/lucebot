import datetime
import io
import logging
import os
import re
import time

import discord
from dotenv import load_dotenv

import config as cfg
import message_store
from social_interactions import SocialInteractions

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("lucebot")


def _wait_for_token() -> str:
    while True:
        load_dotenv(override=True)
        token = os.getenv("DISCORD_TOKEN")
        if token:
            return token
        log.info("DISCORD_TOKEN not set — configure it via the web UI and save, then the bot will connect automatically")
        time.sleep(5)


TOKEN = _wait_for_token()
cfg.load()

_guild_id_env = os.getenv("DISCORD_GUILD_ID")
GUILD_ID = int(_guild_id_env) if _guild_id_env else None
_purgatory_channel_env = os.getenv("DISCORD_PURGATORY_CHANNEL_ID")
PURGATORY_CHANNEL_ID = int(_purgatory_channel_env) if _purgatory_channel_env else None
_purgatory_role_env = os.getenv("DISCORD_PURGATORY_ROLE_ID")
PURGATORY_ROLE_ID = int(_purgatory_role_env) if _purgatory_role_env else None
_log_channel_env = os.getenv("DISCORD_LOG_CHANNEL_ID")
LOG_CHANNEL_ID = int(_log_channel_env) if _log_channel_env else None

social = SocialInteractions()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)

INVITE_RE = re.compile(r"discord(?:\.gg|(?:app)?\.com/invite)/[\w-]+", re.IGNORECASE)

# Maps log_type → config key. "join" reuses the existing key for backwards compat.
_LOG_TYPE_KEYS = {
    "join": "log_channel_id",
    "message": "message_log_channel_id",
    "member": "member_log_channel_id",
}


def _get_log_channel(log_type: str = None):
    """Return the log channel for log_type, falling back to the join/generic channel."""
    if log_type:
        key = _LOG_TYPE_KEYS.get(log_type)
        if key:
            channel_id = cfg.get(key)
            if channel_id:
                ch = client.get_channel(channel_id)
                if ch:
                    return ch
    fallback_id = LOG_CHANNEL_ID or cfg.get("log_channel_id")
    if fallback_id:
        return client.get_channel(fallback_id)
    return None


# ── slash commands ─────────────────────────────────────────────────────────────

@tree.command(name="set-log-channel", description="Set the channel for a category of log events")
@discord.app_commands.describe(
    log_type="Which events to log in this channel",
    channel="The channel to send log events to",
)
@discord.app_commands.choices(log_type=[
    discord.app_commands.Choice(name="join/leave — member join and leave events", value="join"),
    discord.app_commands.Choice(name="message — delete, edit, purge, invite links", value="message"),
    discord.app_commands.Choice(name="member — role changes, nicknames, bans, timeouts", value="member"),
])
@discord.app_commands.default_permissions(manage_guild=True)
async def set_log_channel_command(
    interaction: discord.Interaction,
    log_type: str,
    channel: discord.TextChannel,
):
    cfg.set(_LOG_TYPE_KEYS[log_type], channel.id)
    labels = {
        "join": "Join/leave events",
        "message": "Message events (delete/edit/purge/invites)",
        "member": "Member events (roles/nicknames/bans/timeouts)",
    }
    await interaction.response.send_message(
        f"{labels[log_type]} will now be logged in {channel.mention}.\n"
        f"*Any log type without a dedicated channel falls back to the join/leave channel.*",
        ephemeral=True,
    )
    log.info("Log channel for '%s' set to %s by %s", log_type, channel.id, interaction.user)


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

    await channel.set_permissions(
        role, view_channel=True, send_messages=True, read_message_history=True
    )

    denied = 0
    for ch in guild.channels:
        if ch.id == channel.id or isinstance(ch, discord.CategoryChannel):
            continue
        try:
            await ch.set_permissions(role, view_channel=False)
            denied += 1
        except discord.Forbidden:
            log.warning("Could not set permissions on channel %s", ch)

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

        full_mapping = reaction_roles[message_id]
        lines = []
        for emoji, role_id in full_mapping.items():
            role = interaction.guild.get_role(role_id)
            role_str = role.mention if role else "(unknown role)"
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


# ── gateway events ─────────────────────────────────────────────────────────────

_store_ready = False


@client.event
async def on_ready():
    global _store_ready
    log.info("Logged in as %s", client.user)
    if not _store_ready:
        await message_store.init()
        _store_ready = True
    await tree.sync()
    if GUILD_ID:
        guild_obj = discord.Object(id=GUILD_ID)
        await tree.sync(guild=guild_obj)
        log.info("Slash commands synced (global + guild %s)", GUILD_ID)
    else:
        log.info("Slash commands synced (global only — may take up to 1 hour)")


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

    log_channel = _get_log_channel("join")
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
    log_channel = _get_log_channel("join")
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
async def on_raw_message_delete(payload):
    if not payload.guild_id:
        return
    ch = _get_log_channel("message")
    if not ch:
        return

    cached = payload.cached_message
    if cached:
        if cached.author.bot:
            return
        author_name = str(cached.author)
        author_avatar = str(cached.author.display_avatar.url)
        author_id = cached.author.id
        content = cached.content
    else:
        stored = await message_store.get(payload.message_id)
        if not stored:
            return
        author_name = stored["author_name"]
        author_avatar = stored["author_avatar"]
        author_id = stored["author_id"]
        content = stored["content"]

    await message_store.delete(payload.message_id)

    embed = discord.Embed(
        title="Message Deleted",
        color=discord.Color.red(),
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    embed.set_author(name=author_name, icon_url=author_avatar)
    embed.add_field(name="Channel", value=f"<#{payload.channel_id}>", inline=True)
    if content:
        embed.add_field(name="Content", value=content[:1024], inline=False)
    embed.set_footer(text=f"User ID: {author_id} | Message ID: {payload.message_id}")
    await ch.send(embed=embed)


@client.event
async def on_raw_message_edit(payload):
    if not payload.guild_id:
        return

    new_content = payload.data.get("content", "")

    cached = payload.cached_message
    if cached:
        if cached.author.bot:
            return
        old_content = cached.content
        author_name = str(cached.author)
        author_avatar = str(cached.author.display_avatar.url)
        author_id = cached.author.id
    else:
        stored = await message_store.get(payload.message_id)
        if not stored:
            return
        old_content = stored["content"]
        author_name = stored["author_name"]
        author_avatar = stored["author_avatar"]
        author_id = stored["author_id"]

    if old_content == new_content:
        return

    await message_store.update_content(payload.message_id, new_content)

    ch = _get_log_channel("message")
    if not ch:
        return

    jump_url = f"https://discord.com/channels/{payload.guild_id}/{payload.channel_id}/{payload.message_id}"
    embed = discord.Embed(
        title="Message Edited",
        color=discord.Color.orange(),
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    embed.set_author(name=author_name, icon_url=author_avatar)
    embed.add_field(name="Channel", value=f"<#{payload.channel_id}>", inline=True)
    embed.add_field(name="Before", value=old_content[:1024] or "(empty)", inline=False)
    embed.add_field(name="After", value=new_content[:1024] or "(empty)", inline=False)
    embed.add_field(name="Jump", value=f"[Go to message]({jump_url})", inline=True)
    embed.set_footer(text=f"User ID: {author_id} | Message ID: {payload.message_id}")
    await ch.send(embed=embed)


@client.event
async def on_raw_bulk_message_delete(payload):
    if not payload.guild_id:
        return
    ch = _get_log_channel("message")
    if not ch:
        return

    message_ids = list(payload.message_ids)
    stored = await message_store.get_many(message_ids)
    await message_store.delete_many(message_ids)

    embed = discord.Embed(
        title="Messages Purged",
        description=f"{len(message_ids)} messages deleted in <#{payload.channel_id}>",
        color=discord.Color.dark_red(),
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    if stored:
        embed.add_field(name="Recovered", value=f"{len(stored)}/{len(message_ids)} messages — see attached log", inline=False)
    embed.set_footer(text=f"Channel ID: {payload.channel_id}")
    await ch.send(embed=embed)

    if stored:
        lines = []
        for msg in sorted(stored, key=lambda m: m["created_at"]):
            ts = datetime.datetime.fromtimestamp(msg["created_at"], tz=datetime.timezone.utc)
            lines.append(f"[{ts.strftime('%Y-%m-%d %H:%M:%S UTC')}] {msg['author_name']}: {msg['content']}")
        await ch.send(file=discord.File(io.BytesIO("\n".join(lines).encode()), filename="purged_messages.txt"))


@client.event
async def on_member_update(before, after):
    ch = _get_log_channel("member")
    if not ch:
        return

    added = [r for r in after.roles if r not in before.roles]
    removed = [r for r in before.roles if r not in after.roles]
    if added or removed:
        embed = discord.Embed(
            title="Member Roles Updated",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.set_author(name=str(after), icon_url=after.display_avatar.url)
        if added:
            embed.add_field(name="Added", value=" ".join(r.mention for r in added), inline=False)
        if removed:
            embed.add_field(name="Removed", value=" ".join(r.mention for r in removed), inline=False)
        embed.set_footer(text=f"User ID: {after.id}")
        await ch.send(embed=embed)

    if before.nick != after.nick:
        embed = discord.Embed(
            title="Nickname Changed",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.set_author(name=str(after), icon_url=after.display_avatar.url)
        embed.add_field(name="Before", value=before.nick or "(none)", inline=True)
        embed.add_field(name="After", value=after.nick or "(none)", inline=True)
        embed.set_footer(text=f"User ID: {after.id}")
        await ch.send(embed=embed)

    now = datetime.datetime.now(datetime.timezone.utc)
    if before.timed_out_until != after.timed_out_until:
        if after.timed_out_until and after.timed_out_until > now:
            embed = discord.Embed(
                title="Member Timed Out",
                color=discord.Color.orange(),
                timestamp=now,
            )
            embed.set_author(name=str(after), icon_url=after.display_avatar.url)
            embed.add_field(
                name="Until",
                value=discord.utils.format_dt(after.timed_out_until, style="F"),
                inline=False,
            )
        else:
            embed = discord.Embed(
                title="Timeout Removed",
                color=discord.Color.green(),
                timestamp=now,
            )
            embed.set_author(name=str(after), icon_url=after.display_avatar.url)
        embed.set_footer(text=f"User ID: {after.id}")
        await ch.send(embed=embed)


@client.event
async def on_user_update(before, after):
    if before.name == after.name and before.display_name == after.display_name:
        return
    for guild in client.guilds:
        if guild.get_member(after.id) is None:
            continue
        ch = _get_log_channel("member")
        if not ch:
            continue
        embed = discord.Embed(
            title="Username Changed",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.set_author(name=str(after), icon_url=after.display_avatar.url)
        if before.name != after.name:
            embed.add_field(name="Username Before", value=before.name, inline=True)
            embed.add_field(name="Username After", value=after.name, inline=True)
        if before.display_name != after.display_name:
            embed.add_field(name="Display Name Before", value=before.display_name, inline=True)
            embed.add_field(name="Display Name After", value=after.display_name, inline=True)
        embed.set_footer(text=f"User ID: {after.id}")
        await ch.send(embed=embed)


@client.event
async def on_member_ban(guild, user):
    ch = _get_log_channel("member")
    if not ch:
        return
    embed = discord.Embed(
        title="Member Banned",
        description=f"{user.mention} ({user})",
        color=discord.Color.dark_red(),
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.set_footer(text=f"User ID: {user.id}")
    await ch.send(embed=embed)


@client.event
async def on_member_unban(guild, user):
    ch = _get_log_channel("member")
    if not ch:
        return
    embed = discord.Embed(
        title="Member Unbanned",
        description=f"{user.mention} ({user})",
        color=discord.Color.green(),
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.set_footer(text=f"User ID: {user.id}")
    await ch.send(embed=embed)


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.guild and not message.author.bot:
        try:
            await message_store.store(message)
        except Exception:
            log.exception("Failed to store message %s", message.id)

    if message.guild and not message.author.bot and INVITE_RE.search(message.content):
        log.info("Invite link detected from %s in #%s", message.author, message.channel)
        ch = _get_log_channel("member")
        if not ch:
            log.warning("Invite link detected but no member log channel configured")
        if ch:
            embed = discord.Embed(
                title="Invite Link Posted",
                color=discord.Color.gold(),
                timestamp=datetime.datetime.now(datetime.timezone.utc),
            )
            embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
            embed.add_field(name="Channel", value=message.channel.mention, inline=True)
            embed.add_field(name="Content", value=message.content[:1024], inline=False)
            embed.add_field(name="Jump", value=f"[Go to message]({message.jump_url})", inline=True)
            embed.set_footer(text=f"User ID: {message.author.id} | Message ID: {message.id}")
            await ch.send(embed=embed)

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


client.run(TOKEN)
