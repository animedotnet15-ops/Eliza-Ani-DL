import aiohttp

import config.settings as config
import database.media as media_db
from core.logger import get_logger

LOGGER = get_logger("services.recommend")


async def recommend_for_user(favorites: list, history: list, limit: int = 6) -> list:
    """Always-available, non-AI recommender: pools genres from the user's
    favorites/history and finds other high-view titles sharing them."""
    genres = set()
    seen_ids = set()
    for anime_id in (favorites or [])[:10] + [h.get("anime_id") for h in (history or [])[:10]]:
        if not anime_id or anime_id in seen_ids:
            continue
        seen_ids.add(anime_id)
        doc = await media_db.get_anime(anime_id)
        if doc:
            genres.update(doc.get("genres", []))

    if not genres:
        return await media_db.trending(limit)

    exclude = list(seen_ids)[0] if seen_ids else ""
    return await media_db.recommend_by_genre(list(genres), exclude_id=exclude, limit=limit)


async def ai_suggest(query_or_title: str) -> str:
    """Optional: if GEMINI_API_KEY is set, ask it for a short list of
    similar anime to suggest alongside search results. Falls back to a
    plain message if no key is configured, rather than failing silently."""
    if not config.GEMINI_API_KEY:
        return ""

    prompt = (
        f"In one short line, suggest 3 anime similar to \"{query_or_title}\" "
        "as a comma-separated list of titles only, nothing else."
    )
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-1.5-flash:generateContent?key={config.GEMINI_API_KEY}"
    )
    payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                data = await resp.json()
                return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        LOGGER.warning(f"AI suggestion call failed: {e}")
        return ""
