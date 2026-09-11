# TUWEL integration

## Access

The importer sends form-encoded POST requests to
`https://tuwel.tuwien.ac.at/webservice/rest/server.php`, with `wstoken`,
`wsfunction`, and `moodlewsrestformat=json`. The token is sent in the request
body, never in URLs or stored in the database.

Set `TUW_TUWEL_TOKEN` in your private `.env` to a manually obtained, authorized
Moodle web-service token. `TokenAuth` implements the `TuwelAuth` interface.
Token acquisition/refresh, interactive login and MFA remain outside this
application. No passwords, OTPs, cookies or browser sessions are handled.

A credential-free probe of TUWEL's REST endpoint returned Moodle JSON
`errorcode=invalidtoken`. The data contracts below were inspected in
[official Moodle 5.0 source](https://github.com/moodle/moodle/tree/MOODLE_500_STABLE).
No authenticated TUWEL response was obtained during development; fixtures are
synthetic projections of those documented contracts. A particular token's
available functions and permissions must still be verified on the live site.
The importer checks the function list supplied by `core_webservice_get_site_info`.

## Functions and fields

| Function | Parameters / fields used |
| --- | --- |
| `core_webservice_get_site_info` | Current `userid`; available `functions[].name` |
| `core_enrol_get_users_courses` | `userid`; course `id`, `fullname`, `shortname`, `idnumber`, `visible`; optional `startdate/enddate` |
| `mod_assign_get_assignments` | `courseids[]`; `courses[].id/assignments[]`; assignment `id`, `cmid`, `course`, `name`, `duedate`, `allowsubmissionsfromdate`, `teamsubmission` |
| `core_calendar_get_calendar_events` | `events[courseids][]`; options `timestart/timeend`, `ignorehidden=1`, `userevents=0`, `siteevents=0`; event `id`, `courseid`, `name`, `modulename`, `instance`, `eventtype`, `timestart`, `timeduration`, `visible` |
| `mod_assign_get_submission_status` | `assignid`, `userid=0` (current user); optional `lastattempt.submission.status/userid`, `teamsubmission`, `extensionduedate` |

Definitions: [courses](https://github.com/moodle/moodle/blob/MOODLE_500_STABLE/enrol/externallib.php),
[calendar](https://github.com/moodle/moodle/blob/MOODLE_500_STABLE/calendar/externallib.php),
[assignments/submission](https://github.com/moodle/moodle/blob/MOODLE_500_STABLE/mod/assign/externallib.php).

Missing required capabilities fail explicitly. Submission lookup is optional
when the token does not advertise that function; state remains unknown.
If an advertised function fails, the sync fails rather than silently losing data.

## Course selection and identity

`core_enrol_get_users_courses` retrieves the user's enrolled courses. Choose
which offerings to import using `TUW_TUWEL_COURSES`, a JSON map from Moodle
course ID to verified course number and semester. Find the Moodle ID in the
course URL (`/course/view.php?id=...`). Example shape:

```text
{"<moodle-course-id>":{"course_code":"<TU-course-number>","semester":"<YYYYS-or-YYYYW>"}}
```

Course numbers normalize from `194.025` to `194025`. Existing TISS courses
with the same number and semester are reused. Moodle's `idnumber` is arbitrary
text, not a guaranteed semester field; if it is exactly a course number it is
checked against the mapping. Shortnames, start dates and titles are never used
to guess a semester. A missing enrollment or conflicting mapping fails before
writing. Explicit selection allows late deadlines from older course offerings;
there is no automatic semester filter.

Event identity uses `source=tuwel` with namespaced, source-provided identifiers:

- Assignments: `assign:<assignment.id>`.
- Calendar assignment due events with `modulename=assign` and a positive
  `instance`: the same `assign:<instance>` identity.
- Other calendar events: `calendar:<event.id>`.

Assignment records take precedence over their calendar copies. Moodle's
assignment function applies user/group overrides; an explicitly returned
submission extension overrides its due date. Calendar-only assignments can
later be enriched by the activity response without creating another row.
Unmatched calendar records retain their own IDs; no title/date fuzzy matching
is performed. Assignment opening/calendar copies are omitted when the activity
is present. A calendar-only assignment imports its due event, not its opening.

## Semantics and limitations

- Assignment dates are imported for every selected visible activity returned.
  Calendar retrieval covers today through 90 days ahead; no pagination or
  arbitrary result limit is imposed by the chosen function.
- Unix timestamps convert to aware Europe/Vienna values. A zero assignment
  timestamp means unknown/unset, never 1970. `due_at` and `starts_at` are
  distinct; assignments without either are retained but omitted from date views.
- Only structured calendar module/type fields determine `quiz`,
  `submission_deadline`, `assignment`, or `other`. No UE-test heuristics exist.
  Distinct quiz opening/closing calendar events remain distinct source events.
- Submission states `new/draft/submitted/reopened` are stored only when
  explicitly reported for the current user. Unknown, absent, or team-only
  information stays unknown. Grades and elapsed deadlines imply nothing.
  This is a single-user database; use one TUWEL account.
- Activity URLs use Moodle course-module IDs; calendar-only records link to
  their source calendar event. Tokens and private response bodies are not saved.
- Network/server errors, authentication errors, access errors, malformed
  payloads and warning-bearing partial responses are distinct from valid empty
  responses. Any failure prevents all writes for that sync.
- Repeated imports update the same IDs and refresh `last_seen_at`. Unchanged
  records preserve `updated_at`; changed dates/status refresh it. No absent
  event is deleted, and no change notifications or cancellation inference run.
- `/deadlines` includes due dates from today's Vienna midnight onward,
  including submitted assignments (shown with their reported state).
  `/week` covers today plus six days, ending exclusively at local midnight
  seven days later, combining TISS and TUWEL once per stored Event.
- Migration 0003 adds nullable due/submission fields and allows a missing start.
  Downgrade maps deadline-only rows' due dates into M2's required start; it
  refuses undated rows rather than inventing timestamps.
