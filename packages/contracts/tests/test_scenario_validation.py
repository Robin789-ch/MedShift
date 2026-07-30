from copy import deepcopy
from typing import Any

import pytest
from pydantic import ValidationError

from medshift_contracts import Scenario


def valid_scenario() -> dict[str, Any]:
    return {
        "planning_weeks": 1,
        "employees": [
            {
                "employee_id": "11111111-1111-1111-1111-111111111111",
                "display_name": "Avery",
                "overtime_hours": 0,
                "weekly_hours_ceiling": 40,
            }
        ],
        "departments": [
            {
                "department_id": "22222222-2222-2222-2222-222222222222",
                "display_name": "Ward A",
                "shift_type": "day",
                "symbol": "WA",
                "color": "#123456",
                "duration_hours": 8,
                "staffing_demand": [1, 1, 1, 1, 1, 0, 0],
            }
        ],
        "planning_entries": [],
    }


def test_scenario_rejects_invalid_identity_reference_and_entry_contracts() -> None:
    invalid_scenarios: list[dict[str, Any]] = []

    duplicate_employee = valid_scenario()
    duplicate_employee["employees"].append(deepcopy(duplicate_employee["employees"][0]))
    invalid_scenarios.append(duplicate_employee)

    invalid_department_type = valid_scenario()
    invalid_department_type["departments"][0]["shift_type"] = "formation"
    invalid_scenarios.append(invalid_department_type)

    invalid_demand = valid_scenario()
    invalid_demand["departments"][0]["staffing_demand"] = [1, 1, 1]
    invalid_scenarios.append(invalid_demand)

    unknown_employee = valid_scenario()
    unknown_employee["planning_entries"] = [
        {
            "kind": "fixed_assignment",
            "employee_id": "99999999-9999-9999-9999-999999999999",
            "day_index": 0,
            "target": {"kind": "shift_type", "shift_type": "off"},
        }
    ]
    invalid_scenarios.append(unknown_employee)

    outside_horizon = valid_scenario()
    outside_horizon["planning_entries"] = [
        {
            "kind": "fixed_assignment",
            "employee_id": "11111111-1111-1111-1111-111111111111",
            "day_index": 7,
            "target": {"kind": "shift_type", "shift_type": "off"},
        }
    ]
    invalid_scenarios.append(outside_horizon)

    collision = valid_scenario()
    collision["planning_entries"] = [
        {
            "kind": "fixed_assignment",
            "employee_id": "11111111-1111-1111-1111-111111111111",
            "day_index": 0,
            "target": {"kind": "shift_type", "shift_type": "off"},
        },
        {
            "kind": "employee_preference",
            "employee_id": "11111111-1111-1111-1111-111111111111",
            "day_index": 0,
            "target": {"kind": "shift_type", "shift_type": "day"},
            "direction": "desired",
        },
    ]
    invalid_scenarios.append(collision)

    ineligible_formation_preference = valid_scenario()
    ineligible_formation_preference["planning_entries"] = [
        {
            "kind": "employee_preference",
            "employee_id": "11111111-1111-1111-1111-111111111111",
            "day_index": 0,
            "target": {"kind": "shift_type", "shift_type": "formation"},
            "direction": "desired",
        }
    ]
    invalid_scenarios.append(ineligible_formation_preference)

    avoided_holiday = valid_scenario()
    avoided_holiday["planning_entries"] = [
        {
            "kind": "employee_preference",
            "employee_id": "11111111-1111-1111-1111-111111111111",
            "day_index": 0,
            "target": {"kind": "shift_type", "shift_type": "holiday"},
            "direction": "avoided",
        }
    ]
    invalid_scenarios.append(avoided_holiday)

    unknown_discriminator = valid_scenario()
    unknown_discriminator["planning_entries"] = [
        {
            "kind": "request",
            "employee_id": "11111111-1111-1111-1111-111111111111",
            "day_index": 0,
            "target": {"kind": "shift_type", "shift_type": "off"},
        }
    ]
    invalid_scenarios.append(unknown_discriminator)

    for invalid_scenario in invalid_scenarios:
        with pytest.raises(ValidationError):
            Scenario.model_validate(invalid_scenario)
