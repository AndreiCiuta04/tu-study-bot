# TUW Study Bot

M0 foundation for a personal TU Wien study-management bot. Requires Python 3.12+
and pip. Run all commands from the repository root.

## Setup and run

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
uvicorn app.api.app:app --reload
```

In another terminal:

```bash
curl --fail http://127.0.0.1:8000/health
```

Expected: HTTP 200 with `{"status":"ok"}`. This is a liveness endpoint:
it does not check database readiness. Importing or starting the application does
not create tables or run migrations.

## Configuration

Settings load from environment variables and the root `.env` file; environment
variables take precedence. The application and Alembic use the same settings.

| Variable | Default | Meaning |
| --- | --- | --- |
| `TUW_DATABASE_URL` | `sqlite:///./tuw-study-bot.db` | SQLAlchemy database URL; relative SQLite paths resolve from the working directory |
| `TUW_LOG_LEVEL` | `INFO` | DEBUG, INFO, WARNING, ERROR, or CRITICAL |

Keep secrets in the ignored `.env` file or environment. Do not log credentials,
tokens, source payloads, or database URLs. Basic logging goes to stderr.

## Verification

With the virtual environment activated:

```bash
pytest
ruff check .
ruff format --check .
mypy app
alembic upgrade head
python -c "from app.api.app import app; from fastapi.testclient import TestClient; response = TestClient(app).get('/health'); assert response.status_code == 200; assert response.json() == {'status': 'ok'}; print(response.json())"
```

Tests use temporary databases and require no university credentials or network.

## Migrations

```bash
alembic upgrade head
alembic current
alembic history
```

M0 includes an intentionally empty baseline revision: only Alembic's version
table is created. No domain tables exist yet. For future schema changes, define
models using `app.db.base.Base`, import their modules in `migrations/env.py` so
metadata is registered, then generate and review a migration:

```bash
alembic revision --autogenerate -m "describe schema change"
alembic upgrade head
```

To revert the latest revision in a disposable development database:

```bash
alembic downgrade -1
```

Database metadata uses stable constraint names. Future models and migrations
must remain PostgreSQL-compatible; PostgreSQL deployment and its driver are
deferred. Never use `create_all()` for application schema management.

## Architecture

The modular monolith follows:

```text
Router / Handler -> Service -> Repository -> Database
```

- `app/api/app.py`: FastAPI composition and settings/logging setup.
- `app/routers/`: transport parsing and response formatting; calls services only.
- `app/services/`: application logic, independent of FastAPI and ORM objects.
- `app/repositories/`: future persistence operations; only this application layer
  may query SQLAlchemy sessions/models. No dummy repository is needed for liveness.
- `app/db/`: infrastructure for metadata, engines and session factories.
  Repositories will use `session_factory.begin()` for transaction scopes, with
  automatic commit, rollback and cleanup. Engine owners must dispose engines.
- `app/config/`: settings and logging.
- `migrations/`: Alembic infrastructure and reviewed schema revisions.
- `tests/unit/`, `tests/integration/`: isolated behavior and boundary checks.

Services will return plain entities/DTOs rather than ORM models. Database
infrastructure and migrations may configure SQLAlchemy; routers and services
must not access it. Health uses a service function without an unnecessary class
or database query. SQLite enables foreign keys on every connection.

The supplied project context remains in `tuw-study-bot-astra-context-v3/`.

## Scope

M0 only. M1 will add the Telegram shell, allowed-user restriction, basic
formatting, `/help` and an empty-database `/today` response, after explicit
authorization. TISS, TUWEL, domain models, reminders, scheduling, worksheet/study/
exam planning and AI are deferred to their respective later milestones.
