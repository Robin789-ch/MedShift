from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from medshift_contracts import SolveRequest, SolveResult


def representative_solve_request() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "workspace_revision": 4,
        "planning_weeks": 1,
        "employees": [
            {
                "employee_id": "11111111-1111-1111-1111-111111111111",
                "overtime_hours": 8,
                "weekly_hours_ceiling": 40,
            }
        ],
        "departments": [
            {
                "department_id": "22222222-2222-2222-2222-222222222222",
                "shift_type": "day",
                "duration_hours": 8,
                "staffing_demand": [1, 1, 1, 1, 1, 0, 0],
            }
        ],
        "planning_entries": [
            {
                "kind": "fixed_assignment",
                "employee_id": "11111111-1111-1111-1111-111111111111",
                "day_index": 0,
                "target": {
                    "kind": "department",
                    "department_id": "22222222-2222-2222-2222-222222222222",
                },
            }
        ],
        "policies": [
            {
                "id": "30000000-0000-0000-0000-000000000001",
                "kind": "consecutive_shift_limit",
                "shift_type": "night",
                "minimum_run_length": None,
                "maximum_run_length": 3,
            }
        ],
        "objectives": [
            {
                "id": "40000000-0000-0000-0000-000000000001",
                "kind": "employee_preference_objective",
                "desired_weight": 5,
                "avoided_weight": 7,
            }
        ],
    }


def test_representative_solve_request_round_trips() -> None:
    raw_request = representative_solve_request()

    assert SolveRequest.model_validate(raw_request).model_dump(
        mode="json"
    ) == raw_request


def test_every_solve_result_variant_round_trips() -> None:
    diagnostics_with_objective: dict[str, Any] = {
        "wall_time_seconds": 0.25,
        "conflicts": 2,
        "branches": 8,
        "objective_value": 15,
        "best_objective_bound": 15.0,
        "contributions": [
            {
                "objective_id": "40000000-0000-0000-0000-000000000001",
                "contribution": 15,
            }
        ],
    }
    diagnostics_without_objective: dict[str, Any] = {
        "wall_time_seconds": 0.25,
        "conflicts": 2,
        "branches": 8,
        "objective_value": None,
        "best_objective_bound": None,
        "contributions": [],
    }
    schedule = {
        "employees": [
            {
                "employee_id": "11111111-1111-1111-1111-111111111111",
                "days": [
                    {
                        "day_index": 0,
                        "shift_type": "day",
                        "department_id": "22222222-2222-2222-2222-222222222222",
                    },
                    {
                        "day_index": 1,
                        "shift_type": "off",
                        "department_id": None,
                    },
                ],
            }
        ]
    }
    results = [
        {
            "status": "optimal",
            "schedule": schedule,
            "diagnostics": diagnostics_with_objective,
        },
        {
            "status": "feasible",
            "schedule": schedule,
            "diagnostics": diagnostics_with_objective,
        },
        {
            "status": "infeasible",
            "diagnostics": diagnostics_without_objective,
        },
        {
            "status": "unknown",
            "diagnostics": diagnostics_without_objective,
        },
    ]
    adapter: TypeAdapter[SolveResult] = TypeAdapter(SolveResult)

    assert [
        adapter.dump_python(adapter.validate_python(result), mode="json")
        for result in results
    ] == results


def test_solve_contracts_reject_invalid_revision_schedule_and_diagnostics() -> None:
    invalid_revision = representative_solve_request()
    invalid_revision["workspace_revision"] = 0
    presentation_metadata = representative_solve_request()
    presentation_metadata["employees"][0]["display_name"] = "Avery"

    uneven_schedule = {
        "status": "optimal",
        "schedule": {
            "employees": [
                {
                    "employee_id": "11111111-1111-1111-1111-111111111111",
                    "days": [
                        {
                            "day_index": 0,
                            "shift_type": "off",
                            "department_id": None,
                        }
                    ],
                },
                {
                    "employee_id": "22222222-2222-2222-2222-222222222222",
                    "days": [
                        {
                            "day_index": 0,
                            "shift_type": "off",
                            "department_id": None,
                        },
                        {
                            "day_index": 1,
                            "shift_type": "off",
                            "department_id": None,
                        },
                    ],
                },
            ]
        },
        "diagnostics": {
            "wall_time_seconds": 0.1,
            "conflicts": 0,
            "branches": 0,
            "objective_value": 0,
            "best_objective_bound": 0.0,
            "contributions": [],
        },
    }
    mismatched_contributions = {
        "status": "unknown",
        "diagnostics": {
            "wall_time_seconds": 1.0,
            "conflicts": 0,
            "branches": 0,
            "objective_value": None,
            "best_objective_bound": None,
            "contributions": [
                {
                    "objective_id": "40000000-0000-0000-0000-000000000001",
                    "contribution": 1,
                }
            ],
        },
    }

    with pytest.raises(ValidationError):
        SolveRequest.model_validate(invalid_revision)
    with pytest.raises(ValidationError):
        SolveRequest.model_validate(presentation_metadata)
    for invalid_result in (uneven_schedule, mismatched_contributions):
        with pytest.raises(ValidationError):
            TypeAdapter(SolveResult).validate_python(invalid_result)
