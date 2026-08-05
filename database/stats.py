from datetime import datetime, timedelta

from database.connection import db

logs = db["logs"]


async def ensure_indexes():
    await logs.create_index("on")
    await logs.create_index("event_type")


async def log_event(event_type: str, data: dict = None):
    await logs.insert_one({"event_type": event_type, "data": data or {}, "on": datetime.utcnow()})


async def count_event(event_type: str, since: datetime = None) -> int:
    query = {"event_type": event_type}
    if since:
        query["on"] = {"$gte": since}
    return await logs.count_documents(query)


async def daily_stats() -> dict:
    since = datetime.utcnow() - timedelta(days=1)
    return {
        "searches_24h": await count_event("search", since),
        "downloads_24h": await count_event("download", since),
        "streams_24h": await count_event("stream", since),
        "verifications_24h": await count_event("verify_success", since),
        "bypass_attempts_24h": await count_event("bypass_detected", since),
        "new_users_24h": await count_event("new_user", since),
    }
