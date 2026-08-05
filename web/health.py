from aiohttp import web

import config.settings as config
from core.logger import get_logger

LOGGER = get_logger("web.health")


async def health(request):
    return web.json_response({"status": "running", "bot": config.BOT_NAME})


async def start_health_server():
    app_ = web.Application()
    app_.router.add_get("/", health)
    app_.router.add_get("/health", health)
    runner = web.AppRunner(app_)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", config.PORT)
    await site.start()
    LOGGER.info(f"Health check server listening on :{config.PORT}")
