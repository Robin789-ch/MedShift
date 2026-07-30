import os
from collections.abc import Mapping

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from httpx import AsyncBaseTransport, AsyncClient, HTTPError
from pydantic import ValidationError

from medshift_agent.config import Settings
from medshift_agent.openapi import configure_contract_openapi
from medshift_contracts import HealthResponse, request_invalid_error


def create_app(
    environ: Mapping[str, str] | None = None,
    optimizer_transport: AsyncBaseTransport | None = None,
) -> FastAPI:
    runtime_environ = os.environ if environ is None else environ
    app = FastAPI(title="MedShift Agent", version="0.2.0")

    @app.exception_handler(RequestValidationError)
    async def request_validation_error(
        _request: Request,
        _error: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=request_invalid_error().model_dump(mode="json"),
        )

    @app.get("/api/health", response_model=HealthResponse)
    async def health() -> HealthResponse | JSONResponse:
        try:
            settings = Settings.from_environ(runtime_environ)
        except (KeyError, ValueError):
            unavailable = HealthResponse(
                service="agent",
                status="error",
                checks={
                    "configuration": "error",
                    "optimizer": "not_checked",
                },
            )
            return JSONResponse(
                status_code=503,
                content=unavailable.model_dump(),
            )

        try:
            async with AsyncClient(
                transport=optimizer_transport,
                timeout=settings.optimizer_timeout_seconds,
            ) as client:
                response = await client.get(f"{settings.optimizer_url}/health")
                optimizer_health = HealthResponse.model_validate(response.json())
            optimizer_ready = (
                response.is_success
                and optimizer_health.service == "optimizer"
                and optimizer_health.status == "ok"
            )
        except (HTTPError, ValidationError):
            optimizer_ready = False

        if not optimizer_ready:
            unavailable = HealthResponse(
                service="agent",
                status="error",
                checks={
                    "configuration": "ok",
                    "optimizer": "error",
                },
            )
            return JSONResponse(
                status_code=503,
                content=unavailable.model_dump(),
            )

        return HealthResponse(
            service="agent",
            status="ok",
            checks={
                "configuration": "ok",
                "optimizer": "ok",
            },
        )

    configure_contract_openapi(app)
    return app


app = create_app()
