from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.services import health_service

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status=health_service.get_health_status())
