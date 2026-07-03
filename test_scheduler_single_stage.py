#!/usr/bin/env python3
"""Tests for the experimental single-stage schedule optimizer."""

from __future__ import annotations

import contextlib
import io
import unittest

from scheduler_single_stage import solve_schedule


def base_config() -> dict:
    return {
        "num_employees": 2,
        "num_weeks": 1,
        "shifts": ["O", "D", "N", "F", "R", "H"],
        "employee_names": ["Ada", "Ben"],
        "fixed_assignments": [],
        "requests": [],
        "shift_constraints": [],
        "weekly_sum_constraints": [],
        "penalized_transitions": [],
        "excess_cover_penalties": [0, 0],
        "department_fixed_assignments": [],
        "department_requests": [],
        "department_switch_penalty": 1,
        "departments": [
            {
                "id": "day",
                "name": "Day",
                "shift": "D",
                "symbol": "D",
                "color": "#ffe08a",
                "duration_hours": 8,
                "requirements": [1, 1, 1, 1, 1, 1, 1],
            }
        ],
    }


class SingleStageDepartmentSchedulingTest(unittest.TestCase):
    def solve_quietly(self, config: dict) -> tuple[dict | None, str]:
        log = io.StringIO()
        with contextlib.redirect_stdout(log):
            result = solve_schedule(config, "max_time_in_seconds:1.0", "")
        return result, log.getvalue()

    def test_department_request_is_optimized_in_single_stage(self) -> None:
        config = base_config()
        config["departments"][0]["requirements"] = [1, 0, 0, 0, 0, 0, 0]
        config["department_requests"] = [[1, "day", 0, -100]]

        result, log = self.solve_quietly(config)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["plan"][1][0], "D")
        self.assertEqual(result["department_plan"][1][0], "day")
        self.assertIn("Single-stage schedule", log)
        self.assertNotIn("Stage 2:", log)

    def test_fixed_department_assignment_sets_broad_shift(self) -> None:
        config = base_config()
        config["departments"][0]["requirements"] = [1, 0, 0, 0, 0, 0, 0]
        config["department_fixed_assignments"] = [[1, "day", 0]]

        result, _log = self.solve_quietly(config)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["plan"][1][0], "D")
        self.assertEqual(result["department_plan"][1][0], "day")

    def test_conflicting_department_and_broad_assignment_is_infeasible(self) -> None:
        config = base_config()
        config["departments"][0]["requirements"] = [1, 0, 0, 0, 0, 0, 0]
        config["fixed_assignments"] = [[0, "O", 0]]
        config["department_fixed_assignments"] = [[0, "day", 0]]

        result, _log = self.solve_quietly(config)

        self.assertIsNone(result)

    def test_switch_penalty_prefers_department_continuity(self) -> None:
        config = base_config()
        config["departments"] = [
            {
                "id": "alpha",
                "name": "Alpha",
                "shift": "D",
                "symbol": "A",
                "requirements": [1, 1, 1, 0, 0, 0, 0],
            },
            {
                "id": "beta",
                "name": "Beta",
                "shift": "D",
                "symbol": "B",
                "requirements": [1, 1, 1, 0, 0, 0, 0],
            },
        ]

        result, _log = self.solve_quietly(config)

        self.assertIsNotNone(result)
        assert result is not None
        first_worker_departments = result["department_plan"][0][:3]
        second_worker_departments = result["department_plan"][1][:3]
        self.assertEqual(len(set(first_worker_departments)), 1)
        self.assertEqual(len(set(second_worker_departments)), 1)
        self.assertNotEqual(first_worker_departments[0], second_worker_departments[0])

    def test_max_hours_per_week_uses_department_duration(self) -> None:
        config = base_config()
        config["num_employees"] = 1
        config["employee_names"] = ["Ada"]
        config["departments"][0]["requirements"] = [1, 1, 0, 0, 0, 0, 0]
        config["departments"][0]["duration_hours"] = 8
        config["max_hours_per_week"] = 16

        result, _log = self.solve_quietly(config)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["departments"][0]["duration_hours"], 8)

        config["departments"][0]["duration_hours"] = 12
        result, _log = self.solve_quietly(config)

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
