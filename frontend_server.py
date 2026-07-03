#!/usr/bin/env python3
"""Tiny development server for configuring and visualizing shift schedules."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import pathlib
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from scheduler import parse_config, solve_shift_scheduling


CONFIG_PATH = pathlib.Path(__file__).with_name("config.toml")
SOLVER_PARAMS = "max_time_in_seconds:10.0"
STATE: dict[str, Any] = {
    "version": 0,
    "received_at": None,
    "schedule": None,
    "log": "",
}
STATE_LOCK = threading.Lock()
REQUIRED_SCHEDULE_FIELDS = {"shifts", "num_workers", "num_days", "plan"}


PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Shift Planner</title>
  <style>
    :root {
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: #1f2937;
      background: #f5f7fa;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      padding: 22px;
    }

    main {
      max-width: 1240px;
      margin: 0 auto;
    }

    header,
    .toolbar,
    .row {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    header {
      justify-content: space-between;
      margin-bottom: 18px;
    }

    h1,
    h2 {
      margin: 0;
      letter-spacing: 0;
    }

    h1 { font-size: 24px; }
    h2 { font-size: 16px; }

    button,
    input {
      font: inherit;
    }

    button {
      min-height: 36px;
      border: 1px solid #c9d2dc;
      border-radius: 6px;
      background: #ffffff;
      color: #1f2937;
      cursor: pointer;
      font-weight: 700;
      padding: 0 12px;
    }

    button:hover {
      background: #f1f5f9;
    }

    button.primary {
      border-color: #2563eb;
      background: #2563eb;
      color: white;
    }

    button.primary:hover {
      background: #1d4ed8;
    }

    button:disabled {
      cursor: wait;
      opacity: 0.65;
    }

    input {
      min-height: 36px;
      border: 1px solid #c9d2dc;
      border-radius: 6px;
      padding: 0 10px;
    }

    label {
      display: grid;
      gap: 6px;
      color: #475467;
      font-size: 13px;
      font-weight: 700;
    }

    .view {
      display: grid;
      gap: 18px;
    }

    .hidden {
      display: none !important;
    }

    .panel {
      border: 1px solid #d0d7de;
      border-radius: 8px;
      background: white;
      padding: 16px;
    }

    .panel-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 14px;
    }

    .setup-grid {
      display: grid;
      grid-template-columns: minmax(260px, 1fr) minmax(420px, 1.6fr);
      gap: 18px;
    }

    #employees {
      display: grid;
      gap: 8px;
    }

    .employee-row {
      display: grid;
      grid-template-columns: 1fr 36px;
      gap: 8px;
    }

    .icon-button {
      width: 36px;
      padding: 0;
    }

    .coverage-table,
    .schedule-table,
    .result-table {
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
    }

    th,
    td {
      border: 1px solid #d0d7de;
      text-align: center;
    }

    th {
      height: 36px;
      background: #eef2f6;
      color: #334155;
      font-size: 13px;
    }

    .coverage-table input {
      width: 100%;
      min-height: 34px;
      border: 0;
      border-radius: 0;
      text-align: center;
    }

    .table-wrap {
      overflow: auto;
      border: 1px solid #d0d7de;
      border-radius: 8px;
      background: white;
    }

    .table-wrap table {
      border: 0;
      min-width: 620px;
    }

    .table-wrap th,
    .table-wrap td {
      min-width: 44px;
      height: 44px;
    }

    .worker {
      position: sticky;
      left: 0;
      z-index: 2;
      width: 140px;
      min-width: 140px;
      background: #eef2f6;
      color: #334155;
      text-align: left;
      padding-left: 12px;
      font-size: 13px;
      font-weight: 700;
    }

    .schedule-cell {
      cursor: pointer;
      outline: 0;
      font-size: 16px;
      font-weight: 800;
    }

    .schedule-cell:focus,
    .schedule-cell.selected {
      box-shadow: inset 0 0 0 3px #2563eb;
    }

    .mode-group {
      display: inline-flex;
      overflow: hidden;
      border: 1px solid #c9d2dc;
      border-radius: 6px;
      background: white;
    }

    .mode-group button {
      border: 0;
      border-radius: 0;
      border-right: 1px solid #c9d2dc;
    }

    .mode-group button:last-child {
      border-right: 0;
    }

    .mode-group button.active {
      background: #1f2937;
      color: white;
    }

    .fixed { background: #e5e7eb; color: #374151; }
    .desired { background: #dff7e7; color: #14532d; }
    .not-desired { background: #fde2e2; color: #7f1d1d; }

    .shift-o { background: #e6e8ec; color: #384252; }
    .shift-d { background: #ffe08a; color: #4f3400; }
    .shift-m { background: #ffe08a; color: #4f3400; }
    .shift-a { background: #9dd7ff; color: #07385c; }
    .shift-n { background: #5964d8; color: white; }
    .shift-f { background: #d9c7ff; color: #39206b; }
    .shift-r { background: #bfe7e3; color: #164e47; }

    #status {
      color: #667085;
      font-size: 14px;
      text-align: right;
    }

    .legend {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      color: #475467;
      font-size: 13px;
    }

    .legend span {
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }

    .swatch {
      width: 18px;
      height: 18px;
      border-radius: 4px;
      border: 1px solid rgb(0 0 0 / 12%);
    }

    .log-panel {
      display: grid;
      gap: 10px;
    }

    .log-output {
      max-height: 420px;
      overflow: auto;
      margin: 0;
      border: 1px solid #d0d7de;
      border-radius: 8px;
      background: #111827;
      color: #d1d5db;
      padding: 12px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
      font-size: 12px;
      line-height: 1.45;
      white-space: pre-wrap;
    }

    @media (max-width: 860px) {
      body { padding: 14px; }
      header,
      .toolbar {
        align-items: flex-start;
        flex-direction: column;
      }
      .setup-grid {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Shift Planner</h1>
      <div id="status">Loading config...</div>
    </header>

    <section id="setup-view" class="view">
      <div class="setup-grid">
        <section class="panel">
          <div class="panel-head">
            <h2>Employees</h2>
            <button id="add-employee" type="button">Add</button>
          </div>
          <div id="employees"></div>
          <label style="margin-top: 14px;">
            Weeks
            <input id="weeks" type="number" min="1" max="12" step="1">
          </label>
        </section>

        <section class="panel">
          <div class="panel-head">
            <h2>Weekly Cover Demand</h2>
          </div>
          <table class="coverage-table">
            <thead id="coverage-head"></thead>
            <tbody id="coverage"></tbody>
          </table>
        </section>
      </div>
      <div class="toolbar">
        <button id="build-schedule" class="primary" type="button">Next</button>
      </div>
    </section>

    <section id="schedule-view" class="view hidden">
      <div class="toolbar">
        <div class="mode-group" id="modes">
          <button type="button" data-mode="fixed" class="active">Fixed</button>
          <button type="button" data-mode="desired">Desired</button>
          <button type="button" data-mode="not-desired">Not Desired</button>
        </div>
        <button id="back-setup" type="button">Back</button>
        <button id="optimize" class="primary" type="button">Optimize</button>
        <button id="logs-toggle" type="button" disabled>Logs</button>
      </div>
      <div id="schedule-wrap" class="table-wrap"></div>
      <div class="legend">
        <span><i class="swatch fixed"></i>Fixed</span>
        <span><i class="swatch desired"></i>Desired</span>
        <span><i class="swatch not-desired"></i>Not Desired</span>
      </div>
      <section id="result-panel" class="panel hidden">
        <div class="panel-head">
          <h2>Optimized Schedule</h2>
        </div>
        <div id="result-wrap" class="table-wrap"></div>
        <div id="result-legend" class="legend" style="margin-top: 14px;"></div>
      </section>
      <section id="log-panel" class="panel log-panel hidden">
        <div class="panel-head">
          <h2>Optimization Logs</h2>
          <button id="logs-close" type="button">Close</button>
        </div>
        <pre id="log-output" class="log-output"></pre>
      </section>
    </section>
  </main>

  <script>
    const daysOfWeek = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
    const requestWeights = { desired: -2, "not-desired": 4 };

    const setupView = document.getElementById("setup-view");
    const scheduleView = document.getElementById("schedule-view");
    const employeesEl = document.getElementById("employees");
    const weeksEl = document.getElementById("weeks");
    const coverageHead = document.getElementById("coverage-head");
    const coverageEl = document.getElementById("coverage");
    const scheduleWrap = document.getElementById("schedule-wrap");
    const resultPanel = document.getElementById("result-panel");
    const resultWrap = document.getElementById("result-wrap");
    const resultLegend = document.getElementById("result-legend");
    const logPanel = document.getElementById("log-panel");
    const logOutput = document.getElementById("log-output");
    const logsToggle = document.getElementById("logs-toggle");
    const statusEl = document.getElementById("status");
    const optimizeButton = document.getElementById("optimize");

    let defaults = null;
    let shifts = [];
    let shiftAttributes = {};
    let shiftNames = {};
    let coverShifts = [];
    let employeeNames = [];
    let weeklyCoverDemands = [];
    let activeMode = "fixed";
    let assignments = new Map();
    let selectedCell = null;
    let latestLog = "";

    function validShift(shift) {
      return shifts.includes(shift);
    }

    function shiftClass(shift) {
      return `shift-${String(shift).toLowerCase()}`;
    }

    function assignmentKey(worker, day) {
      return `${worker}:${day}`;
    }

    function setStatus(text) {
      statusEl.textContent = text;
    }

    function setLatestLog(logText) {
      latestLog = logText || "";
      logOutput.textContent = latestLog || "No optimizer logs yet.";
      logsToggle.disabled = !latestLog;
      if (!latestLog) {
        logPanel.classList.add("hidden");
      }
    }

    function makeCell(tag, text, className) {
      const cell = document.createElement(tag);
      cell.textContent = text;
      if (className) {
        cell.className = className;
      }
      return cell;
    }

    function renderEmployees() {
      employeesEl.replaceChildren(...employeeNames.map((name, index) => {
        const row = document.createElement("div");
        row.className = "employee-row";

        const input = document.createElement("input");
        input.value = name;
        input.dataset.index = index;
        input.addEventListener("input", () => {
          employeeNames[index] = input.value;
        });

        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "icon-button";
        remove.textContent = "x";
        remove.disabled = employeeNames.length === 1;
        remove.addEventListener("click", () => {
          employeeNames.splice(index, 1);
          renderEmployees();
        });

        row.append(input, remove);
        return row;
      }));
    }

    function renderCoverage() {
      const header = document.createElement("tr");
      header.append(makeCell("th", "Day"));
      coverShifts.forEach((shift) => {
        header.append(makeCell("th", shift));
      });
      coverageHead.replaceChildren(header);

      coverageEl.replaceChildren(...daysOfWeek.map((day, dayIndex) => {
        const row = document.createElement("tr");
        row.append(makeCell("th", day));

        for (let shift = 0; shift < coverShifts.length; shift += 1) {
          const cell = document.createElement("td");
          const input = document.createElement("input");
          input.type = "number";
          input.min = "0";
          input.step = "1";
          input.value = weeklyCoverDemands[dayIndex]?.[shift] ?? 0;
          input.addEventListener("input", () => {
            weeklyCoverDemands[dayIndex][shift] = Number(input.value || 0);
          });
          cell.append(input);
          row.append(cell);
        }
        return row;
      }));
    }

    function syncSetupForm() {
      employeeNames = employeeNames.map((name, index) => {
        const trimmed = String(name).trim();
        return trimmed || `Worker ${index + 1}`;
      });
      weeksEl.value = String(Math.max(1, Number(weeksEl.value || 1)));
    }

    function renderScheduleEditor() {
      const weeks = Number(weeksEl.value || 1);
      const days = weeks * 7;
      const table = document.createElement("table");
      table.className = "schedule-table";
      const head = document.createElement("tr");

      head.append(makeCell("th", "Employee", "worker"));
      for (let day = 0; day < days; day += 1) {
        head.append(makeCell("th", `D${day + 1}`));
      }
      table.append(head);

      employeeNames.forEach((name, worker) => {
        const row = document.createElement("tr");
        row.append(makeCell("td", name, "worker"));

        for (let day = 0; day < days; day += 1) {
          const key = assignmentKey(worker, day);
          const assignment = assignments.get(key);
          const cell = makeCell("td", assignment?.shift || "", "schedule-cell");
          cell.tabIndex = 0;
          cell.dataset.worker = worker;
          cell.dataset.day = day;
          if (assignment) {
            cell.classList.add(assignment.type);
          }
          cell.addEventListener("click", () => selectCell(cell));
          cell.addEventListener("focus", () => selectCell(cell));
          cell.addEventListener("keydown", onCellKey);
          row.append(cell);
        }
        table.append(row);
      });

      scheduleWrap.replaceChildren(table);
    }

    function selectCell(cell) {
      if (selectedCell) {
        selectedCell.classList.remove("selected");
      }
      selectedCell = cell;
      selectedCell.classList.add("selected");
      const worker = Number(cell.dataset.worker);
      const day = Number(cell.dataset.day) + 1;
      setStatus(`${employeeNames[worker]} D${day}`);
    }

    function onCellKey(event) {
      const key = event.key.toUpperCase();
      const worker = Number(event.currentTarget.dataset.worker);
      const day = Number(event.currentTarget.dataset.day);
      const mapKey = assignmentKey(worker, day);

      if (["BACKSPACE", "DELETE"].includes(key)) {
        assignments.delete(mapKey);
        renderScheduleEditor();
        setStatus("Cleared");
        event.preventDefault();
        return;
      }

      if (!validShift(key)) {
        return;
      }

      assignments.set(mapKey, { type: activeMode, shift: key });
      renderScheduleEditor();
      const nextCell = scheduleWrap.querySelector(`[data-worker="${worker}"][data-day="${day}"]`);
      nextCell?.focus();
      setStatus(`${activeMode.replace("-", " ")} ${key}`);
      event.preventDefault();
    }

    function renderResultLegend(shifts) {
      resultLegend.replaceChildren(...shifts.map((shift) => {
        const item = document.createElement("span");
        item.append(makeCell("i", "", `swatch ${shiftClass(shift)}`), `${shift}: ${shiftNames[shift] || "Shift"}`);
        return item;
      }));
    }

    function renderResult(schedule) {
      const workers = Number(schedule.num_workers || 0);
      const days = Number(schedule.num_days || 0);
      const names = schedule.employee_names || employeeNames;
      const plan = Array.isArray(schedule.plan) ? schedule.plan : [];
      const table = document.createElement("table");
      table.className = "result-table";
      const head = document.createElement("tr");

      head.append(makeCell("th", "Employee", "worker"));
      for (let day = 0; day < days; day += 1) {
        head.append(makeCell("th", `D${day + 1}`));
      }
      table.append(head);

      for (let worker = 0; worker < workers; worker += 1) {
        const row = document.createElement("tr");
        row.append(makeCell("td", names[worker] || `Worker ${worker + 1}`, "worker"));
        for (let day = 0; day < days; day += 1) {
          const shift = plan[worker]?.[day] || "";
          row.append(makeCell("td", shift, shift ? shiftClass(shift) : ""));
        }
        table.append(row);
      }

      resultWrap.replaceChildren(table);
      renderResultLegend(Array.isArray(schedule.shifts) ? schedule.shifts : []);
      resultPanel.classList.remove("hidden");
    }

    function buildConfig() {
      const config = structuredClone(defaults);
      config.employee_names = [...employeeNames];
      config.num_employees = employeeNames.length;
      config.num_weeks = Number(weeksEl.value || 1);
      config.weekly_cover_demands = weeklyCoverDemands.map((row) => row.map(Number));
      config.fixed_assignments = [];
      config.requests = [];

      for (const [key, assignment] of assignments.entries()) {
        const [worker, day] = key.split(":").map(Number);
        const shift = assignment.shift;
        if (worker >= config.num_employees || day >= config.num_weeks * 7 || !validShift(shift)) {
          continue;
        }

        if (assignment.type === "fixed") {
          config.fixed_assignments.push([worker, shift, day]);
        } else {
          config.requests.push([worker, shift, day, requestWeights[assignment.type]]);
        }
      }

      return config;
    }

    async function optimize() {
      optimizeButton.disabled = true;
      resultPanel.classList.add("hidden");
      logPanel.classList.add("hidden");
      setLatestLog("");
      setStatus("Optimizing...");

      try {
        const response = await fetch("/optimize", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(buildConfig()),
        });
        const payload = await response.json();
        setLatestLog(payload.log);
        if (!response.ok) {
          throw new Error(payload.error || `HTTP ${response.status}`);
        }

        renderResult(payload.schedule);
        setStatus(`Optimized ${new Date(payload.received_at).toLocaleTimeString()}`);
      } catch (error) {
        setStatus(`Error: ${error.message}`);
      } finally {
        optimizeButton.disabled = false;
      }
    }

    document.getElementById("add-employee").addEventListener("click", () => {
      employeeNames.push(`Worker ${employeeNames.length + 1}`);
      renderEmployees();
    });

    document.getElementById("build-schedule").addEventListener("click", () => {
      syncSetupForm();
      setupView.classList.add("hidden");
      scheduleView.classList.remove("hidden");
      resultPanel.classList.add("hidden");
      logPanel.classList.add("hidden");
      renderScheduleEditor();
      setStatus("Ready");
    });

    document.getElementById("back-setup").addEventListener("click", () => {
      scheduleView.classList.add("hidden");
      setupView.classList.remove("hidden");
      setStatus("Editing config");
    });

    document.getElementById("modes").addEventListener("click", (event) => {
      const button = event.target.closest("button[data-mode]");
      if (!button) {
        return;
      }
      activeMode = button.dataset.mode;
      document.querySelectorAll("#modes button").forEach((modeButton) => {
        modeButton.classList.toggle("active", modeButton === button);
      });
      setStatus(activeMode.replace("-", " "));
    });

    optimizeButton.addEventListener("click", optimize);

    logsToggle.addEventListener("click", () => {
      logPanel.classList.toggle("hidden");
    });

    document.getElementById("logs-close").addEventListener("click", () => {
      logPanel.classList.add("hidden");
    });

    async function init() {
      try {
        const response = await fetch("/defaults", { cache: "no-store" });
        defaults = await response.json();
        shifts = defaults.shifts || ["O", "D", "N", "F", "R"];
        shiftAttributes = defaults.shift_attributes || {};
        shiftNames = Object.fromEntries(shifts.map((shift) => [
          shift,
          shiftAttributes[shift]?.name || shift,
        ]));
        coverShifts = shifts.filter((shift) => shiftAttributes[shift]?.covers_demand);
        if (coverShifts.length === 0) {
          coverShifts = shifts.filter((shift) => !["O", "F", "R"].includes(shift));
        }
        employeeNames = defaults.employee_names || Array.from(
          { length: Number(defaults.num_employees || 1) },
          (_, index) => `Worker ${index + 1}`,
        );
        weeklyCoverDemands = (defaults.weekly_cover_demands || []).map((row) => {
          const normalized = [...row];
          while (normalized.length < coverShifts.length) {
            normalized.push(0);
          }
          return normalized.slice(0, coverShifts.length);
        });
        while (weeklyCoverDemands.length < 7) {
          weeklyCoverDemands.push(Array(coverShifts.length).fill(0));
        }
        weeksEl.value = defaults.num_weeks || 1;
        setLatestLog("");
        renderEmployees();
        renderCoverage();
        setStatus("Ready");
      } catch (error) {
        setStatus(`Error: ${error.message}`);
      }
    }

    init();
  </script>
</body>
</html>
"""


