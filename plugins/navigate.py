import secrets

from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup

import config.settings as config
import database.users as users_db
import database.media as media_db
import database.stats as stats_db
from languages.strings import t
from services.search import search_anime
from services.recommend import recommend_for_user, ai_suggest
from middlewares.guards import not_banned, maintenance_gate, flood_protect
from handlers.error_handler import safe_handler
from utils.buttons import primary, success, danger
from utils.formatters import format_size, paginate, truncate

# Short-lived in-memory navigation sessions - keeps callback_data well under
# Telegram's 64-byte limit regardless of how long an anime title/slug is.
# Sessions don't need to survive a restart; users just re-search.
NAV_SESSIONS = {}


def _new_session(anime_id: str) -> str:
    sid = secrets.token_hex(4)
    NAV_SESSIONS[sid] = {"anime_id": anime_id, "season": None, "episode": None, "quality": None, "audio": None}
    return sid


def _session(sid: str) -> dict:
    return NAV_SESSIONS.get(sid)


# ── keyboards ────────────────────────────────────────────────────────────
def results_kb(results: list) -> InlineKeyboardMarkup:
    rows = []
    for r in results:
        sid = _new_session(r["anime_id"])
        year = f" ({r['year']})" if r.get("year") else ""
        rows.append([primary(f"🎬 {truncate(r['title'], 40)}{year}", callback_data=f"nv:{sid}:open")])
    rows.append([danger("✖ Close", callback_data="menu:close")])
    return InlineKeyboardMarkup(rows)


def detail_kb(sid: str, anime: dict) -> InlineKeyboardMarkup:
    seasons = sorted(anime.get("seasons", {}).keys())
    rows = []
    for i in range(0, len(seasons), 2):
        row = [primary(f"📺 {s}", callback_data=f"nv:{sid}:season:{s}") for s in seasons[i:i + 2]]
        rows.append(row)
    fav_label = "❤️ Remove Favorite" if anime.get("_is_favorite") else "🤍 Add Favorite"
    rows.append([success(fav_label, callback_data=f"nv:{sid}:favtoggle")])
    rows.append([primary("🏠 Home", callback_data="menu:back_home"), danger("✖ Close", callback_data="menu:close")])
    return InlineKeyboardMarkup(rows)


def episode_kb(sid: str, season_key: str, episodes: list, page: int = 0) -> InlineKeyboardMarkup:
    page_items, total_pages = paginate(episodes, page, per_page=10)
    rows = []
    for i in range(0, len(page_items), 5):
        row = [primary(f"E{ep.replace('E', '')}", callback_data=f"nv:{sid}:episode:{season_key}:{ep}") for ep in page_items[i:i + 5]]
        rows.append(row)

    nav_row = []
    if page > 0:
        nav_row.append(primary("« Prev", callback_data=f"nv:{sid}:epage:{season_key}:{page-1}"))
    if page < total_pages - 1:
        nav_row.append(primary("Next »", callback_data=f"nv:{sid}:epage:{season_key}:{page+1}"))
    if nav_row:
        rows.append(nav_row)

    rows.append([primary("⬅ Back", callback_data=f"nv:{sid}:open"), danger("✖ Close", callback_data="menu:close")])
    return InlineKeyboardMarkup(rows)


def quality_kb(sid: str, season_key: str, episode_key: str, qualities: list) -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(qualities), 3):
        row = [primary(f"🖥 {q}", callback_data=f"nv:{sid}:quality:{season_key}:{episode_key}:{q}") for q in qualities[i:i + 3]]
        rows.append(row)
    rows.append([primary("⬅ Back", callback_data=f"nv:{sid}:season:{season_key}"), danger("✖ Close", callback_data="menu:close")])
    return InlineKeyboardMarkup(rows)


def audio_kb(sid: str, season_key: str, episode_key: str, quality: str, audios: list) -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(audios), 2):
        row = [primary(f"🔊 {a}", callback_data=f"nv:{sid}:audio:{season_key}:{episode_key}:{quality}:{a}") for a in audios[i:i + 2]]
        rows.append(row)
    rows.append([primary("⬅ Back", callback_data=f"nv:{sid}:episode:{season_key}:{episode_key}"), danger("✖ Close", callback_data="menu:close")])
    return InlineKeyboardMarkup(rows)


