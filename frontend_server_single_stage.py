#!/usr/bin/env python3
"""Single-stage development server for configuring and visualizing schedules."""

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

from scheduler_single_stage import parse_config, solve_schedule


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
  <title>Single-Stage Shift Planner</title>
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
    input,
    select {
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

    input,
    select {
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

    .department-list {
      display: grid;
      gap: 12px;
    }

    .department-row {
      display: grid;
      gap: 10px;
      border-top: 1px solid #e5e7eb;
      padding-top: 12px;
    }

    .department-row:first-child {
      border-top: 0;
      padding-top: 0;
    }

    .department-main {
      display: grid;
      grid-template-columns: minmax(150px, 1fr) 88px 76px 78px 50px 36px;
      gap: 8px;
      align-items: end;
    }

    .department-requirements {
      display: grid;
      grid-template-columns: repeat(7, minmax(54px, 1fr));
      gap: 8px;
    }

    .department-requirements input {
      width: 100%;
      text-align: center;
    }

    .color-input {
      width: 50px;
      padding: 3px;
    }

    .icon-button {
      width: 36px;
      padding: 0;
    }

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

    .assignment-picker {
      min-width: 240px;
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
    .shift-h { background: #f8b4c4; color: #5f1730; }

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
      .department-main,
      .department-requirements {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Single-Stage Shift Planner</h1>
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
          <label style="margin-top: 14px;">
            Max hours/week
            <input id="max-hours-week" type="number" min="1" max="168" step="1">
          </label>
        </section>

        <section class="panel">
          <div class="panel-head">
            <h2>Departments</h2>
            <button id="add-department" type="button">Add</button>
          </div>
          <div id="departments" class="department-list"></div>
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
        <select id="assignment-picker" class="assignment-picker"></select>
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
    const defaultShiftColors = {
      O: "#e6e8ec",
      D: "#ffe08a",
      N: "#5964d8",
      F: "#d9c7ff",
      R: "#bfe7e3",
      H: "#f8b4c4",
    };

    const setupView = document.getElementById("setup-view");
    const scheduleView = document.getElementById("schedule-view");
    const employeesEl = document.getElementById("employees");
    const weeksEl = document.getElementById("weeks");
    const maxHoursWeekEl = document.getElementById("max-hours-week");
    const departmentsEl = document.getElementById("departments");
    const scheduleWrap = document.getElementById("schedule-wrap");
    const resultPanel = document.getElementById("result-panel");
    const resultWrap = document.getElementById("result-wrap");
    const resultLegend = document.getElementById("result-legend");
    const logPanel = document.getElementById("log-panel");
    const logOutput = document.getElementById("log-output");
    const logsToggle = document.getElementById("logs-toggle");
    const statusEl = document.getElementById("status");
    const optimizeButton = document.getElementById("optimize");
    const assignmentPicker = document.getElementById("assignment-picker");

    let defaults = null;
    let shifts = [];
    let shiftAttributes = {};
    let shiftNames = {};
    let coverShifts = [];
    let employeeNames = [];
    let departments = [];
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

    function readableTextColor(hexColor) {
      const value = String(hexColor || "").replace("#", "");
      if (value.length !== 6) {
        return "#1f2937";
      }
      const red = parseInt(value.slice(0, 2), 16);
      const green = parseInt(value.slice(2, 4), 16);
      const blue = parseInt(value.slice(4, 6), 16);
      const brightness = (red * 299 + green * 587 + blue * 114) / 1000;
      return brightness > 145 ? "#1f2937" : "#ffffff";
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

    function normalizeRequirements(requirements) {
      const normalized = Array.isArray(requirements) ? requirements.slice(0, 7) : [];
      while (normalized.length < 7) {
        normalized.push(0);
      }
      return normalized.map((value) => Math.max(0, Number(value || 0)));
    }

    function defaultDurationHours(shift) {
      return shift === "N" ? 12 : 8;
    }

    function normalizeDurationHours(value, shift) {
      const fallback = defaultDurationHours(shift);
      const number = Number(value);
      if (!Number.isFinite(number) || number <= 0) {
        return fallback;
      }
      return Math.max(1, Math.min(24, Math.round(number)));
    }

    function normalizeMaxHours(value) {
      const number = Number(value);
      if (!Number.isFinite(number) || number <= 0) {
        return null;
      }
      return Math.max(1, Math.min(168, Math.round(number)));
    }

    function normalizeColor(color, shift) {
      const value = String(color || "");
      if (/^#[0-9a-fA-F]{6}$/.test(value)) {
        return value;
      }
      return defaultShiftColors[shift] || "#9dd7ff";
    }

    function slug(value) {
      return String(value || "")
        .trim()
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "") || "department";
    }

    function normalizeDepartment(department, index) {
      const fallbackShift = coverShifts[0] || "D";
      const shift = coverShifts.includes(department?.shift) ? department.shift : fallbackShift;
      const fallbackName = `${shiftNames[shift] || shift} ${index + 1}`;
      const name = String(department?.name || fallbackName).trim() || fallbackName;
      const symbol = String(department?.symbol || shift).trim().slice(0, 3).toUpperCase() || shift;
      return {
        id: String(department?.id || slug(name || `${shift}-${index + 1}`)),
        name,
        shift,
        symbol,
        color: normalizeColor(department?.color, shift),
        duration_hours: normalizeDurationHours(department?.duration_hours, shift),
        requirements: normalizeRequirements(department?.requirements),
      };
    }

    function normalizeDepartmentList(departmentList) {
      const used = new Set();
      return departmentList.map((department, index) => {
        const normalized = normalizeDepartment(department, index);
        const baseId = slug(normalized.id);
        let id = baseId;
        let suffix = 2;
        while (used.has(id)) {
          id = `${baseId}-${suffix}`;
          suffix += 1;
        }
        used.add(id);
        return { ...normalized, id };
      });
    }

    function departmentsFromWeeklyCoverDemands(weeklyCoverDemands) {
      return coverShifts.map((shift, shiftIndex) => normalizeDepartment({
        id: slug(shift),
        name: shiftNames[shift] || shift,
        shift,
        symbol: shift,
        color: defaultShiftColors[shift],
        duration_hours: defaultDurationHours(shift),
        requirements: daysOfWeek.map((_, dayIndex) => weeklyCoverDemands[dayIndex]?.[shiftIndex] ?? 0),
      }, shiftIndex));
    }

    function makeLabel(text, control) {
      const label = document.createElement("label");
      label.append(text, control);
      return label;
    }

    function renderDepartments() {
      departmentsEl.replaceChildren(...departments.map((department, index) => {
        const row = document.createElement("div");
        row.className = "department-row";

        const main = document.createElement("div");
        main.className = "department-main";

        const name = document.createElement("input");
        name.value = department.name;
        name.addEventListener("input", () => {
          departments[index].name = name.value;
        });

        const shift = document.createElement("select");
        coverShifts.forEach((shiftCode) => {
          const option = document.createElement("option");
          option.value = shiftCode;
          option.textContent = `${shiftNames[shiftCode] || shiftCode} (${shiftCode})`;
          shift.append(option);
        });
        shift.value = department.shift;
        shift.addEventListener("change", () => {
          departments[index].shift = shift.value;
          departments[index].duration_hours = normalizeDurationHours(
            departments[index].duration_hours,
            shift.value,
          );
        });

        const duration = document.createElement("input");
        duration.type = "number";
        duration.min = "1";
        duration.max = "24";
        duration.step = "1";
        duration.value = department.duration_hours;
        duration.addEventListener("input", () => {
          departments[index].duration_hours = normalizeDurationHours(
            duration.value,
            departments[index].shift,
          );
        });

        const symbol = document.createElement("input");
        symbol.value = department.symbol;
        symbol.maxLength = 3;
        symbol.addEventListener("input", () => {
          departments[index].symbol = symbol.value.trim().slice(0, 3).toUpperCase();
        });

        const color = document.createElement("input");
        color.type = "color";
        color.className = "color-input";
        color.value = department.color;
        color.addEventListener("input", () => {
          departments[index].color = color.value;
        });

        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "icon-button";
        remove.textContent = "x";
        remove.addEventListener("click", () => {
          departments.splice(index, 1);
          renderDepartments();
        });

        main.append(
          makeLabel("Name", name),
          makeLabel("Shift", shift),
          makeLabel("Hours", duration),
          makeLabel("Symbol", symbol),
          makeLabel("Color", color),
          remove,
        );

        const requirements = document.createElement("div");
        requirements.className = "department-requirements";
        daysOfWeek.forEach((day, dayIndex) => {
          const input = document.createElement("input");
          input.type = "number";
          input.min = "0";
          input.step = "1";
          input.value = department.requirements[dayIndex] ?? 0;
          input.addEventListener("input", () => {
            departments[index].requirements[dayIndex] = Math.max(0, Number(input.value || 0));
          });
          requirements.append(makeLabel(day, input));
        });

        row.append(main, requirements);
        return row;
      }));
      renderAssignmentPicker();
    }

    function weeklyCoverDemandsFromDepartments() {
      return daysOfWeek.map((_, dayIndex) => coverShifts.map((shift) => (
        departments
          .filter((department) => department.shift === shift)
          .reduce((sum, department) => sum + Number(department.requirements[dayIndex] || 0), 0)
      )));
    }

    function departmentMap() {
      return new Map(departments.map((department) => [department.id, department]));
    }

    function selectedPickerAssignment() {
      const value = assignmentPicker.value || "";
      if (!value) {
        return null;
      }
      const [kind, id] = value.split(":", 2);
      if (kind === "shift" && validShift(id)) {
        return { kind: "shift", shift: id };
      }
      if (kind === "department" && departmentMap().has(id)) {
        return { kind: "department", department_id: id };
      }
      return null;
    }

    function assignmentText(assignment) {
      if (!assignment) {
        return "";
      }
      if (assignment.kind === "department") {
        const department = departmentMap().get(assignment.department_id);
        return department?.symbol || "?";
      }
      return assignment.shift || "";
    }

    function assignmentTitle(assignment) {
      if (!assignment) {
        return "";
      }
      if (assignment.kind === "department") {
        const department = departmentMap().get(assignment.department_id);
        return department ? `${department.name} (${department.shift})` : assignment.department_id;
      }
      return `${shiftNames[assignment.shift] || assignment.shift} (${assignment.shift})`;
    }

    function renderAssignmentPicker() {
      const options = [];
      const clear = document.createElement("option");
      clear.value = "";
      clear.textContent = "Clear cell";
      options.push(clear);

      const shiftGroup = document.createElement("optgroup");
      shiftGroup.label = "Shifts";
      shifts.forEach((shift) => {
        const option = document.createElement("option");
        option.value = `shift:${shift}`;
        option.textContent = `${shiftNames[shift] || shift} (${shift})`;
        shiftGroup.append(option);
      });
      options.push(shiftGroup);

      coverShifts.forEach((shift) => {
        const shiftDepartments = departments.filter((department) => department.shift === shift);
        if (shiftDepartments.length === 0) {
          return;
        }
        const group = document.createElement("optgroup");
        group.label = `${shiftNames[shift] || shift} departments`;
        shiftDepartments.forEach((department) => {
          const option = document.createElement("option");
          option.value = `department:${department.id}`;
          option.textContent = `${department.symbol}: ${department.name}`;
          group.append(option);
        });
        options.push(group);
      });

      const previous = assignmentPicker.value;
      assignmentPicker.replaceChildren(...options);
      if ([...assignmentPicker.options].some((option) => option.value === previous)) {
        assignmentPicker.value = previous;
      } else {
        const defaultShift = shifts.includes("D") ? "D" : shifts[0];
        assignmentPicker.value = defaultShift ? `shift:${defaultShift}` : "";
      }
    }

    function syncSetupForm() {
      employeeNames = employeeNames.map((name, index) => {
        const trimmed = String(name).trim();
        return trimmed || `Worker ${index + 1}`;
      });
      departments = normalizeDepartmentList(departments);
      weeksEl.value = String(Math.max(1, Number(weeksEl.value || 1)));
      const maxHours = normalizeMaxHours(maxHoursWeekEl.value);
      maxHoursWeekEl.value = maxHours === null ? "" : String(maxHours);
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
          const cell = makeCell("td", assignmentText(assignment), "schedule-cell");
          cell.tabIndex = 0;
          cell.dataset.worker = worker;
          cell.dataset.day = day;
          cell.title = assignmentTitle(assignment);
          if (assignment) {
            cell.classList.add(assignment.type);
          }
          cell.addEventListener("click", () => {
            selectCell(cell);
            applyPickerToCell(cell);
          });
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

    function applyPickerToCell(cell) {
      const worker = Number(cell.dataset.worker);
      const day = Number(cell.dataset.day);
      const mapKey = assignmentKey(worker, day);
      const assignment = selectedPickerAssignment();

      if (!assignment) {
        assignments.delete(mapKey);
        renderScheduleEditor();
        setStatus("Cleared");
        return;
      }

      assignments.set(mapKey, { type: activeMode, ...assignment });
      renderScheduleEditor();
      const nextCell = scheduleWrap.querySelector(`[data-worker="${worker}"][data-day="${day}"]`);
      nextCell?.focus();
      setStatus(`${activeMode.replace("-", " ")} ${assignmentTitle(assignment)}`);
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

      assignments.set(mapKey, { type: activeMode, kind: "shift", shift: key });
      renderScheduleEditor();
      const nextCell = scheduleWrap.querySelector(`[data-worker="${worker}"][data-day="${day}"]`);
      nextCell?.focus();
      setStatus(`${activeMode.replace("-", " ")} ${key}`);
      event.preventDefault();
    }

    function renderResultLegend(schedule) {
      const scheduleShifts = Array.isArray(schedule.shifts) ? schedule.shifts : [];
      const scheduleDepartments = Array.isArray(schedule.departments) ? schedule.departments : departments;
      const shiftItems = scheduleShifts.map((shift) => {
        const item = document.createElement("span");
        item.append(makeCell("i", "", `swatch ${shiftClass(shift)}`), `${shift}: ${shiftNames[shift] || "Shift"}`);
        return item;
      });
      const departmentItems = scheduleDepartments.map((department) => {
        const item = document.createElement("span");
        const swatch = makeCell("i", "", "swatch");
        swatch.style.background = department.color;
        item.append(swatch, `${department.symbol}: ${department.name}`);
        return item;
      });
      resultLegend.replaceChildren(...shiftItems, ...departmentItems);
    }

    function renderResult(schedule) {
      const workers = Number(schedule.num_workers || 0);
      const days = Number(schedule.num_days || 0);
      const names = schedule.employee_names || employeeNames;
      const plan = Array.isArray(schedule.plan) ? schedule.plan : [];
      const departmentPlan = Array.isArray(schedule.department_plan) ? schedule.department_plan : [];
      const resultDepartments = new Map(
        (Array.isArray(schedule.departments) ? schedule.departments : departments)
          .map((department) => [department.id, department])
      );
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
          const department = resultDepartments.get(departmentPlan[worker]?.[day]);
          const cell = makeCell("td", department?.symbol || shift, department ? "" : (shift ? shiftClass(shift) : ""));
          if (department) {
            cell.style.background = department.color;
            cell.style.color = readableTextColor(department.color);
            cell.title = `${department.name} (${department.shift})`;
          }
          row.append(cell);
        }
        table.append(row);
      }

      resultWrap.replaceChildren(table);
      renderResultLegend(schedule);
      resultPanel.classList.remove("hidden");
    }

    function buildConfig() {
      departments = normalizeDepartmentList(departments);
      const config = structuredClone(defaults);
      config.employee_names = [...employeeNames];
      config.num_employees = employeeNames.length;
      config.num_weeks = Number(weeksEl.value || 1);
      const maxHours = normalizeMaxHours(maxHoursWeekEl.value);
      if (maxHours === null) {
        delete config.max_hours_per_week;
      } else {
        config.max_hours_per_week = maxHours;
      }
      config.departments = departments.map((department) => ({
        ...department,
        duration_hours: Number(department.duration_hours),
        requirements: department.requirements.map(Number),
      }));
      config.weekly_cover_demands = weeklyCoverDemandsFromDepartments();
      config.fixed_assignments = [];
      config.requests = [];
      config.department_fixed_assignments = [];
      config.department_requests = [];

      for (const [key, assignment] of assignments.entries()) {
        const [worker, day] = key.split(":").map(Number);
        if (worker >= config.num_employees || day >= config.num_weeks * 7) {
          continue;
        }

        if (assignment.kind === "department") {
          if (!departmentMap().has(assignment.department_id)) {
            continue;
          }
          if (assignment.type === "fixed") {
            config.department_fixed_assignments.push([worker, assignment.department_id, day]);
          } else {
            config.department_requests.push([
              worker,
              assignment.department_id,
              day,
              requestWeights[assignment.type],
            ]);
          }
          continue;
        }

        const shift = assignment.shift;
        if (!validShift(shift)) {
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

    document.getElementById("add-department").addEventListener("click", () => {
      const shift = coverShifts[0] || "D";
      departments.push(normalizeDepartment({
        id: `${slug(shift)}-${departments.length + 1}`,
        name: `${shiftNames[shift] || shift} ${departments.length + 1}`,
        shift,
        symbol: shift,
        color: defaultShiftColors[shift],
        duration_hours: defaultDurationHours(shift),
        requirements: Array(7).fill(0),
      }, departments.length));
      renderDepartments();
    });

    document.getElementById("build-schedule").addEventListener("click", () => {
      syncSetupForm();
      renderAssignmentPicker();
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
        shifts = defaults.shifts || ["O", "D", "N", "F", "R", "H"];
        shiftAttributes = defaults.shift_attributes || {};
        shiftNames = Object.fromEntries(shifts.map((shift) => [
          shift,
          shiftAttributes[shift]?.name || shift,
        ]));
        coverShifts = shifts.filter((shift) => shiftAttributes[shift]?.covers_demand);
        if (coverShifts.length === 0) {
          coverShifts = shifts.filter((shift) => !["O", "F", "R", "H"].includes(shift));
        }
        employeeNames = defaults.employee_names || Array.from(
          { length: Number(defaults.num_employees || 1) },
          (_, index) => `Worker ${index + 1}`,
        );
        if (Array.isArray(defaults.departments) && defaults.departments.length > 0) {
          departments = normalizeDepartmentList(defaults.departments);
        } else {
          departments = normalizeDepartmentList(
            departmentsFromWeeklyCoverDemands(defaults.weekly_cover_demands || [])
          );
        }
        weeksEl.value = defaults.num_weeks || 1;
        maxHoursWeekEl.value = defaults.max_hours_per_week || "";
        setLatestLog("");
        renderEmployees();
        renderDepartments();
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
                result = solve_schedule(config, SOLVER_PARAMS, "")
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
    parser.add_argument("--port", default=8001, type=int)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), ScheduleHandler)
    print(f"Listening on http://{args.host}:{args.port}")
    print("Open / to configure schedules, POST schedules to /schedule")
    server.serve_forever()


if __name__ == "__main__":
    main()
