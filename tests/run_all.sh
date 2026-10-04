#!/usr/bin/env bash
# Runs every Work Desk check: content lint, core unit tests, Module 4 browser
# suite, and the Module 4 behavioral snapshot. Needs node, python3, playwright.
set -euo pipefail
cd "$(dirname "$0")/.."
PORT="${PORT:-8765}"
if ! curl -s -o /dev/null "http://localhost:$PORT/index.html"; then
  python3 -m http.server "$PORT" >/dev/null 2>&1 & SERVER=$!
  trap 'kill $SERVER' EXIT; sleep 1
fi
export DESK_TEST_BASE="http://localhost:$PORT"
echo "== content lint";        node tools/desk-codec.js check module-4/desk-data.js
echo "== core unit tests";     node tests/unit/core.test.js
echo "== module 4 browser";    python3 tests/e2e/test_module4.py | tail -1
echo "== module 4 behavior";   python3 tests/e2e/snapshot_module4.py
