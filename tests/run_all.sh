#!/usr/bin/env bash
# Runs every check: Everfield continuity, content lint, core unit tests, the engine number
# field, the Module 4 browser suite and behavioral snapshot, and the Module 2, 3, 5, 6, 7, 8, 9 and 13 suites. Needs node, python3, playwright.
set -euo pipefail
cd "$(dirname "$0")/.."
PORT="${PORT:-8765}"
if ! curl -s -o /dev/null "http://localhost:$PORT/index.html"; then
  python3 -m http.server "$PORT" >/dev/null 2>&1 & SERVER=$!
  trap 'kill $SERVER' EXIT; sleep 1
fi
export DESK_TEST_BASE="http://localhost:$PORT"
echo "== everfield continuity"; node tools/everfield-check.js | tail -1
echo "== content lint m2";     node tools/desk-codec.js check module-2/desk-data.js
echo "== content lint m3";     node tools/desk-codec.js check module-3/desk-data.js
echo "== content lint m5";     node tools/desk-codec.js check module-5/desk-data.js
echo "== content lint m6";     node tools/desk-codec.js check module-6/desk-data.js
echo "== content lint m4";     node tools/desk-codec.js check module-4/desk-data.js
echo "== content lint m7";     node tools/desk-codec.js check module-7/desk-data.js
echo "== content lint m8";     node tools/desk-codec.js check module-8/desk-data.js
echo "== content lint m9";     node tools/desk-codec.js check module-9/desk-data.js
echo "== content lint m13";    node tools/desk-codec.js check module-13/desk-data.js
echo "== core unit tests";     node tests/unit/core.test.js
echo "== engine number field"; python3 tests/e2e/test_engine_number.py | tail -1
echo "== module 4 browser";    python3 tests/e2e/test_module4.py | tail -1
echo "== module 4 behavior";   python3 tests/e2e/snapshot_module4.py
echo "== module 2 browser";    python3 tests/e2e/test_module2.py | tail -1
echo "== module 3 browser";    python3 tests/e2e/test_module3.py | tail -1
echo "== module 5 browser";    python3 tests/e2e/test_module5.py | tail -1
echo "== module 6 browser";    python3 tests/e2e/test_module6.py | tail -1
echo "== module 7 browser";    python3 tests/e2e/test_module7.py | tail -1
echo "== module 8 browser";    python3 tests/e2e/test_module8.py | tail -1
echo "== module 9 browser";    python3 tests/e2e/test_module9.py | tail -1
echo "== module 13 browser";   python3 tests/e2e/test_module13.py | tail -1
