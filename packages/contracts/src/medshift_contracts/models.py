from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    NonNegativeInt,
    model_validator,
)


EmployeeId = UUID
DepartmentId = UUID
DecisionId = UUID
ProposalId = UUID
DayIndex = Annotated[int, Field(ge=0)]
ObjectiveWeight = Annotated[int, Field(gt=0)]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ShiftType(StrEnum):
    OFF = "off"
    DAY = "day"
    NIGHT = "night"
    FORMATION = "formation"
    RECOVERY = "recovery"
    HOLIDAY = "holiday"


class OffShiftTypeDefinition(ContractModel):
    shift_type: Literal[ShiftType.OFF]
    code: Literal["O"]
    name: Literal["Off"]
    covers_demand: Literal[False]
    is_night: Literal[False]
    counts_toward_workload_balance: Literal[False]
    assignment_hours: Literal[0]
    recovers_overtime: Literal[False]
    eligibility: Literal["automatic"]


class DayShiftTypeDefinition(ContractModel):
    shift_type: Literal[ShiftType.DAY]
    code: Literal["D"]
    name: Literal["Day"]
    covers_demand: Literal[True]
    is_night: Literal[False]
    counts_toward_workload_balance: Literal[True]
    assignment_hours: Literal[None]
    recovers_overtime: Literal[False]
    eligibility: Literal["automatic"]


class NightShiftTypeDefinition(ContractModel):
    shift_type: Literal[ShiftType.NIGHT]
    code: Literal["N"]
    name: Literal["Night"]
    covers_demand: Literal[True]
    is_night: Literal[True]
    counts_toward_workload_balance: Literal[True]
    assignment_hours: Literal[None]
    recovers_overtime: Literal[False]
    eligibility: Literal["automatic"]


class FormationShiftTypeDefinition(ContractModel):
    shift_type: Literal[ShiftType.FORMATION]
    code: Literal["F"]
    name: Literal["Formation"]
    covers_demand: Literal[False]
    is_night: Literal[False]
    counts_toward_workload_balance: Literal[True]
    assignment_hours: Literal[8]
    recovers_overtime: Literal[False]
    eligibility: Literal["fixed_assignment_only"]


class RecoveryShiftTypeDefinition(ContractModel):
    shift_type: Literal[ShiftType.RECOVERY]
    code: Literal["R"]
    name: Literal["Recovery"]
    covers_demand: Literal[False]
    is_night: Literal[False]
    counts_toward_workload_balance: Literal[False]
    assignment_hours: Literal[8]
    recovers_overtime: Literal[True]
    eligibility: Literal["automatic"]


class HolidayShiftTypeDefinition(ContractModel):
    shift_type: Literal[ShiftType.HOLIDAY]
    code: Literal["H"]
    name: Literal["Holiday"]
    covers_demand: Literal[False]
    is_night: Literal[False]
    counts_toward_workload_balance: Literal[True]
    assignment_hours: Literal[0]
    recovers_overtime: Literal[False]
    eligibility: Literal["fixed_assignment_or_desired_preference"]


ShiftTypeDefinition = Annotated[
    OffShiftTypeDefinition
    | DayShiftTypeDefinition
    | NightShiftTypeDefinition
    | FormationShiftTypeDefinition
    | RecoveryShiftTypeDefinition
    | HolidayShiftTypeDefinition,
    Field(discriminator="shift_type"),
]

ShiftTypeCatalogue = tuple[
    OffShiftTypeDefinition,
    DayShiftTypeDefinition,
    NightShiftTypeDefinition,
    FormationShiftTypeDefinition,
    RecoveryShiftTypeDefinition,
    HolidayShiftTypeDefinition,
]

