"""
Telegram Manga/Manhwa Info Bot
Uses Comick.io API to fetch and format manga/manhwa details.

Requirements:
    pip install python-telegram-bot requests

Setup:
    1. Get a Telegram Bot Token from @BotFather
    2. Set BOT_TOKEN as environment variable OR replace below
    3. Run: python manga_bot_comick.py
"""

import os
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN", "7973494693:AAEXCP2cOQydMuwO3daU1gdu-tHCaQa2-ow")

COMICK_BASE = "https://api.comick.fun"

# ── Helpers ───────────────────────────────────────────────────────────────────

SMALLCAPS = str.maketrans(
    "abcdefghijklmnopqrstuvwxyz",
    "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ"
)

def to_smallcaps(text: str) -> str:
    return text.lower().translate(SMALLCAPS)

def format_type(country: str) -> str:
    return {
        "KR": "Mᴀɴʜᴡᴀ",
        "CN": "Mᴀɴʜᴜᴀ",
        "JP": "Mᴀɴɢᴀ",
    }.get(country, to_smallcaps(country) if country else "Mᴀɴɢᴀ")

def format_status(status: int) -> str:
    return {
        1: "Oɴɢᴏɪɴɢ",
        2: "Cᴏᴍᴘʟᴇᴛᴇᴅ",
        3: "Cᴀɴᴄᴇʟʟᴇᴅ",
        4: "Hɪᴀᴛᴜs",
    }.get(status, "Uɴᴋɴᴏᴡɴ")

def truncate(text: str, limit: int = 600) -> str:
    if not text:
        return "N/A"
    text = " ".join(text.split())
    return text[:limit].rstrip() + "..." if len(text) > limit else text

def get_english_alt_titles(comic: dict, main_title: str) -> list:
    """Return English alt titles excluding the main title."""
    seen = {main_title.lower().strip()}
    alts = []
    for t in comic.get("md_titles", []):
        lang = t.get("lang", "")
        title = (t.get("title") or "").strip()
        if lang == "en" and title and title.lower() not in seen:
            seen.add(title.lower())
            alts.append(title)
    return alts

# ── Comick API ────────────────────────────────────────────────────────────────

def search_comick(title: str) -> dict | None:
    resp = requests.get(
        f"{COMICK_BASE}/v1.0/search",
        params={"q": title, "limit": 1, "type": "comic"},
        timeout=10
    )
    results = resp.json()
    return results[0] if results else None

def get_comic_detail(hid: str) -> dict | None:
    resp = requests.get(f"{COMICK_BASE}/comic/{hid}", timeout=10)
    return resp.json().get("comic")

def get_chapter_count(hid: str) -> int | None:
    resp = requests.get(
        f"{COMICK_BASE}/comic/{hid}/chapters",
        params={"limit": 1, "page": 1},
        timeout=10
    )
    chapters = resp.json().get("chapters", [])
    if chapters:
        ch = chapters[0].get("chap")
        try:
            return int(float(ch)) if ch else None
        except (ValueError, TypeError):
            return None
    return None

def build_cover_url(b2key: str) -> str | None:
    return f"https://meo.comick.pictures/{b2key}" if b2key else None

