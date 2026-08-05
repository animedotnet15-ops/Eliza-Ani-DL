import traceback
from functools import wraps

from pyrogram.types import Message, CallbackQuery

import config.settings as config
from core.logger import get_logger
from database.stats import log_event

LOGGER = get_logger("handlers.error")


def safe_handler(func):
    """Wrap every plugin handler so one bad update can't crash the whole
    dispatcher; logs full tracebacks to the log channel for debugging."""
    @wraps(func)
    async def wrapper(client, update, *args, **kwargs):
        try:
            return await func(client, update, *args, **kwargs)
        except Exception as e:
            tb = traceback.format_exc()
            LOGGER.error(f"Unhandled error in {func.__name__}: {e}\n{tb}")
            await log_event("error", {"handler": func.__name__, "error": str(e)})

            if config.LOG_CHANNEL:
                try:
                    await client.send_message(
                        config.LOG_CHANNEL,
                        f"⚠️ **Error in `{func.__name__}`**\n\n`{str(e)[:500]}`",
                    )
                except Exception:
                    pass

            target = update.message if isinstance(update, CallbackQuery) else update
            try:
                if isinstance(update, CallbackQuery):
                    await update.answer("⚠️ Something went wrong. Try again.", show_alert=True)
                elif isinstance(update, Message):
                    await update.reply_text("⚠️ Something went wrong processing that. Please try again.")
            except Exception:
                pass
    return wrapper
