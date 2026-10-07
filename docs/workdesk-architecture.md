# Work Desk engine — architecture notes

The Work Desk is the learning engine behind Module 4 (Orders & Fulfillment), Module 5 (Inventory Basics), Module 6 (Customer Support in E-commerce), Module 7 (Returns, Refunds & Exceptions), Module 9 (Operational Data: Verify Before You Report, working title) and Module 13 (Client Communication & Reporting), refactored so other modules can reuse its mechanics without copying Module 4. It is client-side only: no backend, accounts, scoring, timers or tracking. The design source of truth is the *Learning Experience Reference Architecture & Propagation Specification*.

## Files

| File | Role | Knows about a module? |
| --- | --- | --- |
| `shared/workdesk.js` | **Core.** Answer protection, module-scoped storage, validators (tiers 1–5), stage evaluation registry, feedback composition and safety filter, retry policy, verified-work state. No DOM; runs in Node for tests and the codec. | No |
| `shared/workdesk-ui.js` | **UI.** Evidence kinds (record, message, table, reference), evidence gate tracker, stage renderers (decision, triage, sequence, compose), feedback blocks, pause and re-check, earned work samples. | No |
| `shared/workdesk-page.js` | **Page controller.** Brief → stages → next task, contextual buttons, status line, task pills, `#task-N` links, legacy progress integration. | No |
| `shared/workdesk.css` | Desk styles, all under `desk-` classes on the existing tokens. | No |
| `shared/everfield-data.js` | **Shared authored state.** Company, team, partners, channels, products and product facts, calendar and timeline. Deep-frozen. | No (module dates only) |
| `shared/everfield-records.js` | **Shared authored records.** Orders and stock rows that two or more modules show. Deep-frozen, answer-free; not loaded by any page yet. See `docs/everfield-continuity.md`. | No |
| `<module>/desk-data.js` | **Module content.** Plain `config` + encoded `payload` (tasks, records, prompts, feedback, hashed answer keys). Generated, never hand-edited. | Yes |
| `tools/desk-codec.js` | Encode, decode, and lint module content. Uses the core's hashing. | No |

A module page loads, in order: `progress.js`, `everfield-data.js`, `workdesk.js`, `workdesk-ui.js`, `workdesk-page.js`, its own `desk-data.js`, then calls `PVADeskPage.mount({ module: "m4" })`.

## What is reusable, and what is Module 4's

**Reusable (engine):** evidence cards and the gate; the four stage types; tier 1–5 validation; free-text junk filter; consistency rules; feedback composition and the answer-safety filter; pause and re-check; self-check with stale-confirmation clearing; draft persistence; earned work-sample generation; derived completion; per-module storage; per-module answer protection; legacy-progress integration.

