# MedShift

MedShift is a small hospital shift-planning app. It helps build a staff
schedule with broad shift types, concrete department assignments, fixed days,
requests, weekly hour limits, and overtime recovery.

It runs locally in your browser. There is no database and no account system.

## What It Can Do

- Plan multiple weeks at once.
- Configure employees and pending overtime hours.
- Configure departments, weekday staffing needs, shift length, symbol, and color.
- Mark fixed assignments, desired assignments, and not-desired assignments.
- Optimize a schedule with Google OR-Tools.
- View the result table and solver logs in the browser.

The default example uses these broad shifts:

- `O`: off
- `D`: day
- `N`: night
- `F`: formation/training
- `R`: overtime recovery
- `H`: holiday

## Requirements

- Python 3.11 or newer
- `pip`

Python 3.13 is recommended because that is the version used for the current
local test environment.

## Setup

Create a virtual environment and install the pinned dependencies:

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

If `python3.13` is not installed, use another Python 3.11+ executable:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

## Run The App

Start the local web app:

```sh
.venv/bin/python -B frontend_server.py --port 8000
```

Open this URL:

```text
http://127.0.0.1:8000
```

In the app:

1. Set employees, overtime balances, number of weeks, and departments.
2. Click `Next`.
3. Paint fixed assignments or requests onto the grid.
4. Click `Optimize`.

## Run From The Command Line

You can also solve the example config without opening the browser:

```sh
.venv/bin/python -B scheduler.py --config=config.toml --params=max_time_in_seconds:10.0
```

If the browser app is already running on port `8000`, the command also sends
the latest solved schedule to the app.

## Customize The Example

The default schedule lives in `config.toml`.

Most users should start by changing:

- `num_employees`
- `num_weeks`
- `employee_overtime_hours`
- `fixed_assignments`
- `requests`
- `departments`
- `max_hours_per_week`

Department demand is configured per weekday:

```toml
[[departments]]
id = "day"
name = "Day"
shift = "D"
symbol = "D"
color = "#ffe08a"
duration_hours = 8
requirements = [5, 5, 4, 5, 4, 3, 4]
```

The `requirements` list starts on Monday and must contain up to seven numbers.

## Requests And Fixed Assignments

Fixed broad shift assignment:

```toml
fixed_assignments = [
  [0, "O", 0],
  [2, "D", 1],
]
```

Broad shift request:

```toml
requests = [
  [3, "O", 5, -4],
  [2, "N", 4, 6],
]
```

Negative weights mean desired. Positive weights mean not desired.

Department assignments use department IDs:

```toml
department_fixed_assignments = [
  [1, "day", 0],
]

department_requests = [
  [2, "night", 4, -4],
  [5, "day", 3, 4],
]
```

## Test

Run the test suite:

```sh
.venv/bin/python -B -m unittest discover
```

## Status

This project is ready for local testing, but it is still a small prototype. The
optimizer can report no feasible solution if the staffing requirements,
fixed assignments, and hour limits conflict.
