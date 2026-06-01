# Senior Analyst Studio — Telegram Bot + Web Admin

Production-ready Telegram bot (aiogram + SQLite + APScheduler) for webinar registration,
scheduled reminders, post-webinar nurturing funnel, **plus** a FastAPI web admin
dashboard (React + Vite + Tailwind + recharts) running in the same Python process.

- **Stack**: Python 3.11+, aiogram 3.x, APScheduler, FastAPI, uvicorn, SQLite (WAL)
- **Frontend**: React 18 + Vite + TypeScript + Tailwind + TanStack Query + recharts
- **Mode**: long-polling Telegram + HTTP server, coordinated via `asyncio.gather`
- **Timezone**: Europe/Moscow

## 1. Configure

```bash
cp .env.example .env
```

Required vars: `TELEGRAM_BOT_TOKEN`, `ADMIN_IDS`, `ZOOM_LINK`, `LANDING_URL`,
`CALL_LINK`, `ADMIN_PASSWORD`. Optional: `WEB_HOST` (default `0.0.0.0`),
`WEB_PORT` (default `8000`; on Railway/Render `$PORT` takes precedence).

## 2. Run locally

```bash
pip install -r requirements.txt
# Build the dashboard (one-off, or after frontend changes):
cd web/frontend && npm install && npm run build && cd ../..
python bot.py
```

- Telegram bot starts polling.
- Web admin available at **http://localhost:8000** (HTTP Basic Auth:
  user `admin`, password from `ADMIN_PASSWORD`).
- Health: `GET /health` → `{"status":"ok","bot_running":true}` (no auth).

## 3. Docker

```bash
docker build -t sas_bot .
docker run -d --name sas_bot \
  --env-file .env -p 8000:8000 \
  -v "$(pwd)/data:/app/data" -e DB_PATH=/app/data/sas_bot.db \
  --restart unless-stopped sas_bot
```

The image multi-stage builds the React bundle into `web/static/` and exposes port 8000.

## 4. Web admin

- **Dashboard** `/` — stat cards, hourly registrations line chart, segment bars, funnel.
- **Users** `/users` — filter by segment, search by name/username, paginate, open
  detail dialog to view 30 latest events and change segment / mark unsubscribed.
- **Events** `/events` — filter by event type and user_id.
- **Broadcast** `/broadcast` — pick segment, preview target count, send via the
  live bot instance with delivery stats.

All `/api/*` routes require HTTP Basic Auth. Polling refreshes stats every 30s.

## 5. Telegram commands

**User**
- `/start` — registration flow
- `/help` — list commands
- `/zoom` — Zoom link (registered users only)
- `/landing`, `/call`, `/unsubscribe`
- Any non-command text → forwarded to admins with inline **Ответить** button;
  first admin to click locks the conversation, has 10 minutes to reply.

**Admin** (Telegram IDs in `ADMIN_IDS`)
- `/stats`, `/segment <tg_id|@username> <segment>`, `/broadcast <segment|all> <text>`,
  `/export`, `/test <message_id>`.

## 6. Concurrency

`db.py` opens SQLite with `journal_mode=WAL`, `busy_timeout=5000`,
`synchronous=NORMAL`, fresh connection per operation. Safe for the bot
writing (registrations, events) while the dashboard reads + admin segment
edits happen concurrently.

## 7. Project layout

```
sas_bot/
├── bot.py              # entry: asyncio.gather(bot polling, uvicorn)
├── config.py           # env validation
├── db.py               # SQLite (WAL) + analytics queries
├── handlers.py         # /start FSM, /zoom, message forwarding, ReplyFlow
├── admin.py            # /stats /segment /broadcast /export /test
├── broadcast.py        # rate-limited sender
├── scheduler.py        # APScheduler jobs (M1–M7)
├── content.py          # message templates
├── web/
│   ├── api.py          # FastAPI app + HTTP Basic auth
│   ├── static/         # built React bundle (served by FastAPI)
│   └── frontend/       # Vite + React + Tailwind sources
├── requirements.txt
├── Dockerfile
└── .env.example
```