**Module 4 only (content, in `module-4/desk-data.js`):** the eight tasks and their records (#5401–#5419), every prompt, finding, option and feedback line, the Order Log and update structures, button labels (`stage.cta`), the sequence gate wording, two fallback feedback lines, the completion banner, the work-sample company line, and the salt and key. Module 4's simulated date is in `everfield-data.js` → `calendar.m4`.

**Module 7 (content, in `module-7/desk-data.js`):** ten tasks over orders #5420–#5444 and returns #230–#240 (all Module 7-local), policy cards quoting the approved clauses in `docs/everfield-continuity.md` §6 word for word (the checker enforces it), the Exception Resolution Log compose stage, salt `everfield-desk-m7-v1`, `legacyPill: "check"`. Simulated date: `calendar.m7` (Thu, Sep 17).

**Module 5 (content, in `module-5/desk-data.js`):** four tasks (decision I1-a: m5-l2, m5-l8, m5-l6, m5-l7, all existing ids; the hub lists these four) on one Module 5-local working day, Wed Sep 2, with the clock moving from 9:15 AM to 4:30 PM. Read → Flag → Investigate → Record: stock states (triage), which issues go to Maya now (triage + decision), comparing like with like before calling a count difference (two decisions, one a same-surface transfer), and EF-101's movement tracker (compose with three typed balances; earns the Inventory Tracker). The 8:00 AM stock sheet keeps the shared early-September snapshot rows; alert levels are Module 5-local (T1); Return #229 is a shared record (R1). Salt `everfield-desk-m5-v1`, `legacyPill: "check"`. Simulated date: `calendar.m5` (Wed, Sep 2).

**Module 6 (content, in `module-6/desk-data.js`):** three tasks (decision D8: m6-l2, m6-l4, m6-l9, all existing ids; the hub lists these three) on one Module 6-local support day, Thu Sep 10 (D3): orders #5483–#5495, tracking CP-7731-08xx, the shared Return #229 (D4), an EF-105 stock card, no EF-103. Read the inbox → Reply from the record → Not yours to decide: what each message needs (triage + a stock-question decision), replies built only from the customer's own record, including one the record can't answer (compose with one own-words reply), and escalation with a handoff to Sofia plus the day's replies (decision + compose; earns the E-commerce Customer Response Pack). M6 owns the customer-facing reply and handoff; M7 owns the operational decision (D2): M6 quotes canon cards P5, P7 and P8 and never decides a return, refund or replacement. Address changes and marketplace messaging stay reference only (D5, D6). Salt `everfield-desk-m6-v1`, `legacyPill: "check"`. Simulated date: `calendar.m6` (Thu, Sep 10).

**Module 9 (content, in `module-9/desk-data.js`):** four tasks (decision I1-a: m9-l3, m9-l9, new m9-l11, m9-l10; the hub lists these four) over one Module 9-local week, Mon Sep 21 – Fri Sep 25: orders #5450–#5462, tracking CP-7731-06xx, ClearPath's weekly report, a stock sheet without EF-102/EF-103/EF-106, and an open-items log. Pattern Count → Verify → Reconcile → Report; typed-number fields in Lessons 1, 2 and 4, each paired with a choice about what the number means; Lesson 4 earns the Operations Tracker. Unit costs come from the product canon in `docs/everfield-continuity.md` §6 (decision D5). Salt `everfield-desk-m9-v1`, `legacyPill: "check"`. Simulated date: `calendar.m9` (Fri, Sep 25). The page adds two module-local layout rules (evidence cards wide enough for their tables, and grid cells allowed to shrink so a wide table scrolls inside its own region instead of pushing a phone page sideways).

**Module 13 (content, in `module-13/desk-data.js`):** three tasks (decision I1-a: m13-l2, m13-l5, m13-l8, all existing ids; the hub lists these three) over one Module 13-local week, Mon Sep 28 – Fri Oct 2 (decision W1-a): orders #5465–#5482, returns #241 onward, tracking CP-7731-07xx, no EF-103. Select → Sharpen → Report: what gets reported and when (triage + decision, midweek), fixing report lines a reader couldn't use (decision + compose, one typed count paired with its interpretation), and the Weekly Operations Report for Sofia, requested by Maya (one compose with six sections, a checked summary, self-check and human review; earns the Weekly E-commerce Operations Report). Lesson 3 starts from a verified Operations Tracker that the learner uses as given and never re-verifies (D6, kept by giving Module 13 its own week so no other module's graded answers appear). Lesson 1 declares its own work date (`workDate`: Wed, Sep 30); the other two run on `calendar.m13` (Fri, Oct 2). Salt `everfield-desk-m13-v1`, `legacyPill: "check"`.

**Per-lesson work date:** a task may carry `workDate` (e.g. "Wed, Sep 30"). The page shows it in the desk bar while that task is open and falls back to the module's `calendar` date otherwise, so modules without it are unchanged. The continuity checker validates it (on the timeline, no later than the module's day) and checks that lesson's clocks and dates against it.

**Engine CSS (decision E3):** `.desk-records > *{ min-width: 0; }` lives in `shared/workdesk.css`, so a wide table inside an evidence card scrolls in its own region instead of pushing a phone page sideways. It was first written as a Module 9 page rule and promoted once the full regression showed parity.

**Phone tables (Module 5 break test M5-RESP-01/02):** below 640 px each table row stacks into a block, and every value shows its column name above it (`data-label`, drawn by CSS). No column is left behind sideways scrolling. Desktop keeps the normal column-header table. The renderer adds explicit ARIA table roles so the stacked layout keeps its table semantics. Evidence-card titles get a 10em flex basis so the Reviewed chip and Hide button wrap below a long title instead of overlapping it. Known, left as is: on desktop, a few Module 7 and Module 9 tables in two-column card layouts still scroll inside their card, which the repair brief asked to preserve.

Known limitation: a `triage` stage renders only its rows, so it has no open side card. Module 7's triage tasks that need policy (l5) carry the clauses in the task reference shown with the brief, and the stage intro points back to it.

## Release status

