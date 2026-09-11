"""Moodle REST transport and DTO parsing only."""

from typing import TypeVar

import httpx
from pydantic import BaseModel, TypeAdapter, ValidationError

from app.integrations.tuwel.auth import TuwelAuth
from app.integrations.tuwel.dtos import (
    AssignmentResponse,
    CalendarResponse,
    Course,
    SiteInfo,
    SubmissionResponse,
)
from app.integrations.tuwel.errors import (
    TuwelAccessError,
    TuwelAuthenticationError,
    TuwelNetworkError,
    TuwelResponseError,
)

ENDPOINT = "https://tuwel.tuwien.ac.at/webservice/rest/server.php"
T = TypeVar("T", bound=BaseModel)


class TuwelClient:
    def __init__(self, http: httpx.AsyncClient, auth: TuwelAuth) -> None:
        self._http = http
        self._auth = auth

    async def _call(
        self, function: str, params: dict[str, str] | None = None
    ) -> object:
        data = dict(params or {})
        data.update(
            wstoken=self._auth.token(), wsfunction=function, moodlewsrestformat="json"
        )
        try:
            response = await self._http.post(ENDPOINT, data=data)
        except httpx.RequestError:
            raise TuwelNetworkError() from None
        if response.status_code == 401:
            raise TuwelAuthenticationError()
        if response.status_code == 403:
            raise TuwelAccessError()
        if response.status_code >= 500:
            raise TuwelNetworkError()
        if response.status_code != 200:
            raise TuwelResponseError()
        try:
            payload: object = response.json()
        except ValueError:
            raise TuwelResponseError() from None
        if isinstance(payload, dict):
            code = payload.get("errorcode")
            if code in (
                "invalidtoken",
                "invalidtimedtoken",
                "requireloginerror",
            ):
                raise TuwelAuthenticationError()
            if code in (
                "webservice_access_exception",
                "nopermissions",
                "nopermission",
                "accessdenied",
                "accessexception",
            ):
                raise TuwelAccessError()
            if (
                "exception" in payload
                or "errorcode" in payload
                or payload.get("warnings")
            ):
                raise TuwelResponseError()
        return payload

    async def _model(
        self, function: str, model: type[T], params: dict[str, str] | None = None
    ) -> T:
        payload = await self._call(function, params)
        try:
            return model.model_validate(payload)
        except ValidationError:
            raise TuwelResponseError() from None

    async def site_info(self) -> SiteInfo:
        return await self._model("core_webservice_get_site_info", SiteInfo)

    async def courses(self, userid: int) -> tuple[Course, ...]:
        payload = await self._call(
            "core_enrol_get_users_courses", {"userid": str(userid)}
        )
        try:
            return TypeAdapter(tuple[Course, ...]).validate_python(payload)
        except ValidationError:
            raise TuwelResponseError() from None

    async def assignments(self, course_ids: tuple[int, ...]) -> AssignmentResponse:
        if not course_ids:
            return AssignmentResponse(courses=())
        params = {f"courseids[{i}]": str(cid) for i, cid in enumerate(course_ids)}
        return await self._model(
            "mod_assign_get_assignments", AssignmentResponse, params
        )

    async def calendar(
        self, course_ids: tuple[int, ...], start: int, end: int
    ) -> CalendarResponse:
        if not course_ids:
            return CalendarResponse(events=())
        params = {
            f"events[courseids][{i}]": str(cid) for i, cid in enumerate(course_ids)
        }
        params.update(
            {
                "options[timestart]": str(start),
                "options[timeend]": str(end),
                "options[userevents]": "0",
                "options[siteevents]": "0",
                "options[ignorehidden]": "1",
            }
        )
        return await self._model(
            "core_calendar_get_calendar_events", CalendarResponse, params
        )

    async def submission(self, assignment_id: int) -> SubmissionResponse:
        return await self._model(
            "mod_assign_get_submission_status",
            SubmissionResponse,
            {"assignid": str(assignment_id), "userid": "0"},
        )
