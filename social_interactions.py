import json
import logging
import random
import time
from pathlib import Path
from typing import Dict, List, Set

import discord

log = logging.getLogger("lucebot.social")

DATA_PATH = Path("data/social_interactions")
COOLDOWN_SECONDS = 5


class MessageTracker:
    def __init__(self, messages: List[str]):
        self.all_messages = messages
        self.available_messages: Dict[int, List[str]] = {}

    def get_message(self, guild_id: int) -> str:
        if guild_id not in self.available_messages or not self.available_messages[guild_id]:
            self.available_messages[guild_id] = self.all_messages.copy()
            random.shuffle(self.available_messages[guild_id])
        return self.available_messages[guild_id].pop()


class SocialInteractions:
    def __init__(self):
        DATA_PATH.mkdir(parents=True, exist_ok=True)
        self._load_messages()
        self.compliment_tracker = MessageTracker(self.compliments)
        self.insult_tracker = MessageTracker(self.insults)
        self.blocked_users: Set[int] = self._load_blocked_users()
        self._cooldowns: Dict[int, float] = {}
        log.info(
            "SocialInteractions ready (%d compliments, %d insults, %d blocked)",
            len(self.compliments), len(self.insults), len(self.blocked_users),
        )

    # ── message loading ────────────────────────────────────────────────────────

    def _load_messages(self) -> None:
        self.compliments = self._load_file("compliments.md")
        self.insults = self._load_file("insults.md")

    def _load_file(self, filename: str) -> List[str]:
        path = DATA_PATH / filename
        if not path.exists():
            log.error("Message file not found: %s", path)
            return []
        content = path.read_text(encoding="utf-8")
        if content.strip().startswith("["):
            try:
                return [self._clean(m) for m in json.loads(content)]
            except json.JSONDecodeError:
                pass
        return [self._clean(line) for line in content.splitlines() if line.strip()]

    def _clean(self, message: str) -> str:
        cleaned = message.strip()
        if cleaned and cleaned[0].isdigit():
            parts = cleaned.split(" ", 1)
            if len(parts) > 1 and any(c in parts[0] for c in [".", ")", "]"]):
                cleaned = parts[1]
        return cleaned.strip()

    # ── blocked users ──────────────────────────────────────────────────────────

    def _load_blocked_users(self) -> Set[int]:
        path = DATA_PATH / "blocked_users.json"
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return set(data.get("blocked_users", []))
            except Exception as e:
                log.error("Error loading blocked users: %s", e)
        return set()

    def _save_blocked_users(self) -> None:
        path = DATA_PATH / "blocked_users.json"
        path.write_text(
            json.dumps({"blocked_users": list(self.blocked_users)}, indent=4),
            encoding="utf-8",
        )

    # ── cooldown ───────────────────────────────────────────────────────────────

    def _on_cooldown(self, user_id: int) -> float:
        """Return remaining cooldown seconds, or 0 if the user is clear."""
        last = self._cooldowns.get(user_id, 0)
        remaining = COOLDOWN_SECONDS - (time.monotonic() - last)
        if remaining > 0:
            return remaining
        self._cooldowns[user_id] = time.monotonic()
        return 0

    # ── command handlers ───────────────────────────────────────────────────────

    async def handle_compliment(self, message: discord.Message, bot_user: discord.ClientUser) -> None:
        if message.author.id in self.blocked_users:
            await message.channel.send("You don't have permission to use this command.")
            return

        remaining = self._on_cooldown(message.author.id)
        if remaining:
            await message.channel.send(f"You're doing that too fast! Try again in {remaining:.1f}s.")
            return

        user = message.mentions[0] if message.mentions else message.author

        if user.bot and user.id != bot_user.id:
            await message.channel.send("I can't compliment other bots, but I'm sure they're doing their best! 🤖")
            return
        if user.id == bot_user.id:
            await message.channel.send("That's sweet of you, but I'd rather compliment you instead! 💖")
            return

        text = self.compliment_tracker.get_message(message.guild.id)
        await message.channel.send(f"{user.mention} {text}")
        log.info("Compliment sent by %s to %s", message.author, user)

    async def handle_insult(self, message: discord.Message, bot_user: discord.ClientUser) -> None:
        if message.author.id in self.blocked_users:
            await message.channel.send("You don't have permission to use this command.")
            return

        remaining = self._on_cooldown(message.author.id)
        if remaining:
            await message.channel.send(f"You're doing that too fast! Try again in {remaining:.1f}s.")
            return

        user = message.mentions[0] if message.mentions else message.author

        if user.bot and user.id != bot_user.id:
            await message.channel.send("I don't insult my fellow bots! We have to stick together! 🤖")
            return
        if user.id == bot_user.id:
            await message.channel.send("Nice try, but I'm not falling for that! Try insulting someone else! 😏")
            return

        text = self.insult_tracker.get_message(message.guild.id)
        await message.channel.send(f"{user.mention} {text}")
        log.info("Insult sent by %s to %s", message.author, user)

    async def handle_blockuser(self, message: discord.Message) -> None:
        if not message.author.guild_permissions.administrator:
            await message.channel.send("You need administrator permission to use this command.")
            return
        if not message.mentions:
            await message.channel.send("Usage: `!blockuser @member`")
            return
        user = message.mentions[0]
        if user.id in self.blocked_users:
            await message.channel.send(f"{user.mention} is already blocked from using social interaction commands.")
            return
        self.blocked_users.add(user.id)
        self._save_blocked_users()
        await message.channel.send(f"✅ {user.mention} is now blocked from using social interaction commands.")
        log.info("Blocked %s from social interactions (by %s)", user, message.author)

    async def handle_unblockuser(self, message: discord.Message) -> None:
        if not message.author.guild_permissions.administrator:
            await message.channel.send("You need administrator permission to use this command.")
            return
        if not message.mentions:
            await message.channel.send("Usage: `!unblockuser @member`")
            return
        user = message.mentions[0]
        if user.id not in self.blocked_users:
            await message.channel.send(f"{user.mention} is not blocked from using social interaction commands.")
            return
        self.blocked_users.discard(user.id)
        self._save_blocked_users()
        await message.channel.send(f"✅ {user.mention} is now unblocked and can use social interaction commands.")
        log.info("Unblocked %s from social interactions (by %s)", user, message.author)

    async def handle_listblockedusers(self, message: discord.Message, bot: discord.Client) -> None:
        if not message.author.guild_permissions.administrator:
            await message.channel.send("You need administrator permission to use this command.")
            return
        if not self.blocked_users:
            await message.channel.send("No users are currently blocked from using social interaction commands.")
            return
        lines = []
        for uid in self.blocked_users:
            user = bot.get_user(uid)
            lines.append(f"• {user.mention} (ID: {uid})" if user else f"• Unknown User (ID: {uid})")
        embed = discord.Embed(
            title="Blocked Users",
            description="Users blocked from using social interaction commands:",
            color=discord.Color.red(),
        )
        embed.add_field(
            name=f"Blocked Users ({len(self.blocked_users)})",
            value="\n".join(lines),
            inline=False,
        )
        await message.channel.send(embed=embed)

    async def handle_reload(self, message: discord.Message) -> None:
        if not message.author.guild_permissions.administrator:
            await message.channel.send("You need administrator permission to use this command.")
            return
        old_c, old_i = len(self.compliments), len(self.insults)
        self._load_messages()
        self.compliment_tracker = MessageTracker(self.compliments)
        self.insult_tracker = MessageTracker(self.insults)
        await message.channel.send(
            f"✅ Messages reloaded!\n"
            f"- Compliments: {old_c} → {len(self.compliments)}\n"
            f"- Insults: {old_i} → {len(self.insults)}"
        )
        log.info("Messages reloaded by %s", message.author)
