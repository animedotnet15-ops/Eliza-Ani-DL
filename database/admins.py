import config.settings as config
from database.connection import db

admins_col = db["admins"]


async def add_admin(user_id: int):
    await admins_col.update_one({"user_id": user_id}, {"$set": {"user_id": user_id}}, upsert=True)


async def remove_admin(user_id: int):
    await admins_col.delete_one({"user_id": user_id})


async def list_admins() -> list:
    return [doc["user_id"] async for doc in admins_col.find({})]


async def is_admin(user_id: int) -> bool:
    if user_id in config.ADMINS:
        return True
    return await admins_col.find_one({"user_id": user_id}) is not None
