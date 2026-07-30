import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";

import {
  fetchState,
  saveScenario,
  type Scenario,
  type StateResponse,
} from "./scenario";
import "./styles.css";

const starterScenario: Scenario = {
  planning_weeks: 1,
  employees: [
    {
      employee_id: "11111111-1111-1111-1111-111111111111",
      display_name: "Starter Employee",
      overtime_hours: 0,
      weekly_hours_ceiling: 40,
    },
  ],
  departments: [],
  planning_entries: [],
};

function App() {
  const [state, setState] = useState<StateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    void fetchState()
      .then(setState)
      .catch(() => setError("MedShift could not load the saved Scenario."));
  }, []);

  async function createStarterScenario() {
    setSaving(true);
    setError(null);
    try {
      setState(await saveScenario(null, starterScenario));
    } catch {
      setError("MedShift could not save the Scenario.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <main>
      <h1>MedShift</h1>
      {error && <p role="alert">{error}</p>}
      {!state && !error && <p>Loading saved Scenario…</p>}
      {state?.initialized === false && (
        <section>
          <h2>Create the first Scenario</h2>
          <p>
            Start with one Employee and a one-week Planning Horizon. The full
            editors arrive in the next focused tickets.
          </p>
          <button
            type="button"
            disabled={saving}
            onClick={() => void createStarterScenario()}
          >
            {saving ? "Saving…" : "Create and save Scenario"}
          </button>
        </section>
      )}
      {state?.initialized === true && (
        <section>
          <h2>Scenario saved</h2>
          <p>Workspace revision {state.revision}</p>
          <dl>
            <div>
              <dt>Planning Horizon</dt>
              <dd>{state.scenario.planning_weeks} week</dd>
            </div>
            <div>
              <dt>Employee</dt>
              <dd>{state.scenario.employees[0]?.display_name}</dd>
            </div>
          </dl>
        </section>
      )}
    </main>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
