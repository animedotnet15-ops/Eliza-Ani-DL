import secrets
from datetime import datetime, timedelta

import aiohttp

from database.connection import db
from database.settings_db import get_settings
from core.logger import get_logger

LOGGER = get_logger("services.shortener")

verifications = db["verifications"]


async def ensure_indexes():
    await verifications.create_index("token", unique=True)
    await verifications.create_index("issued_on", expireAfterSeconds=60 * 60 * 24 * 3)  # auto-cleanup stale tokens


async def shorten_url(long_url: str) -> str:
    settings = await get_settings()
    api_key = settings.get("shortener_api")
    domain = settings.get("shortener_domain")

    if not api_key or not domain:
        return long_url  # shortener not configured - fall back to the raw link

    api_url = f"https://{domain}/api"
    params = {"api": api_key, "url": long_url}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json(content_type=None)
                shortened = data.get("shortenedUrl") or data.get("shortened_url") or data.get("short_url")
                return shortened or long_url
    except Exception as e:
        LOGGER.warning(f"Shortener API failed, falling back to raw link: {e}")
        return long_url


async def create_verification_token(user_id: int) -> str:
    token = secrets.token_urlsafe(12)
    await verifications.update_one(
        {"user_id": user_id},
        {"$set": {"token": token, "user_id": user_id, "issued_on": datetime.utcnow(), "used": False}},
        upsert=True,
    )
    return token


async def build_verification_link(bot_username: str, user_id: int) -> tuple:
    """Returns (shortened_link, tutorial_note)."""
    token = await create_verification_token(user_id)
    deep_link = f"https://t.me/{bot_username}?start=verify_{token}"
    short_link = await shorten_url(deep_link)
    return short_link, token


class VerificationResult:
    SUCCESS = "success"
    TOO_FAST = "too_fast"
    EXPIRED = "expired"
    INVALID = "invalid"


async def check_verification(user_id: int, token: str) -> str:
    record = await verifications.find_one({"user_id": user_id, "token": token})
    if not record:
        return VerificationResult.INVALID
    if record.get("used"):
        return VerificationResult.INVALID

    settings = await get_settings()
    min_minutes = settings.get("verify_min_minutes", 2)
    max_minutes = settings.get("verify_max_minutes", 5)

    elapsed = datetime.utcnow() - record["issued_on"]
    elapsed_minutes = elapsed.total_seconds() / 60

    await verifications.update_one({"_id": record["_id"]}, {"$set": {"used": True}})

    if elapsed_minutes < min_minutes:
        return VerificationResult.TOO_FAST
    if elapsed_minutes > max_minutes:
        return VerificationResult.EXPIRED
    return VerificationResult.SUCCESS
