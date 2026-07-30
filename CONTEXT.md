# MedShift Scheduling

MedShift describes a hospital staffing scenario and selects a roster that satisfies its commitments and policies while best meeting its objectives.

## Language

**Scenario Data**:
Facts and user-entered decisions that define the scheduling situation to solve, including employees, the planning horizon, staffing demand, weekly-hours ceilings, assignments, and preferences.
_Avoid_: Problem data, constraint data

**Employee**:
A person included in the scheduling scenario whose identity remains stable when their display name or position in a list changes.
_Avoid_: Worker index, employee row

**Planning Horizon**:
The whole number of consecutive Monday-through-Sunday weeks covered by one scheduling scenario.
_Avoid_: Number of days, calendar range, `num_weeks`

**Shift Type**:
A predetermined kind of daily employee status whose semantics include whether it is work, covers staffing demand, occurs at night, consumes hours, recovers overtime, or requires explicit user input before assignment.
_Avoid_: User-defined shift, shift code, shift attribute record

**Department**:
A work area with a stable identity, an associated Shift Type, an assignment duration, and Staffing Demand. Its identity remains stable when its display name, symbol, or color changes.
_Avoid_: Department row, department index

**Assignment Hours**:
The hours an assignment contributes toward an Employee's Weekly-Hours Ceiling. A department assignment uses the Department's duration; any other assignment uses its Shift Type's duration.
_Avoid_: Work hours, shift duration

**Staffing Demand**:
The exact number of employees to assign to a department for each day of the week. Assigning either fewer or more employees fails the demand.
_Avoid_: Daily employee count, cover constraint, requirement matrix

**Weekly-Hours Ceiling**:
The mandatory maximum number of hours assigned to one specific employee within a planning week. Every employee has their own ceiling.
_Avoid_: Maximum weekly hours constraint, weekly cap

**Fixed Assignment**:
A user commitment that a particular employee must receive a particular shift or department assignment on a particular day.
_Avoid_: Hard constraint, locked cell

**Employee Preference**:
A specific employee's expressed desire for or against a particular shift or department assignment on a particular day. It does not carry its own objective weight.
_Avoid_: Request, soft constraint

**Employee-Preference Objective**:
The global relative importance of satisfying desired assignments and avoiding unwanted assignments across all employees.
_Avoid_: Request weight, per-preference weight

**Workload-Balance Objective**:
The priority given to reducing, across the entire Planning Horizon, the difference between the employees with the most and fewest assignments whose Shift Type counts toward workload balance.
_Avoid_: Work cost, work balance constraint

**Night-Shift-Balance Objective**:
The priority given to reducing, across the entire Planning Horizon, the difference between the employees with the most and fewest night-shift assignments.
_Avoid_: Night cost, work balance constraint

**Remaining-Overtime Objective**:
The priority given to reducing the total unrecovered overtime across all employees.
_Avoid_: Remaining cost, overtime balance

**Maximum-Remaining-Overtime Objective**:
The priority given to reducing the largest unrecovered overtime balance held by any one employee.
_Avoid_: Maximum remaining cost, overtime balance

**Excess-Recovery Objective**:
The priority given to avoiding recovery assignments whose hours exceed an employee's accrued overtime.
_Avoid_: Over-recovery cost, overtime balance

**Consecutive-Department-Continuity Objective**:
The priority given to keeping an employee in the same department on adjacent days assigned to the same Shift Type, including Sunday-to-Monday boundaries. An intervening day without that Shift Type ends the continuity run.
_Avoid_: Department switch cost, department continuity

**Scheduling Policy**:
A reusable rule that determines which rosters are allowed independently of one particular employee's fixed assignments or preferences.
_Avoid_: Constraint

**Optimization Objective**:
A soft scheduling priority used to choose among otherwise allowed rosters.
_Avoid_: Soft constraint, cost function

**Objective Weight**:
A positive integer controlling an optimization objective's importance relative to the other objectives in the current scenario. Direction is expressed separately, and weights are manually calibrated rather than normalized when the workforce or planning horizon changes.
_Avoid_: Low importance, normal importance, high importance, ponderation

**Consecutive-Shift Limit**:
The optional lower and upper bounds on an uninterrupted run of one Shift Type across the continuous Planning Horizon, including Sunday-to-Monday boundaries. A missing bound means unbounded, and a run touching either outer boundary is evaluated as complete.
_Avoid_: Shift constraint, hard sequence constraint

**Consecutive-Shift Preference**:
The optional preferred lower and upper bounds on an uninterrupted run of one Shift Type across the continuous Planning Horizon, including Sunday-to-Monday boundaries. A missing bound has no preference, and a run touching either outer boundary is evaluated as complete.
_Avoid_: Soft sequence constraint

**Weekly Shift-Count Limit**:
The optional lower and upper bounds on assignments to one Shift Type for an employee in a planning week. A missing bound means unbounded.
_Avoid_: Weekly sum constraint

**Weekly Shift-Count Preference**:
The optional preferred lower and upper bounds on assignments to one Shift Type for an employee in a planning week. A missing bound has no preference.
_Avoid_: Soft weekly sum constraint

**Forbidden Shift Transition**:
A pair of Shift Types that may not be assigned consecutively to the same employee in the specified order, including across a Sunday-to-Monday boundary.
_Avoid_: Zero-cost transition, penalized transition

**Shift Transition Preference**:
An explicit encouragement or discouragement of assigning one shift type immediately after another to the same employee.
_Avoid_: Negative penalty, transition cost
