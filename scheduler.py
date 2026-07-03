
#!/usr/bin/env python3
# Copyright 2010-2025 Google LLC
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Creates a shift scheduling problem and solves it."""

import json
import pathlib
import re
import tomllib
import urllib.request
from typing import Any

from absl import app
from absl import flags

from ortools.sat.python import cp_model


_OUTPUT_PROTO = None
_PARAMS = None
_CONFIG = None


def _define_cli_flags() -> None:
    global _OUTPUT_PROTO, _PARAMS, _CONFIG
    _OUTPUT_PROTO = flags.DEFINE_string(
        "output_proto", "", "Output file to write the cp_model proto to."
    )
    _PARAMS = flags.DEFINE_string(
        "params", "max_time_in_seconds:10.0", "Sat solver parameters."
    )
    _CONFIG = flags.DEFINE_string("config", "config.toml", "Model config file.")

FRONTEND_URL = "http://127.0.0.1:8000/schedule"


def parse_config(path: str) -> dict[str, Any]:
    """Parses model parameters from a TOML config file."""
    config_path = pathlib.Path(path)
    if config_path.suffix.lower() != ".toml":
        raise ValueError(f"Unsupported config format: {config_path.suffix}")

    with open(config_path, "rb") as config_file:
        return tomllib.load(config_file)


def send_to_frontend(result, url: str = FRONTEND_URL) -> None:
    """Sends a solved schedule to the development visualization server."""
    if result is None:
        return

    data = json.dumps(result).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=2):
            pass
    except Exception as exc:  # The visualizer is optional during solver runs.
        print(f"Could not send schedule to frontend at {url}: {exc}")


def negated_bounded_span(
    works: list[cp_model.BoolVarT], start: int, length: int
) -> list[cp_model.BoolVarT]:
    """Filters an isolated sub-sequence of variables assigned to True.

    Extract the span of Boolean variables [start, start + length), negate them,
    and if there is variables to the left/right of this span, surround the span by
    them in non negated form.

    Args:
      works: a list of variables to extract the span from.
      start: the start to the span.
      length: the length of the span.

    Returns:
      a list of variables which conjunction will be false if the sub-list is
      assigned to True, and correctly bounded by variables assigned to False,
      or by the start or end of works.
    """
    sequence = []
    # left border (start of works, or works[start - 1])
    if start > 0:
        sequence.append(works[start - 1])
    for i in range(length):
        sequence.append(~works[start + i])
    # right border (end of works or works[start + length])
    if start + length < len(works):
        sequence.append(works[start + length])
    return sequence


def add_soft_sequence_constraint(
    model: cp_model.CpModel,
    works: list[cp_model.BoolVarT],
    hard_min: int,
    soft_min: int,
    min_cost: int,
    soft_max: int,
    hard_max: int,
    max_cost: int,
    prefix: str,
) -> tuple[list[cp_model.BoolVarT], list[int]]:
    """Sequence constraint on true variables with soft and hard bounds.

    This constraint look at every maximal contiguous sequence of variables
    assigned to true. If forbids sequence of length < hard_min or > hard_max.
    Then it creates penalty terms if the length is < soft_min or > soft_max.

    Args:
      model: the sequence constraint is built on this model.
      works: a list of Boolean variables.
      hard_min: any sequence of true variables must have a length of at least
        hard_min.
      soft_min: any sequence should have a length of at least soft_min, or a
        linear penalty on the delta will be added to the objective.
      min_cost: the coefficient of the linear penalty if the length is less than
        soft_min.
      soft_max: any sequence should have a length of at most soft_max, or a linear
        penalty on the delta will be added to the objective.
      hard_max: any sequence of true variables must have a length of at most
        hard_max.
      max_cost: the coefficient of the linear penalty if the length is more than
        soft_max.
      prefix: a base name for penalty literals.

    Returns:
      a tuple (variables_list, coefficient_list) containing the different
      penalties created by the sequence constraint.
    """
    cost_literals = []
    cost_coefficients = []

    # Forbid sequences that are too short.
    for length in range(1, hard_min):
        for start in range(len(works) - length + 1):
            model.add_bool_or(negated_bounded_span(works, start, length))

    # Penalize sequences that are below the soft limit.
    if min_cost > 0:
        for length in range(hard_min, soft_min):
            for start in range(len(works) - length + 1):
                span = negated_bounded_span(works, start, length)
                name = f": under_span(start={start}, length={length})"
                lit = model.new_bool_var(prefix + name)
                span.append(lit)
                model.add_bool_or(span)
                cost_literals.append(lit)
                # We filter exactly the sequence with a short length.
                # The penalty is proportional to the delta with soft_min.
                cost_coefficients.append(min_cost * (soft_min - length))

    # Penalize sequences that are above the soft limit.
    if max_cost > 0:
        for length in range(soft_max + 1, hard_max + 1):
            for start in range(len(works) - length + 1):
                span = negated_bounded_span(works, start, length)
                name = f": over_span(start={start}, length={length})"
                lit = model.new_bool_var(prefix + name)
                span.append(lit)
                model.add_bool_or(span)
                cost_literals.append(lit)
                # Cost paid is max_cost * excess length.
                cost_coefficients.append(max_cost * (length - soft_max))

    # Just forbid any sequence of true variables with length hard_max + 1
    for start in range(len(works) - hard_max):
        model.add_bool_or([~works[i] for i in range(start, start + hard_max + 1)])
    return cost_literals, cost_coefficients


def shift_index(shifts: list[str], shift: int | str) -> int:
    """Returns the shift index for an integer index or shift label."""
    if isinstance(shift, int):
        if 0 <= shift < len(shifts):
            return shift
        raise ValueError(f"Shift index out of range: {shift}")

    if shift in shifts:
        return shifts.index(shift)
    raise ValueError(f"Unknown shift label: {shift}")


def shift_attributes(config: dict[str, Any], shifts: list[str]) -> dict[str, dict[str, Any]]:
    """Returns per-shift semantics, with conservative defaults."""
    configured = config.get("shift_attributes", {})
    attributes = {}
    for shift in shifts:
        attributes[shift] = {
            "name": shift,
            "counts_as_work": shift not in {"O", "R"},
            "covers_demand": shift not in {"O", "F", "R", "H"},
            "counts_as_weekly_off": shift == "O",
            "is_night": shift == "N",
            "requires_fixed_assignment": shift == "F",
            "requires_assignment_request": shift == "H",
            "duration_hours": 8 if shift in {"F", "R"} else 0,
        }
        attributes[shift].update(configured.get(shift, {}))
    return attributes


def shift_indices_with_attribute(
    shifts: list[str], attributes: dict[str, dict[str, Any]], attribute: str
) -> list[int]:
    """Returns shift indices whose configured attribute is true."""
    return [
        index
        for index, shift in enumerate(shifts)
        if bool(attributes[shift].get(attribute, False))
    ]


def _slug(value: Any) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")
    return slug or "department"


def _normalize_requirements(requirements: Any) -> list[int]:
    values = list(requirements) if isinstance(requirements, list) else []
    if len(values) > 7:
        raise ValueError("Department requirements must contain at most 7 values")
    while len(values) < 7:
        values.append(0)

    normalized = []
    for value in values:
        count = int(value)
        if count < 0:
            raise ValueError("Department requirements cannot be negative")
        normalized.append(count)
    return normalized


def _normalize_duration_hours(value: Any, shift: str) -> int:
    if value is None or value == "":
        return 12 if shift == "N" else 8
    duration = int(value)
    if duration <= 0 or duration > 24:
        raise ValueError("Department duration_hours must be between 1 and 24")
    return duration


def _normalize_max_hours_per_week(config: dict[str, Any]) -> int | None:
    if "max_hours_per_week" not in config or config["max_hours_per_week"] in (None, ""):
        return None
    max_hours = int(config["max_hours_per_week"])
    if max_hours <= 0:
        raise ValueError("max_hours_per_week must be greater than 0")
    return max_hours


def _normalize_employee_overtime_hours(
    config: dict[str, Any], num_employees: int
) -> list[int]:
    values = list(config.get("employee_overtime_hours", []))
    normalized = []
    for index in range(num_employees):
        value = int(values[index]) if index < len(values) else 0
        if value < 0:
            raise ValueError("employee_overtime_hours cannot contain negative values")
        normalized.append(value)
    return normalized


def normalize_departments(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Returns normalized department definitions with stable IDs."""
    shifts = list(config["shifts"])
    attributes = shift_attributes(config, shifts)
    cover_shifts = [
        shifts[index] for index in shift_indices_with_attribute(shifts, attributes, "covers_demand")
    ]
    cover_shift_set = set(cover_shifts)
    configured_departments = config.get("departments") or []
    if not configured_departments:
        weekly_cover_demands = config.get("weekly_cover_demands", [])
        configured_departments = []
        for shift in cover_shifts:
            cover_index = cover_shifts.index(shift)
            configured_departments.append(
                {
                    "id": _slug(shift),
                    "name": attributes[shift].get("name", shift),
                    "shift": shift,
                    "symbol": shift,
                    "requirements": [
                        weekly_cover_demands[day][cover_index]
                        if day < len(weekly_cover_demands)
                        and cover_index < len(weekly_cover_demands[day])
                        else 0
                        for day in range(7)
                    ],
                }
            )

    departments = []
    used_ids: set[str] = set()
    for index, department in enumerate(configured_departments):
        shift = department.get("shift")
        if shift is None:
            raise ValueError("Department shift is required")
        shift_label = shifts[shift_index(shifts, shift)]
        if shift_label not in cover_shift_set:
            raise ValueError(f"Department shift must cover demand: {shift_label}")

        explicit_id = "id" in department and str(department["id"]).strip()
        base_id = _slug(department.get("id") or department.get("name") or shift_label)
        department_id = base_id
        if department_id in used_ids:
            if explicit_id:
                raise ValueError(f"Duplicate department id: {department_id}")
            suffix = 2
            while f"{base_id}_{suffix}" in used_ids:
                suffix += 1
            department_id = f"{base_id}_{suffix}"
        used_ids.add(department_id)

        symbol = str(department.get("symbol") or shift_label).strip().upper()
        if not symbol:
            symbol = shift_label
        color = str(department.get("color") or "").strip()
        if not re.match(r"^#[0-9a-fA-F]{6}$", color):
            color = "#ffe08a" if shift_label == "D" else "#5964d8"

        departments.append(
            {
                "id": department_id,
                "name": str(department.get("name") or department_id).strip(),
                "shift": shift_label,
                "symbol": symbol[:3],
                "color": color,
                "duration_hours": _normalize_duration_hours(
                    department.get("duration_hours"), shift_label
                ),
                "requirements": _normalize_requirements(department.get("requirements")),
            }
        )

    return departments


