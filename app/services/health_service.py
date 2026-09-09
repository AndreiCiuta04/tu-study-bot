"""Application liveness, independent of transports and persistence."""

from typing import Literal


def get_health_status() -> Literal["ok"]:
    return "ok"
