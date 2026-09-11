"""Plain-text Telegram responses."""

from app.entities.events import EventOverview, ExamOverview


def format_help() -> str:
    return (
        "/help — Show available commands\n"
        "/today — Show today's overview\n/exams — Show upcoming exams\n"
        "/deadlines — Show upcoming deadlines\n/week — Show the next 7 days"
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


def format_events(
    events: tuple[EventOverview, ...], *, week: bool = False
) -> tuple[str, ...]:
    if not events:
        return (
            "No events in the next 7 days." if week else "No upcoming deadlines found.",
        )
    heading = "📅 Next 7 days" if week else "📌 Upcoming deadlines"
    messages = []
    message = heading
    for item in events:
        event = item.event
        at = event.occurs_at
        countdown = "Today" if item.days_remaining == 0 else f"D-{item.days_remaining}"
        status = f" [{event.submission_status}]" if event.submission_status else ""
        entry = (
            f"\n\n{event.course_name}\n{event.title} — "
            f"{at.day} {at:%b}, {at:%H:%M} — {countdown}{status}"
        )
        if len((message + entry).encode("utf-16-le")) // 2 > 4000:
            messages.append(message)
            message = heading
        message += entry
    messages.append(message)
    return tuple(messages)
