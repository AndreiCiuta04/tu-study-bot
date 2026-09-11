"""Validated subsets of the official Moodle web-service response contracts."""

from pydantic import BaseModel, ConfigDict, Field


class WireModel(BaseModel):
    model_config = ConfigDict(frozen=True, hide_input_in_errors=True)


class Function(WireModel):
    name: str


class SiteInfo(WireModel):
    userid: int = Field(gt=0)
    functions: tuple[Function, ...]


class Course(WireModel):
    id: int = Field(gt=0)
    fullname: str = Field(min_length=1, max_length=500)
    shortname: str
    idnumber: str
    visible: int
    startdate: int | None = None
    enddate: int | None = None


class Assignment(WireModel):
    id: int = Field(gt=0)
    cmid: int = Field(gt=0)
    course: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=500)
    duedate: int = Field(ge=0)
    allowsubmissionsfromdate: int = Field(ge=0)
    teamsubmission: int


class AssignmentCourse(WireModel):
    id: int = Field(gt=0)
    assignments: tuple[Assignment, ...]


class AssignmentResponse(WireModel):
    courses: tuple[AssignmentCourse, ...]


class CalendarEvent(WireModel):
    id: int = Field(gt=0)
    courseid: int = Field(ge=0)
    name: str = Field(min_length=1, max_length=500)
    modulename: str | None = None
    instance: int = Field(ge=0)
    eventtype: str
    timestart: int = Field(gt=0)
    timeduration: int = Field(ge=0)
    visible: int


class CalendarResponse(WireModel):
    events: tuple[CalendarEvent, ...]


class Submission(WireModel):
    status: str
    userid: int | None = None


class LastAttempt(WireModel):
    submission: Submission | None = None
    teamsubmission: Submission | None = None
    extensionduedate: int = Field(default=0, ge=0)


class SubmissionResponse(WireModel):
    lastattempt: LastAttempt | None = None
