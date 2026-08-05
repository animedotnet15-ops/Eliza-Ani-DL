import os


def _int(name, default=0):
    val = os.environ.get(name)
    try:
        return int(val) if val else default
    except ValueError:
        return default


def _list(name):
    return [x.strip() for x in os.environ.get(name, "").split(",") if x.strip()]


def _int_list(name):
    out = []
    for x in _list(name):
        try:
            out.append(int(x))
        except ValueError:
            pass
    return out


# ── Telegram credentials ────────────────────────────────────────────────────
API_ID = _int("API_ID")
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# ── Bot identity ─────────────────────────────────────────────────────────────
BOT_NAME = os.environ.get("BOT_NAME", "Eliza")

# ── Owner / admins (bot-level, distinct from Telegram group admins) ─────────
OWNER_ID = _int("OWNER_ID")
ADMINS = set(_int_list("ADMINS") + ([OWNER_ID] if OWNER_ID else []))

# ── MongoDB Atlas ────────────────────────────────────────────────────────────
DATABASE_URI = os.environ.get("DATABASE_URI", "")
DATABASE_NAME = os.environ.get("DATABASE_NAME", "eliza")

# ── Source channels indexed for content (comma-separated numeric ids) ──────
# Can also be managed at runtime via /addchannel /removechannel (admin panel)
SOURCE_CHANNELS = _int_list("SOURCE_CHANNELS")

# ── Log channel ──────────────────────────────────────────────────────────────
LOG_CHANNEL = _int("LOG_CHANNEL")

# ── Force subscribe (initial seed list; editable at runtime too) ───────────
FORCE_SUB_CHANNELS = _list("FORCE_SUB_CHANNELS")  # usernames or invite links

# ── Link shortener defaults (all editable later via admin panel) ───────────
SHORTENER_API = os.environ.get("SHORTENER_API", "")
SHORTENER_DOMAIN = os.environ.get("SHORTENER_DOMAIN", "")
VERIFY_MIN_MINUTES = _int("VERIFY_MIN_MINUTES", 2)
VERIFY_MAX_MINUTES = _int("VERIFY_MAX_MINUTES", 5)
VERIFY_VALIDITY_HOURS = _int("VERIFY_VALIDITY_HOURS", 6)  # 0 = unlimited

# ── AI suggestions (optional; falls back to a non-AI recommender if unset) ──
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# ── Web health-check server (Render/Railway) ────────────────────────────────
PORT = _int("PORT", 8080)

# ── Misc ─────────────────────────────────────────────────────────────────────
SUPPORT_CHAT = os.environ.get("SUPPORT_CHAT", "")
UPDATES_CHANNEL = os.environ.get("UPDATES_CHANNEL", "")
DEFAULT_LANGUAGE = os.environ.get("DEFAULT_LANGUAGE", "en")

_required = {
    "API_ID": API_ID,
    "API_HASH": API_HASH,
    "BOT_TOKEN": BOT_TOKEN,
    "OWNER_ID": OWNER_ID,
    "DATABASE_URI": DATABASE_URI,
}
_missing = [name for name, val in _required.items() if not val]
if _missing:
    raise SystemExit(
        f"\n❌ Missing/empty required environment variables: {', '.join(_missing)}\n"
        "See .env.example.\n"
    )
