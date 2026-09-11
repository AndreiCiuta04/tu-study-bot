"""Orchestrate TUWEL import; only repositories access the database."""

from datetime import datetime, time, timedelta

from app.entities.events import EventData
from app.integrations.tuwel.client import TuwelClient
from app.integrations.tuwel.errors import TuwelAccessError, TuwelResponseError
from app.integrations.tuwel.mapper import (
    CourseMapping,
    map_assignment,
    map_calendar,
    map_course,
)
from app.repositories.unit_of_work import UnitOfWork
from app.services.countdown import VIENNA

REQUIRED_FUNCTIONS = {
    "core_enrol_get_users_courses",
    "mod_assign_get_assignments",
    "core_calendar_get_calendar_events",
}


class TuwelSyncService:
    def __init__(self, client: TuwelClient, unit_of_work: UnitOfWork) -> None:
        self._client = client
        self._unit_of_work = unit_of_work

    async def sync(
        self,
        mappings: dict[int, CourseMapping],
        now: datetime | None = None,
    ) -> int:
        now = now if now is not None else datetime.now(VIENNA)
        if now.utcoffset() is None:
            raise ValueError("Sync requires a timezone-aware clock")
        site = await self._client.site_info()
        functions = {function.name for function in site.functions}
        if not REQUIRED_FUNCTIONS <= functions:
            raise TuwelAccessError()
        courses = await self._client.courses(site.userid)
        by_id = {course.id: course for course in courses}
        if not mappings and courses:
            raise ValueError("Configure TUW_TUWEL_COURSES to select course offerings")
        if not mappings:
            return 0
        if not mappings.keys() <= by_id.keys():
            raise ValueError("A configured TUWEL course is not enrolled")
        selected = {
            cid: map_course(by_id[cid], mapping) for cid, mapping in mappings.items()
        }
        course_ids = tuple(selected)
        assignments = await self._client.assignments(course_ids)
        start = datetime.combine(now.astimezone(VIENNA).date(), time.min, VIENNA)
        calendar = await self._client.calendar(
            course_ids,
            int(start.timestamp()),
            int((start + timedelta(days=90)).timestamp()),
        )
        records: dict[str, tuple[int, EventData]] = {}
        assignment_courses: dict[int, int] = {}
        for group in assignments.courses:
            if group.id not in selected:
                raise TuwelResponseError()
            for assignment in group.assignments:
                if assignment.course != group.id or assignment.id in assignment_courses:
                    raise TuwelResponseError()
                assignment_courses[assignment.id] = group.id
                submission = None
                if "mod_assign_get_submission_status" in functions:
                    submission = await self._client.submission(assignment.id)
                data = map_assignment(assignment, submission, site.userid)
                records[data.source_id] = (group.id, data)
        for event in calendar.events:
            if event.courseid not in selected or not event.visible:
                continue
            if event.modulename == "assign" and event.instance > 0:
                if event.instance in assignment_courses:
                    if assignment_courses[event.instance] != event.courseid:
                        raise TuwelResponseError()
                    # get_assignments applies Moodle's user/group overrides;
                    # submission status can additionally expose an extension.
                    # Keep this authoritative activity record, not its calendar copy.
                    continue
                if event.eventtype != "due":
                    continue
            data = map_calendar(event)
            record = (event.courseid, data)
            if data.source_id in records and records[data.source_id] != record:
                raise TuwelResponseError()
            records[data.source_id] = record
        # All HTTP and mapping completes before any database write.
        with self._unit_of_work.transaction() as repositories:
            ids = {
                cid: repositories.courses.upsert(course, now)
                for cid, course in selected.items()
            }
            for cid, data in records.values():
                repositories.events.upsert(ids[cid], data, now)
        return len(records)