A **regression-locked** module's learner-facing content and design are frozen: it is an approved reference implementation. Shared engine changes stay allowed, but every one must keep each locked module's regression suite green (`tests/run_all.sh`).

| Module | Status | Release |
| --- | --- | --- |
| Module 4 · Orders & Fulfillment | Released · regression-locked | Released together with Modules 7 and 9 |
| Module 7 · Returns, Refunds & Exceptions | Released · regression-locked | Released together with Modules 4 and 9 |
| Module 9 · Operational Data | Released · regression-locked | Released together with Modules 4 and 7 |
| Module 5 · Inventory Basics | Released · regression-locked | Production `9780c00` |
| Module 6 · Customer Support in E-commerce | **Released · reference implementation ready · regression-locked** (2026-10-07) | Implementation `eb21c1e`, merged to `main` as `24f5d09`, deployed to production |
| Module 13 · Client Communication & Reporting | **Released · reference implementation ready · regression-locked** (2026-10-07) | Implementation `7e09594`, merged to `main` as `444c6e7`, deployed to production |

**Module 6 release record.** Independent Gemini break test of `eb21c1e`. The first report was not grounded in the build: it cited orders, carriers and UI that don't exist, and none of its findings reproduced. The re-test, run against the review packet and screenshots, graded it A (reference implementation ready) with 0 confirmed defects. Two non-blocking observations were deliberately left unchanged: one triage card might be guessed as the cautious choice, and the shared Show/Hide toggles are 30 px tall, above the WCAG AA 24 px minimum. Regression was fully green before and after the merge: continuity checks; content lint for M4, M5, M6, M7, M9 and M13; shared engine 39/39; number field 17/17; M4 136/136 plus 111/111 behaviour states; M5 188/188; M6 161/161; M7 186/186; M9 196/196; M13 194/194. The production smoke test passed for Lessons 1–3, the reply validator, the earned pack and its persistence, and the portfolio line. Production: https://pva-ecommerce-free-training.pages.dev/module-6/

**Module 13 release record.** Independent Gemini break test of `7e09594`: A, reference implementation ready, 0 confirmed defects. Two non-blocking observations were deliberately left unchanged: possible focus trapping in the evidence drawer on very narrow screens, and the phone keyboard pushing Lesson 3's submit button below the fold at 320 px. Regression was fully green before and after the merge: continuity checks; content lint for M4, M5, M7, M9 and M13; shared engine 39/39; number field 17/17; M4 136/136 plus 111/111 behaviour states; M5 188/188; M7 186/186; M9 196/196; M13 194/194. The production smoke test passed for Lessons 1–3, portfolio and persistence, and deployment integrity. Production: https://pva-ecommerce-free-training.pages.dev/module-13/

## Configuration boundary (`config` in a module's source)

```jsonc
{
  "moduleId": "m4",                       // required; storage key and calendar entry derive from it
  "salt": "everfield-desk-v1",            // required; per module
  "key": "EverfieldOpsDesk",              // optional encoding key
  "legacyPill": "check",                  // "check" | "distinct" -- see Progress
  "retry": { "pauseAfterFails": 2 },      // optional
  "text": { "exampleSimilarity": 0.55 },  // optional junk-filter thresholds
  "sample": { "companyLine": "…" },       // work-sample header line
  "copy": { "reasoningFallback": "…", "page": { "complete": "…" } },  // override any generic wording
  "legacyGlobal": "M4_DESK_DATA"          // Module 4 only: alias for pilot-era tests
}
```

**Typed numbers (engine 2.1).** A `compose` field `{ type: "number", unit?, decimals? (default 0), min? (default 0), max, accept: ["58"] }`. Entries are normalised the same way when locked and when checked: an optional leading "$", thousands commas and spaces are removed, and the value is fixed to `decimals`. An entry with more decimal places than declared is refused, never rounded into a pass. A non-number gets a format message; a wrong number gets only the field's `msg` (a principle, never the value or a direction). `max` is required with `accept` because the codec recovers the answer by searching `min..max` (at most 2,000,000 values). The work sample prints the canonical value with its unit ("$243.60", "58 units"). The input is a plain text field with `inputmode`, so no spinner or locale formatting.

Stage data can add `cta` (button into the stage), `gateText` and `recheckText` (sequence), `humanReview` (tier 5 note), per-field `criteria` (tier 3), and per-finding `principle` + `look` as an alternative to `miss`.

## Storage namespace