SHIFT_TYPES: ShiftTypeCatalogue = (
    OffShiftTypeDefinition(
        shift_type=ShiftType.OFF,
        code="O",
        name="Off",
        covers_demand=False,
        is_night=False,
        counts_toward_workload_balance=False,
        assignment_hours=0,
        recovers_overtime=False,
        eligibility="automatic",
    ),
    DayShiftTypeDefinition(
        shift_type=ShiftType.DAY,
        code="D",
        name="Day",
        covers_demand=True,
        is_night=False,
        counts_toward_workload_balance=True,
        assignment_hours=None,
        recovers_overtime=False,
        eligibility="automatic",
    ),
    NightShiftTypeDefinition(
        shift_type=ShiftType.NIGHT,
        code="N",
        name="Night",
        covers_demand=True,
        is_night=True,
        counts_toward_workload_balance=True,
        assignment_hours=None,
        recovers_overtime=False,
        eligibility="automatic",
    ),
    FormationShiftTypeDefinition(
        shift_type=ShiftType.FORMATION,
        code="F",
        name="Formation",
        covers_demand=False,
        is_night=False,
        counts_toward_workload_balance=True,
        assignment_hours=8,
        recovers_overtime=False,
        eligibility="fixed_assignment_only",
    ),
    RecoveryShiftTypeDefinition(
        shift_type=ShiftType.RECOVERY,
        code="R",
        name="Recovery",
        covers_demand=False,
        is_night=False,
        counts_toward_workload_balance=False,
        assignment_hours=8,
        recovers_overtime=True,
        eligibility="automatic",
    ),
    HolidayShiftTypeDefinition(
        shift_type=ShiftType.HOLIDAY,
        code="H",
        name="Holiday",
        covers_demand=False,
        is_night=False,
        counts_toward_workload_balance=True,
        assignment_hours=0,
        recovers_overtime=False,
        eligibility="fixed_assignment_or_desired_preference",
    ),
)


class Employee(ContractModel):
    employee_id: EmployeeId
    display_name: Annotated[str, Field(min_length=1)]
    overtime_hours: Annotated[int, Field(ge=0, le=1000)]
    weekly_hours_ceiling: Annotated[int, Field(ge=1, le=168)]


class Department(ContractModel):
    department_id: DepartmentId
    display_name: Annotated[str, Field(min_length=1)]
    shift_type: Literal[ShiftType.DAY, ShiftType.NIGHT]
    symbol: Annotated[str, Field(min_length=1, max_length=3)]
    color: Annotated[str, Field(pattern=r"^#[0-9A-Fa-f]{6}$")]
    duration_hours: Annotated[int, Field(ge=1, le=24)]
    staffing_demand: tuple[
        NonNegativeInt,
        NonNegativeInt,
        NonNegativeInt,
        NonNegativeInt,
        NonNegativeInt,
        NonNegativeInt,
        NonNegativeInt,
    ]


class ShiftTypeTarget(ContractModel):
    kind: Literal["shift_type"]
    shift_type: ShiftType


class DepartmentTarget(ContractModel):
    kind: Literal["department"]
    department_id: DepartmentId


AssignmentTarget = Annotated[
    ShiftTypeTarget | DepartmentTarget,
    Field(discriminator="kind"),
]


class FixedAssignment(ContractModel):
    kind: Literal["fixed_assignment"]
    employee_id: EmployeeId
    day_index: DayIndex
    target: AssignmentTarget


class EmployeePreference(ContractModel):
    kind: Literal["employee_preference"]
    employee_id: EmployeeId
    day_index: DayIndex
    target: AssignmentTarget
    direction: Literal["desired", "avoided"]


PlanningEntry = Annotated[
    FixedAssignment | EmployeePreference,
    Field(discriminator="kind"),
]


