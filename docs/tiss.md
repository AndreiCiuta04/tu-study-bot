# TISS data contract

## Public endpoints

- Course metadata: `GET https://tiss.tuwien.ac.at/api/course/{number}-{semester}`.
- Exams: `GET https://tiss.tuwien.ac.at/api/course/{number}/examDates`,
  optionally `?fromDate=YYYY-MM-DD`.

Course numbers are normalized consistently: `194.025` becomes `194025`.
Synchronization validates the course offering before fetching exams.
The exam endpoint is course-wide and does not report the source semester.
The CLI's explicit semester chooses which course offering owns imported events;
it is not inferred from the exam date.

These public responses were inspected on 2026-09-09:

- [194025, 2026S course metadata](https://tiss.tuwien.ac.at/api/course/194025-2026S)
- [194025 exam dates](https://tiss.tuwien.ac.at/api/course/194025/examDates)

Course XML uses the `course/v10` namespace with `courseNumber`,
`semesterCode`, and a localized `title` (`i18n/v10`); English is preferred,
with German as fallback. Other metadata is outside this import's scope.

The observed exam response has a `tuvienna` root with `version="1.0"` and
namespace `https://tiss.tuwien.ac.at/api/schemas/exams/v10`. Each `exam` has:

| XML field | Observed value | Handling |
| --- | --- | --- |
| `@id` | `528535` | Actual TISS source identifier |
| `title` | `Exam 2nd Attempt  (2026-09-09)` | Event title |
| `examinationBegin` | `2026-09-09T10:00:00.000+02:00` | Event start |
| `applicationEnd` | `2026-09-06T23:59:00.000+02:00` | Parsed only |
| `deregistrationEnd` | `2026-09-07T23:59:00.000+02:00` | Parsed only |

The exam fixture preserves this public response. The course fixture is a
minimal projection of the inspected public course metadata, excluding people
and unrelated text. Tests never contact TISS.

## Identity and updates

`(source, source_id)` is unique; `source_id` uses the actual `exam/@id`.
No synthetic identity or date/title-derived identity is used. Missing IDs cause
validation failure before persistence instead of an invented ID. A changed
title or start time with the same ID updates the existing event.

The exam response supplies no detail URL, so provenance links point to the
selected public course page. Registration cutoffs are not persisted as events.

An unchanged record preserves `created_at`, `first_seen_at`, and `updated_at`;
successful sightings refresh `last_seen_at`. Meaningful updates refresh
`updated_at`. All writes in a single-course import commit or roll back together.
Source IDs stay unique across course offerings, including when an explicit
later import associates an exam with another offering.

A 404 from the exam endpoint means no available dates after successful course
validation. A course 404, network error, server error, or malformed response
fails the import. Empty or missing results never delete existing events.
No cancellation inference or change notifications are implemented.

## Time and boundaries

Naive source times are interpreted in Europe/Vienna; ambiguous or nonexistent
floating DST times are rejected. Offset-aware values retain their instant.
Database timestamps are normalized to naive UTC at the storage boundary and
always returned as aware Vienna datetimes, consistently on SQLite/PostgreSQL.
No application service receives naive persisted timestamps.

Exam queries include today's Vienna calendar date and future dates, including
exams earlier today. Day differences use local dates, not elapsed seconds.

The client only fetches and parses XML. The mapper produces immutable domain
values. SyncService coordinates the client, mapper, and repositories inside a
repository-owned transaction. Telegram handlers call an injected exam service
operation; the composition root wires and closes database resources. Synchronous
exam reads run off the Telegram event loop. No authenticated TISS access,
calendar scraping, scheduler, or TUWEL integration is included.
