from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport

from medshift_agent.app import create_app


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
