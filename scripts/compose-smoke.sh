#!/usr/bin/env bash
set -euo pipefail

frontend_log="$(mktemp)"
npm --prefix frontend run dev >"$frontend_log" 2>&1 &
frontend_pid=$!

cleanup() {
  kill "$frontend_pid" 2>/dev/null || true
  rm -f "$frontend_log"
}
trap cleanup EXIT

for _ in $(seq 1 60); do
  if health="$(curl --fail --silent --show-error http://127.0.0.1:5173/api/health 2>/dev/null)"; then
    HEALTH_RESPONSE="$health" node -e '
      const health = JSON.parse(process.env.HEALTH_RESPONSE);
      if (
        health.service !== "agent" ||
        health.status !== "ok" ||
        health.checks.configuration !== "ok" ||
        health.checks.optimizer !== "ok"
      ) {
        process.exit(1);
      }
    '
    echo "Frontend → Agent → Optimizer health path is ready."
    exit 0
  fi
  sleep 1
done

cat "$frontend_log"
exit 1
