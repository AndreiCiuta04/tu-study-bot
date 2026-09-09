"""TISS XML values, separate from internal domain values."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TissCourse(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)
    course_number: str = Field(pattern=r"^[0-9A-Z]{6}$")
    semester_code: str = Field(pattern=r"^\d{4}[SW]$")
    title: str = Field(min_length=1, max_length=500)


class TissExam(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)
    id: str = Field(min_length=1, max_length=500)
    title: str = Field(min_length=1, max_length=500)
    examination_begin: datetime
    application_end: datetime | None = None
    deregistration_end: datetime | None = None