def default_config() -> dict[str, Any]:
    config = parse_config(str(CONFIG_PATH))
    config.setdefault(
        "employee_names",
        [f"Worker {index + 1}" for index in range(int(config["num_employees"]))],
    )
    return config


def store_schedule(schedule: dict[str, Any] | None, log: str = "") -> dict[str, Any]:
    with STATE_LOCK:
        STATE["version"] += 1
        STATE["received_at"] = datetime.now(timezone.utc).isoformat()
        STATE["schedule"] = schedule
        STATE["log"] = log
        return dict(STATE)


class ScheduleHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._common_headers()
        self.end_headers()

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/":
            self._send(PAGE.encode("utf-8"), "text/html; charset=utf-8")
            return

        if path == "/defaults":
            self._send_json(default_config())
            return

        if path == "/schedule":
            with STATE_LOCK:
                payload = dict(STATE)

            if payload["schedule"] is None:
                self.send_response(204)
                self._common_headers()
                self.end_headers()
                return

            self._send_json(payload)
            return

        if path == "/logs":
            with STATE_LOCK:
                payload = {
                    "version": STATE["version"],
                    "received_at": STATE["received_at"],
                    "log": STATE["log"],
                }
            self._send_json(payload)
            return

        self.send_error(404)

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/schedule":
            self._receive_schedule()
            return

        if path == "/optimize":
            self._optimize()
            return

        self.send_error(404)

    def _read_json(self) -> Any:
        content_length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(content_length).decode("utf-8"))

    def _receive_schedule(self) -> None:
        try:
            schedule = self._read_json()
        except (ValueError, json.JSONDecodeError):
            self.send_error(400, "Invalid JSON")
            return

        if not isinstance(schedule, dict):
            self.send_error(400, "Schedule payload must be a JSON object")
            return

        missing = REQUIRED_SCHEDULE_FIELDS - set(schedule)
        if missing:
            self.send_error(400, f"Missing fields: {', '.join(sorted(missing))}")
            return

        payload = store_schedule(schedule)
        self._send_json({"ok": True, "version": payload["version"]})

    def _optimize(self) -> None:
        log = ""
        try:
            config = self._read_json()
            if not isinstance(config, dict):
                raise ValueError("Config payload must be a JSON object")
            log_stream = io.StringIO()
            with contextlib.redirect_stdout(log_stream):
                result = solve_shift_scheduling(config, SOLVER_PARAMS, "")
            log = log_stream.getvalue()
        except Exception as exc:
            log = log or str(exc)
            store_schedule(None, log)
            self._send_json({"ok": False, "error": str(exc), "log": log}, status=400)
            return

        if result is None:
            payload = store_schedule(None, log)
            self._send_json(
                {
                    "ok": False,
                    "error": "No feasible solution found.",
                    "log": log,
                    "version": payload["version"],
                    "received_at": payload["received_at"],
                },
                status=422,
            )
            return

        payload = store_schedule(result, log)
        self._send_json({"ok": True, **payload})

    def log_message(self, format: str, *args: Any) -> None:
        print(f"{self.address_string()} - {format % args}")

    def _common_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send(self, body: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self._common_headers()
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        self._send(json.dumps(payload).encode("utf-8"), "application/json", status)


def main() -> None:
    parser = argparse.ArgumentParser(description="Configure and visualize shift schedules.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), ScheduleHandler)
    print(f"Listening on http://{args.host}:{args.port}")
    print("Open / to configure schedules, POST schedules to /schedule")
    server.serve_forever()


if __name__ == "__main__":
    main()
