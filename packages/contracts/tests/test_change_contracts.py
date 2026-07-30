from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from medshift_contracts import (
    AssignmentTarget,
    Objective,
    PlanningEntry,
    Policy,
    ProposalChange,
    SolveResult,
    StateResponse,
    WorkspaceChange,
)


def test_every_workspace_change_variant_round_trips() -> None:
    changes: list[dict[str, Any]] = [
        {
            "kind": "add_policy",
            "policy": {
                "id": "10000000-0000-0000-0000-000000000001",
                "kind": "consecutive_shift_limit",
                "shift_type": "night",
                "minimum_run_length": 2,
                "maximum_run_length": None,
            },
        },
        {
            "kind": "update_policy",
            "policy_id": "10000000-0000-0000-0000-000000000002",
            "policy": {
                "id": "10000000-0000-0000-0000-000000000002",
                "kind": "weekly_shift_count_limit",
                "shift_type": "day",
                "minimum_count": None,
                "maximum_count": 5,
            },
        },
        {
            "kind": "remove_policy",
            "policy_id": "10000000-0000-0000-0000-000000000003",
        },
        {
            "kind": "add_objective",
            "objective": {
                "id": "20000000-0000-0000-0000-000000000001",
                "kind": "workload_balance_objective",
                "weight": 3,
            },
        },
        {
            "kind": "update_objective",
            "objective_id": "20000000-0000-0000-0000-000000000002",
            "objective": {
                "id": "20000000-0000-0000-0000-000000000002",
                "kind": "night_shift_balance_objective",
                "weight": 5,
            },
        },
        {
            "kind": "remove_objective",
            "objective_id": "20000000-0000-0000-0000-000000000003",
        },
    ]
    adapter: TypeAdapter[WorkspaceChange] = TypeAdapter(WorkspaceChange)

    assert [
        adapter.dump_python(adapter.validate_python(change), mode="json")
        for change in changes
    ] == changes


def test_update_change_rejects_a_replacement_with_a_different_id() -> None:
    invalid_change = {
        "kind": "update_policy",
        "policy_id": "10000000-0000-0000-0000-000000000001",
        "policy": {
            "id": "10000000-0000-0000-0000-000000000002",
            "kind": "consecutive_shift_limit",
            "shift_type": "day",
            "minimum_run_length": None,
            "maximum_run_length": 5,
        },
    }

    with pytest.raises(ValidationError):
        TypeAdapter(WorkspaceChange).validate_python(invalid_change)


def test_every_discriminated_union_rejects_an_unknown_discriminator() -> None:
    invalid_unions = [
        (AssignmentTarget, {"kind": "future_target"}),
        (PlanningEntry, {"kind": "future_entry"}),
        (Policy, {"kind": "future_policy"}),
        (Objective, {"kind": "future_objective"}),
        (WorkspaceChange, {"kind": "future_change"}),
        (ProposalChange, {"kind": "future_proposal_change"}),
        (SolveResult, {"status": "future_status"}),
        (StateResponse, {"initialized": "future_state"}),
    ]

    for union, value in invalid_unions:
        with pytest.raises(ValidationError):
            TypeAdapter(union).validate_python(value)
