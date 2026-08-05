import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config.settings as config
from core.logger import LOGGER
from core.client import app, connect_with_retry
from database.connection import mongo
import database.users as users_db
import database.media as media_db
import database.channels as channels_db
import database.stats as stats_db
import services.shortener as shortener_service
from web.health import start_health_server

scheduler = AsyncIOScheduler()


def register_plugins():
    from plugins import (
        start, verification, navigate, user_features,
        admin, settings_admin,
    )

    start.register(app)
    verification.register(app)
    navigate.register(app)
    user_features.register(app)
    admin.register(app)
    settings_admin.register(app)
    LOGGER.info("All plugins registered.")


async def load_settings():
    from database.settings_db import get_settings
    await get_settings()  # ensures the settings document exists with defaults
    LOGGER.info("Settings loaded.")


async def ensure_all_indexes():
    await users_db.ensure_indexes()
    await media_db.ensure_indexes()
    await channels_db.ensure_indexes()
    await stats_db.ensure_indexes()
    await shortener_service.ensure_indexes()
    LOGGER.info("Database indexes ensured.")


async def start_indexer():
    from indexer.indexer import register_live_handlers, full_scan_all_channels

    register_live_handlers(app)
    asyncio.create_task(full_scan_all_channels(app))
    LOGGER.info("Indexer started (live handlers registered, initial full scan running in background).")


async def start_scheduler():
    from indexer.indexer import full_scan_all_channels

    # Continuous background watchdog - not a periodic job, so a plain task fits better than apscheduler.
    asyncio.create_task(mongo.watchdog())

    # Periodic full re-scan (belt-and-suspenders in case a live update was missed) - this is
    # exactly the kind of recurring job apscheduler is for.
    scheduler.add_job(full_scan_all_channels, "interval", seconds=3600, args=[app], id="periodic_rescan")
    scheduler.start()
    LOGGER.info("Scheduler started (hourly full re-scan) + MongoDB watchdog running.")


async def main():
    LOGGER.info(f"Starting {config.BOT_NAME}...")

    # 1. Config already loaded via config.settings import above.
    # 2. Connect MongoDB (with retry).
    await mongo.ping_with_retry()

    # 3. Connect Telegram (with retry).
    await connect_with_retry()
    me = await app.get_me()
    LOGGER.info(f"Bot connected as @{me.username}")

    # 4. Load languages (static import, already available).
    # 5. Load settings.
    await load_settings()

    # 6. Ensure DB indexes.
    await ensure_all_indexes()

    # 7. Start scheduler.
    await start_scheduler()

    # 8. Start indexer.
    await start_indexer()

    # 9. Register plugin handlers.
    register_plugins()

    # 10. Health check server (Render/Railway).
    await start_health_server()

    if config.LOG_CHANNEL:
        try:
            await app.send_message(config.LOG_CHANNEL, f"✅ **{config.BOT_NAME} started successfully.**")
        except Exception as e:
            LOGGER.warning(f"Couldn't send startup message to log channel: {e}")

    LOGGER.info(f"{config.BOT_NAME} is fully up and running.")
    await asyncio.Event().wait()


if __name__ == "__main__":
    try:
        import uvloop
        uvloop.install()
    except ImportError:
        pass  # uvloop is Linux-only

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        LOGGER.info("Shutting down (KeyboardInterrupt).")
