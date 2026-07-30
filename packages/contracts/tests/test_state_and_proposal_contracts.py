from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from medshift_contracts import Proposal, ProposalChange, StateResponse


def shift_types() -> list[dict[str, Any]]:
    return [
        {
            "shift_type": "off",
            "code": "O",
            "name": "Off",
            "covers_demand": False,
            "is_night": False,
            "counts_toward_workload_balance": False,
            "assignment_hours": 0,
            "recovers_overtime": False,
            "eligibility": "automatic",
        },
        {
            "shift_type": "day",
            "code": "D",
            "name": "Day",
            "covers_demand": True,
            "is_night": False,
            "counts_toward_workload_balance": True,
            "assignment_hours": None,
            "recovers_overtime": False,
            "eligibility": "automatic",
        },
        {
            "shift_type": "night",
            "code": "N",
            "name": "Night",
            "covers_demand": True,
            "is_night": True,
            "counts_toward_workload_balance": True,
            "assignment_hours": None,
            "recovers_overtime": False,
            "eligibility": "automatic",
        },
        {
            "shift_type": "formation",
            "code": "F",
            "name": "Formation",
            "covers_demand": False,
            "is_night": False,
            "counts_toward_workload_balance": True,
            "assignment_hours": 8,
            "recovers_overtime": False,
            "eligibility": "fixed_assignment_only",
        },
        {
            "shift_type": "recovery",
            "code": "R",
            "name": "Recovery",
            "covers_demand": False,
            "is_night": False,
            "counts_toward_workload_balance": False,
            "assignment_hours": 8,
            "recovers_overtime": True,
            "eligibility": "automatic",
        },
        {
            "shift_type": "holiday",
            "code": "H",
            "name": "Holiday",
            "covers_demand": False,
            "is_night": False,
            "counts_toward_workload_balance": True,
            "assignment_hours": 0,
            "recovers_overtime": False,
            "eligibility": "fixed_assignment_or_desired_preference",
        },
    ]


def test_every_proposal_change_variant_round_trips() -> None:
    view = {
        "title": "Limit consecutive Night shifts",
        "summary": "Night runs must contain at most three shifts.",
        "details": [{"label": "Maximum", "value": "3"}],
    }
    proposal_changes: list[dict[str, Any]] = [
        {
            "kind": "addition",
            "decision_type": "policy",
            "after": view,
        },
        {
            "kind": "update",
            "decision_type": "policy",
            "before": view,
            "after": {
                **view,
                "summary": "Night runs must contain at most four shifts.",
                "details": [{"label": "Maximum", "value": "4"}],
            },
        },
        {
            "kind": "removal",
            "decision_type": "policy",
            "before": view,
        },
    ]
    adapter: TypeAdapter[ProposalChange] = TypeAdapter(ProposalChange)

    assert [
        adapter.dump_python(adapter.validate_python(change), mode="json")
        for change in proposal_changes
    ] == proposal_changes

    proposal = {
        "proposal_id": "30000000-0000-0000-0000-000000000001",
        "base_revision": 4,
        "changes": proposal_changes,
    }
    assert Proposal.model_validate(proposal).model_dump(mode="json") == proposal


def test_initialized_and_uninitialized_state_variants_round_trip() -> None:
    states: list[dict[str, Any]] = [
        {
            "initialized": False,
            "shift_types": shift_types(),
        },
        {
            "initialized": True,
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
            "shift_types": shift_types(),
            "policies": [],
            "objectives": [],
        },
    ]
    adapter: TypeAdapter[StateResponse] = TypeAdapter(StateResponse)

    assert [
        adapter.dump_python(adapter.validate_python(state), mode="json")
        for state in states
    ] == states


def test_state_rejects_redefined_shift_type_semantics() -> None:
    invalid_shift_types = shift_types()
    invalid_shift_types[1] = {
        **invalid_shift_types[1],
        "code": "X",
        "name": "Custom",
        "covers_demand": False,
        "is_night": True,
        "counts_toward_workload_balance": False,
        "assignment_hours": 99,
        "recovers_overtime": True,
    }
    invalid_state = {
        "initialized": False,
        "shift_types": invalid_shift_types,
    }

    with pytest.raises(ValidationError):
        TypeAdapter(StateResponse).validate_python(invalid_state)