class Scenario(ContractModel):
    planning_weeks: Annotated[int, Field(ge=1, le=12)]
    employees: Annotated[list[Employee], Field(min_length=1)]
    departments: list[Department]
    planning_entries: list[PlanningEntry]

    @model_validator(mode="after")
    def validate_references_and_entries(self) -> "Scenario":
        employee_ids = [employee.employee_id for employee in self.employees]
        if len(employee_ids) != len(set(employee_ids)):
            raise ValueError("Employee IDs must be unique")

        departments = {
            department.department_id: department for department in self.departments
        }
        if len(departments) != len(self.departments):
            raise ValueError("Department IDs must be unique")

        occupied_cells: set[tuple[EmployeeId, int]] = set()
        for entry in self.planning_entries:
            if entry.employee_id not in employee_ids:
                raise ValueError("Planning Entry references an unknown Employee")
            if entry.day_index >= self.planning_weeks * 7:
                raise ValueError("Planning Entry falls outside the Planning Horizon")

            cell = (entry.employee_id, entry.day_index)
            if cell in occupied_cells:
                raise ValueError("Only one Planning Entry is allowed per Employee/day")
            occupied_cells.add(cell)

            if isinstance(entry.target, DepartmentTarget):
                if entry.target.department_id not in departments:
                    raise ValueError("Planning Entry references an unknown Department")
                continue

            shift_type = entry.target.shift_type
            if isinstance(entry, EmployeePreference):
                if shift_type is ShiftType.FORMATION:
                    raise ValueError("Formation is eligible only for Fixed Assignments")
                if shift_type is ShiftType.HOLIDAY and entry.direction == "avoided":
                    raise ValueError("Holiday is eligible only as a desired preference")

        return self


class ScenarioSaveRequest(ContractModel):
    base_revision: Annotated[int, Field(ge=1)] | None
    scenario: Scenario


class ConsecutiveShiftLimit(ContractModel):
    id: DecisionId
    kind: Literal["consecutive_shift_limit"]
    shift_type: ShiftType
    minimum_run_length: int | None
    maximum_run_length: int | None

    @model_validator(mode="after")
    def validate_bounds(self) -> "ConsecutiveShiftLimit":
        minimum = self.minimum_run_length
        maximum = self.maximum_run_length
        if minimum is None and maximum is None:
            raise ValueError("At least one run-length bound is required")
        if minimum is not None and minimum <= 0:
            raise ValueError("Minimum run length must be positive")
        if maximum is not None and maximum <= 0:
            raise ValueError("Maximum run length must be positive")
        if minimum is not None and maximum is not None and minimum > maximum:
            raise ValueError("Minimum run length cannot exceed maximum")
        return self


class WeeklyShiftCountLimit(ContractModel):
    id: DecisionId
    kind: Literal["weekly_shift_count_limit"]
    shift_type: ShiftType
    minimum_count: Annotated[int, Field(ge=0, le=7)] | None
    maximum_count: Annotated[int, Field(ge=0, le=7)] | None

    @model_validator(mode="after")
    def validate_bounds(self) -> "WeeklyShiftCountLimit":
        minimum = self.minimum_count
        maximum = self.maximum_count
        if minimum is None and maximum is None:
            raise ValueError("At least one weekly count bound is required")
        if minimum is not None and maximum is not None and minimum > maximum:
            raise ValueError("Minimum weekly count cannot exceed maximum")
        return self


class ForbiddenShiftTransition(ContractModel):
    id: DecisionId
    kind: Literal["forbidden_shift_transition"]
    from_shift_type: ShiftType
    to_shift_type: ShiftType


Policy = Annotated[
    ConsecutiveShiftLimit
    | WeeklyShiftCountLimit
    | ForbiddenShiftTransition,
    Field(discriminator="kind"),
]


class WeightedBound(ContractModel):
    value: int
    weight: ObjectiveWeight


class ConsecutiveShiftPreference(ContractModel):
    id: DecisionId
    kind: Literal["consecutive_shift_preference"]
    shift_type: ShiftType
    preferred_minimum: WeightedBound | None
    preferred_maximum: WeightedBound | None

    @model_validator(mode="after")
    def validate_bounds(self) -> "ConsecutiveShiftPreference":
        minimum = self.preferred_minimum
        maximum = self.preferred_maximum
        if minimum is None and maximum is None:
            raise ValueError("At least one preferred run-length bound is required")
        if minimum is not None and minimum.value <= 0:
            raise ValueError("Preferred minimum run length must be positive")
        if maximum is not None and maximum.value <= 0:
            raise ValueError("Preferred maximum run length must be positive")
        if (
            minimum is not None
            and maximum is not None
            and minimum.value > maximum.value
        ):
            raise ValueError("Preferred minimum run length cannot exceed maximum")
        return self


