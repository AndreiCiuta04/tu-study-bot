# TUW Study Bot

A private Telegram study assistant for TU Wien, bringing university information
and personal study work into concise daily overviews.

Currently supports single-user access, public TISS exam imports, and exam
countdowns. Commands: `/help`, `/today` (empty state), and `/exams`.
TUWEL and personal study planning are not available yet.

Python 3.12+, FastAPI, python-telegram-bot, SQLAlchemy, Alembic and SQLite.

## Local setup

Run from the repository root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
```

Set `TUW_TELEGRAM_BOT_TOKEN` and `TUW_ALLOWED_TELEGRAM_USER_ID` in your private
`.env`. Environment variables override file settings. `TUW_DATABASE_URL` and
`TUW_LOG_LEVEL` configure storage and logging.

## Run

```bash
python -m app.integrations.telegram.bot
```

Use a private chat; other users and group chats are silently ignored.
`/exams` lists imported exams from today onward, using Vienna calendar dates.
It does not select exams or create personal plans.

Import exam dates explicitly; no Telegram or TISS credentials are needed:

```bash
python -m app.cli.sync_tiss 194.025 2026S
python -m app.cli.sync_tiss 194025 2026S --from-date 2026-09-09
```

Select the course offering semester explicitly: the exam endpoint does not return
a semester. Repeated imports update matching IDs and retain events absent from
later responses. See [TISS data notes](docs/tiss.md) for endpoints and identity.

Run the independent HTTP application if needed:

```bash
uvicorn app.api.app:app --reload
curl --fail http://127.0.0.1:8000/health
```

Health returns `{"status":"ok"}` without Telegram credentials.

## Development

```bash
pytest
ruff check .
ruff format --check .
mypy app
alembic upgrade head
```

Tests use migrated temporary databases and mocked HTTP/Telegram calls.
Application startup does not alter the schema.