def download_kb(sid: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [success("⬇ Download", callback_data=f"nv:{sid}:get:dl"), primary("▶ Stream", callback_data=f"nv:{sid}:get:st")],
        [primary("⬅ Back", callback_data=f"nv:{sid}:backaudio"), primary("🏠 Home", callback_data="menu:back_home")],
        [danger("✖ Close", callback_data="menu:close")],
    ])


# ── rendering helpers ───────────────────────────────────────────────────
async def render_detail(sid: str, anime_id: str, user_id: int) -> tuple:
    anime = await media_db.get_anime(anime_id)
    if not anime:
        return "❌ This title is no longer available.", None

    anime["_is_favorite"] = await users_db.is_favorite(user_id, anime_id)
    genres = ", ".join(anime.get("genres", [])) or "Unknown"
    year_suffix = f" ({anime['year']})" if anime.get("year") else ""
    text = (
        f"🎬 **{anime['title']}**{year_suffix}\n\n"
        f"{anime.get('description') or 'No description available.'}\n\n"
        f"📌 Status: `{anime.get('status', 'unknown').title()}`\n"
        f"🎭 Genres: `{genres}`\n"
        f"📺 Seasons: `{len(anime.get('seasons', {}))}`"
    )
    return text, anime


def register(app: Client):

    # ── plain-text search (no command needed) ─────────────────────────
    @app.on_message(filters.text & filters.private & ~filters.command([
        "start", "help", "verify", "unmuteverify", "language", "settings",
        "restart", "shutdown", "broadcast", "stats", "maintenance",
        "addadmin", "removeadmin", "addchannel", "removechannel", "reindex",
        "backup", "restore", "ban", "unban", "favorites", "history", "profile",
    ]))
    @safe_handler
    @not_banned
    @maintenance_gate
    @flood_protect
    async def search_handler(client: Client, message: Message):
        lang = await users_db.get_language(message.from_user.id, config.DEFAULT_LANGUAGE)
        query = message.text.strip()
        if len(query) < 2:
            return

        status = await message.reply_text("🔎 Searching...")
        results = await search_anime(query, message.from_user.id)

        if not results:
            await status.edit_text(t("no_results", lang))
            return

        await status.edit_text(f"🔍 **Results for:** `{query}`", reply_markup=results_kb(results))

    # ── open anime detail ────────────────────────────────────────────
    @app.on_callback_query(filters.regex(r"^nv:(\w+):open$"))
    @safe_handler
    async def open_detail_cb(client: Client, query: CallbackQuery):
        sid = query.matches[0].group(1)
        session = _session(sid)
        if not session:
            await query.answer("This session expired — please search again.", show_alert=True)
            return

        text, anime = await render_detail(sid, session["anime_id"], query.from_user.id)
        if not anime:
            await query.message.edit_text(text)
            return

        await media_db.increment_views(session["anime_id"])
        await query.message.edit_text(text, reply_markup=detail_kb(sid, anime))

    @app.on_callback_query(filters.regex(r"^nv:(\w+):favtoggle$"))
    @safe_handler
    async def fav_toggle_cb(client: Client, query: CallbackQuery):
        sid = query.matches[0].group(1)
        session = _session(sid)
        if not session:
            await query.answer("Session expired.", show_alert=True)
            return
        anime_id = session["anime_id"]
        if await users_db.is_favorite(query.from_user.id, anime_id):
            await users_db.remove_favorite(query.from_user.id, anime_id)
            await query.answer("Removed from favorites.")
        else:
            await users_db.add_favorite(query.from_user.id, anime_id)
            await query.answer("Added to favorites!")
        text, anime = await render_detail(sid, anime_id, query.from_user.id)
        await query.message.edit_text(text, reply_markup=detail_kb(sid, anime))

    # ── season -> episode list ──────────────────────────────────────
    @app.on_callback_query(filters.regex(r"^nv:(\w+):season:(\w+)$"))
    @safe_handler
    async def open_season_cb(client: Client, query: CallbackQuery):
        sid, season_key = query.matches[0].groups()
        session = _session(sid)
        if not session:
            await query.answer("Session expired.", show_alert=True)
            return
        anime = await media_db.get_anime(session["anime_id"])
        episodes = sorted((anime.get("seasons", {}).get(season_key, {}).get("episodes", {})).keys())
        if not episodes:
            await query.answer("No episodes found for this season.", show_alert=True)
            return
        session["season"] = season_key
        lang = await users_db.get_language(query.from_user.id, config.DEFAULT_LANGUAGE)
        await query.message.edit_text(
            f"{t('choose_episode', lang)}\n\n📺 {anime['title']} — {season_key}",
            reply_markup=episode_kb(sid, season_key, episodes),
        )

    @app.on_callback_query(filters.regex(r"^nv:(\w+):epage:(\w+):(\d+)$"))
    @safe_handler
    async def episode_page_cb(client: Client, query: CallbackQuery):
        sid, season_key, page = query.matches[0].groups()
        session = _session(sid)
        if not session:
            await query.answer("Session expired.", show_alert=True)
            return
        anime = await media_db.get_anime(session["anime_id"])
        episodes = sorted((anime.get("seasons", {}).get(season_key, {}).get("episodes", {})).keys())
        await query.message.edit_reply_markup(episode_kb(sid, season_key, episodes, page=int(page)))

    # ── episode -> quality list ──────────────────────────────────────
    @app.on_callback_query(filters.regex(r"^nv:(\w+):episode:(\w+):(\w+)$"))
    @safe_handler
    async def open_episode_cb(client: Client, query: CallbackQuery):
        sid, season_key, episode_key = query.matches[0].groups()
        session = _session(sid)
        if not session:
            await query.answer("Session expired.", show_alert=True)
            return
        anime = await media_db.get_anime(session["anime_id"])
        ep_data = anime.get("seasons", {}).get(season_key, {}).get("episodes", {}).get(episode_key, {})
        qualities = sorted(ep_data.get("qualities", {}).keys())
        if not qualities:
            await query.answer("No files found for this episode.", show_alert=True)
            return
        session["episode"] = episode_key
        lang = await users_db.get_language(query.from_user.id, config.DEFAULT_LANGUAGE)
        await query.message.edit_text(
            f"{t('choose_quality', lang)}\n\n📺 {anime['title']} — {season_key} {episode_key}",
            reply_markup=quality_kb(sid, season_key, episode_key, qualities),
        )

    # ── quality -> audio list ─────────────────────────────────────────
    @app.on_callback_query(filters.regex(r"^nv:(\w+):quality:(\w+):(\w+):([\w\.]+)$"))
    @safe_handler
    async def open_quality_cb(client: Client, query: CallbackQuery):
        sid, season_key, episode_key, quality = query.matches[0].groups()
        session = _session(sid)
        if not session:
            await query.answer("Session expired.", show_alert=True)
            return
        anime = await media_db.get_anime(session["anime_id"])
        q_data = anime["seasons"][season_key]["episodes"][episode_key]["qualities"].get(quality, {})
        audios = sorted(q_data.get("audios", {}).keys())
        if not audios:
            await query.answer("No audio tracks found.", show_alert=True)
            return
        session["quality"] = quality
        lang = await users_db.get_language(query.from_user.id, config.DEFAULT_LANGUAGE)
        await query.message.edit_text(
            f"{t('choose_audio', lang)}\n\n📺 {anime['title']} — {season_key} {episode_key} [{quality}]",
            reply_markup=audio_kb(sid, season_key, episode_key, quality, audios),
        )

    # ── audio -> download/stream page ─────────────────────────────────
    @app.on_callback_query(filters.regex(r"^nv:(\w+):audio:(\w+):(\w+):([\w\.]+):(.+)$"))
    @safe_handler
    async def open_audio_cb(client: Client, query: CallbackQuery):
        sid, season_key, episode_key, quality, audio = query.matches[0].groups()
        session = _session(sid)
        if not session:
            await query.answer("Session expired.", show_alert=True)
            return
        anime = await media_db.get_anime(session["anime_id"])
        file_info = anime["seasons"][season_key]["episodes"][episode_key]["qualities"][quality]["audios"].get(audio)
        if not file_info:
            await query.answer("File not found.", show_alert=True)
            return
        session["audio"] = audio

        text = (
            f"📦 **{anime['title']}** — {season_key} {episode_key}\n\n"
            f"🖥 Quality: `{quality}`\n🔊 Audio: `{audio}`\n"
            f"💾 Size: `{format_size(file_info.get('file_size', 0))}`\n\n"
            "Choose an option:"
        )
        await query.message.edit_text(text, reply_markup=download_kb(sid))

    @app.on_callback_query(filters.regex(r"^nv:(\w+):backaudio$"))
    @safe_handler
    async def back_to_audio_cb(client: Client, query: CallbackQuery):
        sid = query.matches[0].group(1)
        session = _session(sid)
        if not session or not session.get("season") or not session.get("episode"):
            await query.answer("Session expired.", show_alert=True)
            return
        anime = await media_db.get_anime(session["anime_id"])
        ep_data = anime["seasons"][session["season"]]["episodes"][session["episode"]]
        qualities = sorted(ep_data.get("qualities", {}).keys())
        lang = await users_db.get_language(query.from_user.id, config.DEFAULT_LANGUAGE)
        await query.message.edit_text(
            f"{t('choose_quality', lang)}\n\n📺 {anime['title']} — {session['season']} {session['episode']}",
            reply_markup=quality_kb(sid, session["season"], session["episode"], qualities),
        )

    # ── deliver file (download or stream) ─────────────────────────────
    @app.on_callback_query(filters.regex(r"^nv:(\w+):get:(dl|st)$"))
    @safe_handler
    async def deliver_cb(client: Client, query: CallbackQuery):
        sid, action = query.matches[0].groups()
        session = _session(sid)
        if not session or not all([session.get("season"), session.get("episode"), session.get("quality"), session.get("audio")]):
            await query.answer("Session expired — please search again.", show_alert=True)
            return

        from plugins.verification import needs_verification, send_verification_prompt
        if await needs_verification(query.from_user.id):
            await query.answer()
            await send_verification_prompt(client, query.message.chat.id, query.from_user)
            return

        anime = await media_db.get_anime(session["anime_id"])
        file_info = (
            anime["seasons"][session["season"]]["episodes"][session["episode"]]
            ["qualities"][session["quality"]]["audios"][session["audio"]]
        )

        await query.answer("Sending...")
        caption = (
            f"🎬 **{anime['title']}** — {session['season']} {session['episode']}\n"
            f"🖥 {session['quality']} | 🔊 {session['audio']}"
        )

        if action == "dl":
            await client.send_document(query.message.chat.id, file_info["file_id"], caption=caption)
            await stats_db.log_event("download", {"user_id": query.from_user.id, "anime_id": session["anime_id"]})
        else:
            await client.send_video(query.message.chat.id, file_info["file_id"], caption=caption, supports_streaming=True)
            await stats_db.log_event("stream", {"user_id": query.from_user.id, "anime_id": session["anime_id"]})

        await users_db.push_history(query.from_user.id, {
            "anime_id": session["anime_id"], "title": anime["title"],
            "season": session["season"], "episode": session["episode"],
        })
        await users_db.update_continue_watching(
            query.from_user.id, session["anime_id"], session["season"], session["episode"]
        )

async def deliver_file_by_token(client: Client, message: Message, sid: str):
    """Used for shareable direct-watch deep links (/start get_<sid>)."""
    session = _session(sid)
    if not session or not all([session.get("season"), session.get("episode"), session.get("quality"), session.get("audio")]):
        await message.reply_text("❌ This link has expired. Please search again.")
        return

    from plugins.verification import needs_verification, send_verification_prompt
    if await needs_verification(message.from_user.id):
        await send_verification_prompt(client, message.chat.id, message.from_user)
        return

    anime = await media_db.get_anime(session["anime_id"])
    file_info = (
        anime["seasons"][session["season"]]["episodes"][session["episode"]]
        ["qualities"][session["quality"]]["audios"][session["audio"]]
    )
    await client.send_document(message.chat.id, file_info["file_id"], caption=f"🎬 {anime['title']}")
