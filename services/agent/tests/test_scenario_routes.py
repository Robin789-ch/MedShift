import json
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from medshift_agent.app import create_app
from medshift_agent.workspace import FileWorkspace, InMemoryWorkspace
from medshift_contracts import (
    SHIFT_TYPES,
    ConsecutiveShiftLimit,
    Scenario,
    ShiftType,
    Workspace,
)


def minimum_scenario(display_name: str = "Avery") -> dict[str, object]:
    return {
        "planning_weeks": 1,
        "employees": [
            {
                "employee_id": "11111111-1111-1111-1111-111111111111",
                "display_name": display_name,
                "overtime_hours": 0,
                "weekly_hours_ceiling": 40,
            }
        ],
        "departments": [],
        "planning_entries": [],
    }


def test_state_reports_an_uninitialized_workspace() -> None:
    client = TestClient(create_app(workspace=InMemoryWorkspace()))

    response = client.get("/api/state")

    assert response.status_code == 200
    assert response.json() == {
        "initialized": False,
        "shift_types": [
            shift_type.model_dump(mode="json") for shift_type in SHIFT_TYPES
        ],
    }


def test_first_scenario_save_returns_revision_one_and_reloads() -> None:
    client = TestClient(create_app(workspace=InMemoryWorkspace()))

    response = client.put(
        "/api/scenario",
        json={
            "base_revision": None,
            "scenario": minimum_scenario(),
        },
    )

    assert response.status_code == 200
    assert response.json()["initialized"] is True
    assert response.json()["revision"] == 1
    assert response.json()["scenario"] == minimum_scenario()
    assert client.get("/api/state").json() == response.json()


def test_agent_restart_restores_the_saved_scenario(tmp_path: Path) -> None:
    workspace_path = tmp_path / "workspace.json"
    first_agent = TestClient(
        create_app(workspace=FileWorkspace(workspace_path)),
    )
    saved = first_agent.put(
        "/api/scenario",
        json={"base_revision": None, "scenario": minimum_scenario()},
    )

    restarted_agent = TestClient(
        create_app(workspace=FileWorkspace(workspace_path)),
    )

    assert restarted_agent.get("/api/state").json() == saved.json()


def test_stale_scenario_save_returns_stable_error_without_overwriting() -> None:
    client = TestClient(create_app(workspace=InMemoryWorkspace()))
    first = client.put(
        "/api/scenario",
        json={"base_revision": None, "scenario": minimum_scenario()},
    )
    second = client.put(
        "/api/scenario",
        json={
            "base_revision": first.json()["revision"],
            "scenario": minimum_scenario("Blair"),
        },
    )

    stale = client.put(
        "/api/scenario",
        json={
            "base_revision": first.json()["revision"],
            "scenario": minimum_scenario("Casey"),
        },
    )

    assert second.json()["revision"] == 2
    assert stale.status_code == 409
    assert stale.json() == {
        "error": {
            "code": "revision_conflict",
            "message": "The workspace changed before the Scenario was saved.",
            "details": {},
        }
    }
    assert client.get("/api/state").json() == second.json()


def test_invalid_prospective_workspace_returns_stable_error_without_saving() -> None:
    initial = Workspace(
        schema_version=1,
        revision=4,
        scenario=Scenario.model_validate(
            {**minimum_scenario(), "planning_weeks": 2},
        ),
        policies=[
            ConsecutiveShiftLimit(
                id=UUID("22222222-2222-2222-2222-222222222222"),
                kind="consecutive_shift_limit",
                shift_type=ShiftType.NIGHT,
                minimum_run_length=None,
                maximum_run_length=14,
            )
        ],
        objectives=[],
    )
    workspace = InMemoryWorkspace(initial)
    client = TestClient(create_app(workspace=workspace))

    response = client.put(
        "/api/scenario",
        json={"base_revision": 4, "scenario": minimum_scenario()},
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "decision_invalid",
            "message": "The Scenario is incompatible with an active decision.",
            "details": {},
        }
    }
    assert workspace.load() == initial


@pytest.mark.parametrize("path", ["/api/chat", "/api/solve"])
def test_workspace_operations_require_an_initialized_workspace(path: str) -> None:
    client = TestClient(create_app(workspace=InMemoryWorkspace()))

    response = client.post(path)

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "workspace_not_initialized",
            "message": "Save a Scenario before using this operation.",
            "details": {},
        }
    }


@pytest.mark.parametrize(
    ("contents", "status_code", "code", "message"),
    [
        (
            b"{not-json",
            500,
            "workspace_corrupt",
            "The saved workspace is corrupt.",
        ),
        (
            json.dumps({"schema_version": 2}).encode(),
            409,
            "workspace_version_unsupported",
            "The saved workspace uses an unsupported schema version.",
        ),
    ],
)
def test_state_reports_stable_errors_for_invalid_existing_files(
    tmp_path: Path,
    contents: bytes,
    status_code: int,
    code: str,
    message: str,
) -> None:
    workspace_path = tmp_path / "workspace.json"
    workspace_path.write_bytes(contents)
    client = TestClient(create_app(workspace=FileWorkspace(workspace_path)))

    response = client.get("/api/state")

    assert response.status_code == status_code
    assert response.json() == {
        "error": {
            "code": code,
            "message": message,
            "details": {},
        }
    }
