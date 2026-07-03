#!/usr/bin/env python3
"""Tests for schedule optimizer helpers."""

from __future__ import annotations

import contextlib
import io
import unittest

from ortools.sat.python import cp_model

from scheduler import add_work_balancing_constraint, solve_shift_scheduling


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
            "shifts": ["O", "D", "N", "F", "R"],
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


if __name__ == "__main__":
    unittest.main()
