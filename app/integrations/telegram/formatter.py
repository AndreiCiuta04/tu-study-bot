"""Plain-text Telegram responses."""

from app.entities.events import ExamOverview


def format_help() -> str:
    return (
        "/help — Show available commands\n"
        "/today — Show today's overview\n/exams — Show upcoming exams"
    )


def format_today(items: tuple[str, ...]) -> str:
    if not items:
        return "Nothing planned for today yet."
    return "Today\n" + "\n".join(f"• {item}" for item in items)


def format_exams(exams: tuple[ExamOverview, ...]) -> tuple[str, ...]:
    if not exams:
        return ("No upcoming exams found.",)
    messages = []
    message = "📚 Upcoming exams"
    for overview in exams:
        exam = overview.exam
        countdown = (
            "Today" if overview.days_remaining == 0 else f"D-{overview.days_remaining}"
        )
        # Starts are returned in Vienna time by the persistence boundary.
        date_text = f"{exam.starts_at.day} {exam.starts_at:%b %Y}"
        entry = f"\n\n{exam.course_name}\n{exam.title}\n{date_text} — {countdown}"
        if len((message + entry).encode("utf-16-le")) // 2 > 4000:
            messages.append(message)
            message = "📚 Upcoming exams"
        message += entry
    messages.append(message)
    return tuple(messages)
