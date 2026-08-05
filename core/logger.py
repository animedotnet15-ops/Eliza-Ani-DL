import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s - %(message)s",
    datefmt="%d-%b-%y %I:%M:%S %p",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


LOGGER = get_logger("Eliza")
