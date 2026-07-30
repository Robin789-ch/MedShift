from collections.abc import Callable
from importlib import import_module

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from medshift_contracts import HealthResponse, request_invalid_error


def check_optimizer_imports() -> None:
    import_module("ortools.sat.python.cp_model")


def create_app(import_check: Callable[[], None] = check_optimizer_imports) -> FastAPI:
    app = FastAPI(title="MedShift Optimizer", version="0.2.0")

    @app.exception_handler(RequestValidationError)
    async def request_validation_error(
        _request: Request,
        _error: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=request_invalid_error().model_dump(mode="json"),
        )

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse | JSONResponse:
        try:
            import_check()
        except ImportError:
            unavailable = HealthResponse(
                service="optimizer",
                status="error",
                checks={"imports": "error"},
            )
            return JSONResponse(
                status_code=503,
                content=unavailable.model_dump(),
            )

        return HealthResponse(
            service="optimizer",
            status="ok",
            checks={"imports": "ok"},
        )

    return app


app = create_app()
