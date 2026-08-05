from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup

import config.settings as config
import database.users as users_db
import database.stats as stats_db
from database.settings_db import get_settings
from languages.strings import t
from services.shortener import build_verification_link, check_verification, VerificationResult
from handlers.error_handler import safe_handler
from utils.buttons import primary, success, danger

MUTED_VERIFIERS = set()  # in-memory; bypass-muted users can't request new links this session


def verify_kb(link: str, tutorial_url: str = "") -> InlineKeyboardMarkup:
    rows = [[success("🔑 Verify", url=link)]]
    if tutorial_url:
        rows.append([primary("📺 How to verify", url=tutorial_url)])
    return InlineKeyboardMarkup(rows)


async def needs_verification(user_id: int) -> bool:
    settings = await get_settings()
    if not settings.get("shortener_enabled"):
        return False
    return not await users_db.is_verified(user_id)


async def send_verification_prompt(client: Client, chat_id: int, user):
    lang = await users_db.get_language(user.id, config.DEFAULT_LANGUAGE)
    settings = await get_settings()

    if user.id in MUTED_VERIFIERS:
        await client.send_message(chat_id, "🔇 You've been muted from verifying due to bypass detection. Contact the admin.")
        return

    me = await client.get_me()
    link, _token = await build_verification_link(me.username, user.id)
    validity = settings.get("verify_validity_hours", 6)
    validity_text = "unlimited" if validity <= 0 else f"{validity} hour(s)"

    text = (
        f"{t('verify_required', lang)}\n\n"
        f"⏱ Take at least **{settings.get('verify_min_minutes', 2)} min** to complete it "
        f"(and no more than **{settings.get('verify_max_minutes', 5)} min**).\n"
        f"✅ Once verified, access lasts **{validity_text}**."
    )
    await client.send_message(chat_id, text, reply_markup=verify_kb(link, settings.get("verify_tutorial_url", "")))


async def handle_verification_deeplink(client: Client, message: Message, token: str):
    user = message.from_user
    lang = await users_db.get_language(user.id, config.DEFAULT_LANGUAGE)
    settings = await get_settings()

    result = await check_verification(user.id, token)

    if result == VerificationResult.SUCCESS:
        await users_db.set_verified(user.id, settings.get("verify_validity_hours", 6))
        await stats_db.log_event("verify_success", {"user_id": user.id})
        await message.reply_text(t("verify_success", lang))
        if config.LOG_CHANNEL:
            await client.send_message(config.LOG_CHANNEL, f"✅ Verification success: `{user.id}` (@{user.username or 'N/A'})")

    elif result == VerificationResult.TOO_FAST:
        MUTED_VERIFIERS.add(user.id)
        await stats_db.log_event("bypass_detected", {"user_id": user.id})
        await message.reply_text(t("verify_too_fast", lang))
        if config.LOG_CHANNEL:
            await client.send_message(config.LOG_CHANNEL, f"🚨 Bypass detected: `{user.id}` (@{user.username or 'N/A'})")

    elif result == VerificationResult.EXPIRED:
        await stats_db.log_event("verify_failed", {"user_id": user.id, "reason": "expired"})
        await message.reply_text(t("verify_expired", lang))
        await send_verification_prompt(client, message.chat.id, user)

    else:
        await message.reply_text("❌ Invalid or already-used verification link.")


def register(app: Client):

    @app.on_message(filters.command("verify"))
    @safe_handler
    async def verify_cmd(client: Client, message: Message):
        await send_verification_prompt(client, message.chat.id, message.from_user)

    @app.on_callback_query(filters.regex(r"^menu:verifystatus$"))
    @safe_handler
    async def verify_status_cb(client: Client, query: CallbackQuery):
        lang = await users_db.get_language(query.from_user.id, config.DEFAULT_LANGUAGE)
        verified = await users_db.is_verified(query.from_user.id)
        settings = await get_settings()
        if not settings.get("shortener_enabled"):
            await query.answer("✅ Verification isn't required right now.", show_alert=True)
            return
        if verified:
            await query.answer(t("verify_success", lang), show_alert=True)
        else:
            await query.message.delete()
            await send_verification_prompt(client, query.message.chat.id, query.from_user)

    @app.on_message(filters.command("unmuteverify"))
    @safe_handler
    async def unmute_verify_cmd(client: Client, message: Message):
        import database.admins as admins_db
        if not await admins_db.is_admin(message.from_user.id):
            return
        if len(message.command) < 2:
            await message.reply_text("Usage: `/unmuteverify <user_id>`")
            return
        uid = int(message.command[1])
        MUTED_VERIFIERS.discard(uid)
        await message.reply_text(f"✅ `{uid}` can verify again.")
