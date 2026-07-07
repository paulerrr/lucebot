import datetime
import html
import logging
import re

import aiohttp
import discord

log = logging.getLogger("lucebot")

BASE_URL = "https://www.vaticannews.va"
DAY_URL = BASE_URL + "/en/saints/{month:02d}/{day:02d}.html"
# Vatican News returns 403 to non-browser user agents
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    )
}

EST = datetime.timezone(datetime.timedelta(hours=-5))

MAX_EMBEDS = 10  # Discord limit per message
MAX_DESCRIPTION = 4096  # Discord limit per embed

# Each saint on the day page lives in a <section ... section--isStatic>
# block: an <h2> name, and for the featured saint(s) also an image, a
# short bio <p> and a "Read all..." link to the full biography article.
_SECTION_RE = re.compile(
    r'<section class="section[^"]*section--isStatic[^"]*"[^>]*>(.*?)</section>',
    re.S,
)
_H2_RE = re.compile(r"<h2[^>]*>(.*?)</h2>", re.S)
_IMG_RE = re.compile(r'data-original="([^"]+)"')
_P_RE = re.compile(r"<p[^>]*>(.*?)</p>", re.S)
_LINK_RE = re.compile(r'class="saintReadMore" href="([^"]+)"')
_TAG_RE = re.compile(r"<[^>]+>")
_FIGURE_RE = re.compile(r"<figure>.*?</figure>", re.S)


def _clean(text: str) -> str:
    """Strip tags, unescape entities and collapse whitespace."""
    return re.sub(r"\s+", " ", html.unescape(_TAG_RE.sub("", text))).strip()


def _absolute(url: str) -> str:
    return url if url.startswith("http") else BASE_URL + url


def _format_bio(content: str) -> str:
    """Convert the article's HTML body to Discord markdown."""
    content = _FIGURE_RE.sub("", content)
    content = re.sub(r"<br\s*/?>", "\n", content)
    content = _H2_RE.sub(lambda m: "\n\n**" + _clean(m.group(1)) + "**\n", content)
    content = re.sub(r"</p>", "\n\n", content)
    content = html.unescape(_TAG_RE.sub("", content))
    lines = [re.sub(r"[ \t\xa0]+", " ", line).strip() for line in content.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _split_paragraphs(text: str, limit: int) -> list[str]:
    """Split text into chunks of at most ``limit`` chars at paragraph breaks."""
    chunks: list[str] = []
    current = ""
    for para in text.split("\n\n"):
        para = para[:limit]
        if current and len(current) + len(para) + 2 > limit:
            chunks.append(current)
            current = para
        else:
            current = current + "\n\n" + para if current else para
    if current:
        chunks.append(current)
    return chunks


def _parse_article(page: str) -> str | None:
    """Extract the full biography text from a saint article page."""
    start = page.find('santi--detail"')
    if start == -1:
        return None
    start = page.find(">", start) + 1
    end = page.find("</div>", start)
    body = page[start:end if end != -1 else None]
    bio = _format_bio(body)
    return bio or None


async def _fetch(session: aiohttp.ClientSession, url: str) -> tuple[int, str | None]:
    """Return ``(status, body)``; status is 0 on connection errors."""
    try:
        async with session.get(url, headers=HEADERS) as resp:
            if resp.status != 200:
                log.error("Failed to fetch %s (HTTP %s)", url, resp.status)
                return resp.status, None
            return 200, await resp.text()
    except Exception:
        log.exception("Failed to fetch %s", url)
        return 0, None


def _saint_embeds(
    name: str, bio: str, article_url: str | None, image_url: str | None, room: int
) -> list[discord.Embed]:
    """Build one or more embeds for a saint, using at most ``room`` embeds."""
    embeds = []
    for chunk in _split_paragraphs(bio, MAX_DESCRIPTION)[:room]:
        embed = discord.Embed(
            title=name if not embeds else None,
            description=chunk,
            color=discord.Color.gold(),
        )
        if not embeds:
            if article_url:
                embed.url = article_url
            if image_url:
                embed.set_thumbnail(url=image_url)
        embeds.append(embed)
    if embeds:
        embeds[-1].set_footer(text="Vatican News · Saint of the Day")
    return embeds


async def get_daily_saint() -> list[discord.Embed] | None | str:
    """Fetch today's saint of the day from Vatican News.

    Returns a list of embeds with the featured saint's full biography
    (plus any other saints celebrated today), the string ``"no_feast"``
    when no saint is listed, or ``None`` on fetch errors.
    """
    today = datetime.datetime.now(EST)
    day_url = DAY_URL.format(month=today.month, day=today.day)

    async with aiohttp.ClientSession() as session:
        status, page = await _fetch(session, day_url)
        if status == 404:
            # Days like All Saints/All Souls have no saint page
            return "no_feast"
        if page is None:
            return None

        embeds: list[discord.Embed] = []
        others: list[str] = []
        for body in _SECTION_RE.findall(page):
            name_match = _H2_RE.search(body)
            if not name_match:
                continue
            name = _clean(name_match.group(1))
            if not name:
                continue

            blurb_match = _P_RE.search(body)
            link_match = _LINK_RE.search(body)
            if (not blurb_match and not link_match) or len(embeds) >= MAX_EMBEDS - 1:
                others.append(name)
                continue

            # Prefer the full biography from the linked article; fall
            # back to the day page's short blurb if that fails.
            article_url = _absolute(link_match.group(1)) if link_match else None
            bio = None
            if article_url:
                _, article = await _fetch(session, article_url)
                if article is not None:
                    bio = _parse_article(article)
            if bio is None and blurb_match:
                bio = _clean(blurb_match.group(1))
            if not bio:
                others.append(name)
                continue

            img_match = _IMG_RE.search(body)
            image_url = _absolute(img_match.group(1)) if img_match else None
            embeds += _saint_embeds(
                name, bio, article_url, image_url, MAX_EMBEDS - 1 - len(embeds)
            )

    if others:
        listing = "\n".join(others)[:1024]
        if embeds:
            embeds[-1].add_field(
                name="Also celebrated today", value=listing, inline=False
            )
        else:
            embed = discord.Embed(
                title="Saints of the day",
                description=listing,
                color=discord.Color.gold(),
            )
            embed.set_footer(text="Vatican News · Saint of the Day")
            embeds.append(embed)

    if not embeds:
        log.warning("No saint sections found on %s", day_url)
        return "no_feast"

    return embeds
