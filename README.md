# MedShift

MedShift V0.2 is a local scheduling prototype. The current tracer bullet proves
the runtime wiring only:

- a React, TypeScript, and Vite frontend runs on the host at
  `http://localhost:5173`;
- the frontend proxies relative `/api` requests to the containerized Agent at
  `http://localhost:8000`;
- the Agent checks the stateless Optimizer at `http://optimizer:8001`;
- only the Agent mounts `data/`.

Workspace, Chat, and solver behavior are intentionally reserved for later
tickets.

## Requirements

- Python 3.14
- [uv](https://docs.astral.sh/uv/)
- Node.js and npm
- Docker with Compose

## Install

```sh
uv sync --frozen
npm --prefix frontend ci
```

## Run

Start the Python services:

```sh
docker compose up --build
```

In another terminal, start the host frontend:

```sh
npm --prefix frontend run dev
```

Opening `http://localhost:5173` exercises the relative `/api/health` proxy. The
optional OpenRouter variables can be copied from `.env.example` into an ignored
`.env`; they are passed only to the Agent container.

## Verify

With Compose running:

```sh
scripts/compose-smoke.sh
```

Run the automated checks:

```sh
uv run pytest
uv run mypy packages/contracts/src services/agent/src services/optimizer/src
npm --prefix frontend run check:api
npm --prefix frontend run typecheck
npm --prefix frontend run build
```
