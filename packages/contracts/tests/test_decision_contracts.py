from typing import Any

from pydantic import TypeAdapter

import pytest
from pydantic import ValidationError

from medshift_contracts import Objective, Policy, Workspace


def test_every_policy_and_objective_variant_round_trips() -> None:
    policies: list[dict[str, Any]] = [
        {
            "id": "10000000-0000-0000-0000-000000000001",
            "kind": "consecutive_shift_limit",
            "shift_type": "night",
            "minimum_run_length": 2,
            "maximum_run_length": 4,
        },
        {
            "id": "10000000-0000-0000-0000-000000000002",
            "kind": "weekly_shift_count_limit",
            "shift_type": "recovery",
            "minimum_count": None,
            "maximum_count": 2,
        },
        {
            "id": "10000000-0000-0000-0000-000000000003",
            "kind": "forbidden_shift_transition",
            "from_shift_type": "night",
            "to_shift_type": "day",
        },
    ]
    objectives: list[dict[str, Any]] = [
        {
            "id": "20000000-0000-0000-0000-000000000001",
            "kind": "consecutive_shift_preference",
            "shift_type": "day",
            "preferred_minimum": {"value": 2, "weight": 5},
            "preferred_maximum": {"value": 4, "weight": 7},
        },
        {
            "id": "20000000-0000-0000-0000-000000000002",
            "kind": "weekly_shift_count_preference",
            "shift_type": "night",
            "preferred_minimum": None,
            "preferred_maximum": {"value": 3, "weight": 11},
        },
        {
            "id": "20000000-0000-0000-0000-000000000003",
            "kind": "shift_transition_preference",
            "from_shift_type": "day",
            "to_shift_type": "night",
            "direction": "discourage",
            "weight": 13,
        },
        {
            "id": "20000000-0000-0000-0000-000000000004",
            "kind": "employee_preference_objective",
            "desired_weight": 17,
            "avoided_weight": 19,
        },
        {
            "id": "20000000-0000-0000-0000-000000000005",
            "kind": "workload_balance_objective",
            "weight": 23,
        },
        {
            "id": "20000000-0000-0000-0000-000000000006",
            "kind": "night_shift_balance_objective",
            "weight": 29,
        },
        {
            "id": "20000000-0000-0000-0000-000000000007",
            "kind": "remaining_overtime_objective",
            "weight": 31,
        },
        {
            "id": "20000000-0000-0000-0000-000000000008",
            "kind": "maximum_remaining_overtime_objective",
            "weight": 37,
        },
        {
            "id": "20000000-0000-0000-0000-000000000009",
            "kind": "excess_recovery_objective",
            "weight": 41,
        },
        {
            "id": "20000000-0000-0000-0000-000000000010",
            "kind": "consecutive_department_continuity_objective",
            "weight": 43,
        },
    ]

    policy_adapter: TypeAdapter[Policy] = TypeAdapter(Policy)
    objective_adapter: TypeAdapter[Objective] = TypeAdapter(Objective)

    assert [
        policy_adapter.dump_python(
            policy_adapter.validate_python(policy),
            mode="json",
        )
        for policy in policies
    ] == policies
    assert [
        objective_adapter.dump_python(
            objective_adapter.validate_python(objective),
            mode="json",
        )
        for objective in objectives
    ] == objectives


def workspace_with(
    *,
    policies: list[dict[str, Any]],
    objectives: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
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
        "policies": policies,
        "objectives": objectives,
    }


def test_workspace_rejects_invalid_decision_identity_bounds_and_natural_keys() -> None:
    duplicate_policy_key = workspace_with(
        policies=[
            {
                "id": "10000000-0000-0000-0000-000000000001",
                "kind": "weekly_shift_count_limit",
                "shift_type": "night",
                "minimum_count": 1,
                "maximum_count": None,
            },
            {
                "id": "10000000-0000-0000-0000-000000000002",
                "kind": "weekly_shift_count_limit",
                "shift_type": "night",
                "minimum_count": None,
                "maximum_count": 4,
            },
        ],
        objectives=[],
    )
    duplicate_objective_key = workspace_with(
        policies=[],
        objectives=[
            {
                "id": "20000000-0000-0000-0000-000000000001",
                "kind": "workload_balance_objective",
                "weight": 1,
            },
            {
                "id": "20000000-0000-0000-0000-000000000002",
                "kind": "workload_balance_objective",
                "weight": 2,
            },
        ],
    )
    duplicate_decision_id = workspace_with(
        policies=[
            {
                "id": "30000000-0000-0000-0000-000000000001",
                "kind": "forbidden_shift_transition",
                "from_shift_type": "night",
                "to_shift_type": "day",
            }
        ],
        objectives=[
            {
                "id": "30000000-0000-0000-0000-000000000001",
                "kind": "night_shift_balance_objective",
                "weight": 1,
            }
        ],
    )
    run_exceeds_horizon = workspace_with(
        policies=[
            {
                "id": "40000000-0000-0000-0000-000000000001",
                "kind": "consecutive_shift_limit",
                "shift_type": "day",
                "minimum_run_length": 8,
                "maximum_run_length": None,
            }
        ],
        objectives=[],
    )

    for invalid_workspace in (
        duplicate_policy_key,
        duplicate_objective_key,
        duplicate_decision_id,
        run_exceeds_horizon,
    ):
        with pytest.raises(ValidationError):
            Workspace.model_validate(invalid_workspace)


def test_workspace_accepts_well_formed_contradictory_decisions() -> None:
    contradictory_workspace = workspace_with(
        policies=[
            {
                "id": "50000000-0000-0000-0000-000000000001",
                "kind": "weekly_shift_count_limit",
                "shift_type": "day",
                "minimum_count": 7,
                "maximum_count": None,
            },
            {
                "id": "50000000-0000-0000-0000-000000000002",
                "kind": "weekly_shift_count_limit",
                "shift_type": "night",
                "minimum_count": 7,
                "maximum_count": None,
            },
        ],
        objectives=[],
    )

    assert Workspace.model_validate(contradictory_workspace).model_dump(
        mode="json"
    ) == contradictory_workspace


def test_decisions_reject_missing_reversed_or_out_of_range_bounds() -> None:
    invalid_decisions = [
        (
            Policy,
            {
                "id": "60000000-0000-0000-0000-000000000001",
                "kind": "consecutive_shift_limit",
                "shift_type": "day",
                "minimum_run_length": None,
                "maximum_run_length": None,
            },
        ),
        (
            Policy,
            {
                "id": "60000000-0000-0000-0000-000000000002",
                "kind": "weekly_shift_count_limit",
                "shift_type": "day",
                "minimum_count": 6,
                "maximum_count": 2,
            },
        ),
        (
            Objective,
            {
                "id": "60000000-0000-0000-0000-000000000003",
                "kind": "weekly_shift_count_preference",
                "shift_type": "day",
                "preferred_minimum": {"value": -1, "weight": 1},
                "preferred_maximum": None,
            },
        ),
        (
            Objective,
            {
                "id": "60000000-0000-0000-0000-000000000004",
                "kind": "workload_balance_objective",
                "weight": 0,
            },
        ),
    ]

    for decision_type, invalid_decision in invalid_decisions:
        with pytest.raises(ValidationError):
            TypeAdapter(decision_type).validate_python(invalid_decision)
