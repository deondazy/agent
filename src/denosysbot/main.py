"""FastAPI entrypoint."""

from fastapi import FastAPI

from denosysbot.api.routes.runs import router as run_router
from denosysbot.adapters.models.factory import build_model_gateway
from denosysbot.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="DenosysBot-style autonomous coding agent API",
    )
    app.state.model_gateway = build_model_gateway(settings)
    app.state.model_provider_order = [provider.name for provider in app.state.model_gateway.providers]

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok", "env": settings.app_env}

    app.include_router(run_router)
    return app


app = create_app()
