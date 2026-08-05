import asyncio

import motor.motor_asyncio
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

import config.settings as config
from core.logger import get_logger

LOGGER = get_logger("database.connection")


class MongoConnection:
    def __init__(self):
        self.client: motor.motor_asyncio.AsyncIOMotorClient = None
        self.db = None

    def connect(self):
        """Motor/PyMongo already pool + auto-reconnect at the socket level;
        this just builds the client with sane retry settings."""
        self.client = motor.motor_asyncio.AsyncIOMotorClient(
            config.DATABASE_URI,
            serverSelectionTimeoutMS=15000,
            retryWrites=True,
            retryReads=True,
        )
        self.db = self.client[config.DATABASE_NAME]

    async def ping_with_retry(self, max_retries: int = 10, base_delay: float = 3.0):
        attempt = 0
        while True:
            try:
                await self.client.admin.command("ping")
                LOGGER.info("MongoDB connection OK.")
                return
            except (ConnectionFailure, ServerSelectionTimeoutError) as e:
                attempt += 1
                if attempt > max_retries:
                    LOGGER.error(f"Giving up on MongoDB after {max_retries} attempts: {e}")
                    raise
                delay = min(base_delay * (2 ** (attempt - 1)), 60)
                LOGGER.warning(f"MongoDB ping failed ({e}); retrying in {delay:.0f}s")
                await asyncio.sleep(delay)

    async def watchdog(self, interval_seconds: int = 60):
        """Background task: periodically pings MongoDB; on failure,
        reconnects instead of letting the process silently degrade."""
        while True:
            await asyncio.sleep(interval_seconds)
            try:
                await self.client.admin.command("ping")
            except Exception as e:
                LOGGER.warning(f"MongoDB watchdog detected a disconnect ({e}); reconnecting...")
                try:
                    self.connect()
                    await self.ping_with_retry()
                except Exception as reconnect_err:
                    LOGGER.error(f"MongoDB reconnect failed: {reconnect_err}")


mongo = MongoConnection()
mongo.connect()
db = mongo.db
