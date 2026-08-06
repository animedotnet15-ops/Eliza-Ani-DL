from aiohttp import web

import config.settings as config
from core.logger import get_logger
from web.api import register_api_routes

LOGGER = get_logger("web.health")


async def health(request):
    return web.json_response({"status": "running", "bot": config.BOT_NAME})


async def start_health_server():
    app_ = web.Application()
    app_.router.add_get("/", health)
    app_.router.add_get("/health", health)
    register_api_routes(app_)
    runner = web.AppRunner(app_)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", config.PORT)
    await site.start()
    LOGGER.info(f"Health check server listening on :{config.PORT}")
