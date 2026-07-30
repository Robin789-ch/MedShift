FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

WORKDIR /app

COPY pyproject.toml uv.lock .python-version ./
COPY packages/contracts packages/contracts
COPY services/agent/pyproject.toml services/agent/pyproject.toml
COPY services/optimizer services/optimizer

RUN uv sync --frozen --no-dev --package medshift-optimizer

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8001

CMD ["uvicorn", "medshift_optimizer.app:app", "--host", "0.0.0.0", "--port", "8001"]
