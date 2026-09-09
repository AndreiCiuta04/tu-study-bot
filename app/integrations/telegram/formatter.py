"""Plain-text Telegram responses."""


def format_help() -> str:
    return "/help — Show available commands\n/today — Show today's overview"


def format_today(items: tuple[str, ...]) -> str:
    if not items:
        return "Nothing planned for today yet."
    return "Today\n" + "\n".join(f"• {item}" for item in items)
