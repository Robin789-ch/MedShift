#!/usr/bin/env python3
"""Tests for schedule optimizer helpers."""

from __future__ import annotations

import contextlib
import io
import unittest

from ortools.sat.python import cp_model

from scheduler import (
    add_work_balancing_constraint,
    derive_weekly_cover_demands,
    normalize_departments,
    prepare_stage_one_config,
    solve_department_scheduling,
    solve_schedule,
    solve_shift_scheduling,
    shift_attributes,
)


def base_department_config() -> dict:
    return {
        "num_employees": 2,
        "num_weeks": 1,
        "shifts": ["O", "D", "N", "F", "R", "H"],
        "shift_attributes": {
            "O": {
                "counts_as_work": False,
                "covers_demand": False,
                "counts_as_weekly_off": True,
                "is_night": False,
            },
            "D": {
                "counts_as_work": True,
                "covers_demand": True,
                "counts_as_weekly_off": False,
                "is_night": False,
            },
            "N": {
                "counts_as_work": True,
                "covers_demand": True,
                "counts_as_weekly_off": False,
                "is_night": True,
            },
            "F": {
                "counts_as_work": True,
                "covers_demand": False,
                "counts_as_weekly_off": False,
                "is_night": False,
            },
            "R": {
                "counts_as_work": False,
                "covers_demand": False,
                "counts_as_weekly_off": False,
                "is_night": False,
            },
            "H": {
                "counts_as_work": True,
                "covers_demand": False,
                "counts_as_weekly_off": False,
                "is_night": False,
                "requires_assignment_request": True,
            },
        },
        "employee_names": ["Ada", "Ben"],
        "fixed_assignments": [],
        "requests": [],
        "shift_constraints": [],
        "weekly_sum_constraints": [],
        "penalized_transitions": [],
        "weekly_cover_demands": [[1, 0] for _ in range(7)],
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
                "requirements": [1, 1, 1, 1, 1, 1, 1],
            }
        ],
        "work_balance": {
            "night_shift": "N",
            "night_cost": 0,
            "work_cost": 0,
        },
    }


