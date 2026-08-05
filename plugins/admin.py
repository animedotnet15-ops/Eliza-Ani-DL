import asyncio
import io
import json
import os
import sys

from pyrogram import Client, filters
from pyrogram.types import Message

import config.settings as config
import database.admins as admins_db
import database.channels as channels_db
import database.users as users_db
import database.media as media_db
import database.stats as stats_db
from database.settings_db import get_settings, set_setting
from middlewares.guards import admin_only
from handlers.error_handler import safe_handler


def register(app: Client):

    @app.on_message(filters.command("restart"))
    @safe_handler
    @admin_only
    async def restart_cmd(client: Client, message: Message):
        await message.reply_text("🔄 Restarting...")
        if config.LOG_CHANNEL:
            await client.send_message(config.LOG_CHANNEL, f"🔄 Bot restarted by `{message.from_user.id}`")
        os.execv(sys.executable, [sys.executable] + sys.argv)

    @app.on_message(filters.command("shutdown"))
    @safe_handler
    @admin_only
    async def shutdown_cmd(client: Client, message: Message):
        await message.reply_text("⏻ Shutting down...")
        if config.LOG_CHANNEL:
            await client.send_message(config.LOG_CHANNEL, f"⏻ Bot shut down by `{message.from_user.id}`")
        await client.stop()
        sys.exit(0)

    @app.on_message(filters.command("broadcast"))
    @safe_handler
    @admin_only
    async def broadcast_cmd(client: Client, message: Message):
        text = " ".join(message.command[1:]).strip()
        source = message.reply_to_message
        if not text and not source:
            await message.reply_text("Usage: `/broadcast <message>` (or reply to a message with /broadcast)")
            return

        user_ids = await users_db.all_user_ids()
        status = await message.reply_text(f"📣 Broadcasting to {len(user_ids)} users...")

        sent, failed = 0, 0
        for uid in user_ids:
            try:
                if source:
                    await source.copy(uid)
                else:
                    await client.send_message(uid, text)
                sent += 1
            except Exception:
                failed += 1
            await asyncio.sleep(0.05)

        await status.edit_text(f"✅ Broadcast done. Sent: {sent}, Failed: {failed}.")
        if config.LOG_CHANNEL:
            await client.send_message(config.LOG_CHANNEL, f"📣 Broadcast by `{message.from_user.id}` — sent {sent}, failed {failed}")

    @app.on_message(filters.command("stats"))
    @safe_handler
    @admin_only
    async def stats_cmd(client: Client, message: Message):
        total_users = await users_db.total_users()
        total_anime = await media_db.total_anime()
        total_channels = len(await channels_db.list_channels())
        daily = await stats_db.daily_stats()

        await message.reply_text(
            "📊 **Bot Statistics**\n\n"
            f"👤 Total users: `{total_users}`\n"
            f"🎬 Indexed anime: `{total_anime}`\n"
            f"📡 Source channels: `{total_channels}`\n\n"
            "**Last 24 hours:**\n"
            f"🔍 Searches: `{daily['searches_24h']}`\n"
            f"⬇ Downloads: `{daily['downloads_24h']}`\n"
            f"▶ Streams: `{daily['streams_24h']}`\n"
            f"✅ Verifications: `{daily['verifications_24h']}`\n"
            f"🚨 Bypass attempts: `{daily['bypass_attempts_24h']}`\n"
            f"🆕 New users: `{daily['new_users_24h']}`\n"
        )

    @app.on_message(filters.command("maintenance"))
    @safe_handler
    @admin_only
    async def maintenance_cmd(client: Client, message: Message):
        settings = await get_settings()
        new_value = not settings.get("maintenance_mode", False)
        await set_setting("maintenance_mode", new_value)
        await message.reply_text(f"🛠 Maintenance mode is now {'ON' if new_value else 'OFF'}.")

    @app.on_message(filters.command("addadmin"))
    @safe_handler
    @admin_only
    async def add_admin_cmd(client: Client, message: Message):
        if len(message.command) < 2:
            await message.reply_text("Usage: `/addadmin <user_id>`")
            return
        uid = int(message.command[1])
        await admins_db.add_admin(uid)
        await message.reply_text(f"✅ `{uid}` added as admin.")

    @app.on_message(filters.command("removeadmin"))
    @safe_handler
    @admin_only
    async def remove_admin_cmd(client: Client, message: Message):
        if len(message.command) < 2:
            await message.reply_text("Usage: `/removeadmin <user_id>`")
            return
        uid = int(message.command[1])
        await admins_db.remove_admin(uid)
        await message.reply_text(f"✅ `{uid}` removed from admins.")

    @app.on_message(filters.command("ban"))
    @safe_handler
    @admin_only
    async def ban_cmd(client: Client, message: Message):
        if len(message.command) < 2:
            await message.reply_text("Usage: `/ban <user_id>`")
            return
        uid = int(message.command[1])
        await users_db.ban_user(uid)
        await message.reply_text(f"⛔ `{uid}` banned.")

    @app.on_message(filters.command("unban"))
    @safe_handler
    @admin_only
    async def unban_cmd(client: Client, message: Message):
        if len(message.command) < 2:
            await message.reply_text("Usage: `/unban <user_id>`")
            return
        uid = int(message.command[1])
        await users_db.unban_user(uid)
        await message.reply_text(f"✅ `{uid}` unbanned.")

    @app.on_message(filters.command("addchannel"))
    @safe_handler
    @admin_only
    async def add_channel_cmd(client: Client, message: Message):
        if len(message.command) < 2:
            await message.reply_text("Usage: `/addchannel <channel_id>` (bot must be admin there)")
            return
        cid = int(message.command[1])
        try:
            chat = await client.get_chat(cid)
            title = chat.title
        except Exception as e:
            await message.reply_text(f"❌ Couldn't access that channel: {e}")
            return
        await channels_db.add_channel(cid, title, added_by=message.from_user.id)
        await message.reply_text(f"✅ Added channel **{title}**. Run `/reindex` to scan it.")

    @app.on_message(filters.command("removechannel"))
    @safe_handler
    @admin_only
    async def remove_channel_cmd(client: Client, message: Message):
        if len(message.command) < 2:
            await message.reply_text("Usage: `/removechannel <channel_id>`")
            return
        cid = int(message.command[1])
        ok = await channels_db.remove_channel(cid)
        await message.reply_text("✅ Channel removed." if ok else "❌ Channel not found.")

    @app.on_message(filters.command("channels"))
    @safe_handler
    @admin_only
    async def list_channels_cmd(client: Client, message: Message):
        chans = await channels_db.list_channels()
        if not chans:
            await message.reply_text("No channels configured yet.")
            return
        lines = [f"• {c.get('title', 'Unknown')} — `{c['channel_id']}` {'🟢' if c.get('enabled') else '🔴'}" for c in chans]
        await message.reply_text("📡 **Source Channels:**\n\n" + "\n".join(lines))

    @app.on_message(filters.command("reindex"))
    @safe_handler
    @admin_only
    async def reindex_cmd(client: Client, message: Message):
        from indexer.indexer import full_scan_all_channels
        status = await message.reply_text("🗂 Running full index scan across all channels...")
        await full_scan_all_channels(client)
        await status.edit_text("✅ Indexing complete.")

    @app.on_message(filters.command("backup"))
    @safe_handler
    @admin_only
    async def backup_cmd(client: Client, message: Message):
        status = await message.reply_text("📦 Building backup...")
        data = {
            "users_count": await users_db.total_users(),
            "anime_count": await media_db.total_anime(),
            "channels": await channels_db.list_channels(),
            "settings": await get_settings(),
        }
        buf = io.BytesIO(json.dumps(data, default=str, indent=2).encode())
        buf.name = "eliza_backup.json"
        await message.reply_document(buf, caption="📦 Configuration backup (channels + settings; media content lives in Telegram/MongoDB directly).")
        await status.delete()

    @app.on_message(filters.command("restore") & filters.reply)
    @safe_handler
    @admin_only
    async def restore_cmd(client: Client, message: Message):
        if not message.reply_to_message or not message.reply_to_message.document:
            await message.reply_text("Reply to a backup JSON file with `/restore`.")
            return
        path = await message.reply_to_message.download()
        try:
            with open(path) as f:
                data = json.load(f)
            for chan in data.get("channels", []):
                await channels_db.add_channel(chan["channel_id"], chan.get("title", ""))
            for key, value in data.get("settings", {}).items():
                if key != "_id":
                    await set_setting(key, value)
            await message.reply_text("✅ Restore complete (channels + settings).")
        except Exception as e:
            await message.reply_text(f"❌ Restore failed: {e}")
        finally:
            try:
                os.remove(path)
            except OSError:
                pass
