FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

WORKDIR /app

COPY pyproject.toml uv.lock .python-version ./
COPY packages/contracts packages/contracts
COPY services/agent services/agent
COPY services/optimizer/pyproject.toml services/optimizer/pyproject.toml

RUN uv sync --frozen --no-dev --package medshift-agent

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "medshift_agent.app:app", "--host", "0.0.0.0", "--port", "8000"]
