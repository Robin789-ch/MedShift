import os
from collections.abc import Mapping

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from httpx import AsyncBaseTransport, AsyncClient, HTTPError
from pydantic import ValidationError

from medshift_agent.config import Settings
from medshift_agent.openapi import configure_contract_openapi
from medshift_agent.workspace import (
    FileWorkspace,
    RevisionConflictError,
    WorkspaceCorruptError,
    WorkspaceInvalidError,
    WorkspaceStore,
    WorkspaceVersionUnsupportedError,
)
from medshift_contracts import (
    SHIFT_TYPES,
    ApplicationError,
    ErrorCode,
    ErrorEnvelope,
    HealthResponse,
    InitializedState,
    ScenarioSaveRequest,
    StateResponse,
    UninitializedState,
    Workspace,
    request_invalid_error,
)


class WorkspaceNotInitializedError(Exception):
    pass


def create_app(
    environ: Mapping[str, str] | None = None,
    optimizer_transport: AsyncBaseTransport | None = None,
    workspace: WorkspaceStore | None = None,
) -> FastAPI:
    runtime_environ = os.environ if environ is None else environ
    app = FastAPI(title="MedShift Agent", version="0.2.0")
    workspace_backend = workspace

    def get_workspace() -> WorkspaceStore:
        nonlocal workspace_backend
        if workspace_backend is None:
            settings = Settings.from_environ(runtime_environ)
            workspace_backend = FileWorkspace(settings.workspace_path)
        return workspace_backend

    def error_response(
        status_code: int,
        code: ErrorCode,
        message: str,
    ) -> JSONResponse:
        error = ErrorEnvelope(
            error=ApplicationError(
                code=code,
                message=message,
                details={},
            )
        )
        return JSONResponse(
            status_code=status_code,
            content=error.model_dump(mode="json"),
        )

    def initialized_state(current: Workspace) -> InitializedState:
        return InitializedState(
            initialized=True,
            revision=current.revision,
            scenario=current.scenario,
            shift_types=SHIFT_TYPES,
            policies=[],
            objectives=[],
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_error(
        _request: Request,
        _error: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=request_invalid_error().model_dump(mode="json"),
        )

    @app.exception_handler(RevisionConflictError)
    async def revision_conflict(
        _request: Request,
        _error: RevisionConflictError,
    ) -> JSONResponse:
        return error_response(
            409,
            "revision_conflict",
            "The workspace changed before the Scenario was saved.",
        )

    @app.exception_handler(WorkspaceNotInitializedError)
    async def workspace_not_initialized(
        _request: Request,
        _error: WorkspaceNotInitializedError,
    ) -> JSONResponse:
        return error_response(
            409,
            "workspace_not_initialized",
            "Save a Scenario before using this operation.",
        )

    @app.exception_handler(WorkspaceCorruptError)
    async def workspace_corrupt(
        _request: Request,
        _error: WorkspaceCorruptError,
    ) -> JSONResponse:
        return error_response(
            500,
            "workspace_corrupt",
            "The saved workspace is corrupt.",
        )

    @app.exception_handler(WorkspaceVersionUnsupportedError)
    async def workspace_version_unsupported(
        _request: Request,
        _error: WorkspaceVersionUnsupportedError,
    ) -> JSONResponse:
        return error_response(
            409,
            "workspace_version_unsupported",
            "The saved workspace uses an unsupported schema version.",
        )

    @app.exception_handler(WorkspaceInvalidError)
    async def workspace_invalid(
        _request: Request,
        _error: WorkspaceInvalidError,
    ) -> JSONResponse:
        return error_response(
            422,
            "decision_invalid",
            "The Scenario is incompatible with an active decision.",
        )

    @app.get("/api/state", response_model=StateResponse)
    async def state() -> UninitializedState | InitializedState:
        current = get_workspace().load()
        if current is None:
            return UninitializedState(
                initialized=False,
                shift_types=SHIFT_TYPES,
            )
        return initialized_state(current)

    @app.put("/api/scenario", response_model=InitializedState)
    async def save_scenario(request: ScenarioSaveRequest) -> InitializedState:
        saved = get_workspace().save_scenario(
            request.base_revision,
            request.scenario,
        )
        return initialized_state(saved)

    @app.post("/api/chat")
    async def chat() -> JSONResponse:
        if get_workspace().load() is None:
            raise WorkspaceNotInitializedError
        return JSONResponse(status_code=501, content={})

    @app.post("/api/solve")
    async def solve() -> JSONResponse:
        if get_workspace().load() is None:
            raise WorkspaceNotInitializedError
        return JSONResponse(status_code=501, content={})

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
