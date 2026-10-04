# Work Desk engine — architecture notes

The Work Desk is the learning engine behind Module 4 (Orders & Fulfillment), refactored so other modules can reuse its mechanics without copying Module 4. It is client-side only: no backend, accounts, scoring, timers or tracking. The design source of truth is the *Learning Experience Reference Architecture & Propagation Specification*.

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

Stage data can add `cta` (button into the stage), `gateText` and `recheckText` (sequence), `humanReview` (tier 5 note), per-field `criteria` (tier 3), and per-finding `principle` + `look` as an alternative to `miss`.

## Storage namespace

- One key per module: `pva-ecom-ft-<moduleId>-desk` (Module 4: `pva-ecom-ft-m4-desk`, unchanged from the pilot).
- `createDesk` refuses a missing or invalid id, the reserved id `progress` (the legacy key is `pva-ecom-ft-progress`), and two modules claiming one key.
- Per task it stores views, attempts, fails, last and passing answers, drafts, opened and re-check evidence, and confirmations. It never stores a "completed" flag.

## Validators

| Tier | Mechanism | Defined by |
| --- | --- | --- |
| 1 Exact | Salted hashes per finding, option, row, sequence position, field value or set | Codec, from `correct` / `answer` / `correctOrder` / `accept` markers in the plaintext source |
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
