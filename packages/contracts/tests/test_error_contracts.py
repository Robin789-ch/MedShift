import pytest
from pydantic import ValidationError

from medshift_contracts import ErrorEnvelope, Workspace


def test_every_stable_error_code_round_trips() -> None:
    codes = [
        "request_invalid",
        "workspace_not_initialized",
        "workspace_corrupt",
        "workspace_version_unsupported",
        "revision_conflict",
        "proposal_pending",
        "proposal_not_found",
        "decision_invalid",
        "agent_unavailable",
        "optimizer_unavailable",
        "model_invalid",
        "solve_failed",
    ]

    for code in codes:
        raw_error = {
            "error": {
                "code": code,
                "message": "Stable public message.",
                "details": {},
            }
        }
        assert ErrorEnvelope.model_validate(raw_error).model_dump(
            mode="json"
        ) == raw_error


def test_workspace_rejects_an_unsupported_schema_version() -> None:
    unsupported_workspace = {
        "schema_version": 2,
        "revision": 1,
        "scenario": {
            "planning_weeks": 1,
            "employees": [
                {
                    "employee_id": "11111111-1111-1111-1111-111111111111",
                    "display_name": "Avery",
                    "overtime_hours": 0,
                    "weekly_hours_ceiling": 40,
                }
            ],
            "departments": [],
            "planning_entries": [],
        },
        "policies": [],
        "objectives": [],
    }

    with pytest.raises(ValidationError) as error:
        Workspace.model_validate(unsupported_workspace)

    assert error.value.errors()[0]["type"] == "literal_error"