class WorkBalancingConstraintTest(unittest.TestCase):
    def test_balancing_penalties_track_employee_count_spread(self) -> None:
        model = cp_model.CpModel()
        num_employees = 2
        num_shifts = 4
        num_days = 4
        work = {}

        for e in range(num_employees):
            for s in range(num_shifts):
                for d in range(num_days):
                    work[e, s, d] = model.new_bool_var(f"work{e}_{s}_{d}")

        for e in range(num_employees):
            for d in range(num_days):
                model.add_exactly_one(work[e, s, d] for s in range(num_shifts))

        # Employee 0 works three days, including two nights.
        model.add(work[0, 3, 0] == 1)
        model.add(work[0, 3, 1] == 1)
        model.add(work[0, 1, 2] == 1)
        model.add(work[0, 0, 3] == 1)

        # Employee 1 also works three days, with no nights.
        model.add(work[1, 1, 0] == 1)
        model.add(work[1, 1, 1] == 1)
        model.add(work[1, 1, 2] == 1)
        model.add(work[1, 0, 3] == 1)

        variables, coeffs = add_work_balancing_constraint(
            model,
            work,
            num_employees,
            num_days,
            [1, 2, 3],
            3,
            5,
            7,
            "balance",
        )
        model.minimize(sum(var * coeffs[i] for i, var in enumerate(variables)))

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        self.assertEqual(status, cp_model.OPTIMAL)
        self.assertEqual(coeffs, [5, 7])
        self.assertEqual([solver.value(var) for var in variables], [2, 0])

    def test_solver_accepts_work_balance_config(self) -> None:
        config = {
            "num_employees": 2,
            "num_weeks": 1,
            "shifts": ["O", "D", "N", "F", "R", "H"],
            "shift_attributes": {
                "O": {
                    "counts_as_work": False,
                    "covers_demand": False,
                    "counts_as_weekly_off": True,
                    "is_night": False,
                },
                "D": {
                    "counts_as_work": True,
                    "covers_demand": True,
                    "counts_as_weekly_off": False,
                    "is_night": False,
                },
                "N": {
                    "counts_as_work": True,
                    "covers_demand": True,
                    "counts_as_weekly_off": False,
                    "is_night": True,
                },
                "F": {
                    "counts_as_work": True,
                    "covers_demand": False,
                    "counts_as_weekly_off": False,
                    "is_night": False,
                },
                "R": {
                    "counts_as_work": False,
                    "covers_demand": False,
                    "counts_as_weekly_off": False,
                    "is_night": False,
                },
                "H": {
                    "counts_as_work": True,
                    "covers_demand": False,
                    "counts_as_weekly_off": False,
                    "is_night": False,
                    "requires_assignment_request": True,
                },
            },
            "employee_names": ["Ada", "Ben"],
            "fixed_assignments": [[0, "F", 0], [1, "R", 0]],
            "requests": [],
            "shift_constraints": [],
            "weekly_sum_constraints": [],
            "penalized_transitions": [],
            "weekly_cover_demands": [[0, 0]] + [[1, 0] for _ in range(6)],
            "excess_cover_penalties": [0, 0],
            "work_balance": {
                "night_shift": "N",
                "night_cost": 1,
                "work_cost": 1,
            },
        }

        with contextlib.redirect_stdout(io.StringIO()):
            result = solve_shift_scheduling(config, "max_time_in_seconds:1.0", "")

        self.assertIsNotNone(result)
        self.assertEqual(result["employee_names"], ["Ada", "Ben"])
        self.assertEqual(result["num_workers"], 2)
        self.assertEqual(result["num_days"], 7)
        self.assertEqual(result["plan"][0][0], "F")
        self.assertEqual(result["plan"][1][0], "R")

    def test_formation_shift_requires_fixed_assignment(self) -> None:
        config = base_department_config()
        config["num_employees"] = 1
        config["employee_names"] = ["Ada"]
        config["weekly_cover_demands"] = [[0, 0] for _ in range(7)]
        config["departments"][0]["requirements"] = [0, 0, 0, 0, 0, 0, 0]
        config["requests"] = [[0, "F", 0, -1000]]

        with contextlib.redirect_stdout(io.StringIO()):
            result = solve_shift_scheduling(config, "max_time_in_seconds:1.0", "")

        self.assertIsNotNone(result)
        self.assertNotEqual(result["plan"][0][0], "F")

        config["fixed_assignments"] = [[0, "F", 0]]
        with contextlib.redirect_stdout(io.StringIO()):
            result = solve_shift_scheduling(config, "max_time_in_seconds:1.0", "")

        self.assertIsNotNone(result)
        self.assertEqual(result["plan"][0][0], "F")

    def test_holiday_shift_requires_desired_request_or_fixed_assignment(self) -> None:
        config = base_department_config()
        config["num_employees"] = 1
        config["employee_names"] = ["Ada"]
        config["weekly_cover_demands"] = [[0, 0] for _ in range(7)]
        config["departments"][0]["requirements"] = [0, 0, 0, 0, 0, 0, 0]

        attributes = shift_attributes(config, config["shifts"])
        self.assertTrue(attributes["H"]["counts_as_work"])
        self.assertFalse(attributes["H"]["covers_demand"])
        self.assertFalse(attributes["H"]["counts_as_weekly_off"])
        self.assertTrue(attributes["H"]["requires_assignment_request"])

        config["requests"] = [[0, "H", 0, 1000]]
        with contextlib.redirect_stdout(io.StringIO()):
            result = solve_shift_scheduling(config, "max_time_in_seconds:1.0", "")

        self.assertIsNotNone(result)
        self.assertNotEqual(result["plan"][0][0], "H")

        config["requests"] = [[0, "H", 0, -1000]]
        with contextlib.redirect_stdout(io.StringIO()):
            result = solve_shift_scheduling(config, "max_time_in_seconds:1.0", "")

        self.assertIsNotNone(result)
        self.assertEqual(result["plan"][0][0], "H")

        config["requests"] = []
        config["fixed_assignments"] = [[0, "H", 0]]
        with contextlib.redirect_stdout(io.StringIO()):
            result = solve_shift_scheduling(config, "max_time_in_seconds:1.0", "")

        self.assertIsNotNone(result)
        self.assertEqual(result["plan"][0][0], "H")

    def test_reward_gains_are_printed(self) -> None:
        config = base_department_config()
        config["num_employees"] = 1
        config["employee_names"] = ["Ada"]
        config["weekly_cover_demands"] = [[0, 0] for _ in range(7)]
        config["departments"][0]["requirements"] = [0, 0, 0, 0, 0, 0, 0]
        config["requests"] = [[0, "O", 0, -1000]]

        log = io.StringIO()
        with contextlib.redirect_stdout(log):
            result = solve_shift_scheduling(config, "max_time_in_seconds:1.0", "")

        self.assertIsNotNone(result)
        self.assertIn("fulfilled, gain=1000", log.getvalue())


