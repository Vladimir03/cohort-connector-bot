# Senior Analyst Studio — Telegram Bot

Production-ready Telegram bot for webinar registration, scheduled reminders, and a post-webinar nurturing funnel.

- **Stack**: Python 3.11+, aiogram 3.x, APScheduler, SQLite, python-dotenv
- **Mode**: long-polling (no webhooks)
- **Timezone**: Europe/Moscow

## 1. Get credentials

1. **Bot token** — open [@BotFather](https://t.me/BotFather) in Telegram, send `/newbot`, follow prompts, copy the token.
2. **Admin Telegram IDs** — open [@userinfobot](https://t.me/userinfobot), copy your numeric ID. Comma-separate multiple admins.

## 2. Configure env

```bash
cp .env.example .env
# edit .env: TELEGRAM_BOT_TOKEN, ADMIN_IDS, ZOOM_LINK, LANDING_URL, CALL_LINK
```

All variables are required — the bot fails fast on startup if any is missing.

## 3. Run locally

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python bot.py
```

DB file `sas_bot.db` is created automatically in the working directory.

## 4. Run with Docker

```bash
docker build -t sas_bot .
docker run -d --name sas_bot \
  --env-file .env \
  -v "$(pwd)/data:/app/data" \
  -e DB_PATH=/app/data/sas_bot.db \
  --restart unless-stopped \
  sas_bot
```

Mount a host directory to persist the SQLite DB across restarts.

## 5. Commands

**User**
- `/start` — registration flow (or info if already registered)
- `/help` — list commands
- `/landing` — program landing URL
- `/call` — schedule 30-min call
- `/unsubscribe` — stop receiving broadcasts

**Admin** (only IDs in `ADMIN_IDS`)
- `/stats` — total users, segment breakdown, unsubscribed count
- `/segment <tg_id|@username> <segment>` — set a user's segment
  - segments: `pre_webinar`, `attended_live`, `no_show`, `hot_lead`, `customer`, `churned`
- `/broadcast <segment|all> <text>` — ad-hoc broadcast
- `/export` — download users CSV
- `/test <message_id>` — preview a broadcast template
  - ids: `m1_day_before`, `m2_one_hour`, `m3_thanks`, `m4_reveal`, `m5_faq`, `m6_open`, `m7_deadline`

## 6. Scheduled broadcasts

Configured in `scheduler.py` for the webinar on **2026-06-04 19:00 МСК**. Adjust dates in the `JOBS` list as needed. Jobs missed by less than 1 hour still fire (`misfire_grace_time=3600`).

## 7. Operations notes

- Users who block the bot are auto-marked `unsubscribed=1` on next broadcast attempt.
- Sends are throttled to ~20 msg/sec to stay under Telegram's 30/sec limit.
- All times in code are interpreted as `Europe/Moscow`.
- After the live webinar, manually mark attendees with `/segment <id> attended_live` (and no-shows with `no_show`) so M3 targeting is accurate. Move CTA-clickers / repliers to `hot_lead` so M7 reaches them.

## Files

```
sas_bot/
├── bot.py            # entry point
├── config.py         # env loading + validation
├── db.py             # SQLite layer
├── handlers.py       # user commands + registration FSM
├── admin.py          # admin commands
├── broadcast.py      # send_to_users helper
├── scheduler.py      # APScheduler jobs
├── content.py        # message templates
├── requirements.txt
├── Dockerfile
└── .env.example
```
