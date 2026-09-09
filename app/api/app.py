"""ASGI application composition."""

from fastapi import FastAPI

from app.config.logging import configure_logging
from app.config.settings import Settings
from app.routers.health_router import router as health_router


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings if settings is not None else Settings()
    configure_logging(settings.log_level)
    application = FastAPI(title="TUW Study Bot", version="0.1.0")
    application.include_router(health_router)
    return application


app = create_app()
