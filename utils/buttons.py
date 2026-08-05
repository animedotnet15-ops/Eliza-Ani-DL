"""
Telegram added colored inline buttons (bg_primary/bg_success/bg_danger) at
the protocol level. Some pyrogram forks expose this as
`pyrogram.enums.ButtonStyle`; others don't have it yet. Rather than crash
the whole bot on import if your installed version lacks it, this module
detects it once at import time and no-ops the color if unavailable - every
button still works, it just renders in the default color on older
versions. Check `core/logger` output on startup for a one-time notice.
"""
from pyrogram.types import InlineKeyboardButton

from core.logger import get_logger

LOGGER = get_logger("utils.buttons")

try:
    from pyrogram.enums import ButtonStyle
    _HAS_BUTTON_STYLE = True
except ImportError:
    ButtonStyle = None
    _HAS_BUTTON_STYLE = False
    LOGGER.warning(
        "Your installed pyrogram/kurigram build doesn't expose "
        "pyrogram.enums.ButtonStyle - colored buttons will render in the "
        "default color. Upgrade kurigram if you want PRIMARY/SUCCESS/DANGER "
        "colors: pip install -U kurigram"
    )


def btn(text: str, callback_data: str = None, url: str = None, style: str = None) -> InlineKeyboardButton:
    """style: "primary" | "success" | "danger" | None"""
    kwargs = {"text": text}
    if url:
        kwargs["url"] = url
    else:
        kwargs["callback_data"] = callback_data

    if style and _HAS_BUTTON_STYLE:
        style_map = {
            "primary": ButtonStyle.PRIMARY,
            "success": ButtonStyle.SUCCESS,
            "danger": ButtonStyle.DANGER,
        }
        mapped = style_map.get(style.lower())
        if mapped is not None:
            try:
                kwargs["style"] = mapped
            except Exception:
                pass  # constructor doesn't accept `style` on this version either - ignore and continue

    return InlineKeyboardButton(**kwargs)


def primary(text: str, callback_data: str = None, url: str = None) -> InlineKeyboardButton:
    return btn(text, callback_data, url, style="primary")


def success(text: str, callback_data: str = None, url: str = None) -> InlineKeyboardButton:
    return btn(text, callback_data, url, style="success")


def danger(text: str, callback_data: str = None, url: str = None) -> InlineKeyboardButton:
    return btn(text, callback_data, url, style="danger")
