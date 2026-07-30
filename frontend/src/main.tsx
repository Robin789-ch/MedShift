import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";

import { fetchHealth } from "./health";
import "./styles.css";

function App() {
  const [status, setStatus] = useState("Connecting to MedShift services…");

  useEffect(() => {
    void fetchHealth()
      .then(() => setStatus("MedShift services are ready."))
      .catch(() => setStatus("MedShift services are unavailable."));
  }, []);

  return (
    <main>
      <h1>MedShift</h1>
      <p>{status}</p>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
