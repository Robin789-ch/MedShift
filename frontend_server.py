#!/usr/bin/env python3
"""Tiny development server for visualizing generated shift schedules."""

from __future__ import annotations

import argparse
import json
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


STATE: dict[str, Any] = {"version": 0, "received_at": None, "schedule": None}
STATE_LOCK = threading.Lock()
REQUIRED_FIELDS = {"shifts", "num_workers", "num_days", "plan"}


PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Shift Schedule</title>
  <style>
    body {
      margin: 0;
      padding: 24px;
      background: #f6f7f9;
      color: #1f2937;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    main {
      max-width: 1180px;
      margin: 0 auto;
    }

    header {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 16px;
    }

    h1 {
      margin: 0;
      font-size: 24px;
      letter-spacing: 0;
    }

    #status {
      color: #667085;
      font-size: 14px;
    }

    #table-wrap {
      overflow: auto;
      border: 1px solid #d0d7de;
      border-radius: 8px;
      background: white;
    }

    table {
      width: 100%;
      min-width: 520px;
      border-collapse: collapse;
      table-layout: fixed;
    }

    th,
    td {
      min-width: 44px;
      height: 44px;
      border: 1px solid #d0d7de;
      text-align: center;
      font-weight: 700;
    }

    th,
    td.worker {
      position: sticky;
      background: #eef2f6;
      color: #334155;
      font-size: 13px;
    }

    th {
      top: 0;
    }

    td.worker {
      left: 0;
      width: 110px;
      min-width: 110px;
      text-align: left;
      padding-left: 12px;
    }

    .empty {
      padding: 96px 24px;
      color: #667085;
      text-align: center;
    }

    .legend {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 14px;
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

    .shift-o { background: #e6e8ec; color: #384252; }
    .shift-m { background: #ffe08a; color: #4f3400; }
    .shift-a { background: #9dd7ff; color: #07385c; }
    .shift-n { background: #5964d8; color: white; }

    @media (max-width: 680px) {
      body { padding: 14px; }
      header { flex-direction: column; }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Shift Schedule</h1>
      <div id="status">Waiting for a schedule...</div>
    </header>
    <section id="table-wrap"><div class="empty">Run the optimizer to send a schedule here.</div></section>
    <div id="legend" class="legend"></div>
  </main>

  <script>
    const tableWrap = document.getElementById("table-wrap");
    const legend = document.getElementById("legend");
    const status = document.getElementById("status");
    const names = { O: "Off", M: "Morning", A: "Afternoon", N: "Night" };
    let seenVersion = -1;

    function shiftClass(shift) {
      return `shift-${String(shift).toLowerCase()}`;
    }

    function makeCell(tag, text, className) {
      const cell = document.createElement(tag);
      cell.textContent = text;
      if (className) {
        cell.className = className;
      }
      return cell;
    }

    function renderLegend(shifts) {
      legend.replaceChildren(...shifts.map((shift) => {
        const item = document.createElement("span");
        item.append(makeCell("i", "", `swatch ${shiftClass(shift)}`), `${shift}: ${names[shift] || "Shift"}`);
        return item;
      }));
    }

    function render(schedule) {
      const workers = Number(schedule.num_workers || 0);
      const days = Number(schedule.num_days || 0);
      const plan = Array.isArray(schedule.plan) ? schedule.plan : [];
      const table = document.createElement("table");
      const head = document.createElement("tr");

      head.append(makeCell("th", "Worker"));
      for (let day = 0; day < days; day += 1) {
        head.append(makeCell("th", `D${day + 1}`));
      }
      table.append(head);

      for (let worker = 0; worker < workers; worker += 1) {
        const row = document.createElement("tr");
        row.append(makeCell("td", `worker ${worker}`, "worker"));
        for (let day = 0; day < days; day += 1) {
          const shift = plan[worker]?.[day] || "";
          row.append(makeCell("td", shift, shift ? shiftClass(shift) : ""));
        }
        table.append(row);
      }

      tableWrap.replaceChildren(table);
      renderLegend(Array.isArray(schedule.shifts) ? schedule.shifts : []);
    }

    async function poll() {
      try {
        const response = await fetch("/schedule", { cache: "no-store" });
        if (response.status === 204) {
          return;
        }
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const payload = await response.json();
        if (payload.version === seenVersion) {
          return;
        }

        seenVersion = payload.version;
        render(payload.schedule);
        status.textContent = `Updated ${new Date(payload.received_at).toLocaleTimeString()}`;
      } catch (error) {
        status.textContent = `Server error: ${error.message}`;
      }
    }

    poll();
    setInterval(poll, 1000);
  </script>
</body>
</html>
"""


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

        self.send_error(404)

    def do_POST(self) -> None:
        if self.path.split("?", 1)[0] != "/schedule":
            self.send_error(404)
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            schedule = json.loads(self.rfile.read(content_length).decode("utf-8"))
        except (ValueError, json.JSONDecodeError):
            self.send_error(400, "Invalid JSON")
            return

        if not isinstance(schedule, dict):
            self.send_error(400, "Schedule payload must be a JSON object")
            return

        missing = REQUIRED_FIELDS - set(schedule)
        if missing:
            self.send_error(400, f"Missing fields: {', '.join(sorted(missing))}")
            return

        with STATE_LOCK:
            STATE["version"] += 1
            STATE["received_at"] = datetime.now(timezone.utc).isoformat()
            STATE["schedule"] = schedule
            version = STATE["version"]

        self._send_json({"ok": True, "version": version})

    def log_message(self, format: str, *args: Any) -> None:
        print(f"{self.address_string()} - {format % args}")

    def _common_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send(self, body: bytes, content_type: str) -> None:
        self.send_response(200)
        self._common_headers()
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload: dict[str, Any]) -> None:
        self._send(json.dumps(payload).encode("utf-8"), "application/json")


def main() -> None:
    parser = argparse.ArgumentParser(description="Visualize shift schedules.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), ScheduleHandler)
    print(f"Listening on http://{args.host}:{args.port}")
    print("POST schedules to /schedule")
    server.serve_forever()


if __name__ == "__main__":
    main()