def build_message(comic: dict, chapters: int | None) -> str:
    main_title = comic.get("title") or comic.get("slug", "Unknown")

    # English alt titles joined by |
    alt_titles = get_english_alt_titles(comic, main_title)
    alt_line = (" | ".join(alt_titles)) if alt_titles else None

    country = comic.get("country", "JP")
    media_type = format_type(country)
    status = format_status(comic.get("status", 1))

    score = comic.get("bayesian_rating") or comic.get("rating") or "N/A"
    if isinstance(score, float):
        score = round(score, 1)

    is_ongoing = comic.get("status") == 1
    chapters_str = f"{chapters}+" if (chapters and is_ongoing) else (str(chapters) if chapters else "N/A")

    # Genres
    tags = comic.get("md_comic_md_genres", [])
    genre_names = [t.get("md_genres", {}).get("name", "") for t in tags if t.get("md_genres")]
    genres = ", ".join(to_smallcaps(g) for g in genre_names[:6]) or "N/A"

    # Synopsis — expandable blockquote using <blockquote expandable>
    description = truncate(comic.get("desc", ""))

    # Author / Artist
    author, artist = "N/A", "N/A"
    for person in comic.get("md_comic_md_authors", []):
        role = person.get("role", "")
        name = person.get("md_authors", {}).get("name", "")
        if role == "author" and author == "N/A":
            author = name
        elif role == "artist" and artist == "N/A":
            artist = name

    slug = comic.get("slug", "")
    url = f"https://comick.dev/comic/{slug}" if slug else "https://comick.dev"

    # ── Build title block (blockquote) ────────────────────────────────────────
    # Main title + optional alt titles on next line inside the blockquote
    title_block = f"<blockquote>📖 <b>{main_title}</b>"
    if alt_line:
        title_block += f"\n{alt_line}"
    title_block += "</blockquote>"

    # ── Build synopsis block (expandable blockquote) ──────────────────────────
    synopsis_block = f"<blockquote expandable>{description}</blockquote>"

    msg = (
        f"{title_block}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"➥𝗧𝘆𝗽𝗲: {media_type}\n"
        f"➥𝗦𝘁𝗮𝘁𝘂𝘀: {status}\n"
        f"➥𝗥𝗮𝘁𝗶𝗻𝗴: {score}\n"
        f"➥𝗖𝗵𝗮𝗽𝘁𝗲𝗿𝘀: {chapters_str}\n"
        f"➥𝗚𝗲𝗻𝗿𝗲: {genres}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"➥𝗔𝘂𝘁𝗵𝗼𝗿: {author}\n"
        f"➥𝗔𝗿𝘁𝗶𝘀𝘁: {artist}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"➥𝗦𝘆𝗻𝗼𝗽𝘀𝗶𝘀:\n{synopsis_block}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔗 <a href='{url}'>View on Comick</a>"
    )
    return msg

# ── Core Search Logic ─────────────────────────────────────────────────────────

def fetch_comic(title: str):
    result = search_comick(title)
    if not result:
        return None, None, None

    hid = result.get("hid")
    if not hid:
        return None, None, None

    comic = get_comic_detail(hid)
    if not comic:
        return None, None, None

    chapters = get_chapter_count(hid)
    covers = comic.get("md_covers", [])
    b2key = covers[0].get("b2key") if covers else None
    cover_url = build_cover_url(b2key)

    return comic, chapters, cover_url

# ── Telegram Handlers ─────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📚 <b>Manga/Manhwa Info Bot</b>\n\n"
        "Send me any manga or manhwa title!\n\n"
        "Or use: /manga &lt;title&gt;\n"
        "Powered by <a href='https://comick.io'>Comick.io</a>",
        parse_mode="HTML",
        disable_web_page_preview=True
    )

async def handle_search(update: Update, title: str, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔍 Searching Comick...")

    comic, chapters, cover_url = fetch_comic(title)
    await msg.delete()

    if not comic:
        await update.message.reply_text("❌ No results found. Try a different title.")
        return

    message = build_message(comic, chapters)

    if cover_url:
        try:
            await update.message.reply_photo(
                photo=cover_url,
                caption=message,
                parse_mode="HTML"
            )
            return
        except Exception:
            pass  # Fall back to text if photo fails

    await update.message.reply_text(
        message,
        parse_mode="HTML",
        disable_web_page_preview=True
    )

async def manga_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /manga <title>\nExample: /manga Tower of God")
        return
    await handle_search(update, " ".join(context.args), context)

async def text_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_search(update, update.message.text.strip(), context)

# ── Entry Point ───────────────────────────────────────────────────────────────

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("manga", manga_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_search))
    print("✅ Bot is running with Comick API...")
    app.run_polling()

if __name__ == "__main__":
    main()
