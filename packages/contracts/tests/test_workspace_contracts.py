from medshift_contracts import SHIFT_TYPES, Workspace


def test_workspace_round_trips_without_persisting_shift_type_catalogue() -> None:
    raw_workspace = {
        "schema_version": 1,
        "revision": 3,
        "scenario": {
            "planning_weeks": 2,
            "employees": [
                {
                    "employee_id": "11111111-1111-1111-1111-111111111111",
                    "display_name": "Avery",
                    "overtime_hours": 8,
                    "weekly_hours_ceiling": 40,
                }
            ],
            "departments": [
                {
                    "department_id": "22222222-2222-2222-2222-222222222222",
                    "display_name": "Ward A",
                    "shift_type": "day",
                    "symbol": "WA",
                    "color": "#12Ab34",
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
                },
                {
                    "kind": "employee_preference",
                    "employee_id": "11111111-1111-1111-1111-111111111111",
                    "day_index": 1,
                    "target": {
                        "kind": "shift_type",
                        "shift_type": "holiday",
                    },
                    "direction": "desired",
                },
            ],
        },
        "policies": [],
        "objectives": [],
    }

    workspace = Workspace.model_validate(raw_workspace)
    dumped = workspace.model_dump(mode="json")

    assert dumped == raw_workspace
    assert "shift_types" not in dumped
    assert [(item.shift_type.value, item.code) for item in SHIFT_TYPES] == [
        ("off", "O"),
        ("day", "D"),
        ("night", "N"),
        ("formation", "F"),
        ("recovery", "R"),
        ("holiday", "H"),
    ]
