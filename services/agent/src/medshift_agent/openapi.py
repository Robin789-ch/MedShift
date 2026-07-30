from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from pydantic import TypeAdapter

from medshift_contracts import HealthResponse
from medshift_contracts.models import (
    AssignmentTarget,
    ErrorEnvelope,
    Objective,
    PlanningEntry,
    Policy,
    Proposal,
    ProposalChange,
    Scenario,
    ScenarioSaveRequest,
    ShiftTypeCatalogue,
    ShiftTypeDefinition,
    SolveRequest,
    SolveResult,
    StateResponse,
    Workspace,
    WorkspaceChange,
)


CONTRACT_SCHEMAS: dict[str, TypeAdapter[Any]] = {
    "AssignmentTarget": TypeAdapter(AssignmentTarget),
    "ErrorEnvelope": TypeAdapter(ErrorEnvelope),
    "HealthResponse": TypeAdapter(HealthResponse),
    "Objective": TypeAdapter(Objective),
    "PlanningEntry": TypeAdapter(PlanningEntry),
    "Policy": TypeAdapter(Policy),
    "Proposal": TypeAdapter(Proposal),
    "ProposalChange": TypeAdapter(ProposalChange),
    "Scenario": TypeAdapter(Scenario),
    "ScenarioSaveRequest": TypeAdapter(ScenarioSaveRequest),
    "ShiftTypeCatalogue": TypeAdapter(ShiftTypeCatalogue),
    "ShiftTypeDefinition": TypeAdapter(ShiftTypeDefinition),
    "SolveRequest": TypeAdapter(SolveRequest),
    "SolveResult": TypeAdapter(SolveResult),
    "StateResponse": TypeAdapter(StateResponse),
    "Workspace": TypeAdapter(Workspace),
    "WorkspaceChange": TypeAdapter(WorkspaceChange),
}


def configure_contract_openapi(app: FastAPI) -> None:
    def contract_openapi() -> dict[str, Any]:
        if app.openapi_schema is not None:
            return app.openapi_schema

        schema = get_openapi(
            title=app.title,
            version=app.version,
            openapi_version=app.openapi_version,
            summary=app.summary,
            description=app.description,
            routes=app.routes,
        )
        schemas = schema.setdefault("components", {}).setdefault("schemas", {})

        for name, adapter in CONTRACT_SCHEMAS.items():
            contract_schema = adapter.json_schema(
                ref_template="#/components/schemas/{model}",
            )
            definitions = contract_schema.pop("$defs", {})
            schemas.update(definitions)
            contract_schema["title"] = name
            schemas[name] = contract_schema

        schemas.pop("HTTPValidationError", None)
        schemas.pop("ValidationError", None)
        stable_validation_response = {
            "description": "Request Invalid",
            "content": {
                "application/json": {
                    "schema": {
                        "$ref": "#/components/schemas/ErrorEnvelope",
                    }
                }
            },
        }
        for path in schema.get("paths", {}).values():
            for operation in path.values():
                responses = operation.get("responses", {})
                if "422" in responses:
                    responses["422"] = stable_validation_response

        app.openapi_schema = schema
        return schema

    setattr(app, "openapi", contract_openapi)
