from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup

import database.settings_db as settings_db
from middlewares.guards import admin_only
from handlers.error_handler import safe_handler
from utils.buttons import primary, success, danger


def settings_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [primary("✅ Verification Settings", callback_data="adm:verify")],
        [primary("🔗 Shortener Settings", callback_data="adm:shortener")],
        [primary("📢 Force Subscribe", callback_data="adm:forcesub")],
        [primary("👋 Welcome Settings", callback_data="adm:welcome")],
        [danger("✖ Close", callback_data="menu:close")],
    ])


async def verify_settings_text() -> str:
    s = await settings_db.get_settings()
    validity = "Unlimited" if s.get("verify_validity_hours", 0) <= 0 else f"{s['verify_validity_hours']}h"
    return (
        "✅ **Verification Settings**\n\n"
        f"Minimum time: `{s.get('verify_min_minutes')} min`\n"
        f"Maximum time: `{s.get('verify_max_minutes')} min`\n"
        f"Validity: `{validity}`\n\n"
        "Change with:\n"
        "`/setverifymin <minutes>`\n`/setverifymax <minutes>`\n`/setverifyvalidity <hours>` (0 = unlimited)"
    )


async def shortener_settings_text() -> str:
    s = await settings_db.get_settings()
    return (
        "🔗 **Shortener Settings**\n\n"
        f"Enabled: `{s.get('shortener_enabled')}`\n"
        f"Domain: `{s.get('shortener_domain') or 'Not set'}`\n"
        f"API key: `{'Set' if s.get('shortener_api') else 'Not set'}`\n\n"
        "Change with:\n"
        "`/setshortenerapi <api_key>`\n`/setshortenerdomain <domain>`\n`/toggleshortener`"
    )


async def force_sub_settings_text() -> str:
    s = await settings_db.get_settings()
    channels = s.get("force_sub_channels", [])
    listing = "\n".join(f"• {c}" for c in channels) or "None configured."
    return (
        "📢 **Force Subscribe**\n\n"
        f"Enabled: `{s.get('force_sub_enabled')}`\n\n"
        f"Channels:\n{listing}\n\n"
        "Change with:\n"
        "`/addforcesub <@channel>`\n`/removeforcesub <@channel>`\n`/toggleforcesub`"
    )


async def welcome_settings_text() -> str:
    s = await settings_db.get_settings()
    return (
        "👋 **Welcome Settings**\n\n"
        f"Text: `{s.get('welcome_text', '')[:200]}`\n"
        f"Image: `{'Set' if s.get('welcome_image') else 'Not set'}`\n"
        f"Sticker: `{'Set' if s.get('welcome_sticker') else 'Not set'}`\n\n"
        "Change with:\n"
        "`/setwelcometext <text>` (supports {first_name} {username} {id} {bot_name})\n"
        "Reply to a photo with `/setwelcomeimage`\n"
        "Reply to a sticker with `/setwelcomesticker`"
    )


