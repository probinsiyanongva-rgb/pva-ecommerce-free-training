#!/usr/bin/env bash
# Runs every check: Everfield continuity, content lint, core unit tests, the engine number
# field, the Module 4 browser suite and behavioral snapshot, and the Module 7 and 9 suites. Needs node, python3, playwright.
set -euo pipefail
cd "$(dirname "$0")/.."
PORT="${PORT:-8765}"
if ! curl -s -o /dev/null "http://localhost:$PORT/index.html"; then
  python3 -m http.server "$PORT" >/dev/null 2>&1 & SERVER=$!
  trap 'kill $SERVER' EXIT; sleep 1
fi
export DESK_TEST_BASE="http://localhost:$PORT"
echo "== everfield continuity"; node tools/everfield-check.js | tail -1
echo "== content lint m4";     node tools/desk-codec.js check module-4/desk-data.js
echo "== content lint m7";     node tools/desk-codec.js check module-7/desk-data.js
echo "== content lint m9";     node tools/desk-codec.js check module-9/desk-data.js
echo "== core unit tests";     node tests/unit/core.test.js
echo "== engine number field"; python3 tests/e2e/test_engine_number.py | tail -1
echo "== module 4 browser";    python3 tests/e2e/test_module4.py | tail -1
echo "== module 4 behavior";   python3 tests/e2e/snapshot_module4.py
echo "== module 7 browser";    python3 tests/e2e/test_module7.py | tail -1
echo "== module 9 browser";    python3 tests/e2e/test_module9.py | tail -1
