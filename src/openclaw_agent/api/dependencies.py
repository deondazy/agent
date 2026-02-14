"""FastAPI dependency helpers for shared application services."""

from fastapi import HTTPException, Request

from openclaw_agent.adapters.models.gateway import ModelGateway


def get_model_gateway(request: Request) -> ModelGateway:
    """Resolve the runtime model gateway from FastAPI app state."""

    gateway = getattr(request.app.state, "model_gateway", None)
    if isinstance(gateway, ModelGateway):
        return gateway
    raise HTTPException(status_code=500, detail="model_gateway_unavailable")
