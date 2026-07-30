import type { components } from "./api/schema";

export type Scenario = components["schemas"]["Scenario"];
export type StateResponse = components["schemas"]["StateResponse"];
export type InitializedState = components["schemas"]["InitializedState"];
type ScenarioSaveRequest = components["schemas"]["ScenarioSaveRequest"];

async function readJson<T>(response: Response): Promise<T> {
  const body = (await response.json()) as T;
  if (!response.ok) {
    throw new Error("MedShift could not load or save the Scenario");
  }
  return body;
}

export async function fetchState(): Promise<StateResponse> {
  return readJson<StateResponse>(await fetch("/api/state"));
}

export async function saveScenario(
  baseRevision: number | null,
  scenario: Scenario,
): Promise<InitializedState> {
  const request: ScenarioSaveRequest = {
    base_revision: baseRevision,
    scenario,
  };
  return readJson<InitializedState>(
    await fetch("/api/scenario", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    }),
  );
}