def department_by_id(departments: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {department["id"]: department for department in departments}


def derive_weekly_cover_demands(
    config: dict[str, Any], departments: list[dict[str, Any]]
) -> list[list[int]]:
    """Aggregates department requirements into demand-covering shift demand."""
    shifts = list(config["shifts"])
    attributes = shift_attributes(config, shifts)
    cover_shifts = [
        shifts[index] for index in shift_indices_with_attribute(shifts, attributes, "covers_demand")
    ]
    weekly_cover_demands = [[0 for _ in cover_shifts] for _ in range(7)]
    cover_shift_index = {shift: index for index, shift in enumerate(cover_shifts)}

    for department in departments:
        cover_index = cover_shift_index[department["shift"]]
        for day, requirement in enumerate(department["requirements"]):
            weekly_cover_demands[day][cover_index] += requirement

    return weekly_cover_demands


def add_work_balancing_constraint(
    model: cp_model.CpModel,
    work: dict[tuple[int, int, int], cp_model.BoolVarT],
    num_employees: int,
    num_days: int,
    work_shift_indices: list[int],
    night_shift_index: int | None,
    night_balancing_cost: int,
    work_balancing_cost: int,
    prefix: str,
) -> tuple[list[cp_model.IntVar], list[int]]:
    """Adds penalties for workload and night-count spread between employees.

    Args:
      model: the balancing constraint is built on this model.
      work: assignment variables keyed by (employee, shift, day).
      num_employees: number of employees in the schedule.
      num_days: number of days in the schedule.
      work_shift_indices: shift indices counted as worked shifts.
      night_shift_index: shift index counted as the night shift.
      night_balancing_cost: objective coefficient for night-count spread.
      work_balancing_cost: objective coefficient for work-shift-count spread.
      prefix: a base name for balancing variables.

    Returns:
      a tuple (variables_list, coefficient_list) containing the different
      penalties created by the balancing constraint.
    """
    cost_variables = []
    cost_coefficients = []

    if night_balancing_cost > 0 and night_shift_index is not None:
        night_counts = []
        for e in range(num_employees):
            count = model.new_int_var(
                0, num_days, f"{prefix}(employee {e}): nights"
            )
            model.add(
                count == sum(work[e, night_shift_index, d] for d in range(num_days))
            )
            night_counts.append(count)

        max_nights = model.new_int_var(0, num_days, f"{prefix}: max_nights")
        min_nights = model.new_int_var(0, num_days, f"{prefix}: min_nights")
        night_delta = model.new_int_var(0, num_days, f"{prefix}: night_delta")
        model.add_max_equality(max_nights, night_counts)
        model.add_min_equality(min_nights, night_counts)
        model.add(night_delta == max_nights - min_nights)
        cost_variables.append(night_delta)
        cost_coefficients.append(night_balancing_cost)

    if work_balancing_cost > 0:
        work_counts = []
        for e in range(num_employees):
            count = model.new_int_var(0, num_days, f"{prefix}(employee {e}): work")
            model.add(
                count
                == sum(
                    work[e, s, d]
                    for s in work_shift_indices
                    for d in range(num_days)
                )
            )
            work_counts.append(count)

        max_work = model.new_int_var(0, num_days, f"{prefix}: max_work")
        min_work = model.new_int_var(0, num_days, f"{prefix}: min_work")
        work_delta = model.new_int_var(0, num_days, f"{prefix}: work_delta")
        model.add_max_equality(max_work, work_counts)
        model.add_min_equality(min_work, work_counts)
        model.add(work_delta == max_work - min_work)
        cost_variables.append(work_delta)
        cost_coefficients.append(work_balancing_cost)

    return cost_variables, cost_coefficients


def add_overtime_balance_objective(
    model: cp_model.CpModel,
    work: dict[tuple[int, int, int], cp_model.BoolVarT],
    shifts: list[str],
    attributes: dict[str, dict[str, Any]],
    num_employees: int,
    num_days: int,
    employee_overtime_hours: list[int],
    overtime_balance: dict[str, Any],
) -> tuple[list[cp_model.IntVar], list[int]]:
    """Adds objective terms that prefer recovery for employees with overtime."""
    if not employee_overtime_hours:
        return [], []

    if "recovery_shift" not in overtime_balance and "R" not in shifts:
        return [], []

    recovery_shift = shift_index(shifts, overtime_balance.get("recovery_shift", "R"))
    recovery_duration = int(attributes[shifts[recovery_shift]].get("duration_hours", 0))
    if recovery_duration <= 0:
        return [], []

    max_remaining_cost = int(overtime_balance.get("max_remaining_cost", 4))
    remaining_cost = int(overtime_balance.get("remaining_cost", 1))
    over_recovery_cost = int(overtime_balance.get("over_recovery_cost", 20))
    if max_remaining_cost <= 0 and remaining_cost <= 0 and over_recovery_cost <= 0:
        return [], []

    cost_variables: list[cp_model.IntVar] = []
    cost_coefficients: list[int] = []
    remaining_variables: list[cp_model.IntVar] = []
    max_overtime = max(employee_overtime_hours)
    max_recovery = num_days * recovery_duration

    for e, overtime_hours in enumerate(employee_overtime_hours):
        recovery_hours = model.new_int_var(
            0, max_recovery, f"overtime_balance(employee {e}): recovery_hours"
        )
        model.add(
            recovery_hours
            == sum(work[e, recovery_shift, d] * recovery_duration for d in range(num_days))
        )

        remaining_delta = model.new_int_var(
            -max_recovery,
            max_overtime,
            f"overtime_balance(employee {e}): remaining_delta",
        )
        model.add(remaining_delta == overtime_hours - recovery_hours)
        remaining = model.new_int_var(
            0, max_overtime, f"overtime_balance(employee {e}): remaining"
        )
        model.add_max_equality(remaining, [remaining_delta, 0])
        remaining_variables.append(remaining)
        if remaining_cost > 0:
            cost_variables.append(remaining)
            cost_coefficients.append(remaining_cost)

        over_delta = model.new_int_var(
            -max_overtime,
            max_recovery,
            f"overtime_balance(employee {e}): over_recovery_delta",
        )
        model.add(over_delta == recovery_hours - overtime_hours)
        over_recovered = model.new_int_var(
            0, max_recovery, f"overtime_balance(employee {e}): over_recovered"
        )
        model.add_max_equality(over_recovered, [over_delta, 0])
        if over_recovery_cost > 0:
            cost_variables.append(over_recovered)
            cost_coefficients.append(over_recovery_cost)

    if max_remaining_cost > 0:
        max_remaining = model.new_int_var(
            0, max_overtime, "overtime_balance: max_remaining"
        )
        model.add_max_equality(max_remaining, remaining_variables)
        cost_variables.append(max_remaining)
        cost_coefficients.append(max_remaining_cost)

    return cost_variables, cost_coefficients


def add_soft_sum_constraint(
    model: cp_model.CpModel,
    works: list[cp_model.BoolVarT],
    hard_min: int,
    soft_min: int,
    min_cost: int,
    soft_max: int,
    hard_max: int,
    max_cost: int,
    prefix: str,
) -> tuple[list[cp_model.IntVar], list[int]]:
    """sum constraint with soft and hard bounds.

    This constraint counts the variables assigned to true from works.
    If forbids sum < hard_min or > hard_max.
    Then it creates penalty terms if the sum is < soft_min or > soft_max.

    Args:
      model: the sequence constraint is built on this model.
      works: a list of Boolean variables.
      hard_min: any sequence of true variables must have a sum of at least
        hard_min.
      soft_min: any sequence should have a sum of at least soft_min, or a linear
        penalty on the delta will be added to the objective.
      min_cost: the coefficient of the linear penalty if the sum is less than
        soft_min.
      soft_max: any sequence should have a sum of at most soft_max, or a linear
        penalty on the delta will be added to the objective.
      hard_max: any sequence of true variables must have a sum of at most
        hard_max.
      max_cost: the coefficient of the linear penalty if the sum is more than
        soft_max.
      prefix: a base name for penalty variables.

    Returns:
      a tuple (variables_list, coefficient_list) containing the different
      penalties created by the sequence constraint.
    """
    cost_variables = []
    cost_coefficients = []
    sum_var = model.new_int_var(hard_min, hard_max, "")
    # This adds the hard constraints on the sum.
    model.add(sum_var == sum(works))

    # Penalize sums below the soft_min target.
    if soft_min > hard_min and min_cost > 0:
        delta = model.new_int_var(-len(works), len(works), "")
        model.add(delta == soft_min - sum_var)
        # TODO(user): Compare efficiency with only excess >= soft_min - sum_var.
        excess = model.new_int_var(0, 7, prefix + ": under_sum")
        model.add_max_equality(excess, [delta, 0])
        cost_variables.append(excess)
        cost_coefficients.append(min_cost)

    # Penalize sums above the soft_max target.
    if soft_max < hard_max and max_cost > 0:
        delta = model.new_int_var(-7, 7, "")
        model.add(delta == sum_var - soft_max)
        excess = model.new_int_var(0, 7, prefix + ": over_sum")
        model.add_max_equality(excess, [delta, 0])
        cost_variables.append(excess)
        cost_coefficients.append(max_cost)

    return cost_variables, cost_coefficients


def solve_shift_scheduling(config: dict[str, Any], params: str, output_proto: str):
    """Solves broad shifts and departments in one CP-SAT model."""
    num_employees = int(config["num_employees"])
    num_weeks = int(config["num_weeks"])
    shifts = list(config["shifts"])
    attributes = shift_attributes(config, shifts)
    departments = normalize_departments(config)
    departments_by_id = department_by_id(departments)
    departments_by_shift: dict[str, list[dict[str, Any]]] = {
        shift: [department for department in departments if department["shift"] == shift]
        for shift in shifts
    }
    employee_names = config.get("employee_names")
    employee_overtime_hours = _normalize_employee_overtime_hours(config, num_employees)
    fixed_assignments = config.get("fixed_assignments", [])
    requests = config.get("requests", [])
    shift_constraints = config.get("shift_constraints", [])
    weekly_sum_constraints = config.get("weekly_sum_constraints", [])
    penalized_transitions = config.get("penalized_transitions", [])
    weekly_cover_demands = derive_weekly_cover_demands(config, departments)
    excess_cover_penalties = config.get("excess_cover_penalties", [])
    work_balance = config.get("work_balance", {})
    department_fixed_assignments = config.get("department_fixed_assignments", [])
    department_requests = config.get("department_requests", [])
    department_switch_penalty = int(config.get("department_switch_penalty", 1))
    max_hours_per_week = _normalize_max_hours_per_week(config)
    overtime_balance = config.get("overtime_balance", {})

    num_days = num_weeks * 7
    num_shifts = len(shifts)

    model = cp_model.CpModel()

    work = {}
    for e in range(num_employees):
        for s in range(num_shifts):
            for d in range(num_days):
                work[e, s, d] = model.new_bool_var(f"work{e}_{s}_{d}")

    department_work: dict[tuple[int, str, int], cp_model.BoolVarT] = {}
    for e in range(num_employees):
        for department in departments:
            department_id = department["id"]
            for d in range(num_days):
                department_work[e, department_id, d] = model.new_bool_var(
                    f"department_work{e}_{department_id}_{d}"
                )

    # Linear terms of the objective in a minimization context.
    obj_int_vars: list[cp_model.IntVar] = []
    obj_int_coeffs: list[int] = []
    obj_bool_vars: list[cp_model.BoolVarT] = []
    obj_bool_coeffs: list[int] = []

    # Exactly one shift per day.
    for e in range(num_employees):
        for d in range(num_days):
            model.add_exactly_one(work[e, s, d] for s in range(num_shifts))

    # Link department choices to the broad shift assignment. This keeps shift
    # semantics broad while making department feasibility part of the same solve.
    for e in range(num_employees):
        for s, shift in enumerate(shifts):
            shift_departments = departments_by_shift.get(shift, [])
            if not shift_departments:
                continue
            for d in range(num_days):
                model.add(
                    sum(
                        department_work[e, department["id"], d]
                        for department in shift_departments
                    )
                    == work[e, s, d]
                )

    fixed_assignment_cells = set()
    for e, shift, d in fixed_assignments:
        fixed_assignment_cells.add((int(e), shift_index(shifts, shift), int(d)))

    requested_assignment_cells = set()
    for e, shift, d, weight in requests:
        if int(weight) < 0:
            requested_assignment_cells.add((int(e), shift_index(shifts, shift), int(d)))

    # Some shifts, such as formation days, should only exist when explicitly
    # fixed by the user.
    fixed_only_shift_indices = shift_indices_with_attribute(
        shifts, attributes, "requires_fixed_assignment"
    )
    for s in fixed_only_shift_indices:
        for e in range(num_employees):
            for d in range(num_days):
                if (e, s, d) not in fixed_assignment_cells:
                    model.add(work[e, s, d] == 0)

    # Some shifts, such as holidays, may only be used on cells that were fixed
    # or explicitly requested as desired.
    requested_only_shift_indices = shift_indices_with_attribute(
        shifts, attributes, "requires_assignment_request"
    )
    for s in requested_only_shift_indices:
        for e in range(num_employees):
            for d in range(num_days):
                if (e, s, d) not in fixed_assignment_cells and (
                    e,
                    s,
                    d,
                ) not in requested_assignment_cells:
                    model.add(work[e, s, d] == 0)

    # Fixed assignments.
    for e, shift, d in fixed_assignments:
        s = shift_index(shifts, shift)
        model.add(work[e, s, d] == 1)

    for employee, department_id, day in department_fixed_assignments:
        if department_id not in departments_by_id:
            raise ValueError(f"Unknown department id: {department_id}")
        if not (0 <= int(employee) < num_employees and 0 <= int(day) < num_days):
            raise ValueError("Department fixed assignment is out of range")
        model.add(department_work[int(employee), department_id, int(day)] == 1)

    # Employee requests
    for e, shift, d, w in requests:
        s = shift_index(shifts, shift)
        obj_bool_vars.append(work[e, s, d])
        obj_bool_coeffs.append(w)

    for employee, department_id, day, weight in department_requests:
        if department_id not in departments_by_id:
            raise ValueError(f"Unknown department id: {department_id}")
        if not (0 <= int(employee) < num_employees and 0 <= int(day) < num_days):
            raise ValueError("Department request is out of range")
        obj_bool_vars.append(department_work[int(employee), department_id, int(day)])
        obj_bool_coeffs.append(int(weight))

    variables, coeffs = add_overtime_balance_objective(
        model,
        work,
        shifts,
        attributes,
        num_employees,
        num_days,
        employee_overtime_hours,
        overtime_balance,
    )
    obj_int_vars.extend(variables)
    obj_int_coeffs.extend(coeffs)

    # Balance the maximum number of work shifts and night shifts assigned to one
    # employee.
    night_balancing_cost = int(work_balance.get("night_cost", 0))
    work_balancing_cost = int(work_balance.get("work_cost", 0))
    if night_balancing_cost > 0 or work_balancing_cost > 0:
        work_shift_indices = shift_indices_with_attribute(
            shifts, attributes, "counts_as_work"
        )
        night_shift = None
        if night_balancing_cost > 0:
            if "night_shift" in work_balance:
                night_shift = shift_index(shifts, work_balance["night_shift"])
            else:
                night_shifts = shift_indices_with_attribute(
                    shifts, attributes, "is_night"
                )
                if not night_shifts:
                    raise ValueError("night_cost requires a configured night shift")
                night_shift = night_shifts[0]
        variables, coeffs = add_work_balancing_constraint(
            model,
            work,
            num_employees,
            num_days,
            work_shift_indices,
            night_shift,
            night_balancing_cost,
            work_balancing_cost,
            "work_balance",
        )
        obj_int_vars.extend(variables)
        obj_int_coeffs.extend(coeffs)

    # Shift constraints
    for ct in shift_constraints:
        shift_ref, hard_min, soft_min, min_cost, soft_max, hard_max, max_cost = ct
        shift = shift_index(shifts, shift_ref)
        for e in range(num_employees):
            works = [work[e, shift, d] for d in range(num_days)]
            variables, coeffs = add_soft_sequence_constraint(
                model,
                works,
                hard_min,
                soft_min,
                min_cost,
                soft_max,
                hard_max,
                max_cost,
                f"shift_constraint(employee {e}, shift {shifts[shift]})",
            )
            obj_bool_vars.extend(variables)
            obj_bool_coeffs.extend(coeffs)

    # Weekly sum constraints
    for ct in weekly_sum_constraints:
        shift_ref, hard_min, soft_min, min_cost, soft_max, hard_max, max_cost = ct
        shift = shift_index(shifts, shift_ref)
        for e in range(num_employees):
            for w in range(num_weeks):
                works = [work[e, shift, d + w * 7] for d in range(7)]
                variables, coeffs = add_soft_sum_constraint(
                    model,
                    works,
                    hard_min,
                    soft_min,
                    min_cost,
                    soft_max,
                    hard_max,
                    max_cost,
                    f"weekly_sum_constraint(employee {e}, shift {shifts[shift]}, week {w})",
                )
                obj_int_vars.extend(variables)
                obj_int_coeffs.extend(coeffs)

    # Penalized transitions
    for previous_shift_ref, next_shift_ref, cost in penalized_transitions:
        previous_shift = shift_index(shifts, previous_shift_ref)
        next_shift = shift_index(shifts, next_shift_ref)
        for e in range(num_employees):
            for d in range(num_days - 1):
                previous_work = work[e, previous_shift, d]
                next_work = work[e, next_shift, d + 1]
                if cost == 0:
                    model.add_bool_or([~previous_work, ~next_work])
                else:
                    trans_var = model.new_bool_var(
                        f"transition (employee={e}, day={d})"
                    )
                    model.add_bool_or([~previous_work, ~next_work, trans_var])
                    model.add_implication(trans_var, previous_work)
                    model.add_implication(trans_var, next_work)
                    obj_bool_vars.append(trans_var)
                    obj_bool_coeffs.append(cost)

    if department_switch_penalty > 0:
        for shift, shift_departments in departments_by_shift.items():
            if len(shift_departments) < 2:
                continue
            for e in range(num_employees):
                for d in range(num_days - 1):
                    for previous_department in shift_departments:
                        previous_id = previous_department["id"]
                        previous_var = department_work[e, previous_id, d]
                        for next_department in shift_departments:
                            next_id = next_department["id"]
                            if previous_id == next_id:
                                continue
                            next_var = department_work[e, next_id, d + 1]
                            switch_var = model.new_bool_var(
                                "department_switch"
                                f"(employee={e}, day={d}, shift={shift}, "
                                f"from={previous_id}, to={next_id})"
                            )
                            model.add_bool_or(
                                [~previous_var, ~next_var, switch_var]
                            )
                            obj_bool_vars.append(switch_var)
                            obj_bool_coeffs.append(department_switch_penalty)

    # Exact department cover. The broad cover constraints below are redundant
    # but useful propagation and keep proto comparisons easy to inspect.
    for department in departments:
        department_id = department["id"]
        for day in range(num_days):
            model.add(
                sum(
                    department_work[e, department_id, day]
                    for e in range(num_employees)
                )
                == int(department["requirements"][day % 7])
            )

    if max_hours_per_week is not None:
        for e in range(num_employees):
            for w in range(num_weeks):
                weekly_hour_terms = []
                for department in departments:
                    department_id = department["id"]
                    duration_hours = int(department["duration_hours"])
                    for d in range(7):
                        weekly_hour_terms.append(
                            department_work[e, department_id, w * 7 + d]
                            * duration_hours
                        )

                for s, shift in enumerate(shifts):
                    if departments_by_shift.get(shift):
                        continue
                    duration_hours = int(attributes[shift].get("duration_hours", 0))
                    if duration_hours <= 0:
                        continue
                    for d in range(7):
                        weekly_hour_terms.append(work[e, s, w * 7 + d] * duration_hours)

                model.add(sum(weekly_hour_terms) <= max_hours_per_week)

    # Cover constraints
    cover_shift_indices = shift_indices_with_attribute(shifts, attributes, "covers_demand")
    if excess_cover_penalties and len(excess_cover_penalties) != len(cover_shift_indices):
        raise ValueError(
            "excess_cover_penalties must match the number of demand-covering shifts"
        )
    for row in weekly_cover_demands:
        if len(row) != len(cover_shift_indices):
            raise ValueError(
                "weekly_cover_demands rows must match the number of demand-covering shifts"
            )

    for cover_index, s in enumerate(cover_shift_indices):
        for w in range(num_weeks):
            for d in range(7):
                works = [work[e, s, w * 7 + d] for e in range(num_employees)]
                demand = weekly_cover_demands[d][cover_index]
                model.add(sum(works) == demand)

    # Objective
    model.minimize(
        sum(obj_bool_vars[i] * obj_bool_coeffs[i] for i in range(len(obj_bool_vars)))
        + sum(obj_int_vars[i] * obj_int_coeffs[i] for i in range(len(obj_int_vars)))
    )

    if output_proto:
        print(f"Writing proto to {output_proto}")
        with open(output_proto, "w") as text_file:
            text_file.write(str(model))

    # Solve the model.
    solver = cp_model.CpSolver()
    if params:
        solver.parameters.parse_text_format(params)
    solution_printer = cp_model.ObjectiveSolutionPrinter()
    status = solver.solve(model, solution_printer)

    # Print solution.
    result = None
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        plan = []
        department_plan: list[list[str | None]] = []
        for e in range(num_employees):
            employee_plan = []
            employee_department_plan: list[str | None] = []
            for d in range(num_days):
                for s in range(num_shifts):
                    if solver.boolean_value(work[e, s, d]):
                        employee_plan.append(shifts[s])
                        break
                assigned_department = None
                for department in departments:
                    department_id = department["id"]
                    if solver.boolean_value(department_work[e, department_id, d]):
                        assigned_department = department_id
                        break
                employee_department_plan.append(assigned_department)
            plan.append(employee_plan)
            department_plan.append(employee_department_plan)

        print()
        print("Schedule penalties:")
        printed_penalty = False
        for i, var in enumerate(obj_bool_vars):
            if solver.boolean_value(var):
                penalty = obj_bool_coeffs[i]
                if penalty > 0:
                    print(f"  {var.name} violated, penalty={penalty}")
                else:
                    print(f"  {var.name} fulfilled, gain={-penalty}")
                printed_penalty = True

        for i, var in enumerate(obj_int_vars):
            if solver.value(var) > 0:
                print(
                    f"  {var.name} violated by {solver.value(var)}, linear"
                    f" penalty={obj_int_coeffs[i]}"
                )
                printed_penalty = True

        if not printed_penalty:
            print("  none")

        result = {
            "shifts": shifts,
            "num_workers": num_employees,
            "num_days": num_days,
            "plan": plan,
            "department_plan": department_plan,
            "departments": departments,
        }
        if employee_names:
            result["employee_names"] = employee_names
        result["employee_overtime_hours"] = employee_overtime_hours

    print()
    print("Schedule solver stats:")
    print(solver.response_stats().rstrip())
    return result


def solve_schedule(config: dict[str, Any], params: str, output_proto: str):
    """Runs the shift and department optimizer."""
    print("Schedule optimization")
    return solve_shift_scheduling(config, params, output_proto)


def main(_):
    if _CONFIG is None or _PARAMS is None or _OUTPUT_PROTO is None:
        raise RuntimeError("CLI flags are not initialized")
    config = parse_config(_CONFIG.value)
    result = solve_schedule(config, _PARAMS.value, _OUTPUT_PROTO.value)
    send_to_frontend(result)


if __name__ == "__main__":
    _define_cli_flags()
    app.run(main)
