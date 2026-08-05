from datetime import datetime

from database.connection import db

channels = db["channels"]


async def ensure_indexes():
    await channels.create_index("channel_id", unique=True)


async def add_channel(channel_id: int, title: str = "", added_by: int = 0):
    await channels.update_one(
        {"channel_id": channel_id},
        {"$set": {"title": title, "enabled": True}, "$setOnInsert": {"added_on": datetime.utcnow(), "added_by": added_by}},
        upsert=True,
    )


async def remove_channel(channel_id: int) -> bool:
    result = await channels.delete_one({"channel_id": channel_id})
    return result.deleted_count > 0


async def list_channels(enabled_only: bool = False) -> list:
    query = {"enabled": True} if enabled_only else {}
    return [doc async for doc in channels.find(query)]


async def set_last_indexed_id(channel_id: int, message_id: int):
    await channels.update_one({"channel_id": channel_id}, {"$set": {"last_indexed_id": message_id}})


async def get_last_indexed_id(channel_id: int) -> int:
    doc = await channels.find_one({"channel_id": channel_id})
    return doc.get("last_indexed_id", 0) if doc else 0
