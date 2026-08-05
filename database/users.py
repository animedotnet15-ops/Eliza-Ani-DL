from datetime import datetime, timedelta
from typing import Optional

from database.connection import db

users = db["users"]


async def ensure_indexes():
    await users.create_index("user_id", unique=True)
    await users.create_index("referral_code", unique=True, sparse=True)


async def add_user(user_id: int, first_name: str = "", username: str = "", referred_by: Optional[int] = None):
    existing = await users.find_one({"user_id": user_id})
    if existing:
        await users.update_one(
            {"user_id": user_id}, {"$set": {"first_name": first_name, "username": username}}
        )
        return existing

    doc = {
        "user_id": user_id,
        "first_name": first_name,
        "username": username,
        "language": None,
        "joined_on": datetime.utcnow(),
        "is_premium": False,
        "premium_until": None,
        "referral_code": f"ref{user_id}",
        "referred_by": referred_by,
        "referral_count": 0,
        "favorites": [],
        "history": [],
        "continue_watching": [],
        "banned": False,
        "verified_until": None,
    }
    await users.insert_one(doc)

    if referred_by and referred_by != user_id:
        await users.update_one({"user_id": referred_by}, {"$inc": {"referral_count": 1}})

    return doc


async def get_user(user_id: int) -> Optional[dict]:
    return await users.find_one({"user_id": user_id})


async def set_language(user_id: int, lang_code: str):
    await users.update_one({"user_id": user_id}, {"$set": {"language": lang_code}})


async def get_language(user_id: int, default: str) -> str:
    user = await get_user(user_id)
    return user["language"] if user and user.get("language") else default


async def total_users() -> int:
    return await users.count_documents({})


async def all_user_ids() -> list:
    return [doc["user_id"] async for doc in users.find({}, {"user_id": 1})]


# ── ban / maintenance ────────────────────────────────────────────────────
async def ban_user(user_id: int):
    await users.update_one({"user_id": user_id}, {"$set": {"banned": True}})


async def unban_user(user_id: int):
    await users.update_one({"user_id": user_id}, {"$set": {"banned": False}})


async def is_banned(user_id: int) -> bool:
    user = await get_user(user_id)
    return bool(user and user.get("banned"))


# ── favorites ────────────────────────────────────────────────────────────
async def add_favorite(user_id: int, anime_id: str):
    await users.update_one({"user_id": user_id}, {"$addToSet": {"favorites": anime_id}})


async def remove_favorite(user_id: int, anime_id: str):
    await users.update_one({"user_id": user_id}, {"$pull": {"favorites": anime_id}})


async def get_favorites(user_id: int) -> list:
    user = await get_user(user_id)
    return user.get("favorites", []) if user else []


async def is_favorite(user_id: int, anime_id: str) -> bool:
    return anime_id in await get_favorites(user_id)


# ── history / continue watching ─────────────────────────────────────────
async def push_history(user_id: int, entry: dict, max_items: int = 50):
    entry = {**entry, "viewed_on": datetime.utcnow()}
    await users.update_one(
        {"user_id": user_id},
        {"$push": {"history": {"$each": [entry], "$position": 0, "$slice": max_items}}},
    )


async def get_history(user_id: int, limit: int = 20) -> list:
    user = await get_user(user_id)
    return (user.get("history", []) if user else [])[:limit]


async def update_continue_watching(user_id: int, anime_id: str, season: int, episode: int):
    entry = {"anime_id": anime_id, "season": season, "episode": episode, "updated_on": datetime.utcnow()}
    await users.update_one({"user_id": user_id}, {"$pull": {"continue_watching": {"anime_id": anime_id}}})
    await users.update_one(
        {"user_id": user_id},
        {"$push": {"continue_watching": {"$each": [entry], "$position": 0, "$slice": 25}}},
    )


async def get_continue_watching(user_id: int, limit: int = 10) -> list:
    user = await get_user(user_id)
    return (user.get("continue_watching", []) if user else [])[:limit]


# ── verification (link shortener) ───────────────────────────────────────
async def set_verified(user_id: int, validity_hours: int):
    until = None if validity_hours <= 0 else datetime.utcnow() + timedelta(hours=validity_hours)
    await users.update_one({"user_id": user_id}, {"$set": {"verified_until": until}})


async def is_verified(user_id: int) -> bool:
    user = await get_user(user_id)
    if not user or not user.get("verified_until"):
        return False
    if user["verified_until"] == "unlimited":
        return True
    return user["verified_until"] > datetime.utcnow()


async def set_unlimited_verified(user_id: int):
    await users.update_one({"user_id": user_id}, {"$set": {"verified_until": "unlimited"}})


# ── premium ──────────────────────────────────────────────────────────────
async def set_premium(user_id: int, until: Optional[datetime] = None):
    await users.update_one(
        {"user_id": user_id}, {"$set": {"is_premium": True, "premium_until": until}}
    )


async def remove_premium(user_id: int):
    await users.update_one(
        {"user_id": user_id}, {"$set": {"is_premium": False, "premium_until": None}}
    )


async def is_premium(user_id: int) -> bool:
    user = await get_user(user_id)
    if not user or not user.get("is_premium"):
        return False
    if user.get("premium_until") and user["premium_until"] < datetime.utcnow():
        await remove_premium(user_id)
        return False
    return True
