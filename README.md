# Eliza — Ultimate Telegram Anime Search & Download Bot

Search any anime by just typing its name, browse Season → Episode →
Quality → Audio, then Download or Stream — all backed by Telegram
channels as the content database (no website/file-hosting needed).
Multi-language UI, force-subscribe, link-shortener verification,
favorites/history/continue-watching/recommendations, referrals,
premium users, a full admin panel, and an auto-indexer that scans your
channels in the background.

## Project structure

```
config/       environment-driven settings
core/         pyrogram client + logger
database/     MongoDB collections (users, media, channels, settings, admins, stats)
indexer/      filename parser + background channel scanner
languages/    UI strings for en/ta/hi/te/ml
services/     shortener, force-sub, search, recommendations
middlewares/  admin/ban/maintenance/flood guard decorators
handlers/     global error handler
plugins/      every user-facing & admin command
utils/        colored-button helper, formatters
web/          health-check server (Render/Railway)
bot.py        entry point
```

## Setup guide

### 1. BotFather (get BOT_TOKEN)
1. Message [@BotFather](https://t.me/BotFather) → `/newbot`
2. Follow the prompts, copy the token it gives you into `BOT_TOKEN`.
3. Optional: `/setuserpic`, `/setdescription` to brand it as "Eliza".

### 2. Telegram API (get API_ID / API_HASH)
1. Go to https://my.telegram.org → log in with your phone number.
2. **API development tools** → create an app (any name/platform is fine).
3. Copy the `api_id` and `api_hash` shown into `API_ID` / `API_HASH`.

### 3. MongoDB Atlas (get DATABASE_URI)
1. https://cloud.mongodb.com → create a free (M0) cluster.
2. **Database Access** → add a user with a password.
3. **Network Access** → add `0.0.0.0/0` (allow from anywhere) for cloud
   deploys, or your specific IP for local dev.
4. **Connect** → "Drivers" → copy the `mongodb+srv://...` string into
   `DATABASE_URI`, filling in your username/password.

### 4. Owner ID
Message [@userinfobot](https://t.me/userinfobot) to get your numeric
Telegram user ID → `OWNER_ID`.

### 5. Add your content channels
1. Create a private Telegram channel, upload your anime files there
   (filenames or captions like `Mob Psycho 100 S01 E09 [480p] Tamil`
   parse automatically — see "Indexer" below for the exact format
   detection rules).
2. Add your bot as **admin** of that channel.
3. Get the channel's numeric ID (forward any message from it to
   [@RawDataBot](https://t.me/RawDataBot) and read `chat.id` — it'll
   look like `-1001234567890`).
4. Either put it in `SOURCE_CHANNELS` in `.env`, or add it after the
   bot is running with `/addchannel -1001234567890`.
5. Run `/reindex` (admin only) to scan it.

### 6. Install & run
```bash
pip install -r requirements.txt
cp .env.example .env   # fill in every value above
python3 bot.py
```

## Deployment

### Railway
- Push this repo to GitHub, create a new Railway project from it.
- Railway auto-detects `railway.json` + `Dockerfile`.
- Set every variable from `.env.example` in Railway's **Variables** tab.
- `PORT` is provided automatically by Railway; the health server binds to it.

### Render
- New → Web Service → connect the repo. Render reads `render.yaml`.
- It'll prompt for the `sync: false` variables (the secrets) — fill them in.
- Health check path is `/health`, already wired in `bot.py`/`web/health.py`.

### Docker
```bash
docker compose up -d --build
```
Spins up Eliza + a local MongoDB container together. For a bare VPS
without Docker: `bash start.sh` (installs deps and runs the bot) under
a process manager (systemd/pm2/screen) so it survives reboots.

### Local
```bash
pip install -r requirements.txt
python3 bot.py
```

## Environment variables

See `.env.example` for the full list with comments. Only `API_ID`,
`API_HASH`, `BOT_TOKEN`, `OWNER_ID`, and `DATABASE_URI` are strictly
required to start — everything else (shortener, force-sub, log
channel, AI suggestions) is optional and can also be configured later
through the admin panel commands instead of `.env`.

## Shortener setup

Eliza works with any shortener that exposes a simple
`GET https://{domain}/api?api={key}&url={long_url}` → JSON with a
`shortenedUrl` field (this is the near-universal pattern most
shortener services use). Configure it either via `.env`
(`SHORTENER_API`, `SHORTENER_DOMAIN`) or at runtime:
```
/setshortenerapi <your_api_key>
/setshortenerdomain <your_shortener_domain>
```
Timing rules (`/setverifymin`, `/setverifymax`, `/setverifyvalidity`)
control how "Bypass Detected" / "Verification Expired" are decided —
see `services/shortener.py` for the exact logic.

## Force subscribe

Add channels with `/addforcesub @channelusername` (repeatable for
multiple channels), remove with `/removeforcesub`, toggle the whole
feature on/off with `/toggleforcesub`. The bot must be a member (or
admin) of each force-sub channel to check membership.

## Log channel

Set `LOG_CHANNEL` (numeric id, bot must be a member/admin there) to
receive: startup notices, restarts, errors, broadcasts, verification
successes, and bypass-detection alerts.

## Indexer

- **Live indexing**: any new file uploaded to a configured channel is
  indexed within seconds via a live message handler.
- **Edits**: editing a message's caption re-parses and re-indexes it.
- **Deletes**: deleting a source message removes it from the database.
- **Backfill**: `/addchannel` + `/reindex` does a full historical scan.
- **Periodic re-scan**: an hourly apscheduler job re-scans every
  channel as a safety net for anything missed while the bot was
  offline.
- **Filename parsing**: see `indexer/parser.py` — handles `S01E09`,
  `Season 1 Episode 9`, quality tags (`480p`–`2160p`), and language
  detection (Tamil/English/Hindi/Telugu/Malayalam/Japanese/Korean/
  Multi). Captions are preferred over filenames when both are present,
  since captions are usually cleaner.

## Troubleshooting

- **"Missing/empty environment variables" on startup** — fill in every
  required var listed in the error message; check `.env.example`.
- **Bot doesn't see new files in a channel** — confirm the bot is an
  **admin** of that channel (not just a member) and that the channel
  was added with `/addchannel` + `/reindex`.
- **Search finds nothing** — the indexer hasn't picked up any files
  yet; run `/reindex`, and check `/channels` shows your channel listed.
- **Colored buttons show up as plain/default color** — your installed
  kurigram build doesn't expose `pyrogram.enums.ButtonStyle` yet; the
  bot logs a one-time warning about this at startup and continues
  working fine, just without the color. Try `pip install -U kurigram`.
- **MongoDB keeps disconnecting** — check your Atlas cluster's
  Network Access allows your deploy platform's IP (`0.0.0.0/0` is
  simplest for Railway/Render, which don't have static IPs). The
  built-in watchdog (`database/connection.py`) auto-reconnects, but
  can't fix a firewall block.
- **Shortener always says "Bypass Detected"** — your `verify_min_minutes`
  is probably set too high for your shortener's actual redirect flow;
  lower it with `/setverifymin`.
- **Callback buttons stop working after a while / "Session expired"** —
  navigation state (search → season → episode → quality → audio) is
  kept in memory for compactness and doesn't survive a bot restart;
  users just need to search again. This is intentional — see
  `plugins/navigate.py`'s `NAV_SESSIONS` for the tradeoff.

## FAQ

**Do I need a website/file server?** No — every video file lives in
your private Telegram channel(s); MongoDB only stores metadata
(titles, season/episode/quality/audio → chat_id/message_id/file_id).

**Can I add unlimited channels?** Yes, `/addchannel` any number of
private channels the bot is admin in.

**How does AI Suggestions work without an OpenAI/Gemini key?** The
recommendation engine (`services/recommend.py`) always works via a
genre-similarity fallback using your own indexed catalog. Setting
`GEMINI_API_KEY` additionally unlocks free-text "similar anime" AI
suggestions layered on top.

**Is `/eval` or `/sh` included?** No — this build intentionally leaves
out arbitrary code/shell execution commands since they weren't in the
requested feature list and are a meaningful security surface; the
existing `/restart`, `/backup`, `/reindex` etc. cover the operational
needs from the spec without that risk.
