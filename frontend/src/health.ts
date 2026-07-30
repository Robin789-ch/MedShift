import type { components } from "./api/schema";

export type HealthResponse = components["schemas"]["HealthResponse"];

export async function fetchHealth(): Promise<HealthResponse> {
  const response = await fetch("/api/health");
  const health = (await response.json()) as HealthResponse;
  if (!response.ok) {
    throw new Error("MedShift services are not ready");
  }
  return health;
}
