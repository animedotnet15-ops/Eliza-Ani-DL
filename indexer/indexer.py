import asyncio

from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from pyrogram.handlers import MessageHandler, DeletedMessagesHandler, EditedMessageHandler

import database.channels as channels_db
import database.media as media_db
from core.logger import get_logger
from indexer.parser import parse, season_key, episode_key

LOGGER = get_logger("indexer")

MEDIA_FILTER_TYPES = ("video", "document")


def _get_media_object(message):
    return message.video or message.document


async def _index_message(message):
    media_obj = _get_media_object(message)
    if not media_obj:
        return

    file_name = getattr(media_obj, "file_name", None) or ""
    caption = message.caption or ""
    if not file_name and not caption:
        return

    if await media_db.is_indexed(message.chat.id, message.id):
        return  # already indexed, dedupe

    parsed = parse(file_name, caption)
    thumb = ""
    if getattr(media_obj, "thumbs", None):
        thumb = media_obj.thumbs[0].file_id

    await media_db.add_file_entry(
        title=parsed.title,
        season_key=season_key(parsed.season),
        episode_key=episode_key(parsed.episode),
        quality=parsed.quality,
        audio=parsed.audio,
        channel_id=message.chat.id,
        message_id=message.id,
        file_id=media_obj.file_id,
        file_name=file_name or f"{parsed.title}.mkv",
        file_size=getattr(media_obj, "file_size", 0),
        thumbnail=thumb,
        caption=caption,
    )
    LOGGER.info(f"Indexed: {parsed.title} {season_key(parsed.season)}{episode_key(parsed.episode)} [{parsed.quality}] {parsed.audio}")


async def backfill_channel(client: Client, channel_id: int, batch_size: int = 200):
    """One-off full scan of a channel's history (used when a channel is
    first added, and periodically to catch anything missed)."""
    last_id = await channels_db.get_last_indexed_id(channel_id)
    newest_seen = last_id
    count = 0

    try:
        async for message in client.get_chat_history(channel_id, limit=0):
            if message.id <= last_id:
                break
            if message.id > newest_seen:
                newest_seen = message.id
            if message.media:
                await _index_message(message)
                count += 1
            if count % batch_size == 0 and count > 0:
                await asyncio.sleep(1)  # be gentle with flood limits
    except FloodWait as e:
        LOGGER.warning(f"FloodWait during backfill of {channel_id}: sleeping {e.value}s")
        await asyncio.sleep(e.value)
    except Exception as e:
        LOGGER.error(f"Backfill error for channel {channel_id}: {e}")

    if newest_seen > last_id:
        await channels_db.set_last_indexed_id(channel_id, newest_seen)

    LOGGER.info(f"Backfilled channel {channel_id}: {count} new files indexed.")
    return count


def register_live_handlers(client: Client):
    """Live indexing: new uploads, edits, and deletes in configured channels."""

    async def on_new_message(_, message):
        channels = await channels_db.list_channels(enabled_only=True)
        allowed_ids = {c["channel_id"] for c in channels}
        if message.chat.id not in allowed_ids or not message.media:
            return
        await _index_message(message)
        await channels_db.set_last_indexed_id(message.chat.id, message.id)

    async def on_edited_message(_, message):
        channels = await channels_db.list_channels(enabled_only=True)
        allowed_ids = {c["channel_id"] for c in channels}
        if message.chat.id not in allowed_ids:
            return
        # Re-index: remove the old entry (in case metadata changed) then re-add
        await media_db.remove_file_entry(message.chat.id, message.id)
        if message.media:
            await _index_message(message)

    async def on_deleted_messages(_, messages):
        for message in messages:
            await media_db.remove_file_entry(message.chat.id, message.id)

    client.add_handler(MessageHandler(on_new_message, filters.channel))
    client.add_handler(EditedMessageHandler(on_edited_message, filters.channel))
    client.add_handler(DeletedMessagesHandler(on_deleted_messages, filters.channel))
    LOGGER.info("Live indexer handlers registered.")


async def full_scan_all_channels(client: Client):
    channels = await channels_db.list_channels(enabled_only=True)
    for chan in channels:
        await backfill_channel(client, chan["channel_id"])
        
