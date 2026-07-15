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

# A pattern is either a phrase ("mega seller") or terms joined with "+"
# ("cp + seller"), in which case every term must appear in the message.
DEFAULT_MESSAGE_PATTERNS = [
    "mega seller",
    "cp + seller",
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


def _get_message_patterns():
    patterns = cfg.get("spam_message_patterns")
    if patterns is None:
        patterns = list(DEFAULT_MESSAGE_PATTERNS)
        cfg.set("spam_message_patterns", patterns)
    return patterns


def add_message_pattern(pattern: str) -> bool:
    """Add a phrase to the message auto-ban list. Returns False if already present."""
    pattern = pattern.strip().lower()
    patterns = _get_message_patterns()
    if not pattern or pattern in patterns:
        return False
    patterns.append(pattern)
    cfg.set("spam_message_patterns", patterns)
    return True


def remove_message_pattern(pattern: str) -> bool:
    """Remove a phrase from the message auto-ban list. Returns False if not present."""
    pattern = pattern.strip().lower()
    patterns = _get_message_patterns()
    if pattern not in patterns:
        return False
    patterns.remove(pattern)
    cfg.set("spam_message_patterns", patterns)
    return True


def list_message_patterns():
    return list(_get_message_patterns())


_SYMBOL_RE = re.compile(r"[^a-z0-9\s]+")  # strip symbols, keep word gaps
_SQUASH_RE = re.compile(r"[^a-z0-9]+")  # strip everything but letters/digits

# Minimum squashed length for the no-boundary substring pass; shorter terms
# would false-positive across word joins (e.g. 'cp' in 'basic plan').
MIN_SQUASH_LEN = 6


def _term_matches(term: str, lowered: str, deobfuscated: str, squashed: str) -> bool:
    # Word-boundary match on the raw text and on text with symbols stripped,
    # so 'c.p seller' matches 'cp' but 'cpu' does not.
    word_re = r"\b" + re.escape(term) + r"\b"
    if re.search(word_re, lowered) or re.search(word_re, deobfuscated):
        return True
    # Fully squashed substring match catches 'MegaSeller' and
    # 'm e g a s e l l e r', but only for terms long enough to be unambiguous.
    squashed_term = _SQUASH_RE.sub("", term)
    return len(squashed_term) >= MIN_SQUASH_LEN and squashed_term in squashed


def check_message(content: str):
    """Return a reason string if the message content looks like spam, else None.

    A pattern is a phrase ('mega seller') or terms joined with '+'
    ('cp + seller'), in which case every term must appear somewhere in
    the message. Matching is case-insensitive and obfuscation-resistant:
    'M.EGA S.ELLER' and 'MegaSeller' both match 'mega seller'.
    """
    if not content:
        return None
    lowered = content.lower()
    deobfuscated = _SYMBOL_RE.sub("", lowered)
    squashed = _SQUASH_RE.sub("", lowered)
    for pattern in _get_message_patterns():
        terms = [t.strip() for t in pattern.split("+") if t.strip()]
        if terms and all(_term_matches(t, lowered, deobfuscated, squashed) for t in terms):
            return f"message matched pattern '{pattern}'"
    return None


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


async def check_message_and_ban(message: discord.Message, log_channel=None) -> bool:
    """Check a message's content against the spam patterns and ban the author if matched.

    Returns True if the author was banned.
    """
    author = message.author
    if message.guild is None or not isinstance(author, discord.Member):
        return False
    if author.bot or author.guild_permissions.manage_messages:
        return False

    reason = check_message(message.content)
    if reason is None:
        return False

    try:
        # delete_message_seconds also removes the spam message itself
        await author.ban(
            reason=f"Auto-banned by spam filter: {reason}",
            delete_message_seconds=3600,
        )
    except discord.Forbidden:
        log.error("Missing permissions to auto-ban %s", author)
        return False

    log.info("Auto-banned %s for spam message (%s)", author, reason)

    if log_channel:
        snippet = message.content
        if len(snippet) > 1024:
            snippet = snippet[:1021] + "..."
        embed = discord.Embed(
            title="Member Auto-Banned — Spam Message",
            description=f"{author.mention} ({author})",
            color=discord.Color.dark_red(),
        )
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Message", value=snippet, inline=False)
        embed.add_field(name="Channel", value=message.channel.mention, inline=False)
        embed.set_thumbnail(url=author.display_avatar.url)
        embed.set_footer(text=f"ID: {author.id}")
        embed.timestamp = discord.utils.utcnow()
        await log_channel.send(embed=embed)

    return True


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
