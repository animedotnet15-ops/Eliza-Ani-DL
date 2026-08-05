import config.settings as config
from database.connection import db

settings_col = db["settings"]

DEFAULTS = {
    "_id": "config",
    "maintenance_mode": False,
    "welcome_text": (
        "👋 Hey {first_name}!\n\n"
        "✨ Welcome to **{bot_name}** — search any anime, pick a season, "
        "episode, quality & audio, and stream or download instantly."
    ),
    "welcome_image": "",
    "welcome_sticker": "",
    "shortener_api": config.SHORTENER_API,
    "shortener_domain": config.SHORTENER_DOMAIN,
    "verify_min_minutes": config.VERIFY_MIN_MINUTES,
    "verify_max_minutes": config.VERIFY_MAX_MINUTES,
    "verify_validity_hours": config.VERIFY_VALIDITY_HOURS,
    "shortener_enabled": bool(config.SHORTENER_API),
    "force_sub_channels": config.FORCE_SUB_CHANNELS,
    "force_sub_enabled": bool(config.FORCE_SUB_CHANNELS),
}


async def get_settings() -> dict:
    doc = await settings_col.find_one({"_id": "config"})
    if not doc:
        await settings_col.insert_one(DEFAULTS)
        return dict(DEFAULTS)
    return {**DEFAULTS, **doc}


async def set_setting(key: str, value):
    await settings_col.update_one({"_id": "config"}, {"$set": {key: value}}, upsert=True)


async def toggle_setting(key: str) -> bool:
    current = await get_settings()
    new_value = not current.get(key, False)
    await set_setting(key, new_value)
    return new_value


async def add_force_sub_channel(channel: str):
    await settings_col.update_one({"_id": "config"}, {"$addToSet": {"force_sub_channels": channel}}, upsert=True)


async def remove_force_sub_channel(channel: str):
    await settings_col.update_one({"_id": "config"}, {"$pull": {"force_sub_channels": channel}})
