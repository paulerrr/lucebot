import logging
import random
from pathlib import Path

import aiosqlite
import discord

import config as cfg

log = logging.getLogger("lucebot.leveling")

DB_PATH = Path("data/messages.db")
_db: aiosqlite.Connection = None


# ── XP / level math ────────────────────────────────────────────────────────────

def xp_for_level(level: int) -> int:
    """XP needed to advance from `level` to `level + 1`."""
    return 5 * (level ** 2) + 50 * level + 100


def level_from_xp(total_xp: int) -> tuple[int, int, int]:
    """Return (level, xp_into_level, xp_needed_for_next_level)."""
    level = 0
    remaining = total_xp
    while True:
        needed = xp_for_level(level)
        if remaining < needed:
            return level, remaining, needed
        remaining -= needed
        level += 1


def _xp_bar(current: int, needed: int, length: int = 20) -> str:
    filled = int((current / needed) * length) if needed else 0
    return "█" * filled + "░" * (length - filled)


# ── database ───────────────────────────────────────────────────────────────────

async def init():
    global _db
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    _db = await aiosqlite.connect(DB_PATH)
    await _db.execute("PRAGMA journal_mode=WAL")
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS user_xp (
            guild_id INTEGER NOT NULL,
            user_id  INTEGER NOT NULL,
            xp       INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        )
    """)
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS level_rewards (
            guild_id INTEGER NOT NULL,
            level    INTEGER NOT NULL,
            role_id  INTEGER NOT NULL,
            PRIMARY KEY (guild_id, level)
        )
    """)
    await _db.commit()
    log.info("Leveling system initialised")


