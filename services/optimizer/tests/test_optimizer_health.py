from fastapi.testclient import TestClient

from medshift_contracts import SolveRequest
from medshift_optimizer.app import create_app


def test_health_reports_optimizer_import_readiness() -> None:
    response = TestClient(create_app()).get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "service": "optimizer",
        "status": "ok",
        "checks": {"imports": "ok"},
    }


def test_health_reports_optimizer_import_failure() -> None:
    def fail_import() -> None:
        raise ImportError

    response = TestClient(
        create_app(import_check=fail_import),
        raise_server_exceptions=False,
    ).get("/health")

    assert response.status_code == 503
    assert response.json() == {
        "service": "optimizer",
        "status": "error",
        "checks": {"imports": "error"},
    }


def test_request_validation_uses_the_stable_error_envelope() -> None:
    optimizer = create_app(import_check=lambda: None)

    @optimizer.post("/test-contract", response_model=SolveRequest)
    def accept_request(request: SolveRequest) -> SolveRequest:
        return request

    response = TestClient(optimizer).post(
        "/test-contract",
        json={"schema_version": 2},
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "request_invalid",
            "message": "The request does not match the expected contract.",
            "details": {},
        }
    }
