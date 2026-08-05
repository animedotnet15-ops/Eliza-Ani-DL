import asyncio

from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup

import config.settings as config
import database.users as users_db
import database.admins as admins_db
import database.stats as stats_db
from database.settings_db import get_settings
from languages.strings import t, LANGUAGES
from services.force_sub import get_unjoined_channels
from middlewares.guards import not_banned, maintenance_gate
from handlers.error_handler import safe_handler
from utils.buttons import primary, success, danger

STARTUP_FRAMES = [
    "🔄 Booting up...",
    "📡 Connecting to Telegram...",
    "🗂 Loading anime database...",
    "✅ {bot_name} is ready!",
]


def language_kb() -> InlineKeyboardMarkup:
    rows = []
    codes = list(LANGUAGES.items())
    for i in range(0, len(codes), 2):
        row = []
        for code, meta in codes[i:i + 2]:
            row.append(primary(f"{meta['flag']} {meta['name']}", callback_data=f"setlang:{code}"))
        rows.append(row)
    return InlineKeyboardMarkup(rows)


def force_sub_kb(channels: list) -> InlineKeyboardMarkup:
    rows = [[primary(f"📢 Join Channel {i+1}", url=f"https://t.me/{c.lstrip('@')}")] for i, c in enumerate(channels)]
    rows.append([success("✅ I've Joined", callback_data="checkjoin")])
    return InlineKeyboardMarkup(rows)


def main_menu_kb(lang: str) -> InlineKeyboardMarkup:
    rows = [
        [primary("🔍 Search Anime", callback_data="menu:search_hint"), primary("🔥 Trending", callback_data="menu:trending")],
        [primary("🆕 Latest", callback_data="menu:latest"), success("❤️ Favorites", callback_data="menu:favorites")],
        [success("📖 Continue Watching", callback_data="menu:continue"), primary("🌐 Language", callback_data="menu:language")],
        [primary("✅ Verification", callback_data="menu:verifystatus"), primary("⚙ Settings", callback_data="menu:settings")],
    ]
    support_row = []
    if config.UPDATES_CHANNEL:
        support_row.append(primary("📢 Updates", url=config.UPDATES_CHANNEL))
    if config.SUPPORT_CHAT:
        support_row.append(primary("💬 Support", url=config.SUPPORT_CHAT))
    if support_row:
        rows.append(support_row)
    rows.append([primary("ℹ About", callback_data="menu:about")])
    return InlineKeyboardMarkup(rows)


async def send_welcome(client: Client, chat_id: int, user):
    settings = await get_settings()
    lang = await users_db.get_language(user.id, config.DEFAULT_LANGUAGE)

    text = settings["welcome_text"].format(
        first_name=user.first_name or "there",
        username=f"@{user.username}" if user.username else "N/A",
        id=user.id,
        bot_name=config.BOT_NAME,
    )

    if settings.get("welcome_sticker"):
        try:
            await client.send_sticker(chat_id, settings["welcome_sticker"])
        except Exception:
            pass

    if settings.get("welcome_image"):
        await client.send_photo(chat_id, settings["welcome_image"], caption=text, reply_markup=main_menu_kb(lang))
    else:
        await client.send_message(chat_id, text, reply_markup=main_menu_kb(lang))


def register(app: Client):

    @app.on_message(filters.command("start"))
    @safe_handler
    @not_banned
    @maintenance_gate
    async def start_cmd(client: Client, message: Message):
        user = message.from_user
        payload = message.command[1] if len(message.command) > 1 else None

        existing = await users_db.get_user(user.id)
        referred_by = None
        if payload and payload.startswith("ref") and payload[3:].isdigit():
            referred_by = int(payload[3:])

        await users_db.add_user(user.id, user.first_name or "", user.username or "", referred_by=referred_by)
        if not existing:
            await stats_db.log_event("new_user", {"user_id": user.id})

        # ── deep-link routing ────────────────────────────────────────────
        if payload and payload.startswith("verify_"):
            from plugins.verification import handle_verification_deeplink
            await handle_verification_deeplink(client, message, payload[len("verify_"):])
            return

        if payload and payload.startswith("get_"):
            from plugins.navigate import deliver_file_by_token
            await deliver_file_by_token(client, message, payload[len("get_"):])
            return

        # ── first-time language selection ───────────────────────────────
        user_doc = await users_db.get_user(user.id)
        if not user_doc.get("language"):
            await message.reply_text(t("choose_language", config.DEFAULT_LANGUAGE), reply_markup=language_kb())
            return

        lang = user_doc["language"]

        # ── force subscribe ──────────────────────────────────────────────
        unjoined = await get_unjoined_channels(client, user.id)
        if unjoined:
            await message.reply_text(t("force_sub_required", lang), reply_markup=force_sub_kb(unjoined))
            return

        # ── animated startup + welcome ───────────────────────────────────
        status = await message.reply_text(STARTUP_FRAMES[0])
        for frame in STARTUP_FRAMES[1:]:
            await asyncio.sleep(0.6)
            await status.edit_text(frame.format(bot_name=config.BOT_NAME))
        await status.delete()

        await send_welcome(client, message.chat.id, user)

    @app.on_callback_query(filters.regex(r"^setlang:(\w+)$"))
    @safe_handler
    async def set_language_cb(client: Client, query: CallbackQuery):
        lang = query.data.split(":", 1)[1]
        await users_db.set_language(query.from_user.id, lang)
        await query.message.edit_text(t("language_set", lang))
        await send_welcome(client, query.message.chat.id, query.from_user)

    @app.on_callback_query(filters.regex(r"^checkjoin$"))
    @safe_handler
    async def check_join_cb(client: Client, query: CallbackQuery):
        lang = await users_db.get_language(query.from_user.id, config.DEFAULT_LANGUAGE)
        unjoined = await get_unjoined_channels(client, query.from_user.id)
        if unjoined:
            await query.answer("You haven't joined all channels yet.", show_alert=True)
            return
        await query.message.delete()
        await send_welcome(client, query.message.chat.id, query.from_user)

    @app.on_callback_query(filters.regex(r"^menu:language$"))
    @safe_handler
    async def language_menu_cb(client: Client, query: CallbackQuery):
        lang = await users_db.get_language(query.from_user.id, config.DEFAULT_LANGUAGE)
        await query.message.edit_text(t("choose_language", lang), reply_markup=language_kb())

    @app.on_callback_query(filters.regex(r"^menu:about$"))
    @safe_handler
    async def about_cb(client: Client, query: CallbackQuery):
        await query.answer(
            f"{config.BOT_NAME} — Telegram anime search & streaming bot.",
            show_alert=True,
        )

    @app.on_callback_query(filters.regex(r"^menu:search_hint$"))
    @safe_handler
    async def search_hint_cb(client: Client, query: CallbackQuery):
        lang = await users_db.get_language(query.from_user.id, config.DEFAULT_LANGUAGE)
        await query.answer(t("search_prompt", lang), show_alert=True)

    @app.on_callback_query(filters.regex(r"^menu:back_home$"))
    @safe_handler
    async def back_home_cb(client: Client, query: CallbackQuery):
        lang = await users_db.get_language(query.from_user.id, config.DEFAULT_LANGUAGE)
        await query.message.edit_text(
            t("main_menu", lang, first_name=query.from_user.first_name or "there"),
            reply_markup=main_menu_kb(lang),
        )

    @app.on_callback_query(filters.regex(r"^menu:close$"))
    @safe_handler
    async def close_cb(client: Client, query: CallbackQuery):
        await query.message.delete()
