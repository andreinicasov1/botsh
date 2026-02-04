# Telegram Calendar / Planner Bot v4 (FIX: Uni schedule buttons)
✅ Fix complet: butoanele din "Uni schedule" nu mai schimbă setările de notificări.

## Run (macOS / Linux)
```bash
cd telegram_calendar_bot_v4
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# pune BOT_TOKEN în .env
python3 -m app.main
```

## Important
- Callback-urile pentru notificări au prefix: `notify_uni:*` și `notify_evd:*`
- Callback-urile pentru orar (uni schedule) au prefix: `uni:*`
Deci nu se mai ciocnesc.
