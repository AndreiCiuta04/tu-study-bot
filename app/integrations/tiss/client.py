"""Public TISS HTTP and XML parsing; no persistence or business logic."""

import re
from datetime import date

import httpx
from defusedxml.ElementTree import fromstring

from app.integrations.tiss.dtos import TissCourse, TissExam

BASE_URL = "https://tiss.tuwien.ac.at"
EXAMS_NAMESPACE = "https://tiss.tuwien.ac.at/api/schemas/exams/v10"


class TissPayloadError(ValueError):
    pass


def normalize_course_number(value: str) -> str:
    value = value.strip().upper()
    if not re.fullmatch(r"[0-9A-Z]{3}\.?[0-9A-Z]{3}", value):
        raise ValueError("Expected a course number such as 194.025 or 194025")
    return value.replace(".", "")


def parse_course(payload: bytes) -> TissCourse:
    root = fromstring(payload)
    course = root.find("{*}course")
    if course is None:
        raise TissPayloadError("TISS response contains no course")
    title = course.findtext("{*}title/{*}en") or course.findtext("{*}title/{*}de")
    return TissCourse.model_validate(
        {
            "course_number": course.findtext("{*}courseNumber"),
            "semester_code": course.findtext("{*}semesterCode"),
            "title": title,
        }
    )


def parse_exams(payload: bytes) -> tuple[TissExam, ...]:
    root = fromstring(payload)
    if root.tag != f"{{{EXAMS_NAMESPACE}}}tuvienna":
        raise TissPayloadError("Expected a TISS exams response")
    if any(child.tag != f"{{{EXAMS_NAMESPACE}}}exam" for child in root):
        raise TissPayloadError("Unexpected element in TISS exams response")
    return tuple(
        TissExam.model_validate(
            {
                "id": exam.get("id"),
                "title": exam.findtext("{*}title"),
                "examination_begin": exam.findtext("{*}examinationBegin"),
                "application_end": exam.findtext("{*}applicationEnd"),
                "deregistration_end": exam.findtext("{*}deregistrationEnd"),
            }
        )
        for exam in root
    )


class TissClient:
    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def course(self, course_code: str, semester: str) -> TissCourse:
        course_code = normalize_course_number(course_code)
        if not re.fullmatch(r"\d{4}[SW]", semester):
            raise ValueError("Expected semester YYYY[S/W]")
        response = await self._http.get(
            f"{BASE_URL}/api/course/{course_code}-{semester}"
        )
        response.raise_for_status()
        return parse_course(response.content)

    async def exams(
        self, course_code: str, from_date: date | None = None
    ) -> tuple[TissExam, ...]:
        course_code = normalize_course_number(course_code)
        response = await self._http.get(
            f"{BASE_URL}/api/course/{course_code}/examDates",
            params={"fromDate": from_date.isoformat()} if from_date else None,
        )
        # SyncService validates the course first, so this means no available dates.
        if response.status_code == 404:
            return ()
        response.raise_for_status()
        return parse_exams(response.content)