- One key per module: `pva-ecom-ft-<moduleId>-desk` (Module 4: `pva-ecom-ft-m4-desk`, unchanged from the pilot).
- `createDesk` refuses a missing or invalid id, the reserved id `progress` (the legacy key is `pva-ecom-ft-progress`), and two modules claiming one key.
- Per task it stores views, attempts, fails, last and passing answers, drafts, opened and re-check evidence, and confirmations. It never stores a "completed" flag.

## Validators

| Tier | Mechanism | Defined by |
| --- | --- | --- |
| 1 Exact | Salted hashes per finding, option, row, sequence position, field value, set or typed number | Codec, from `correct` / `answer` / `correctOrder` / `accept` markers in the plaintext source |
| 2 Consistency | `rules` (must mention) and `when` (if field X is Y, must or must not mention) between the learner's own answers; `banned` guesses; example-copy check | Module data |
| 3 Criteria | `required`, `oneOf`, `minItems`, `matchesSource`, `distinctFrom`. Several right answers; rules are visible, not secret | Module data |
| 4 Self-review | Every judgement confirmation ticked; confirmations unlock after evidence is open and clear on edit | Module data (`confirm`) |
| 5 Human review | Declared (`humanReview`), passed through to the result and the work sample, never computed | Module data |
| Junk filter | Blank, filler, repeated words, keyword lists, too few sentences | Engine, thresholds configurable |

## Feedback

`desk.decisionFeedback(stage, result)` returns the chosen action, a missed-findings lead with one pointer per missed finding, the distractors the learner picked with why each is wrong, and "why this matters". Every line passes a safety filter that withholds any line quoting a correct finding or the correct option (a console warning names it). `tools/desk-codec.js check` catches the same mistake when content is authored.

## Retry and reconsideration

Unlimited attempts. Previous selections stay. From the `pauseAfterFails`-th failed attempt on a stage, the evidence behind the mistake closes and must be re-opened before the next attempt: all records in a decision or sequence stage, only the wrong rows in triage, only the failing entries' records in compose. The re-check state survives refresh. Fails are counted per stage (not "consecutive"); see technical debt.

## Work samples

`validated answer → workSampleText() → training work sample`. Generated only from `stage.answer`, never drafts. The header is always `TRAINING WORK SAMPLE`, the piece title, the module's company line, then work date and requester. Title, requester, headings, filename and badge come from the stage's `evidence` block, which has copy and download actions.

## Progress integration

- **Legacy course completion** (`PVAEcom`, `pva-ecom-ft-progress`) is historical. It is never erased, and is written only by the page controller after a task's work verifies.
- **Verified-work state** is derived on every load from answers that re-validate (`PVADesk.verifiedWork()`). A legacy checkmark is never treated as verified work or an earned sample (`PVADesk.legacyCompletion()` is reported separately).
- `legacyPill: "check"` (Module 4 today) shows legacy and verified completion with the same pill checkmark; the status line says which. `"distinct"` shows the checkmark only for verified work and gives legacy-only pills a separate marker.

## Adding a module (outline)

1. Author `<module>.src.json` with `config` (new `moduleId`, new salt) and tasks; reuse existing stage types and evidence kinds.
2. `node tools/desk-codec.js check <module>.src.json`, then `encode` into `<module>/desk-data.js`. Never commit the source.
3. Add the module's date to `everfield-data.js` → `calendar` (it must fit the timeline in `docs/everfield-continuity.md`), and take any record another module already shows from `everfield-records.js`. Run `node tools/everfield-check.js`.
4. In the module page, load the six scripts and call `PVADeskPage.mount({ module: "<id>" })`.
5. Add a browser suite modelled on `tests/e2e/test_module4.py`.

New stage types: `PVADeskCore.registerStageType(type, { evaluate })` + `PVADeskUI.registerRenderer(type, fn)`. New evidence kinds: `PVADeskUI.registerEvidenceKind(name, { title, body, gated, ... })`.

## Technical debt

- Fails are counted per stage, not "consecutive"; after "Revise your work" on a compose stage, the next miss pauses immediately. Kept to preserve Module 4 behaviour.
- `legacyGlobal` (`window.M4_DESK_DATA`) exists only so pilot-era tests run unchanged; remove with them.
- Consistency rules (tier 2) still rely on keyword lists; they must stay generous.
- `/portfolio/` does not yet read `verifiedWork()`; Export/Restore does not yet include desk keys.
- The plaintext Module 4 source is recoverable only by decoding the shipped file; there is no committed builder script, by design.