class TransitionRewardTest(unittest.TestCase):
    def test_negative_transition_reward_requires_actual_transition(self) -> None:
        config = {
            "num_employees": 1,
            "num_weeks": 1,
            "shifts": ["O", "R"],
            "fixed_assignments": [[0, "O", day] for day in range(7)],
            "requests": [],
            "shift_constraints": [],
            "weekly_sum_constraints": [],
            "penalized_transitions": [["O", "R", -2]],
            "weekly_cover_demands": [[] for _ in range(7)],
            "excess_cover_penalties": [],
        }

        log = io.StringIO()
        with contextlib.redirect_stdout(log):
            result = solve_shift_scheduling(config, "max_time_in_seconds:1.0", "")

        self.assertIsNotNone(result)
        self.assertIn("objective: 0", log.getvalue())
        self.assertNotIn("fulfilled, gain=", log.getvalue())

    def test_actual_negative_transition_gain_is_printed_once(self) -> None:
        config = {
            "num_employees": 1,
            "num_weeks": 1,
            "shifts": ["O", "R"],
            "fixed_assignments": [[0, "R" if day == 1 else "O", day] for day in range(7)],
            "requests": [],
            "shift_constraints": [],
            "weekly_sum_constraints": [],
            "penalized_transitions": [["O", "R", -2]],
            "weekly_cover_demands": [[] for _ in range(7)],
            "excess_cover_penalties": [],
        }

        log = io.StringIO()
        with contextlib.redirect_stdout(log):
            result = solve_shift_scheduling(config, "max_time_in_seconds:1.0", "")

        self.assertIsNotNone(result)
        self.assertIn("objective: -2", log.getvalue())
        self.assertEqual(log.getvalue().count("fulfilled, gain=2"), 1)


class LogFormatTest(unittest.TestCase):
    def test_shift_solution_table_is_not_printed(self) -> None:
        config = base_department_config()

        log = io.StringIO()
        with contextlib.redirect_stdout(log):
            result = solve_shift_scheduling(config, "max_time_in_seconds:1.0", "")

        self.assertIsNotNone(result)
        self.assertNotIn("worker 0:", log.getvalue())
        self.assertNotIn("M T W T F S S", log.getvalue())
        self.assertIn("Shift penalties:", log.getvalue())
        self.assertIn("Shift solver stats:", log.getvalue())

    def test_department_stage_prints_objective_iterations(self) -> None:
        config = base_department_config()
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
        shift_result = {
            "shifts": config["shifts"],
            "num_workers": 2,
            "num_days": 3,
            "plan": [["D", "D", "D"], ["D", "D", "D"]],
        }

        log = io.StringIO()
        with contextlib.redirect_stdout(log):
            result = solve_department_scheduling(
                config, shift_result, "max_time_in_seconds:1.0", ""
            )

        self.assertIsNotNone(result)
        self.assertIn("Stage 2 (D): department assignments", log.getvalue())
        self.assertIn("Stage 2 D solution 0", log.getvalue())
        self.assertIn("Stage 2 (D) penalties:", log.getvalue())
        self.assertIn("Stage 2 (D) solver stats:", log.getvalue())

    def test_two_stage_log_has_single_department_heading_per_shift(self) -> None:
        config = base_department_config()
        config["num_employees"] = 3
        config["employee_names"] = ["Ada", "Ben", "Cam"]
        config["departments"] = [
            {
                "id": "day",
                "name": "Day",
                "shift": "D",
                "symbol": "D",
                "requirements": [1, 1, 1, 1, 1, 1, 1],
            },
            {
                "id": "night",
                "name": "Night",
                "shift": "N",
                "symbol": "N",
                "requirements": [1, 1, 1, 1, 1, 1, 1],
            },
        ]

        log = io.StringIO()
        with contextlib.redirect_stdout(log):
            result = solve_schedule(config, "max_time_in_seconds:1.0", "")

        self.assertIsNotNone(result)
        self.assertEqual(log.getvalue().count("Stage 2: department schedule"), 1)
        self.assertEqual(
            log.getvalue().count("Stage 2 (D): department assignments"), 1
        )
        self.assertEqual(
            log.getvalue().count("Stage 2 (N): department assignments"), 1
        )


