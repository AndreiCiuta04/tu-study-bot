"""Explicit authenticated import; token acquisition remains outside this process."""

import asyncio

from app.bootstrap import sync_tuwel
from app.config.settings import TuwelSettings
from app.integrations.tuwel.errors import TuwelError


def main() -> None:
    settings = TuwelSettings()
    try:
        count = asyncio.run(sync_tuwel(settings))
    except TuwelError as error:
        raise SystemExit(str(error)) from None
    except Exception:
        # Never print response bodies, exception details or account configuration.
        raise SystemExit(
            "TUWEL sync failed; check course mappings and database setup."
        ) from None
    print(f"Synchronized {count} TUWEL events.")


if __name__ == "__main__":
    main()
