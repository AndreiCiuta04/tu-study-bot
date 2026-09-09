from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.app import create_app
from app.config.settings import Settings
from app.services.health_service import get_health_status


def test_health_service() -> None:
    assert get_health_status() == "ok"


def test_health_router_calls_service() -> None:
    application = create_app(Settings(_env_file=None))
    with patch(
        "app.routers.health_router.health_service.get_health_status",
        return_value="ok",
    ) as service:
        with TestClient(application) as client:
            response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    service.assert_called_once_with()
