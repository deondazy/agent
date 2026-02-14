"""FastAPI entrypoint."""

from fastapi import FastAPI

from openclaw_agent.api.routes.runs import router as run_router
from openclaw_agent.adapters.models.factory import build_model_gateway
from openclaw_agent.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="OpenClaw-style autonomous coding agent API",
    )
    app.state.model_gateway = build_model_gateway(settings)
    app.state.model_provider_order = [provider.name for provider in app.state.model_gateway.providers]

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok", "env": settings.app_env}

    app.include_router(run_router)
    return app


app = create_app()