async def _get_xp(guild_id: int, user_id: int) -> int:
    async with _db.execute(
        "SELECT xp FROM user_xp WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    ) as cur:
        row = await cur.fetchone()
    return row[0] if row else 0


async def _add_xp(guild_id: int, user_id: int, amount: int) -> tuple[int, int, int]:
    """Add XP. Returns (old_level, new_level, new_total_xp)."""
    old_xp = await _get_xp(guild_id, user_id)
    old_level, _, _ = level_from_xp(old_xp)
    new_xp = old_xp + amount
    new_level, _, _ = level_from_xp(new_xp)
    await _db.execute(
        "INSERT INTO user_xp (guild_id, user_id, xp) VALUES (?, ?, ?)"
        " ON CONFLICT(guild_id, user_id) DO UPDATE SET xp = xp + ?",
        (guild_id, user_id, amount, amount),
    )
    await _db.commit()
    return old_level, new_level, new_xp


async def _set_xp(guild_id: int, user_id: int, amount: int) -> tuple[int, int]:
    """Directly set XP. Returns (old_level, new_level)."""
    amount = max(0, amount)
    old_xp = await _get_xp(guild_id, user_id)
    old_level, _, _ = level_from_xp(old_xp)
    new_level, _, _ = level_from_xp(amount)
    await _db.execute(
        "INSERT INTO user_xp (guild_id, user_id, xp) VALUES (?, ?, ?)"
        " ON CONFLICT(guild_id, user_id) DO UPDATE SET xp = ?",
        (guild_id, user_id, amount, amount),
    )
    await _db.commit()
    return old_level, new_level


async def _reset_xp(guild_id: int, user_id: int):
    await _db.execute(
        "DELETE FROM user_xp WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    )
    await _db.commit()


async def _get_rank(guild_id: int, user_id: int) -> int:
    user_xp = await _get_xp(guild_id, user_id)
    async with _db.execute(
        "SELECT COUNT(*) FROM user_xp WHERE guild_id = ? AND xp > ?",
        (guild_id, user_xp),
    ) as cur:
        row = await cur.fetchone()
    return (row[0] + 1) if row else 1


async def _get_leaderboard(guild_id: int, limit: int = 10) -> list[dict]:
    async with _db.execute(
        "SELECT user_id, xp FROM user_xp WHERE guild_id = ? ORDER BY xp DESC LIMIT ?",
        (guild_id, limit),
    ) as cur:
        rows = await cur.fetchall()
    return [{"user_id": r[0], "xp": r[1]} for r in rows]


async def _get_level_rewards(guild_id: int) -> list[dict]:
    async with _db.execute(
        "SELECT level, role_id FROM level_rewards WHERE guild_id = ? ORDER BY level",
        (guild_id,),
    ) as cur:
        rows = await cur.fetchall()
    return [{"level": r[0], "role_id": r[1]} for r in rows]


# ── level-up handling ──────────────────────────────────────────────────────────

async def _on_level_up(message: discord.Message, client: discord.Client, new_level: int):
    guild = message.guild
    member = message.author
    stack = cfg.get("leveling_stack_rewards", True)
    rewards = await _get_level_rewards(guild.id)

    to_add: list[discord.Role] = []
    to_remove: list[discord.Role] = []

    if stack:
        for r in rewards:
            role = guild.get_role(r["role_id"])
            if role and r["level"] <= new_level and role not in member.roles:
                to_add.append(role)
    else:
        earned = [r for r in rewards if r["level"] <= new_level]
        top_level = max((r["level"] for r in earned), default=None)
        for r in rewards:
            role = guild.get_role(r["role_id"])
            if role is None:
                continue
            if r["level"] == top_level and role not in member.roles:
                to_add.append(role)
            elif r["level"] != top_level and role in member.roles:
                to_remove.append(role)

    try:
        if to_add:
            await member.add_roles(*to_add, reason=f"Level {new_level} reward")
        if to_remove:
            await member.remove_roles(*to_remove, reason="Level reward update (non-stacking)")
    except discord.Forbidden:
        log.warning("Missing permissions to assign level reward roles to %s", member)

    mode = cfg.get("leveling_notify_mode", "current")
    if mode == "off":
        return

    embed = discord.Embed(
        description=f"{member.mention} leveled up to **Level {new_level}**! 🎉",
        color=discord.Color.gold(),
    )
    if to_add:
        embed.add_field(
            name="Role Reward",
            value=" ".join(r.mention for r in to_add),
            inline=False,
        )

    if mode == "dm":
        try:
            await member.send(embed=embed)
        except discord.Forbidden:
            pass
    elif mode == "channel":
        channel_id = cfg.get("leveling_notify_channel_id")
        ch = client.get_channel(channel_id) if channel_id else None
        if ch:
            await ch.send(embed=embed)
    else:  # "current"
        try:
            await message.channel.send(embed=embed)
        except discord.Forbidden:
            pass


# ── on_message hook ────────────────────────────────────────────────────────────

async def handle_message(message: discord.Message, client: discord.Client):
    if not message.guild or message.author.bot:
        return
    if not cfg.get("leveling_enabled", True):
        return
    if message.channel.id in cfg.get("leveling_ignored_channels", []):
        return
    if message.author.id in cfg.get("leveling_ignored_users", []):
        return
    member_role_ids = {r.id for r in message.author.roles}
    if member_role_ids & set(cfg.get("leveling_ignored_roles", [])):
        return

    xp_min = cfg.get("leveling_xp_min", 15)
    xp_max = cfg.get("leveling_xp_max", 25)
    amount = random.randint(xp_min, xp_max)

    old_level, new_level, _ = await _add_xp(message.guild.id, message.author.id, amount)
    if new_level > old_level:
        await _on_level_up(message, client, new_level)


# ── slash commands ─────────────────────────────────────────────────────────────

def setup(tree: discord.app_commands.CommandTree, client: discord.Client):

    @tree.command(name="rank", description="Show your rank card or another member's")
    @discord.app_commands.describe(member="Member to look up (defaults to you)")
    async def rank_command(interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        total_xp = await _get_xp(interaction.guild.id, target.id)
        level, current_xp, needed_xp = level_from_xp(total_xp)
        rank = await _get_rank(interaction.guild.id, target.id)
        bar = _xp_bar(current_xp, needed_xp)

        embed = discord.Embed(color=discord.Color.blurple())
        embed.set_author(name=str(target), icon_url=target.display_avatar.url)
        embed.add_field(name="Rank", value=f"#{rank}", inline=True)
        embed.add_field(name="Level", value=str(level), inline=True)
        embed.add_field(name="Total XP", value=f"{total_xp:,}", inline=True)
        embed.add_field(
            name=f"Progress  →  Level {level + 1}",
            value=f"`{bar}` {current_xp:,} / {needed_xp:,} XP",
            inline=False,
        )
        await interaction.response.send_message(embed=embed)

    @tree.command(name="leaderboard", description="Show the XP leaderboard for this server")
    async def leaderboard_command(interaction: discord.Interaction):
        await interaction.response.defer()
        rows = await _get_leaderboard(interaction.guild.id, limit=10)
        if not rows:
            await interaction.followup.send("No one has earned any XP yet.")
            return
        lines = []
        for i, row in enumerate(rows, start=1):
            member = interaction.guild.get_member(row["user_id"])
            name = member.mention if member else f"<@{row['user_id']}>"
            lvl, _, _ = level_from_xp(row["xp"])
            lines.append(f"**#{i}** {name} — Level {lvl} · {row['xp']:,} XP")
        embed = discord.Embed(
            title=f"XP Leaderboard — {interaction.guild.name}",
            description="\n".join(lines),
            color=discord.Color.gold(),
        )
        await interaction.followup.send(embed=embed)

    @tree.command(name="level-config", description="View or change leveling settings")
    @discord.app_commands.describe(
        enabled="Enable or disable XP earning",
        xp_min="Minimum XP granted per message (default 15)",
        xp_max="Maximum XP granted per message (default 25)",
        stack_rewards="Keep all earned role rewards (True) or only the highest (False)",
    )
    @discord.app_commands.default_permissions(manage_guild=True)
    async def level_config_command(
        interaction: discord.Interaction,
        enabled: bool = None,
        xp_min: int = None,
        xp_max: int = None,
        stack_rewards: bool = None,
    ):
        changed = []
        if enabled is not None:
            cfg.set("leveling_enabled", enabled)
            changed.append(f"Leveling: **{'enabled' if enabled else 'disabled'}**")
        if xp_min is not None:
            cfg.set("leveling_xp_min", xp_min)
            changed.append(f"XP min: **{xp_min}**")
        if xp_max is not None:
            cfg.set("leveling_xp_max", xp_max)
            changed.append(f"XP max: **{xp_max}**")
        if stack_rewards is not None:
            cfg.set("leveling_stack_rewards", stack_rewards)
            changed.append(f"Stack rewards: **{stack_rewards}**")

        if changed:
            await interaction.response.send_message("\n".join(changed), ephemeral=True)
        else:
            lines = [
                f"Enabled: **{cfg.get('leveling_enabled', True)}**",
                f"XP per message: **{cfg.get('leveling_xp_min', 15)}–{cfg.get('leveling_xp_max', 25)}**",
                f"Stack rewards: **{cfg.get('leveling_stack_rewards', True)}**",
                f"Notify mode: **{cfg.get('leveling_notify_mode', 'current')}**",
            ]
            embed = discord.Embed(
                title="Leveling Config",
                description="\n".join(lines),
                color=discord.Color.blurple(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @tree.command(name="level-notify", description="Configure where level-up notifications are sent")
    @discord.app_commands.describe(
        mode="Notification destination",
        channel="Channel to use when mode is 'channel'",
    )
    @discord.app_commands.choices(mode=[
        discord.app_commands.Choice(name="Current channel (where the message was sent)", value="current"),
        discord.app_commands.Choice(name="DM the user", value="dm"),
        discord.app_commands.Choice(name="Specific channel", value="channel"),
        discord.app_commands.Choice(name="Off — no notifications", value="off"),
    ])
    @discord.app_commands.default_permissions(manage_guild=True)
    async def level_notify_command(
        interaction: discord.Interaction,
        mode: str,
        channel: discord.TextChannel = None,
    ):
        if mode == "channel" and channel is None:
            await interaction.response.send_message(
                "Please specify a channel when using mode `channel`.", ephemeral=True
            )
            return
        cfg.set("leveling_notify_mode", mode)
        if mode == "channel":
            cfg.set("leveling_notify_channel_id", channel.id)
            await interaction.response.send_message(
                f"Level-up notifications will be sent in {channel.mention}.", ephemeral=True
            )
        else:
            labels = {"current": "the channel where the message was posted", "dm": "DM", "off": "nowhere"}
            await interaction.response.send_message(
                f"Level-up notifications will go to **{labels[mode]}**.", ephemeral=True
            )

    @tree.command(name="level-reward-add", description="Grant a role when a member reaches a level")
    @discord.app_commands.describe(level="Level required to earn the role", role="Role to grant")
    @discord.app_commands.default_permissions(manage_guild=True)
    async def level_reward_add_command(interaction: discord.Interaction, level: int, role: discord.Role):
        if level < 1:
            await interaction.response.send_message("Level must be at least 1.", ephemeral=True)
            return
        await _db.execute(
            "INSERT INTO level_rewards (guild_id, level, role_id) VALUES (?, ?, ?)"
            " ON CONFLICT(guild_id, level) DO UPDATE SET role_id = ?",
            (interaction.guild.id, level, role.id, role.id),
        )
        await _db.commit()
        await interaction.response.send_message(
            f"{role.mention} will be granted at Level {level}.", ephemeral=True
        )
        log.info("Level reward set: guild=%s level=%d role=%s by %s",
                 interaction.guild.id, level, role.id, interaction.user)

    @tree.command(name="level-reward-remove", description="Remove the role reward for a level")
    @discord.app_commands.describe(level="Level whose reward should be removed")
    @discord.app_commands.default_permissions(manage_guild=True)
    async def level_reward_remove_command(interaction: discord.Interaction, level: int):
        await _db.execute(
            "DELETE FROM level_rewards WHERE guild_id = ? AND level = ?",
            (interaction.guild.id, level),
        )
        await _db.commit()
        await interaction.response.send_message(f"Reward for Level {level} removed.", ephemeral=True)

    @tree.command(name="level-reward-list", description="List all level role rewards")
    @discord.app_commands.default_permissions(manage_guild=True)
    async def level_reward_list_command(interaction: discord.Interaction):
        rewards = await _get_level_rewards(interaction.guild.id)
        if not rewards:
            await interaction.response.send_message("No level rewards configured.", ephemeral=True)
            return
        lines = []
        for r in rewards:
            role = interaction.guild.get_role(r["role_id"])
            role_str = role.mention if role else f"*(deleted role {r['role_id']})*"
            lines.append(f"Level **{r['level']}** → {role_str}")
        embed = discord.Embed(
            title="Level Rewards",
            description="\n".join(lines),
            color=discord.Color.blurple(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @tree.command(name="level-ignore-channel", description="Stop granting XP for messages in a channel")
    @discord.app_commands.describe(channel="Channel to ignore")
    @discord.app_commands.default_permissions(manage_guild=True)
    async def level_ignore_channel_command(interaction: discord.Interaction, channel: discord.TextChannel):
        ignored = cfg.get("leveling_ignored_channels", [])
        if channel.id not in ignored:
            ignored.append(channel.id)
            cfg.set("leveling_ignored_channels", ignored)
        await interaction.response.send_message(
            f"XP will no longer be granted for messages in {channel.mention}.", ephemeral=True
        )

    @tree.command(name="level-unignore-channel", description="Resume granting XP in a channel")
    @discord.app_commands.describe(channel="Channel to unignore")
    @discord.app_commands.default_permissions(manage_guild=True)
    async def level_unignore_channel_command(interaction: discord.Interaction, channel: discord.TextChannel):
        ignored = cfg.get("leveling_ignored_channels", [])
        if channel.id in ignored:
            ignored.remove(channel.id)
            cfg.set("leveling_ignored_channels", ignored)
            await interaction.response.send_message(
                f"XP will now be granted in {channel.mention}.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"{channel.mention} is not ignored.", ephemeral=True
            )

    @tree.command(name="xp-set", description="Set a member's total XP directly")
    @discord.app_commands.describe(member="Member to update", amount="XP to set")
    @discord.app_commands.default_permissions(manage_guild=True)
    async def xp_set_command(interaction: discord.Interaction, member: discord.Member, amount: int):
        if amount < 0:
            await interaction.response.send_message("Amount must be 0 or greater.", ephemeral=True)
            return
        _, new_level = await _set_xp(interaction.guild.id, member.id, amount)
        await interaction.response.send_message(
            f"Set {member.mention}'s XP to **{amount:,}** (Level {new_level}).", ephemeral=True
        )
        log.info("XP set to %d for %s by %s", amount, member, interaction.user)

    @tree.command(name="xp-reset", description="Reset a member's XP and level to zero")
    @discord.app_commands.describe(member="Member to reset")
    @discord.app_commands.default_permissions(manage_guild=True)
    async def xp_reset_command(interaction: discord.Interaction, member: discord.Member):
        await _reset_xp(interaction.guild.id, member.id)
        await interaction.response.send_message(
            f"Reset {member.mention}'s XP to 0.", ephemeral=True
        )
        log.info("XP reset for %s by %s", member, interaction.user)