def register(app: Client):

    @app.on_callback_query(filters.regex(r"^menu:settings$"))
    @safe_handler
    @admin_only
    async def settings_menu_cb(client: Client, query: CallbackQuery):
        await query.message.edit_text("⚙ **Admin Settings**", reply_markup=settings_menu_kb())

    @app.on_callback_query(filters.regex(r"^adm:verify$"))
    @safe_handler
    @admin_only
    async def verify_settings_cb(client: Client, query: CallbackQuery):
        await query.message.edit_text(await verify_settings_text())

    @app.on_callback_query(filters.regex(r"^adm:shortener$"))
    @safe_handler
    @admin_only
    async def shortener_settings_cb(client: Client, query: CallbackQuery):
        await query.message.edit_text(await shortener_settings_text())

    @app.on_callback_query(filters.regex(r"^adm:forcesub$"))
    @safe_handler
    @admin_only
    async def force_sub_settings_cb(client: Client, query: CallbackQuery):
        await query.message.edit_text(await force_sub_settings_text())

    @app.on_callback_query(filters.regex(r"^adm:welcome$"))
    @safe_handler
    @admin_only
    async def welcome_settings_cb(client: Client, query: CallbackQuery):
        await query.message.edit_text(await welcome_settings_text())

    # ── verification setters ──────────────────────────────────────────
    @app.on_message(filters.command("setverifymin"))
    @safe_handler
    @admin_only
    async def set_verify_min_cmd(client: Client, message: Message):
        if len(message.command) < 2 or not message.command[1].isdigit():
            await message.reply_text("Usage: `/setverifymin <minutes>`")
            return
        await settings_db.set_setting("verify_min_minutes", int(message.command[1]))
        await message.reply_text("✅ Updated.")

    @app.on_message(filters.command("setverifymax"))
    @safe_handler
    @admin_only
    async def set_verify_max_cmd(client: Client, message: Message):
        if len(message.command) < 2 or not message.command[1].isdigit():
            await message.reply_text("Usage: `/setverifymax <minutes>`")
            return
        await settings_db.set_setting("verify_max_minutes", int(message.command[1]))
        await message.reply_text("✅ Updated.")

    @app.on_message(filters.command("setverifyvalidity"))
    @safe_handler
    @admin_only
    async def set_verify_validity_cmd(client: Client, message: Message):
        if len(message.command) < 2 or not message.command[1].lstrip("-").isdigit():
            await message.reply_text("Usage: `/setverifyvalidity <hours>` (0 = unlimited)")
            return
        await settings_db.set_setting("verify_validity_hours", int(message.command[1]))
        await message.reply_text("✅ Updated.")

    # ── shortener setters ────────────────────────────────────────────
    @app.on_message(filters.command("setshortenerapi"))
    @safe_handler
    @admin_only
    async def set_shortener_api_cmd(client: Client, message: Message):
        if len(message.command) < 2:
            await message.reply_text("Usage: `/setshortenerapi <api_key>`")
            return
        await settings_db.set_setting("shortener_api", message.command[1])
        await settings_db.set_setting("shortener_enabled", True)
        await message.reply_text("✅ Shortener API key updated.")

    @app.on_message(filters.command("setshortenerdomain"))
    @safe_handler
    @admin_only
    async def set_shortener_domain_cmd(client: Client, message: Message):
        if len(message.command) < 2:
            await message.reply_text("Usage: `/setshortenerdomain <domain>`")
            return
        await settings_db.set_setting("shortener_domain", message.command[1])
        await message.reply_text("✅ Shortener domain updated.")

    @app.on_message(filters.command("toggleshortener"))
    @safe_handler
    @admin_only
    async def toggle_shortener_cmd(client: Client, message: Message):
        new_value = await settings_db.toggle_setting("shortener_enabled")
        await message.reply_text(f"🔗 Shortener verification is now {'ON' if new_value else 'OFF'}.")

    # ── force sub setters ─────────────────────────────────────────────
    @app.on_message(filters.command("addforcesub"))
    @safe_handler
    @admin_only
    async def add_force_sub_cmd(client: Client, message: Message):
        if len(message.command) < 2:
            await message.reply_text("Usage: `/addforcesub <@channel_username>`")
            return
        await settings_db.add_force_sub_channel(message.command[1])
        await settings_db.set_setting("force_sub_enabled", True)
        await message.reply_text("✅ Force-sub channel added.")

    @app.on_message(filters.command("removeforcesub"))
    @safe_handler
    @admin_only
    async def remove_force_sub_cmd(client: Client, message: Message):
        if len(message.command) < 2:
            await message.reply_text("Usage: `/removeforcesub <@channel_username>`")
            return
        await settings_db.remove_force_sub_channel(message.command[1])
        await message.reply_text("✅ Force-sub channel removed.")

    @app.on_message(filters.command("toggleforcesub"))
    @safe_handler
    @admin_only
    async def toggle_force_sub_cmd(client: Client, message: Message):
        new_value = await settings_db.toggle_setting("force_sub_enabled")
        await message.reply_text(f"📢 Force-subscribe is now {'ON' if new_value else 'OFF'}.")

    # ── welcome setters ──────────────────────────────────────────────
    @app.on_message(filters.command("setwelcometext"))
    @safe_handler
    @admin_only
    async def set_welcome_text_cmd(client: Client, message: Message):
        text = message.text.split(maxsplit=1)
        if len(text) < 2:
            await message.reply_text("Usage: `/setwelcometext <text>` — supports {first_name} {username} {id} {bot_name}")
            return
        await settings_db.set_setting("welcome_text", text[1])
        await message.reply_text("✅ Welcome text updated.")

    @app.on_message(filters.command("setwelcomeimage") & filters.reply)
    @safe_handler
    @admin_only
    async def set_welcome_image_cmd(client: Client, message: Message):
        if not message.reply_to_message or not message.reply_to_message.photo:
            await message.reply_text("Reply to a photo with `/setwelcomeimage`.")
            return
        file_id = message.reply_to_message.photo.file_id
        await settings_db.set_setting("welcome_image", file_id)
        await message.reply_text("✅ Welcome image updated.")

    @app.on_message(filters.command("setwelcomesticker") & filters.reply)
    @safe_handler
    @admin_only
    async def set_welcome_sticker_cmd(client: Client, message: Message):
        if not message.reply_to_message or not message.reply_to_message.sticker:
            await message.reply_text("Reply to a sticker with `/setwelcomesticker`.")
            return
        file_id = message.reply_to_message.sticker.file_id
        await settings_db.set_setting("welcome_sticker", file_id)
        await message.reply_text("✅ Welcome sticker updated.")
