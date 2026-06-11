import datetime
import logging
import time
from pathlib import Path

import aiosqlite
import discord

import config as cfg

log = logging.getLogger("lucebot.warnings")
DB_PATH = Path("data/messages.db")
_db: aiosqlite.Connection = None


async def init():
    global _db
    if _db is not None:
        return
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    _db = await aiosqlite.connect(DB_PATH)
    await _db.execute("PRAGMA journal_mode=WAL")
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS warnings (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id   INTEGER NOT NULL,
            user_id    INTEGER NOT NULL,
            warned_by  INTEGER NOT NULL,
            reason     TEXT    NOT NULL,
            created_at REAL    NOT NULL
        )
    """)
    await _db.commit()
    log.info("Warnings system initialised")


async def _add(guild_id: int, user_id: int, warned_by: int, reason: str) -> int:
    await _db.execute(
        "INSERT INTO warnings (guild_id, user_id, warned_by, reason, created_at) VALUES (?,?,?,?,?)",
        (guild_id, user_id, warned_by, reason, time.time()),
    )
    await _db.commit()
    async with _db.execute(
        "SELECT COUNT(*) FROM warnings WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    ) as cur:
        row = await cur.fetchone()
    return row[0] if row else 1


async def _get(guild_id: int, user_id: int) -> list[dict]:
    async with _db.execute(
        "SELECT id, warned_by, reason, created_at FROM warnings"
        " WHERE guild_id = ? AND user_id = ? ORDER BY created_at",
        (guild_id, user_id),
    ) as cur:
        rows = await cur.fetchall()
    return [{"id": r[0], "warned_by": r[1], "reason": r[2], "created_at": r[3]} for r in rows]


async def _clear(guild_id: int, user_id: int) -> int:
    async with _db.execute(
        "SELECT COUNT(*) FROM warnings WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    ) as cur:
        row = await cur.fetchone()
    count = row[0] if row else 0
    await _db.execute(
        "DELETE FROM warnings WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    )
    await _db.commit()
    return count


def _build_embed(member: discord.Member, records: list[dict]) -> discord.Embed:
    lines = []
    for i, w in enumerate(records, 1):
        ts = datetime.datetime.fromtimestamp(w["created_at"], tz=datetime.timezone.utc)
        lines.append(f"**#{i}** {discord.utils.format_dt(ts, style='d')} — {w['reason']}")
    embed = discord.Embed(
        title=f"Warnings for {member.display_name}",
        description="\n".join(lines),
        color=discord.Color.yellow(),
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text=f"{len(records)} total | User ID: {member.id}")
    return embed


async def _post_log(ch, member: discord.Member, warned_by, count: int, reason: str):
    embed = discord.Embed(
        title="Member Warned",
        color=discord.Color.yellow(),
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    embed.set_author(name=str(member), icon_url=member.display_avatar.url)
    embed.add_field(name="Warned by", value=warned_by.mention, inline=True)
    embed.add_field(name="Warning #", value=str(count), inline=True)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.set_footer(text=f"User ID: {member.id}")
    await ch.send(embed=embed)


async def _dm(member: discord.Member, guild_name: str, count: int, reason: str):
    try:
        await member.send(
            f"You received a warning in **{guild_name}**.\n"
            f"**Reason:** {reason}\n"
            f"This is warning #{count}."
        )
    except discord.Forbidden:
        pass


def setup(tree: discord.app_commands.CommandTree, client: discord.Client):

    def _log_channel():
        channel_id = cfg.get("member_log_channel_id")
        return client.get_channel(channel_id) if channel_id else None

    @tree.command(name="warn", description="Warn a member and log the reason")
    @discord.app_commands.describe(member="Member to warn", reason="Reason for the warning")
    @discord.app_commands.default_permissions(manage_messages=True)
    async def warn_command(
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "No reason given",
    ):
        if member.bot:
            await interaction.response.send_message("You can't warn a bot.", ephemeral=True)
            return
        count = await _add(interaction.guild.id, member.id, interaction.user.id, reason)
        await interaction.response.send_message(
            f"Warned {member.mention} (warning #{count}). Reason: {reason}", ephemeral=True
        )
        await _dm(member, interaction.guild.name, count, reason)
        ch = _log_channel()
        if ch:
            await _post_log(ch, member, interaction.user, count, reason)
        log.info("Warned %s (warning #%d) by %s: %s", member, count, interaction.user, reason)

    @tree.command(name="warnings", description="Show a member's warnings")
    @discord.app_commands.describe(member="Member to look up")
    @discord.app_commands.default_permissions(manage_messages=True)
    async def warnings_command(interaction: discord.Interaction, member: discord.Member):
        records = await _get(interaction.guild.id, member.id)
        if not records:
            await interaction.response.send_message(
                f"{member.mention} has no warnings.", ephemeral=True
            )
            return
        await interaction.response.send_message(embed=_build_embed(member, records), ephemeral=True)

    @tree.command(name="warnings-clear", description="Clear all warnings for a member")
    @discord.app_commands.describe(member="Member whose warnings to clear")
    @discord.app_commands.default_permissions(manage_guild=True)
    async def warnings_clear_command(interaction: discord.Interaction, member: discord.Member):
        count = await _clear(interaction.guild.id, member.id)
        if count == 0:
            await interaction.response.send_message(
                f"{member.mention} has no warnings.", ephemeral=True
            )
            return
        await interaction.response.send_message(
            f"Cleared {count} warning(s) for {member.mention}.", ephemeral=True
        )
        log.info("Cleared %d warning(s) for %s by %s", count, member, interaction.user)


async def handle_prefix_command(message: discord.Message, client: discord.Client):
    content = message.content.strip()
    ch = message.channel

    def _log_channel():
        channel_id = cfg.get("member_log_channel_id")
        return client.get_channel(channel_id) if channel_id else None

    if content.startswith("!warnings-clear"):
        if not message.author.guild_permissions.manage_guild:
            await ch.send("You need Manage Server permission to clear warnings.")
            return
        if not message.mentions:
            await ch.send("Usage: `!warnings-clear @member`")
            return
        member = message.mentions[0]
        count = await _clear(message.guild.id, member.id)
        if count == 0:
            await ch.send(f"{member.mention} has no warnings.")
            return
        await ch.send(f"Cleared {count} warning(s) for {member.mention}.")
        log.info("Cleared %d warning(s) for %s by %s", count, member, message.author)

    elif content.startswith("!warnings"):
        if not message.author.guild_permissions.manage_messages:
            await ch.send("You need Manage Messages permission to view warnings.")
            return
        if not message.mentions:
            await ch.send("Usage: `!warnings @member`")
            return
        member = message.mentions[0]
        records = await _get(message.guild.id, member.id)
        if not records:
            await ch.send(f"{member.mention} has no warnings.")
            return
        await ch.send(embed=_build_embed(member, records))

    elif content.startswith("!warn"):
        if not message.author.guild_permissions.manage_messages:
            await ch.send("You need Manage Messages permission to warn members.")
            return
        if not message.mentions:
            await ch.send("Usage: `!warn @member [reason]`")
            return
        member = message.mentions[0]
        if member.bot:
            await ch.send("You can't warn a bot.")
            return
        reason = content[len("!warn"):].strip()
        for pat in (f"<@{member.id}>", f"<@!{member.id}>"):
            reason = reason.replace(pat, "").strip()
        if not reason:
            reason = "No reason given"
        count = await _add(message.guild.id, member.id, message.author.id, reason)
        await ch.send(f"Warned {member.mention} (warning #{count}). Reason: {reason}")
        await _dm(member, message.guild.name, count, reason)
        log_ch = _log_channel()
        if log_ch:
            await _post_log(log_ch, member, message.author, count, reason)
        log.info("Warned %s (warning #%d) by %s: %s", member, count, message.author, reason)
