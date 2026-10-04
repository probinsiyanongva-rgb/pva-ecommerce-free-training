# Work Desk tests

Run everything from the repo root:

```bash
tests/run_all.sh
```

Needs Node, Python 3 and Playwright with Chromium (`pip install playwright && playwright install chromium`). The script starts a static server on port 8765 if one is not already running.

| Check | File | What it guards |
| --- | --- | --- |
| Everfield continuity | `tools/everfield-check.js` | Shared Everfield data is frozen and answer/learner-state free; records used by two modules are shared records whose facts match the module text; SKUs, names and product facts; people and roles vs the hub; weekday/date agreement, numeric dates on the timeline, desk clock vs calendar. Known deferred conflicts print as warnings |
| Content lint | `tools/desk-codec.js check` (Modules 4 and 7) | Answer-pattern bias, feedback that quotes answers, missing hints, distractor-free findings |
| Core unit tests | `tests/unit/core.test.js` | Hash parity with the pilot, per-module salts and storage isolation, the five validator tiers, feedback safety, retry policy, derived completion, extensibility |
| Module 4 browser suite | `tests/e2e/test_module4.py` | Evidence gates, wrong answer → feedback → retry, second-miss pause and re-open (every stage), feedback safety (every decision), transfer, work samples, leakage, persistence, legacy progress, Everfield immutability, table/reference evidence, keyboard, mobile |
| Module 7 browser suite | `tests/e2e/test_module7.py` | The approved design (10 tasks, stage types, one portfolio task, no colour variants, open policy cards), full flow and completion, evidence gates, feedback safety, pause and re-open on every stage, transfer stages that reject the reused answer, consistency of the log notes, forged state, leakage (incl. answer-revealing ids and values), persistence, legacy checkmarks, isolation from Module 4, keyboard, 375 px |
| Module 4 behavior snapshot | `tests/e2e/snapshot_module4.py` | Every learner-visible string and state in 111 states, compared with hashes taken from the pre-refactor pilot build |

## No answers in this folder

This folder is deployed with the site, so it must never contain answers. Tests decode `module-4/desk-data.js` at run time and derive correct and wrong answers from it. The behavior baseline stores only SHA-256 hashes. Raw snapshot dumps (`--dump`) contain answers: keep them local (`*.snapshots.json` is git-ignored).

## When the snapshot fails

A failing snapshot means something a Module 4 learner sees has changed. If the change is intended, run `python3 tests/e2e/snapshot_module4.py --write` and say why in the commit message. If it is not intended, it is a regression.