class WeeklyShiftCountPreference(ContractModel):
    id: DecisionId
    kind: Literal["weekly_shift_count_preference"]
    shift_type: ShiftType
    preferred_minimum: WeightedBound | None
    preferred_maximum: WeightedBound | None

    @model_validator(mode="after")
    def validate_bounds(self) -> "WeeklyShiftCountPreference":
        minimum = self.preferred_minimum
        maximum = self.preferred_maximum
        if minimum is None and maximum is None:
            raise ValueError("At least one preferred weekly count bound is required")
        if minimum is not None and not 0 <= minimum.value <= 7:
            raise ValueError("Preferred minimum weekly count must be within 0...7")
        if maximum is not None and not 0 <= maximum.value <= 7:
            raise ValueError("Preferred maximum weekly count must be within 0...7")
        if (
            minimum is not None
            and maximum is not None
            and minimum.value > maximum.value
        ):
            raise ValueError("Preferred minimum weekly count cannot exceed maximum")
        return self


class ShiftTransitionPreference(ContractModel):
    id: DecisionId
    kind: Literal["shift_transition_preference"]
    from_shift_type: ShiftType
    to_shift_type: ShiftType
    direction: Literal["encourage", "discourage"]
    weight: ObjectiveWeight


class EmployeePreferenceObjective(ContractModel):
    id: DecisionId
    kind: Literal["employee_preference_objective"]
    desired_weight: ObjectiveWeight
    avoided_weight: ObjectiveWeight


class WorkloadBalanceObjective(ContractModel):
    id: DecisionId
    kind: Literal["workload_balance_objective"]
    weight: ObjectiveWeight


class NightShiftBalanceObjective(ContractModel):
    id: DecisionId
    kind: Literal["night_shift_balance_objective"]
    weight: ObjectiveWeight


class RemainingOvertimeObjective(ContractModel):
    id: DecisionId
    kind: Literal["remaining_overtime_objective"]
    weight: ObjectiveWeight


class MaximumRemainingOvertimeObjective(ContractModel):
    id: DecisionId
    kind: Literal["maximum_remaining_overtime_objective"]
    weight: ObjectiveWeight


class ExcessRecoveryObjective(ContractModel):
    id: DecisionId
    kind: Literal["excess_recovery_objective"]
    weight: ObjectiveWeight


class ConsecutiveDepartmentContinuityObjective(ContractModel):
    id: DecisionId
    kind: Literal["consecutive_department_continuity_objective"]
    weight: ObjectiveWeight


Objective = Annotated[
    ConsecutiveShiftPreference
    | WeeklyShiftCountPreference
    | ShiftTransitionPreference
    | EmployeePreferenceObjective
    | WorkloadBalanceObjective
    | NightShiftBalanceObjective
    | RemainingOvertimeObjective
    | MaximumRemainingOvertimeObjective
    | ExcessRecoveryObjective
    | ConsecutiveDepartmentContinuityObjective,
    Field(discriminator="kind"),
]


def _decision_natural_key(
    decision: Policy | Objective,
) -> tuple[object, ...]:
    if isinstance(
        decision,
        (
            ConsecutiveShiftLimit,
            WeeklyShiftCountLimit,
            ConsecutiveShiftPreference,
            WeeklyShiftCountPreference,
        ),
    ):
        return (decision.kind, decision.shift_type)
    if isinstance(
        decision,
        (ForbiddenShiftTransition, ShiftTransitionPreference),
    ):
        return (
            decision.kind,
            decision.from_shift_type,
            decision.to_shift_type,
        )
    return (decision.kind,)


