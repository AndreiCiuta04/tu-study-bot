# TUW Study Bot

A private Telegram study assistant for TU Wien, designed to bring university
information and personal study tasks into a daily overview.

Currently supports restricted access for one user, `/help`, and `/today` with
an empty state. University integrations and study planning are not available yet.

Built with Python 3.12+, FastAPI, python-telegram-bot, SQLAlchemy and Alembic,
using SQLite locally.

## Local setup

Run from the repository root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
```

For Telegram, replace `TUW_TELEGRAM_BOT_TOKEN` and
`TUW_ALLOWED_TELEGRAM_USER_ID` in `.env` with your bot token and numeric user ID.
Keep `.env` private. Environment variables override file settings.
`TUW_DATABASE_URL` and `TUW_LOG_LEVEL` configure storage and logging.

## Run

```bash
python -m app.integrations.telegram.bot
```

The bot uses polling. Send `/help` or `/today` in a private chat.
Other users and group chats are silently ignored.
`/today` currently replies: “Nothing planned for today yet.”

Run the independent HTTP application in another terminal if needed:

```bash
uvicorn app.api.app:app --reload
curl --fail http://127.0.0.1:8000/health
```

Health returns `{"status":"ok"}` and requires no Telegram credentials.

## Development

```bash
pytest
ruff check .
ruff format --check .
mypy app
alembic upgrade head
```

Tests use temporary databases and mocked Telegram calls; no credentials or
network access are required. Apply migrations explicitly before running;
application startup does not change the schema.
