
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
import tomllib
import urllib.request
from typing import Any

from absl import app
from absl import flags

from ortools.sat.python import cp_model

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
            "covers_demand": shift not in {"O", "F", "R"},
            "counts_as_weekly_off": shift == "O",
            "is_night": shift == "N",
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
    """Solves the shift scheduling problem."""
    num_employees = int(config["num_employees"])
    num_weeks = int(config["num_weeks"])
    shifts = list(config["shifts"])
    attributes = shift_attributes(config, shifts)
    employee_names = config.get("employee_names")
    fixed_assignments = config["fixed_assignments"]
    requests = config["requests"]
    shift_constraints = config["shift_constraints"]
    weekly_sum_constraints = config["weekly_sum_constraints"]
    penalized_transitions = config["penalized_transitions"]
    weekly_cover_demands = config["weekly_cover_demands"]
    excess_cover_penalties = config["excess_cover_penalties"]
    work_balance = config.get("work_balance", {})

    num_days = num_weeks * 7
    num_shifts = len(shifts)

    model = cp_model.CpModel()

    work = {}
    for e in range(num_employees):
        for s in range(num_shifts):
            for d in range(num_days):
                work[e, s, d] = model.new_bool_var(f"work{e}_{s}_{d}")

    # Linear terms of the objective in a minimization context.
    obj_int_vars: list[cp_model.IntVar] = []
    obj_int_coeffs: list[int] = []
    obj_bool_vars: list[cp_model.BoolVarT] = []
    obj_bool_coeffs: list[int] = []

    # Exactly one shift per day.
    for e in range(num_employees):
        for d in range(num_days):
            model.add_exactly_one(work[e, s, d] for s in range(num_shifts))

    # Fixed assignments.
    for e, shift, d in fixed_assignments:
        s = shift_index(shifts, shift)
        model.add(work[e, s, d] == 1)

    # Employee requests
    for e, shift, d, w in requests:
        s = shift_index(shifts, shift)
        obj_bool_vars.append(work[e, s, d])
        obj_bool_coeffs.append(w)

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
                transition = [
                    ~work[e, previous_shift, d],
                    ~work[e, next_shift, d + 1],
                ]
                if cost == 0:
                    model.add_bool_or(transition)
                else:
                    trans_var = model.new_bool_var(
                        f"transition (employee={e}, day={d})"
                    )
                    transition.append(trans_var)
                    model.add_bool_or(transition)
                    obj_bool_vars.append(trans_var)
                    obj_bool_coeffs.append(cost)

    # Cover constraints
    cover_shift_indices = shift_indices_with_attribute(shifts, attributes, "covers_demand")
    if len(excess_cover_penalties) != len(cover_shift_indices):
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
                min_demand = weekly_cover_demands[d][cover_index]
                worked = model.new_int_var(min_demand, num_employees, "")
                model.add(worked == sum(works))
                over_penalty = excess_cover_penalties[cover_index]
                if over_penalty > 0:
                    name = f"excess_demand(shift={shifts[s]}, week={w}, day={d})"
                    excess = model.new_int_var(0, num_employees - min_demand, name)
                    model.add(excess == worked - min_demand)
                    obj_int_vars.append(excess)
                    obj_int_coeffs.append(over_penalty)

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
        print()
        header = "          "
        for w in range(num_weeks):
            header += "M T W T F S S "
        print(header)
        plan = []
        for e in range(num_employees):
            schedule = ""
            employee_plan = []
            for d in range(num_days):
                for s in range(num_shifts):
                    if solver.boolean_value(work[e, s, d]):
                        employee_plan.append(shifts[s])
                        schedule += shifts[s] + " "
            plan.append(employee_plan)
            print(f"worker {e}: {schedule}")
        print()
        print("Penalties:")
        for i, var in enumerate(obj_bool_vars):
            if solver.boolean_value(var):
                penalty = obj_bool_coeffs[i]
                if penalty > 0:
                    print(f"  {var.name} violated, penalty={penalty}")
                else:
                    print(f"  {var.name} fulfilled, gain={-penalty}")

        for i, var in enumerate(obj_int_vars):
            if solver.value(var) > 0:
                print(
                    f"  {var.name} violated by {solver.value(var)}, linear"
                    f" penalty={obj_int_coeffs[i]}"
                )

        result = {
            "shifts": shifts,
            "num_workers": num_employees,
            "num_days": num_days,
            "plan": plan,
        }
        if employee_names:
            result["employee_names"] = employee_names

    print()
    print(solver.response_stats())
    return result


def main(_):
    config = parse_config(_CONFIG.value)
    result = solve_shift_scheduling(config, _PARAMS.value, _OUTPUT_PROTO.value)
    send_to_frontend(result)


if __name__ == "__main__":
    app.run(main)
