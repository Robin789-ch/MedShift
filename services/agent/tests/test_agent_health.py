import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport

from medshift_agent.app import create_app
from medshift_contracts import Scenario


def valid_environ(**overrides: str) -> dict[str, str]:
    environ = {
        "OPENROUTER_API_KEY": "",
        "OPENROUTER_MODEL": "",
        "OPTIMIZER_URL": "http://optimizer:8001",
        "WORKSPACE_PATH": "/data/workspace.json",
        "MODEL_TIMEOUT_SECONDS": "60",
        "OPTIMIZER_TIMEOUT_SECONDS": "70",
        "LOG_LEVEL": "INFO",
    }
    environ.update(overrides)
    return environ


def test_health_reports_configuration_and_optimizer_readiness() -> None:
    optimizer = FastAPI()

    @optimizer.get("/health")
    def optimizer_health() -> dict[str, object]:
        return {
            "service": "optimizer",
            "status": "ok",
            "checks": {"imports": "ok"},
        }

    agent = create_app(
        environ=valid_environ(),
        optimizer_transport=ASGITransport(app=optimizer),
    )

    response = TestClient(agent).get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "service": "agent",
        "status": "ok",
        "checks": {
            "configuration": "ok",
            "optimizer": "ok",
        },
    }


def test_health_reports_configuration_failure() -> None:
    agent = create_app(
        environ=valid_environ(OPTIMIZER_URL="not-a-url"),
    )

    response = TestClient(
        agent,
        raise_server_exceptions=False,
    ).get("/api/health")

    assert response.status_code == 503
    assert response.json() == {
        "service": "agent",
        "status": "error",
        "checks": {
            "configuration": "error",
            "optimizer": "not_checked",
        },
    }


def test_health_reports_optimizer_failure() -> None:
    optimizer = FastAPI()

    @optimizer.get("/health", status_code=503)
    def optimizer_health() -> dict[str, object]:
        return {
            "service": "optimizer",
            "status": "error",
            "checks": {"imports": "error"},
        }

    agent = create_app(
        environ=valid_environ(),
        optimizer_transport=ASGITransport(app=optimizer),
    )

    response = TestClient(
        agent,
        raise_server_exceptions=False,
    ).get("/api/health")

    assert response.status_code == 503
    assert response.json() == {
        "service": "agent",
        "status": "error",
        "checks": {
            "configuration": "ok",
            "optimizer": "error",
        },
    }


def test_request_validation_uses_the_stable_error_envelope() -> None:
    agent = create_app(environ=valid_environ())

    @agent.post("/api/test-contract", response_model=Scenario)
    def accept_scenario(scenario: Scenario) -> Scenario:
        return scenario

    response = TestClient(agent).post(
        "/api/test-contract",
        json={"planning_weeks": 0},
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "request_invalid",
            "message": "The request does not match the expected contract.",
            "details": {},
        }
    }


def test_openapi_publishes_all_contracts_with_stable_validation_errors() -> None:
    agent = create_app(environ=valid_environ())

    @agent.post("/api/test-contract", response_model=Scenario)
    def accept_scenario(scenario: Scenario) -> Scenario:
        return scenario

    openapi = agent.openapi()
    schemas = openapi["components"]["schemas"]

    assert {
        "ErrorEnvelope",
        "Objective",
        "Policy",
        "Proposal",
        "ProposalChange",
        "Scenario",
        "SolveRequest",
        "SolveResult",
        "StateResponse",
        "Workspace",
        "WorkspaceChange",
    } <= schemas.keys()
    assert "HTTPValidationError" not in schemas
    assert "ValidationError" not in schemas
    assert openapi["paths"]["/api/test-contract"]["post"]["responses"]["422"] == {
        "description": "Request Invalid",
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/ErrorEnvelope"}
            }
        },
    }
    assert json.dumps(
        create_app(environ=valid_environ()).openapi(),
        sort_keys=True,
    ) == json.dumps(
        create_app(environ=valid_environ()).openapi(),
        sort_keys=True,
    )
