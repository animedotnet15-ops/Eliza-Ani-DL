import asyncio

from pyrogram import Client

import config.settings as config
from core.logger import get_logger

LOGGER = get_logger("client")

app = Client(
    name="eliza_bot",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN,
    workdir="sessions",
)


async def connect_with_retry(max_retries: int = 10, base_delay: float = 3.0):
    """Pyrogram auto-reconnects at the transport level once connected, but
    the *initial* connect can still fail (network blip, DNS, Telegram DC
    hiccup). Retry that with exponential backoff instead of crashing."""
    attempt = 0
    while True:
        try:
            await app.start()
            return
        except Exception as e:
            attempt += 1
            if attempt > max_retries:
                LOGGER.error(f"Giving up connecting to Telegram after {max_retries} attempts: {e}")
                raise
            delay = min(base_delay * (2 ** (attempt - 1)), 60)
            LOGGER.warning(f"Telegram connect failed ({e}); retrying in {delay:.0f}s (attempt {attempt}/{max_retries})")
            await asyncio.sleep(delay)