def _validate_decisions(
    policies: list[Policy],
    objectives: list[Objective],
    horizon_days: int,
) -> None:
    decisions = [*policies, *objectives]
    decision_ids = [decision.id for decision in decisions]
    if len(decision_ids) != len(set(decision_ids)):
        raise ValueError("Decision IDs must be unique")

    policy_keys = [_decision_natural_key(policy) for policy in policies]
    if len(policy_keys) != len(set(policy_keys)):
        raise ValueError("Scheduling Policy natural keys must be unique")

    objective_keys = [_decision_natural_key(objective) for objective in objectives]
    if len(objective_keys) != len(set(objective_keys)):
        raise ValueError("Optimization Objective natural keys must be unique")

    for decision in decisions:
        if isinstance(decision, ConsecutiveShiftLimit):
            values = (
                decision.minimum_run_length,
                decision.maximum_run_length,
            )
        elif isinstance(decision, ConsecutiveShiftPreference):
            values = (
                decision.preferred_minimum.value
                if decision.preferred_minimum is not None
                else None,
                decision.preferred_maximum.value
                if decision.preferred_maximum is not None
                else None,
            )
        else:
            continue
        if any(value is not None and value > horizon_days for value in values):
            raise ValueError("Run length cannot exceed the Planning Horizon")


class Workspace(ContractModel):
    schema_version: Literal[1]
    revision: Annotated[int, Field(ge=1)]
    scenario: Scenario
    policies: list[Policy]
    objectives: list[Objective]

    @model_validator(mode="after")
    def validate_decisions(self) -> "Workspace":
        _validate_decisions(
            self.policies,
            self.objectives,
            self.scenario.planning_weeks * 7,
        )
        return self


class AddPolicy(ContractModel):
    kind: Literal["add_policy"]
    policy: Policy


class UpdatePolicy(ContractModel):
    kind: Literal["update_policy"]
    policy_id: DecisionId
    policy: Policy

    @model_validator(mode="after")
    def preserve_id(self) -> "UpdatePolicy":
        if self.policy.id != self.policy_id:
            raise ValueError("A policy update must preserve its ID")
        return self


class RemovePolicy(ContractModel):
    kind: Literal["remove_policy"]
    policy_id: DecisionId


class AddObjective(ContractModel):
    kind: Literal["add_objective"]
    objective: Objective


class UpdateObjective(ContractModel):
    kind: Literal["update_objective"]
    objective_id: DecisionId
    objective: Objective

    @model_validator(mode="after")
    def preserve_id(self) -> "UpdateObjective":
        if self.objective.id != self.objective_id:
            raise ValueError("An objective update must preserve its ID")
        return self


class RemoveObjective(ContractModel):
    kind: Literal["remove_objective"]
    objective_id: DecisionId


WorkspaceChange = Annotated[
    AddPolicy
    | UpdatePolicy
    | RemovePolicy
    | AddObjective
    | UpdateObjective
    | RemoveObjective,
    Field(discriminator="kind"),
]


class DecisionDetail(ContractModel):
    label: Annotated[str, Field(min_length=1)]
    value: Annotated[str, Field(min_length=1)]


class DecisionView(ContractModel):
    title: Annotated[str, Field(min_length=1)]
    summary: Annotated[str, Field(min_length=1)]
    details: list[DecisionDetail]


class ProposalAddition(ContractModel):
    kind: Literal["addition"]
    decision_type: Literal["policy", "objective"]
    after: DecisionView


class ProposalUpdate(ContractModel):
    kind: Literal["update"]
    decision_type: Literal["policy", "objective"]
    before: DecisionView
    after: DecisionView


class ProposalRemoval(ContractModel):
    kind: Literal["removal"]
    decision_type: Literal["policy", "objective"]
    before: DecisionView


ProposalChange = Annotated[
    ProposalAddition | ProposalUpdate | ProposalRemoval,
    Field(discriminator="kind"),
]


class Proposal(ContractModel):
    proposal_id: ProposalId
    base_revision: Annotated[int, Field(ge=1)]
    changes: Annotated[list[ProposalChange], Field(min_length=1)]


