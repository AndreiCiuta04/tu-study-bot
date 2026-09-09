"""Explicit one-shot TISS import, without a scheduler."""

import argparse
import asyncio
from datetime import date

from app.bootstrap import sync_tiss
from app.config.settings import Settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Import public TISS exam dates")
    parser.add_argument("course", help="Course code, e.g. 194.025")
    parser.add_argument("semester", help="Course offering, e.g. 2026S")
    parser.add_argument("--from-date", type=date.fromisoformat)
    args = parser.parse_args()
    settings = Settings()
    try:
        count = asyncio.run(
            sync_tiss(
                settings.database_url,
                args.course,
                args.semester,
                args.from_date,
            )
        )
    except Exception as error:
        parser.exit(
            1, f"TISS sync failed ({type(error).__name__}); no changes saved.\n"
        )
    print(f"Synchronized {count} exam entries.")


if __name__ == "__main__":
    main()
