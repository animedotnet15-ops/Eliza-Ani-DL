import time
from collections import defaultdict
from functools import wraps

from pyrogram.types import Message, CallbackQuery

import database.admins as admins_db
import database.users as users_db
from database.settings_db import get_settings
from languages.strings import t

_flood_tracker = defaultdict(list)
FLOOD_WINDOW_SECONDS = 10
FLOOD_MAX_ACTIONS = 10


def _user_and_reply(update):
    if isinstance(update, CallbackQuery):
        return update.from_user, update.answer
    return update.from_user, update.reply_text


def admin_only(func):
    @wraps(func)
    async def wrapper(client, update, *args, **kwargs):
        user, reply = _user_and_reply(update)
        if not await admins_db.is_admin(user.id):
            await reply("⛔ This command is for bot admins/owner only.")
            return
        return await func(client, update, *args, **kwargs)
    return wrapper


def not_banned(func):
    @wraps(func)
    async def wrapper(client, update, *args, **kwargs):
        user, reply = _user_and_reply(update)
        if await users_db.is_banned(user.id):
            lang = await users_db.get_language(user.id, "en")
            await reply(t("banned", lang))
            return
        return await func(client, update, *args, **kwargs)
    return wrapper


def maintenance_gate(func):
    @wraps(func)
    async def wrapper(client, update, *args, **kwargs):
        user, reply = _user_and_reply(update)
        if await admins_db.is_admin(user.id):
            return await func(client, update, *args, **kwargs)  # admins bypass maintenance
        settings = await get_settings()
        if settings.get("maintenance_mode"):
            lang = await users_db.get_language(user.id, "en")
            await reply(t("maintenance", lang))
            return
        return await func(client, update, *args, **kwargs)
    return wrapper


def flood_protect(func):
    @wraps(func)
    async def wrapper(client, message: Message, *args, **kwargs):
        uid = message.from_user.id
        now = time.time()
        recent = [ts for ts in _flood_tracker[uid] if now - ts < FLOOD_WINDOW_SECONDS]
        recent.append(now)
        _flood_tracker[uid] = recent
        if len(recent) > FLOOD_MAX_ACTIONS:
            return  # silently drop - avoid adding to the flood with a warning reply
        return await func(client, message, *args, **kwargs)
    return wrapper
