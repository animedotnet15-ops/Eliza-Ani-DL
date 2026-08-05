from pyrogram import Client
from pyrogram.errors import UserNotParticipant

from database.settings_db import get_settings


async def get_unjoined_channels(client: Client, user_id: int) -> list:
    settings = await get_settings()
    if not settings.get("force_sub_enabled"):
        return []

    unjoined = []
    for channel in settings.get("force_sub_channels", []):
        try:
            await client.get_chat_member(channel, user_id)
        except UserNotParticipant:
            unjoined.append(channel)
        except Exception:
            continue  # channel unreachable/invalid - don't block users over a misconfiguration
    return unjoined
