import { afterEach, expect, test, vi } from "vitest";

import {
  fetchState,
  saveScenario,
  type Scenario,
} from "./scenario";

const scenario: Scenario = {
  planning_weeks: 1,
  employees: [
    {
      employee_id: "11111111-1111-1111-1111-111111111111",
      display_name: "Avery",
      overtime_hours: 0,
      weekly_hours_ceiling: 40,
    },
  ],
  departments: [],
  planning_entries: [],
};

afterEach(() => {
  vi.unstubAllGlobals();
});

test("creates, saves, and reloads the minimum valid Scenario", async () => {
  const uninitialized = { initialized: false, shift_types: [] };
  const initialized = {
    initialized: true,
    revision: 1,
    scenario,
    shift_types: [],
    policies: [],
    objectives: [],
  };
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(
      new Response(JSON.stringify(uninitialized), { status: 200 }),
    )
    .mockResolvedValueOnce(
      new Response(JSON.stringify(initialized), { status: 200 }),
    )
    .mockResolvedValueOnce(
      new Response(JSON.stringify(initialized), { status: 200 }),
    );
  vi.stubGlobal("fetch", fetchMock);

  expect(await fetchState()).toEqual(uninitialized);
  expect(await saveScenario(null, scenario)).toEqual(initialized);
  expect(await fetchState()).toEqual(initialized);
  expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/scenario", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ base_revision: null, scenario }),
  });
});
