from datetime import datetime
from typing import Optional

from rapidfuzz import fuzz, process

from database.connection import db

# One document per anime title. Seasons/episodes/quality/audio variants are
# nested inside, since that's the natural shape for the season -> episode ->
# quality -> audio -> download navigation flow.
media = db["media"]

# One row per indexed Telegram message, used purely for de-duplication and
# edit/delete detection by the indexer - never read by user-facing plugins.
indexed_messages = db["indexed_messages"]


async def ensure_indexes():
    await media.create_index("anime_id", unique=True)
    await media.create_index("title")
    await media.create_index("genres")
    await indexed_messages.create_index([("channel_id", 1), ("message_id", 1)], unique=True)


def slugify(title: str) -> str:
    return "-".join(title.lower().split())


async def get_or_create_anime(title: str, year: Optional[int] = None, poster: str = "", description: str = "", genres: Optional[list] = None) -> dict:
    anime_id = slugify(title)
    existing = await media.find_one({"anime_id": anime_id})
    if existing:
        return existing

    doc = {
        "anime_id": anime_id,
        "title": title,
        "year": year,
        "poster": poster,
        "description": description,
        "genres": genres or [],
        "status": "ongoing",
        "seasons": {},  # {"S01": {"episodes": {"E01": {"qualities": {"480p": {"audios": {"Tamil": {...file info...}}}}}}}}
        "views": 0,
        "created_on": datetime.utcnow(),
        "updated_on": datetime.utcnow(),
    }
    await media.insert_one(doc)
    return doc


async def add_file_entry(
    title: str,
    season_key: str,
    episode_key: str,
    quality: str,
    audio: str,
    channel_id: int,
    message_id: int,
    file_id: str,
    file_name: str,
    file_size: int,
    thumbnail: str = "",
    caption: str = "",
    year: Optional[int] = None,
):
    """Called by the indexer for every detected episode file."""
    await get_or_create_anime(title, year=year)
    anime_id = slugify(title)

    path = (
        f"seasons.{season_key}.episodes.{episode_key}."
        f"qualities.{quality}.audios.{audio}"
    )
    file_doc = {
        "channel_id": channel_id,
        "message_id": message_id,
        "file_id": file_id,
        "file_name": file_name,
        "file_size": file_size,
        "thumbnail": thumbnail,
        "caption": caption,
        "indexed_on": datetime.utcnow(),
    }
    await media.update_one(
        {"anime_id": anime_id},
        {"$set": {path: file_doc, "updated_on": datetime.utcnow()}},
    )

    await indexed_messages.update_one(
        {"channel_id": channel_id, "message_id": message_id},
        {"$set": {"anime_id": anime_id, "path": path, "file_name": file_name}},
        upsert=True,
    )


async def remove_file_entry(channel_id: int, message_id: int):
    """Called by the indexer when a source message is deleted."""
    record = await indexed_messages.find_one({"channel_id": channel_id, "message_id": message_id})
    if not record:
        return
    await media.update_one({"anime_id": record["anime_id"]}, {"$unset": {record["path"]: ""}})
    await indexed_messages.delete_one({"channel_id": channel_id, "message_id": message_id})


async def is_indexed(channel_id: int, message_id: int) -> bool:
    return await indexed_messages.find_one({"channel_id": channel_id, "message_id": message_id}) is not None


async def get_anime(anime_id: str) -> Optional[dict]:
    return await media.find_one({"anime_id": anime_id})


async def increment_views(anime_id: str):
    await media.update_one({"anime_id": anime_id}, {"$inc": {"views": 1}})


async def search(query: str, limit: int = 8) -> list:
    """Fuzzy search over anime titles."""
    all_docs = [doc async for doc in media.find({}, {"anime_id": 1, "title": 1, "poster": 1, "year": 1})]
    if not all_docs:
        return []
    titles = {doc["title"]: doc for doc in all_docs}
    matches = process.extract(query, titles.keys(), scorer=fuzz.WRatio, limit=limit)
    return [titles[title] for title, score, _ in matches if score > 45]


async def trending(limit: int = 10) -> list:
    return [doc async for doc in media.find({}).sort("views", -1).limit(limit)]


async def latest(limit: int = 10) -> list:
    return [doc async for doc in media.find({}).sort("created_on", -1).limit(limit)]


async def random_anime() -> Optional[dict]:
    cursor = media.aggregate([{"$sample": {"size": 1}}])
    async for doc in cursor:
        return doc
    return None


async def recommend_by_genre(genres: list, exclude_id: str, limit: int = 6) -> list:
    if not genres:
        return []
    cursor = media.find({"genres": {"$in": genres}, "anime_id": {"$ne": exclude_id}}).sort("views", -1).limit(limit)
    return [doc async for doc in cursor]


async def total_anime() -> int:
    return await media.count_documents({})
