from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup

import config.settings as config
import database.users as users_db
import database.media as media_db
from languages.strings import t
from services.recommend import recommend_for_user
from middlewares.guards import not_banned
from handlers.error_handler import safe_handler
from utils.buttons import primary, success, danger
from utils.formatters import truncate
from plugins.navigate import _new_session


def anime_list_kb(items: list, empty_label: str) -> InlineKeyboardMarkup:
    rows = []
    for item in items:
        anime_id = item.get("anime_id") or item.get("_id")
        title = item.get("title", "Unknown")
        sid = _new_session(anime_id)
        rows.append([primary(f"🎬 {truncate(title, 40)}", callback_data=f"nv:{sid}:open")])
    if not rows:
        rows.append([primary(empty_label, callback_data="menu:search_hint")])
    rows.append([primary("🏠 Home", callback_data="menu:back_home"), danger("✖ Close", callback_data="menu:close")])
    return InlineKeyboardMarkup(rows)


def register(app: Client):

    @app.on_callback_query(filters.regex(r"^menu:favorites$"))
    @safe_handler
    async def favorites_cb(client: Client, query: CallbackQuery):
        fav_ids = await users_db.get_favorites(query.from_user.id)
        animes = [await media_db.get_anime(aid) for aid in fav_ids]
        animes = [a for a in animes if a]
        await query.message.edit_text(
            "❤️ **Your Favorites**" if animes else "❤️ You have no favorites yet.",
            reply_markup=anime_list_kb(animes, "🔍 Search Anime"),
        )

    @app.on_callback_query(filters.regex(r"^menu:continue$"))
    @safe_handler
    async def continue_watching_cb(client: Client, query: CallbackQuery):
        entries = await users_db.get_continue_watching(query.from_user.id)
        animes = []
        for e in entries:
            anime = await media_db.get_anime(e["anime_id"])
            if anime:
                anime["_resume"] = f"{e['season']} {e['episode']}"
                animes.append(anime)
        text = "📖 **Continue Watching**" if animes else "📖 Nothing in progress yet."
        await query.message.edit_text(text, reply_markup=anime_list_kb(animes, "🔍 Search Anime"))

    @app.on_message(filters.command("history"))
    @safe_handler
    @not_banned
    async def history_cmd(client: Client, message: Message):
        entries = await users_db.get_history(message.from_user.id, limit=15)
        if not entries:
            await message.reply_text("📜 No watch history yet.")
            return
        lines = [f"• {e['title']} — {e['season']} {e['episode']}" for e in entries]
        await message.reply_text("📜 **Your Recent History:**\n\n" + "\n".join(lines))

    @app.on_callback_query(filters.regex(r"^menu:trending$"))
    @safe_handler
    async def trending_cb(client: Client, query: CallbackQuery):
        animes = await media_db.trending(limit=10)
        await query.message.edit_text("🔥 **Trending Now**", reply_markup=anime_list_kb(animes, "🔍 Search Anime"))

    @app.on_callback_query(filters.regex(r"^menu:latest$"))
    @safe_handler
    async def latest_cb(client: Client, query: CallbackQuery):
        animes = await media_db.latest(limit=10)
        await query.message.edit_text("🆕 **Latest Added**", reply_markup=anime_list_kb(animes, "🔍 Search Anime"))

    @app.on_message(filters.command("random"))
    @safe_handler
    @not_banned
    async def random_cmd(client: Client, message: Message):
        anime = await media_db.random_anime()
        if not anime:
            await message.reply_text("Nothing indexed yet.")
            return
        sid = _new_session(anime["anime_id"])
        await message.reply_text(
            f"🎲 **Random Pick:** {anime['title']}",
            reply_markup=InlineKeyboardMarkup([[primary("🎬 Open", callback_data=f"nv:{sid}:open")]]),
        )

    @app.on_message(filters.command("recommend"))
    @safe_handler
    @not_banned
    async def recommend_cmd(client: Client, message: Message):
        user = await users_db.get_user(message.from_user.id)
        recs = await recommend_for_user(user.get("favorites", []), user.get("history", []))
        await message.reply_text(
            "✨ **Recommended for you:**" if recs else "Not enough data yet — favorite a few titles first!",
            reply_markup=anime_list_kb(recs, "🔍 Search Anime"),
        )

    @app.on_message(filters.command("profile"))
    @safe_handler
    @not_banned
    async def profile_cmd(client: Client, message: Message):
        user = await users_db.get_user(message.from_user.id)
        premium = "💎 Premium" if await users_db.is_premium(message.from_user.id) else "Free"
        await message.reply_text(
            f"👤 **Your Profile**\n\n"
            f"ID: `{user['user_id']}`\n"
            f"Plan: `{premium}`\n"
            f"Language: `{user.get('language') or 'Not set'}`\n"
            f"Favorites: `{len(user.get('favorites', []))}`\n"
            f"Referrals: `{user.get('referral_count', 0)}`\n\n"
            f"🔗 Your referral link: `https://t.me/{(await client.get_me()).username}?start=ref{user['user_id']}`"
        )