class UninitializedState(ContractModel):
    initialized: Literal[False]
    shift_types: ShiftTypeCatalogue


class InitializedState(ContractModel):
    initialized: Literal[True]
    revision: Annotated[int, Field(ge=1)]
    scenario: Scenario
    shift_types: ShiftTypeCatalogue
    policies: list[DecisionView]
    objectives: list[DecisionView]


StateResponse = Annotated[
    UninitializedState | InitializedState,
    Field(discriminator="initialized"),
]


class SolveEmployee(ContractModel):
    employee_id: EmployeeId
    overtime_hours: Annotated[int, Field(ge=0, le=1000)]
    weekly_hours_ceiling: Annotated[int, Field(ge=1, le=168)]


class SolveDepartment(ContractModel):
    department_id: DepartmentId
    shift_type: Literal[ShiftType.DAY, ShiftType.NIGHT]
    duration_hours: Annotated[int, Field(ge=1, le=24)]
    staffing_demand: tuple[
        NonNegativeInt,
        NonNegativeInt,
        NonNegativeInt,
        NonNegativeInt,
        NonNegativeInt,
        NonNegativeInt,
        NonNegativeInt,
    ]


class SolveRequest(ContractModel):
    schema_version: Literal[1]
    workspace_revision: Annotated[int, Field(ge=1)]
    planning_weeks: Annotated[int, Field(ge=1, le=12)]
    employees: Annotated[list[SolveEmployee], Field(min_length=1)]
    departments: list[SolveDepartment]
    planning_entries: list[PlanningEntry]
    policies: list[Policy]
    objectives: list[Objective]

    @model_validator(mode="after")
    def validate_request(self) -> "SolveRequest":
        employee_ids = [employee.employee_id for employee in self.employees]
        if len(employee_ids) != len(set(employee_ids)):
            raise ValueError("Employee IDs must be unique")

        departments = {
            department.department_id: department for department in self.departments
        }
        if len(departments) != len(self.departments):
            raise ValueError("Department IDs must be unique")

        occupied_cells: set[tuple[EmployeeId, int]] = set()
        for entry in self.planning_entries:
            if entry.employee_id not in employee_ids:
                raise ValueError("Planning Entry references an unknown Employee")
            if entry.day_index >= self.planning_weeks * 7:
                raise ValueError("Planning Entry falls outside the Planning Horizon")
            cell = (entry.employee_id, entry.day_index)
            if cell in occupied_cells:
                raise ValueError("Only one Planning Entry is allowed per Employee/day")
            occupied_cells.add(cell)

            if isinstance(entry.target, DepartmentTarget):
                if entry.target.department_id not in departments:
                    raise ValueError("Planning Entry references an unknown Department")
                continue
            if isinstance(entry, EmployeePreference):
                if entry.target.shift_type is ShiftType.FORMATION:
                    raise ValueError("Formation is eligible only for Fixed Assignments")
                if (
                    entry.target.shift_type is ShiftType.HOLIDAY
                    and entry.direction == "avoided"
                ):
                    raise ValueError("Holiday is eligible only as a desired preference")

        _validate_decisions(
            self.policies,
            self.objectives,
            self.planning_weeks * 7,
        )
        return self


class DayAssignment(ContractModel):
    day_index: DayIndex
    shift_type: ShiftType
    department_id: DepartmentId | None

    @model_validator(mode="after")
    def validate_department(self) -> "DayAssignment":
        covers_demand = self.shift_type in (ShiftType.DAY, ShiftType.NIGHT)
        if covers_demand and self.department_id is None:
            raise ValueError("Demand-covering assignments require a Department")
        if not covers_demand and self.department_id is not None:
            raise ValueError("Non-demand assignments cannot reference a Department")
        return self


