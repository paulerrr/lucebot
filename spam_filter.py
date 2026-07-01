import logging
import re

import discord

import config as cfg

log = logging.getLogger("lucebot.spam")

DEFAULT_KEYWORDS = [
    "seller", "sellers", "mega link", "megalink", "mega links",
    "nitro", "onlyfans", "leaks", "cheap nitro",
    "crypto", "airdrop", "forex", "cc shop", "cvv", "fullz",
]

DOT_RATIO_THRESHOLD = 0.15
MIN_DOTS = 3
MIN_TOKENS = 3


def _get_keywords():
    keywords = cfg.get("spam_keywords")
    if keywords is None:
        keywords = list(DEFAULT_KEYWORDS)
        cfg.set("spam_keywords", keywords)
    return keywords


def add_keyword(word: str) -> bool:
    """Add a keyword to the blocklist. Returns False if it was already present."""
    word = word.strip().lower()
    keywords = _get_keywords()
    if not word or word in keywords:
        return False
    keywords.append(word)
    cfg.set("spam_keywords", keywords)
    return True


def remove_keyword(word: str) -> bool:
    """Remove a keyword from the blocklist. Returns False if it wasn't present."""
    word = word.strip().lower()
    keywords = _get_keywords()
    if word not in keywords:
        return False
    keywords.remove(word)
    cfg.set("spam_keywords", keywords)
    return True


def list_keywords():
    return list(_get_keywords())


def _dot_pattern_reason(name: str):
    """Flag names like '.TEENS .MEGA ..LINKS S.ELLER' — dot-obfuscated spam."""
    dots = name.count(".")
    if dots < MIN_DOTS or not name:
        return None
    tokens = [t for t in re.split(r"[.\s]+", name) if t]
    ratio = dots / len(name)
    if ratio >= DOT_RATIO_THRESHOLD and len(tokens) >= MIN_TOKENS:
        return f"obfuscated dot pattern ({dots} dots across {len(tokens)} tokens)"
    return None


def check_name(name: str):
    """Return a reason string if the name looks like spam, else None."""
    if not name:
        return None
    lowered = name.lower()
    for keyword in _get_keywords():
        if keyword in lowered:
            return f"matched keyword '{keyword}'"
    return _dot_pattern_reason(name)


async def check_and_ban(member: discord.Member, log_channel=None) -> bool:
    """Check a member's username/display name against the spam filter and ban if matched.

    Returns True if the member was banned.
    """
    reason = check_name(member.name) or check_name(member.display_name)
    if reason is None:
        return False

    try:
        await member.ban(reason=f"Auto-banned by spam filter: {reason}", delete_message_seconds=0)
    except discord.Forbidden:
        log.error("Missing permissions to auto-ban %s", member)
        return False

    log.info("Auto-banned %s for spam name (%s)", member, reason)

    if log_channel:
        embed = discord.Embed(
            title="Member Auto-Banned — Spam Filter",
            description=f"{member.mention} ({member})",
            color=discord.Color.dark_red(),
        )
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"ID: {member.id}")
        embed.timestamp = discord.utils.utcnow()
        await log_channel.send(embed=embed)

    return True