class DepartmentSchedulingTest(unittest.TestCase):
    def test_department_demands_are_aggregated_by_cover_shift(self) -> None:
        config = base_department_config()
        config["departments"] = [
            {
                "id": "er",
                "name": "Emergency",
                "shift": "D",
                "symbol": "E",
                "requirements": [1, 2, 0, 0, 0, 0, 0],
            },
            {
                "id": "ward",
                "name": "Ward",
                "shift": "D",
                "symbol": "W",
                "requirements": [2, 0, 0, 0, 0, 0, 0],
            },
            {
                "id": "night",
                "name": "Night",
                "shift": "N",
                "symbol": "N",
                "requirements": [0, 1, 0, 0, 0, 0, 0],
            },
        ]

        departments = normalize_departments(config)

        self.assertEqual(
            derive_weekly_cover_demands(config, departments),
            [[3, 0], [2, 1], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0]],
        )

    def test_legacy_departments_receive_stable_ids(self) -> None:
        config = base_department_config()
        config["departments"] = [
            {
                "name": "Emergency Unit",
                "shift": "D",
                "symbol": "E",
                "requirements": [1, 0, 0, 0, 0, 0, 0],
            },
            {
                "name": "Emergency Unit",
                "shift": "D",
                "symbol": "E2",
                "requirements": [0, 1, 0, 0, 0, 0, 0],
            },
        ]

        departments = normalize_departments(config)

        self.assertEqual([department["id"] for department in departments], [
            "emergency_unit",
            "emergency_unit_2",
        ])

    def test_two_stage_solve_returns_department_plan(self) -> None:
        config = base_department_config()

        with contextlib.redirect_stdout(io.StringIO()):
            result = solve_schedule(config, "max_time_in_seconds:1.0", "")

        self.assertIsNotNone(result)
        self.assertIn("department_plan", result)
        for employee, row in enumerate(result["plan"]):
            for day, shift in enumerate(row):
                if shift == "D":
                    self.assertEqual(result["department_plan"][employee][day], "day")
                else:
                    self.assertIsNone(result["department_plan"][employee][day])

    def test_fixed_department_assignment_projects_to_stage_one(self) -> None:
        config = base_department_config()
        config["department_fixed_assignments"] = [[1, "day", 0]]

        with contextlib.redirect_stdout(io.StringIO()):
            result = solve_schedule(config, "max_time_in_seconds:1.0", "")

        self.assertIsNotNone(result)
        self.assertEqual(result["plan"][1][0], "D")
        self.assertEqual(result["department_plan"][1][0], "day")

    def test_conflicting_department_assignment_fails_cleanly(self) -> None:
        config = base_department_config()
        config["fixed_assignments"] = [[0, "O", 0]]
        config["department_fixed_assignments"] = [[0, "day", 0]]

        with contextlib.redirect_stdout(io.StringIO()):
            result = solve_schedule(config, "max_time_in_seconds:1.0", "")

        self.assertIsNone(result)

    def test_desired_department_request_projects_but_not_desired_does_not(self) -> None:
        config = base_department_config()
        config["departments"][0]["requirements"] = [1, 0, 0, 0, 0, 0, 0]
        config["department_requests"] = [
            [1, "day", 0, -100],
            [0, "day", 0, 100],
        ]

        stage_one_config, _departments = prepare_stage_one_config(config)

        self.assertIn([1, "D", 0, -100], stage_one_config["requests"])
        self.assertNotIn([0, "D", 0, 100], stage_one_config["requests"])

        with contextlib.redirect_stdout(io.StringIO()):
            result = solve_schedule(config, "max_time_in_seconds:1.0", "")

        self.assertIsNotNone(result)
        self.assertEqual(result["plan"][1][0], "D")
        self.assertEqual(result["department_plan"][1][0], "day")

    def test_switch_penalty_prefers_department_continuity(self) -> None:
        config = base_department_config()
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
        shift_result = {
            "shifts": config["shifts"],
            "num_workers": 2,
            "num_days": 3,
            "plan": [["D", "D", "D"], ["D", "D", "D"]],
        }

        with contextlib.redirect_stdout(io.StringIO()):
            result = solve_department_scheduling(
                config, shift_result, "max_time_in_seconds:1.0", ""
            )

        self.assertIsNotNone(result)
        self.assertEqual(len(set(result["department_plan"][0])), 1)
        self.assertEqual(len(set(result["department_plan"][1])), 1)
        self.assertNotEqual(result["department_plan"][0][0], result["department_plan"][1][0])


if __name__ == "__main__":
    unittest.main()