class EmployeeSchedule(ContractModel):
    employee_id: EmployeeId
    days: Annotated[list[DayAssignment], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_order(self) -> "EmployeeSchedule":
        if [day.day_index for day in self.days] != list(range(len(self.days))):
            raise ValueError("Schedule days must be ordered and complete from day zero")
        return self


class Schedule(ContractModel):
    employees: Annotated[list[EmployeeSchedule], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_employees(self) -> "Schedule":
        employee_ids = [employee.employee_id for employee in self.employees]
        if len(employee_ids) != len(set(employee_ids)):
            raise ValueError("Schedule Employee IDs must be unique")
        day_counts = {len(employee.days) for employee in self.employees}
        if len(day_counts) != 1:
            raise ValueError("Every Employee schedule must cover the same horizon")
        return self


class ObjectiveContribution(ContractModel):
    objective_id: DecisionId
    contribution: int


class SolveDiagnostics(ContractModel):
    wall_time_seconds: Annotated[float, Field(ge=0)]
    conflicts: Annotated[int, Field(ge=0)]
    branches: Annotated[int, Field(ge=0)]
    objective_value: int | None
    best_objective_bound: float | None
    contributions: list[ObjectiveContribution]

    @model_validator(mode="after")
    def validate_contributions(self) -> "SolveDiagnostics":
        objective_ids = [
            contribution.objective_id for contribution in self.contributions
        ]
        if len(objective_ids) != len(set(objective_ids)):
            raise ValueError("Objective contribution IDs must be unique")
        if self.objective_value is None and self.contributions:
            raise ValueError("A result without an objective cannot have contributions")
        if self.objective_value is not None and sum(
            contribution.contribution for contribution in self.contributions
        ) != self.objective_value:
            raise ValueError("Objective contributions must sum to the objective value")
        return self


class OptimalSolveResult(ContractModel):
    status: Literal["optimal"]
    schedule: Schedule
    diagnostics: SolveDiagnostics

    @model_validator(mode="after")
    def require_objective(self) -> "OptimalSolveResult":
        if self.diagnostics.objective_value is None:
            raise ValueError("An optimal result requires an objective value")
        return self


class FeasibleSolveResult(ContractModel):
    status: Literal["feasible"]
    schedule: Schedule
    diagnostics: SolveDiagnostics

    @model_validator(mode="after")
    def require_objective(self) -> "FeasibleSolveResult":
        if self.diagnostics.objective_value is None:
            raise ValueError("A feasible result requires an objective value")
        return self


class InfeasibleSolveResult(ContractModel):
    status: Literal["infeasible"]
    diagnostics: SolveDiagnostics

    @model_validator(mode="after")
    def reject_objective(self) -> "InfeasibleSolveResult":
        if self.diagnostics.objective_value is not None:
            raise ValueError("An infeasible result cannot contain an objective value")
        return self


class UnknownSolveResult(ContractModel):
    status: Literal["unknown"]
    diagnostics: SolveDiagnostics

    @model_validator(mode="after")
    def reject_objective(self) -> "UnknownSolveResult":
        if self.diagnostics.objective_value is not None:
            raise ValueError("An unknown result cannot contain an objective value")
        return self


SolveResult = Annotated[
    OptimalSolveResult
    | FeasibleSolveResult
    | InfeasibleSolveResult
    | UnknownSolveResult,
    Field(discriminator="status"),
]


ErrorCode = Literal[
    "request_invalid",
    "workspace_not_initialized",
    "workspace_corrupt",
    "workspace_version_unsupported",
    "revision_conflict",
    "proposal_pending",
    "proposal_not_found",
    "decision_invalid",
    "agent_unavailable",
    "optimizer_unavailable",
    "model_invalid",
    "solve_failed",
]


class ApplicationError(ContractModel):
    code: ErrorCode
    message: Annotated[str, Field(min_length=1)]
    details: dict[str, JsonValue]


class ErrorEnvelope(ContractModel):
    error: ApplicationError


def request_invalid_error() -> ErrorEnvelope:
    return ErrorEnvelope(
        error=ApplicationError(
            code="request_invalid",
            message="The request does not match the expected contract.",
            details={},
        )
    )
