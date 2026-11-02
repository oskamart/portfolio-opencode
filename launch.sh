#!/usr/bin/env bash
# Open the opencode portfolio locally.
#
# Starts the server if it is not already up, then opens the browser. The
# server binds 0.0.0.0 so the page is reachable from the LAN as well.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${PORT:-8094}"   # opencode agent port; 8090 and 8742 are taken
URL="http://127.0.0.1:${PORT}/"
LOGDIR="/tmp/opencode/opencode-logs"
mkdir -p "$LOGDIR"

if ! curl -sf -o /dev/null --max-time 3 "$URL"; then
  echo "starting the portfolio server on port ${PORT}…"
  setsid nohup python3 "$ROOT/serve.py" --host 0.0.0.0 --port "$PORT" --no-browser \
    >"$LOGDIR/portfolio.log" 2>&1 </dev/null &
  disown || true
  for _ in $(seq 1 40); do
    curl -sf -o /dev/null --max-time 2 "$URL" && break
    sleep 0.25
  done
fi

echo "portfolio (opencode): ${URL}"
if command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$URL" >/dev/null 2>&1 &
elif command -v sensible-browser >/dev/null 2>&1; then
  sensible-browser "$URL" >/dev/null 2>&1 &
fi
