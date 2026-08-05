import database.media as media_db
import database.stats as stats_db


async def search_anime(query: str, user_id: int) -> list:
    results = await media_db.search(query)
    await stats_db.log_event("search", {"query": query, "user_id": user_id, "results": len(results)})
    return results


async def autocomplete(partial: str, limit: int = 5) -> list:
    results = await media_db.search(partial, limit=limit)
    return [r["title"] for r in results]
