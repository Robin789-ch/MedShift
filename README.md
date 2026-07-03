# SchedulePlanner

SchedulePlanner is a small OR-Tools CP-SAT shift scheduler with a lightweight
development UI. It solves schedules in two stages:

1. Assign each employee a broad day type: `O`, `D`, `N`, `F`, `R`, or `H`.
2. Assign concrete departments inside solved `D` and `N` cells.

The frontend is intentionally simple: a single Python stdlib web server that
lets you create employees, departments, fixed assignments, requests, run the
optimizer, inspect the result table, and open the captured solver logs.

## Repository Layout

- `scheduler.py`: optimizer, TOML parsing, frontend sender, and CLI entrypoint.
- `frontend_server.py`: tiny configuration/result/log web server.
- `config.toml`: default model configuration.
- `test_scheduler.py`: unit and integration tests for solver behavior.
- `ortools/`: local Python environment used by this repo.

## Quick Start

Run the tests:

```sh
./ortools/bin/python -B -m unittest test_scheduler.py
```

Start the development UI:

```sh
./ortools/bin/python -B frontend_server.py --port 8000
```

Open:

```text
http://127.0.0.1:8000
```

Run the optimizer from the command line:

```sh
./ortools/bin/python -B scheduler.py --config=config.toml --params=max_time_in_seconds:10.0
```

When the frontend server is listening on port `8000`, the CLI run also posts the
latest solved schedule to the UI.

Run the experimental single-stage optimizer in parallel:

```sh
./ortools/bin/python -B frontend_server_single_stage.py --port 8001
./ortools/bin/python -B scheduler_single_stage.py --config=config.toml --params=max_time_in_seconds:10.0
```

The copied single-stage CLI posts to `http://127.0.0.1:8001/schedule` by
default, leaving the baseline two-stage server on port `8000`.

The single-stage UI also exposes optional weekly hour caps. Leave
`max_hours_per_week` blank for no cap, or set it with department
`duration_hours` values to limit each employee's assigned department hours per
week.

## Frontend Workflow

The UI has two main steps:

1. Define employees, number of weeks, and departments.
2. Paint fixed assignments, desired requests, and not-desired requests onto the
   schedule grid, then optimize.

Cell picker choices include broad shifts and departments:

- Broad shifts: `O`, `D`, `N`, `F`, `R`, `H`.
- Departments: configured by ID, displayed by their symbol and color.

The result table keeps the broad `plan` intact and overlays department symbols
and colors for department-assigned `D` and `N` cells. Solver output is captured
in the optional logs drawer.

## HTTP Endpoints

- `GET /`: serves the UI.
- `GET /defaults`: returns the default config built from `config.toml`.
- `POST /optimize`: accepts a config JSON payload, runs both optimizer stages,
  and returns `{ ok, schedule, log }` style state.
- `GET /schedule`: returns the latest stored schedule, or `204` if none exists.
- `POST /schedule`: stores an already-solved schedule payload.
- `GET /logs`: returns the latest captured optimizer log.

## Model Overview

The broad shift symbols currently are:

- `O`: off day; counts toward weekly off-day constraints.
- `D`: day work; covers department demand.
- `N`: night work; covers department demand and counts as night work.
- `F`: formation day; counts as work but covers no demand and may only appear
  as a fixed assignment.
- `R`: overtime recovery; off by work semantics, but does not count toward the
  weekly off-day minimum.
- `H`: holiday; counts as work, covers no demand, and may only appear as a fixed
  assignment or desired request.

Departments are configured in `config.toml` with:

```toml
[[departments]]
id = "day"
name = "Day"
shift = "D"
symbol = "D"
color = "#ffe08a"
requirements = [5, 5, 4, 5, 4, 3, 4]
```

Department demand is the source of truth. Stage one derives exact `D` and `N`
cover requirements from department requirements. Stage two then assigns one
department to every employee/day cell that stage one marked as `D` or `N`.

## Constraint Inputs

Broad fixed assignments:

```toml
fixed_assignments = [
  [0, "O", 0],
  [2, "D", 1],
]
```

Broad requests:

```toml
requests = [
  [3, "O", 5, -4],
  [2, "N", 4, 6],
]
```

Negative weights are desired assignments. Positive weights are not-desired
assignments.

Department constraints use stable department IDs:

```toml
department_fixed_assignments = [
  [1, "day", 0],
]

department_requests = [
  [2, "night", 4, -4],
  [5, "day", 3, 4],
]
```

Desired department requests also project to stage one as broad `D` or `N`
requests. Not-desired department requests remain stage-two-only.

## Solver Logs

Stage one prints OR-Tools objective improvements, shift penalties/gains, and
solver stats. Stage two prints one section per broad department shift, labeled
status, penalties/gains, and solver stats. Stage-two objective iterations appear
when the subproblem has objective terms, for example department requests or
multi-department switch penalties.

The old stage-one schedule table is intentionally no longer printed; the UI
result table is the schedule view.

## Validation

Useful checks before handing off changes:

```sh
./ortools/bin/python -B -m py_compile scheduler.py frontend_server.py test_scheduler.py
./ortools/bin/python -B -m unittest test_scheduler.py
./ortools/bin/python -B -c "from frontend_server import PAGE; import re, sys; sys.stdout.write(re.search(r'<script>(.*)</script>', PAGE, re.S).group(1))" | node --check
git diff --check
```

For an HTTP smoke test with the server running:

```sh
curl -s http://127.0.0.1:8000/defaults \
  | curl -s -X POST -H "Content-Type: application/json" --data-binary @- http://127.0.0.1:8000/optimize
```
