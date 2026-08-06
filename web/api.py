"""REST API for website integration (reuses the same MongoDB the bot
already writes to - no separate sync step needed, results are always
current as of the last indexed/uploaded file).

Endpoints:
  GET /api/search?q=<query>&page=&per_page=
  GET /api/file/{anime_id}
  GET /api/latest?page=&per_page=
  GET /api/popular?page=&per_page=

Note: raw Telegram file_ids are intentionally NOT exposed here - only
metadata (title, seasons/episodes/qualities/audio languages available).
Actual file delivery still goes through the bot itself, so this API
can be public without letting anyone bypass the bot for downloads.
"""
import time
from collections import defaultdict, deque

from aiohttp import web

import database.media as media_db
from core.logger import get_logger

LOGGER = get_logger("web.api")

# ── simple in-memory per-IP rate limiter (no extra infra needed) ───────────
RATE_LIMIT = 30
RATE_WINDOW = 60  # seconds
_hits = defaultdict(deque)


def _rate_limited(request: web.Request) -> bool:
    ip = request.remote or "unknown"
    now = time.time()
    q = _hits[ip]
    while q and now - q[0] > RATE_WINDOW:
        q.popleft()
    if len(q) >= RATE_LIMIT:
        return True
    q.append(now)
    return False


# ── simple in-memory TTL cache for frequent queries ─────────────────────────
_CACHE_TTL = 30  # seconds
_cache = {}


def _cache_get(key):
    entry = _cache.get(key)
    if not entry:
        return None
    value, expires = entry
    if time.time() > expires:
        _cache.pop(key, None)
        return None
    return value


def _cache_set(key, value):
    _cache[key] = (value, time.time() + _CACHE_TTL)


def _serialize_anime(doc: dict) -> dict:
    """Metadata only - see module docstring for why file_ids are excluded."""
    seasons_out = {}
    for s_key, season in (doc.get("seasons") or {}).items():
        episodes_out = {}
        for e_key, ep in (season.get("episodes") or {}).items():
            qualities_out = {}
            for q_key, quality in (ep.get("qualities") or {}).items():
                qualities_out[q_key] = list((quality.get("audios") or {}).keys())
            episodes_out[e_key] = {"qualities": qualities_out}
        seasons_out[s_key] = {"episodes": episodes_out}

    return {
        "anime_id": doc.get("anime_id"),
        "title": doc.get("title"),
        "poster": doc.get("poster", ""),
        "year": doc.get("year"),
        "genres": doc.get("genres", []),
        "status": doc.get("status", ""),
        "views": doc.get("views", 0),
        "seasons": seasons_out,
    }


def _parse_pagination(request: web.Request) -> tuple:
    try:
        page = max(1, int(request.query.get("page", 1)))
    except ValueError:
        page = 1
    try:
        per_page = min(50, max(1, int(request.query.get("per_page", 20))))
    except ValueError:
        per_page = 20
    return page, per_page


def _paginate(items: list, page: int, per_page: int) -> dict:
    total = len(items)
    start = (page - 1) * per_page
    end = start + per_page
    return {
        "results": items[start:end],
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": max(1, (total + per_page - 1) // per_page),
    }


async def api_search(request: web.Request):
    if _rate_limited(request):
        return web.json_response({"error": "rate_limited", "message": "Too many requests - try again shortly."}, status=429)

    query = (request.query.get("q") or "").strip()
    if not query:
        return web.json_response({"error": "missing_query", "message": "Provide ?q=<search term>"}, status=400)

    page, per_page = _parse_pagination(request)
    cache_key = f"search:{query.lower()}"
    results = _cache_get(cache_key)
    if results is None:
        raw = await media_db.search(query, limit=200)
        results = [_serialize_anime(r) for r in raw]
        _cache_set(cache_key, results)

    return web.json_response(_paginate(results, page, per_page))


async def api_file(request: web.Request):
    if _rate_limited(request):
        return web.json_response({"error": "rate_limited"}, status=429)

    anime_id = request.match_info.get("id", "")
    doc = await media_db.get_anime(anime_id)
    if not doc:
        return web.json_response({"error": "not_found", "message": f"No anime with id '{anime_id}'"}, status=404)

    await media_db.increment_views(anime_id)
    return web.json_response(_serialize_anime(doc))


async def api_latest(request: web.Request):
    if _rate_limited(request):
        return web.json_response({"error": "rate_limited"}, status=429)

    page, per_page = _parse_pagination(request)
    results = _cache_get("latest")
    if results is None:
        raw = await media_db.latest(limit=200)
        results = [_serialize_anime(r) for r in raw]
        _cache_set("latest", results)

    return web.json_response(_paginate(results, page, per_page))


async def api_popular(request: web.Request):
    if _rate_limited(request):
        return web.json_response({"error": "rate_limited"}, status=429)

    page, per_page = _parse_pagination(request)
    results = _cache_get("popular")
    if results is None:
        raw = await media_db.trending(limit=200)
        results = [_serialize_anime(r) for r in raw]
        _cache_set("popular", results)

    return web.json_response(_paginate(results, page, per_page))


def register_api_routes(app_: web.Application):
    app_.router.add_get("/api/search", api_search)
    app_.router.add_get("/api/file/{id}", api_file)
    app_.router.add_get("/api/latest", api_latest)
    app_.router.add_get("/api/popular", api_popular)

    @web.middleware
    async def cors_middleware(request: web.Request, handler):
        if request.method == "OPTIONS":
            resp = web.Response()
        else:
            resp = await handler(request)
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return resp

    app_.middlewares.append(cors_middleware)
    for route in ("/api/search", "/api/file/{id}", "/api/latest", "/api/popular"):
        app_.router.add_route("OPTIONS", route, lambda request: web.Response())

    LOGGER.info("REST API routes registered: /api/search /api/file/{id} /api/latest /api/popular")
  
