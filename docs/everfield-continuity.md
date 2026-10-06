# Everfield continuity — audit, canon and shared records

Status: continuity gate for the propagation sequence (spec §13, §14, §19, §21). Written before any Module 7 work. The principle: **continuity is authored, not simulated.**

Sources of truth, one per kind of fact:

| Kind of fact | Source of truth | Notes |
| --- | --- | --- |
| Company, people, roles, channels | Hub "Meet Everfield Goods" panel (`index.html`), mirrored in `shared/everfield-data.js` | The checker fails if the two disagree |
| Product names and product master facts | `shared/everfield-data.js` → `products`, `productFacts` (each fact cites the lesson that first states it, or the approved product canon in §6) | Anything not listed is undefined |
| Calendar and timeline | `shared/everfield-data.js` → `calendar` (desk day per converted module), `timeline` | |
| Authority limits and policies | This document, §6 | Kept out of the runtime files that desk pages load, because they would hint at desk answers |
| Recurring operational records | `shared/everfield-records.js` | Only records two or more modules already share |
| Module cases and answer keys | Each module's own content (`<module>/desk-data.js` or its `LESSONS`) | Never in shared files |
| Learner work | Per-module desk storage, `pva-ecom-ft-progress` | Never in shared files; nothing reads shared records back from it |

`tools/everfield-check.js` enforces all of this (see §8).

---

## 1. Audit — current state

**Company and people.** Everfield Goods LLC; sells home-organization and lifestyle products in the US. People, per the hub and Module 1 (m1-l6): Sofia Ramirez, E-commerce Manager (closest contact); Maya Collins, Operations Manager; Daniel Brooks, Procurement & Supply Manager; Marcus Lee, 3PL Account Manager at ClearPath Fulfillment. Only Sofia and Maya appear in any lesson; Daniel and Marcus appear only on the hub and (by role) in m1-l6. Every lesson that names Sofia or Maya gives the same role (M1, M5, M6, M7, M8, M10, M11, M12, M13, M14, M4 desk).

**Partners and channels.** ClearPath Fulfillment is the only partner named (3PL: receive, store, pick, pack, ship). Pinecrest Manufacturing is named once as EF-103's supplier (m2-l2). Channels on the hub: Brand store, Online marketplace, B2B / bulk. Module 4 uses the first two.

**Products.** Eight SKUs (EF-101…EF-107, EF-200). Every name used anywhere matches the catalog. Stated product facts: EF-101 16in x 11in x 9in, 2.2 lb (m3-l4), Home Organization (m2-l3), unit cost $4.20 (product canon, §6); EF-102 40 pieces (m3-l2); EF-103 Pinecrest, 14-day lead time, Each, Home Organization (m2-l2); EF-104 12-Piece (m2-l4, m11-l7); EF-105 Travel Organization (m2-l3), unit cost $3.85 (product canon, §6); EF-107 3-piece set (m8-l4); EF-200 kit = 2 x EF-101 + 1 x EF-102 + 1 x EF-103 (Module 5 desk, m5-l8 reference; decision K1), listed under Kits (m3-l6); no size or color variants on any SKU (m2-l1).

**Policies and authority.** Consistent across modules (§6). No module defines a return window, a refund threshold, shipping times or carriers.

**Records.** Module 4 owns orders #5401–#5419, tracking CP-7731-04xx, customers J. Alvarez and R. Okafor, and PO EG-1047 (reference example). Other records: Order #4021 (M5, M9), #4022 (M9), Return #229 (M11, M5 — shared since the Module 5 conversion), #5192 (M7), #5310 (M14). Stock figures: M5 snapshot (EF-101 34/6/50, EF-103 0/2/25), M5 Wed Sep 2 stock sheet and cycle count (incl. EF-104 40 vs 36; Module 5-local), the retired M5 kit example (EF-101 100, EF-102 80, EF-103 25), M9 snapshot (EF-102 60/5/0, EF-106 8/2/40), M13 inbound (EF-103 25 expected 9/6), M14 (EF-103 0/0).

**Dates.** All simulated dates fall in September and none states a year.

| Module · lesson | Date | What it is |
| --- | --- | --- |
| M5 m5-l7 | 9/2 | Inventory row: EF-101 −2, customer shipment, Order #4021, balance 32 |
| M9 m9-l3 | 9/2 | Order table: #4021 EF-101 x2 Shipped; #4022 EF-200 x1 Processing |
| M11 m11-l4 | 9/2 | Documentation example: Return #229 processed, EF-101 x2, Restock |
| M13 m13-l5 | 9/6 | Report line: EF-103 0 available, 25 inbound expected 9/6 |
| M4 desk (all tasks) | Sat Sep 5 – Tue Sep 15 | Order, payment, fulfillment and carrier records |
| M4 desk (all tasks) | Tue, Sep 15 · 11:40 AM | Desk day ("now") |
| M4 m4-l8 reference | Sep 12 (+5 days) | Example of Everfield's update style: PO EG-1047 expected arrival |
| M7, M9, M12, M13, M14 | "this week", "Friday", "last/next week" | Relative, no date |

Every weekday-with-date in the course agrees with a calendar in which Sep 15 is a Tuesday.

## 2. Continuity matrix

Classes: **IC** intentional continuity · **AD** accidental duplication · **GC** genuine contradiction · **LO** local-only.

| Item | Current location | Current value | Intended role | Cross-module? | Conflict? | Recommended action |
| --- | --- | --- | --- | --- | --- | --- |
| Desk day | M4 desk; `calendar.m4` | Tue, Sep 15 | M4 working day | No | No — see calendar | Keep (IC with the timeline) |
| 9/2 stock row | M5 m5-l7 | #4021, EF-101 −2, balance 32 | Inventory row example | Yes (M9) | No | Shared record (IC) |
| 9/2 order table | M9 m9-l3 | #4021 Shipped, #4022 Processing | Order data example | Yes (M5) | No | #4021 shared (IC); #4022 LO |
| 9/2 return | M11 m11-l4; M5 m5-l7 | Return #229, EF-101 x2, unopened, Restock | Documentation example; restocked in Module 5's EF-101 tracker | Yes (since the Module 5 conversion) | No; it is not #4021's return (shipped the same day) | **Shared record** (R1) |
| 9/6 inbound | M13 m13-l5 | EF-103 25 inbound expected 9/6 | Report line example | Yes (M5) | No | Shared record (IC) |
| M5 stock snapshot | M5 desk (8:00 AM stock sheet, m5-l7; cards in m5-l2, m5-l8) | EF-101 34/6/50; EF-103 0/2/25 | Inventory snapshot | Yes (M13, M14 "earlier example") | No | Shared record (IC) |
| M5 kit example | M5 m5-l4 (retired) | EF-101 100, EF-102 80, EF-103 25 | Hypothetical ("if…") | No | Differed from the snapshot | **Retired** with the Module 5 conversion (K1) |
| EF-104 reconciliation | M5 m5-l6 | 40 vs ClearPath 36 | Module 5 desk record (Wed Sep 2, 7:00 AM cycle count) | No | No | LO, now dated |
| M9 stock snapshot | M9 m9-l4 (retired) | EF-102 60/5/0; EF-106 8/2/40 | Illustration | No | No | **Retired** with the Module 9 conversion (m9-l4 removed) |
| EF-103 in capstone | M14 m14-t4 | 0 available, 0 inbound | Contrast with M5/M13 | Yes (explicit) | No — after the 9/6 stock sold through | IC; timeline entry |
| PO EG-1047 | M4 m4-l8 reference | Arrival Sep 12, 80 more 5 days later | Style example (original M4 text) | No | No | LO |
| Orders #5401–#5419 | M4 desk | Sep 5–15 | Desk cases | No | No | LO (in desk data) |
| Order #5414 | M4 m4-l6, m4-l7 | Desk case (details in desk data) | Desk case | Situation type only (M14) | See §4 | LO |
| Order #5310 | M14 m14-t3 | Shipped, no tracking | Capstone skill check | Pattern only (M4) | See §4 | LO; decision pending |
| Order #5192 | M7 m7-l10 | 2 damaged EF-101, 3rd report this week | Escalation note example | Pattern (M7 l6, M13 l6, M14 t6) | No | LO; pattern noted §4 |
| Order #4022 | M9 m9-l3 | 9/2, EF-200 x1, Processing | Quiz answer row | No | No | LO |
| Customers | M4 desk | J. Alvarez (#5406), R. Okafor (#5419) | Desk messages | No | No | LO |
| Sofia Ramirez | Hub, M1, M6, M8, M10, M14, M4 | E-commerce Manager | Closest contact | Yes | No | IC; `team.sofia` |
| Maya Collins | Hub, M5, M7, M11, M13, M14, M4 | Operations Manager | Escalations, ClearPath | Yes | No | IC; `team.maya` |
| Daniel Brooks | Hub; `everfield-data.js` | Hub: Procurement & Supply Manager; data file: "Everfield team" | Named contact | Hub only | **GC** (introduced by the engine refactor) | **Fixed** in `everfield-data.js` |
| Marcus Lee | Hub; `everfield-data.js` | Hub: 3PL Account Manager (ClearPath); data file: "Everfield team" | ClearPath contact | Hub only | **GC** (introduced by the engine refactor) | **Fixed**, with `org: "ClearPath Fulfillment"` |
| ClearPath Fulfillment | Hub, M1, M4, M5, M14 | 3PL | Partner | Yes | No | IC; `partners.clearpath` |
| Pinecrest Manufacturing | M2 m2-l2 | EF-103 supplier | Product fact | No | No | `productFacts["EF-103"]` |
| Channels | Hub; `everfield-data.js` | Hub lists 3; data file listed 2 | Company fact | Yes | Drift (data file incomplete) | **Fixed**: added "B2B / bulk" |
| Product names | All modules | Catalog names | Company fact | Yes | No | IC; `products` |
| EF-101 dimensions | M3 m3-l4 | 16in x 11in x 9in, 2.2 lb | Spec example | Yes, after the fix (M6) | No | `productFacts["EF-101"]` |
| EF-103 dimensions | M6 m6-l4, m6-l9 apply | 16in x 11in x 9in | Customer answer | M4 desk ships EF-103 in a 12×9×3 in carton | **GC** — the record could not fit its carton; values copied from EF-101 | **Fixed**: M6 now asks about EF-101 (§5) |
| Variants | M2 m2-l1 vs M7 m7-l4 | "no size/color variants" vs "exchange EF-105 for a different color" | Catalog fact | Yes | **GC** | Fix when Module 7 is converted (§5) |
| Kit recipe | M5 m5-l8 reference (was m5-l4 "Recall…") | 2/1/1 | Company fact | M3 (category), M4 (EF-200 order) | No; "Recall" points at nothing earlier | `productFacts["EF-200"]`; note §7 |
| EF-104 pack | M2 m2-l4, M11 m11-l7 | 12-Piece | Product fact | Yes | No | IC; `productFacts` |
| EF-106 piece count | M12 m12-l9 placeholder | "corrected it from 8 to 6" | Placeholder sample | M14 t9 (no number) | No | LO; not canon (placeholder) |
| Refund / exception authority | M4, M6, M7, M10, M11, M12, M14 | §6 | Policy | Yes | No | Canon in §6 |
| Weekly report day | M13 m13-l2 ("Friday's weekly summary"), M7 m7-l10 ("by Friday") | Friday | Operating rhythm | Yes | No | `operating.weeklyReport` |
| Portfolio / capstone | Hub, portfolio, M14 t10 | 14-piece portfolio, capstone final piece | Course structure | Yes | Hub says "13 portfolio deliverables" and "14-piece" | Not Everfield data; reported only (§7) |

## 3. Everfield calendar

**Finding:** Module 4's Tue Sep 15 and the 9/2 and 9/6 dates do not conflict. They are different points in one September operating period, and they agree with each other where they touch: the 25 EF-103 units due 9/6 are what let Module 4 ship EF-103 orders placed Sep 9 and Sep 11. No date needs to change. (The spec placed "inbound 9/6" in Module 5. It is in Module 13; Module 5 has the stock figures it refers to.)

Weekdays follow a calendar in which Sep 15 is a Tuesday. The year is never shown to learners.

| When | What | Sources |
| --- | --- | --- |
| On or before Wed, Sep 2 | Early-September stock snapshot: EF-101 34 available / 6 reserved / 50 inbound; EF-103 0 / 2 / 25. Before #4021 ships, because the 9/2 row starts from EF-101's 34 | M5 desk (8:00 AM stock sheet) |
| Tue, Sep 1 – Wed, Sep 2 | Module 5 records (all Module 5-local except the shared rows): orders #4023–#4027, EF-101's movements (#4021 −2, Return #229 +2, #4024 shipped from reserved stock, one approved write-off), ClearPath's 7:00 AM cycle count. The 8:00 AM stock sheet keeps the snapshot's EF-101 and EF-103 rows and adds Module 5-local rows and alert levels | M5 desk |
| Wed, Sep 2, 9:15 AM – 4:30 PM | **Module 5 desk day** (EF-103's inbound shown as "due Sun", never as a later date) | M5 desk; `calendar.m5` |
| Wed, Sep 2 | Order #4021 (EF-101 x2) ships, EF-101 balance 34 → 32. Same day: #4022 (EF-200 x1) is Processing; Return #229 (EF-101 x2) is restocked | M5 m5-l7; M9 m9-l3 (desk reference); M11 m11-l4 |
| Before Sun, Sep 6 | Weekly report line: EF-103 0 available, 25 inbound expected 9/6, covering backorders | M13 m13-l5 |
| Sun, Sep 6 | EF-103 inbound (25) expected | M13 m13-l5 |
| Sat, Sep 5 – Mon, Sep 14 | Module 4 order, payment, fulfillment and carrier records | M4 desk |
| Tue, Sep 15, 11:40 AM | **Module 4 desk day** | M4 desk; `calendar.m4` |
| Thu, Sep 3 – Wed, Sep 16 | Module 7 order, return and carrier records (orders #5420–#5444, returns #230–#240, tracking CP-7731-05xx; all Module 7-local) | M7 desk |
| Thu, Sep 17, 10:15 AM | **Module 7 desk day** | M7 desk; `calendar.m7` |
| Mon, Sep 21 – Fri, Sep 25 | Module 9 week (all Module 9-local): order export (orders #5450–#5462, tracking CP-7731-06xx), ClearPath's weekly shipped report, Friday stock sheet (EF-101, EF-104, EF-105, EF-107, EF-200 only; never EF-102, EF-103 or EF-106), open-items log | M9 desk |
| Fri, Sep 25, 3:40 PM | **Module 9 desk day** (Everfield's weekly report day) | M9 desk; `calendar.m9` |
| After EF-103's Sep 6 stock sells through | **Capstone week**: EF-103 at 0 available, 0 inbound. Exact week not fixed | M14 m14-t4 |
| Undated | Illustrations: M5 kit example, M5 EF-104 reconciliation, M7 EF-105 at 0, M12 "42 orders", M13 "3 stockouts". (The old M9 EF-102/EF-106 snapshot was retired with the Module 9 conversion.) | — |

Rules for authors:

1. A converted module gets one desk day in `calendar`; nothing in its records is dated later than that day.
2. A numeric or weekday date in any lesson must be on this timeline or in a shared record. The checker enforces this.
3. Undated illustrations stay undated and are not canon. Do not quote their figures as Everfield's stock.
4. Order numbers are identifiers, not a sequence: Module 4's own numbers are not in date order (#5410 placed Sep 5, #5401 placed Sep 15). Do not work out dates from them.
5. Module 4's PO EG-1047 example is reference material describing an earlier update; its Sep 12 date is not a desk record.

## 4. Capstone #5310 and Module 4 #5414

**Evidence**

- #5310 (M14 m14-t3): "shows 'Shipped' status but has no tracking number recorded at all -- everything else in the batch looks normal". No SKU, no date. Its feedback names "the order-verification skill from Module 4".
- #5414 (M4 desk, m4-l6 and m4-l7): a desk case created by the Module 4 pilot; its situation type is the one t3 describes. (Its details stay in the desk data: this folder is publicly served.)
- The original Module 4 (commit 4fd2cbe) taught the same pattern in m4-l6 with no order number. #5310 was written against that lesson, before #5414 existed.
- Every capstone task restages the canonical scenario of an earlier lesson with a new instance: t3 ↔ M4 l6, t4 ↔ M5/M13 (stated as a contrast), t6 ↔ M7 l10 (damaged EF-101, third report this week), t9 ↔ M12 l3 (AI piece count for EF-106).

**Decision: C (insufficient evidence for A or B). Recommendation: no change now.**

- **Not A.** Nothing says #5310 is the same order as #5414: different number, no shared SKU or date, and #5310 predates #5414.
- **Not B on the evidence.** The two cases share a *pattern*, not a record. Restaging an earlier lesson's pattern is how the whole capstone is designed, not an accident in one task.
- **Assessment effect.** Since the pilot, a learner practises this exact pattern twice in Module 4 (triage, then the exception list), so capstone t3 now checks recognition more than transfer. That is a judgement about what the capstone should test, so it is yours to make. It is not a data defect.
- **If you want transfer:** decide when Module 14 is converted. Replace t3's situation with an order-verification problem the Module 4 desk does not practise, keeping the objective "Process simulated orders and identify exceptions" and the Order Log skill. Module 4's own triage rows are the list of patterns to avoid.

The same applies to t6 vs #5192 (M7): same pattern, not established as the same case.

## 5. Required corrections

| # | Current value | Proposed value | Reason | Affected | Learner-facing? | Status |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `team.daniel.role` "Everfield team"; `team.marcus.role` "Everfield team" | "Procurement & Supply Manager"; "3PL Account Manager", `org: "ClearPath Fulfillment"` | Contradicts the hub and m1-l6. Introduced by the engine refactor | `shared/everfield-data.js` | No. No desk brief comes from Daniel or Marcus; Module 4 snapshot unchanged (111/111) | **Done** |
| 2 | `channels` lists 2 | Adds "B2B / bulk" | Hub lists 3 | `shared/everfield-data.js` | No (no page reads `channels`) | **Done** |
| 3 | M6 m6-l4 observe and question, m6-l9 apply label: "EF-103's exact dimensions … 16in x 11in x 9in" | "EF-101's exact dimensions …" (same numbers) | Physical contradiction: the Module 4 desk packs EF-103 into a 12×9×3 in carton (m4-l4). 16×11×9 is EF-101's record (m3-l4). Swapping the SKU reuses an existing fact instead of inventing new dimensions. Correct answer and option text unchanged | Module 6, lessons 4 and 9 | Yes: three strings name a different SKU; answer unchanged; no stored work affected (apply text isn't saved) | **Done; please confirm** (revert = three-word change) |
| 4 | M7 m7-l4: "exchange EF-105 for a different color" | Exchange for a different SKU, or the same SKU as a replacement | Contradicts m2-l1 "no size/color variants" | Module 7, lesson 4 | Yes | **Deferred**: Module 7 is frozen. Make the fix in the Module 7 conversion. Checker warns until then |
| 5 | M14 t3 #5310 | — | §4 | Module 14 | — | **Your decision**, at Module 14 conversion |

Nothing else met the bar for change (contradiction, impossible timeline, duplicate that weakens assessment, clearly shared data, or unsafe for a future module).

## 6. Authority and policy canon (author-facing)

As stated in the course. Not in `everfield-data.js`, which desk pages load, because several lines bear on Module 4 desk questions. Note that `docs/` is served with the site (unlinked), as the architecture notes already are; keep answer specifics out of this file.

- **Sofia Ramirez**: closest contact. Customer-facing work, online sales, listings, promotions; support issues beyond a VA's documented authority (m1-l6, m6-l1, m14 brief).
- **Maya Collins**: Operations. Escalations; owns the ClearPath relationship; packaging and 3PL patterns (m4-l3, m4-l7, m7-l6, m14 brief).
- **The VA may**: process a standard, in-policy refund for a returned unopened item (m6-l6); set up a promotion Sofia has already decided on (m10-l6); carry out a specific, unambiguous listing edit (m11-l7, m11-l8); report and document facts.
- **The VA escalates or asks**: any policy exception, or a refund without a return (m6-l6, m11-l8, m12-l1, m14 brief); legal threats or unusually large refunds (m6-l9); whether to run a promotion (m10-l6); refunds or reships as a fix for fulfillment problems (m4-l3, m4-l7); patterns across cases (m7-l6).
- **Order of steps**: a refund is finalized only after disposition. "Inspection Required" waits (m7-l5). Return flow: log → reason → inspect → disposition → inventory action → refund status (m7-l3, m11-l1, m14-t8).
- **Out of scope for this Foundation**: supplier negotiation, purchase orders, warehouse logistics (m1-l6, M5 page note).
- **Cadence**: daily, order and inventory monitoring and urgent follow-ups; weekly (report on Friday), inventory, replenishment, open POs, shipments, 3PL performance, KPIs (m13-l2, m13-l8).
- **Undefined (add here before any module uses it)**: return window, refund amount thresholds, shipping service levels, carrier names, EF-103's own dimensions (it must fit a 12×9×3 in carton), EF-106 piece count.

### Returns and exceptions policy (approved 2026-10-04)

Approved with the Module 7 conversion map (decisions D1 and D3). Each clause is the exact wording a desk may quote on its policy card; `tools/everfield-check.js` fails if a module's card differs from this text. The return window is deliberately unspecified: every case a module shows must be a recent delivery, plainly inside any reasonable window.

| Id | Clause | Basis |
| --- | --- | --- |
| P1 | An order that has not been released to ClearPath can be cancelled by the VA. | m4-l2 order note |
| P2 | An order already at ClearPath but not yet shipped can only be stopped by ClearPath. Ask Maya to request an intercept, and promise the customer nothing until she confirms. | m4-l2, m4-l3; Maya owns ClearPath |
| P3 | Once the carrier has the package, a cancellation request becomes a return. | m7-l2 |
| P5 | A returned item that is unopened and marked Restock: the VA finalizes the standard refund. | m6-l6, m7-l5 |
| P6 | A return marked Inspection Required: the refund waits until the inspection is complete. | m7-l5 |
| P7 | Damaged on arrival, with photos: the VA documents the case and Sofia decides between a refund and a replacement. Damage that repeats across orders goes to Maya as a possible pattern. | m7-l5, m7-l6 |
| P8 | A refund without the item coming back is Sofia's decision. | m6-l6 |
| P9 | Exchanges: the returned item is processed like any return. If the replacement is not available to ship, offer to wait for restock (no date promised) or to return for a refund, and let the customer choose. | m6-l5, m7-l4 |
| P10 | A confirmed mis-ship: the correct item goes out at no cost and the wrong item comes back. The VA requests the replacement through Maya. | m6-l7, m7-l7 |
| P11 | Delivered but not received: share the carrier's delivery details with the customer and ask them to check. If it still has not turned up, Maya decides on a carrier claim or a reship. | m4-l7, m7-l8 |
| P12 | Returned to sender: confirm the full address with the customer, then request the reship through Maya. | m7-l9 |

(P4, the return window, is intentionally left out.)

### Product cost canon (approved 2026-10-05)

Approved with the Module 9 curriculum audit (decision D5, adjusted; design map decision C1-a). These unit costs are Everfield product canon, not Module 9 content: `productFacts` cites this table, and the continuity checker reads it. No other SKU has a stated cost; add one here before any module uses it.

| SKU | Unit cost | Basis |
| --- | --- | --- |
| EF-101 | $4.20 | First stated in the original Module 9 (m9-l2); moved here by D5 |
| EF-105 | $3.85 | First stated in the original Module 9 (m9-l2); moved here by D5 |

## 7. Shared records — boundary and proposal

**Shared now** (`shared/everfield-records.js`). Each record was already shown by two or more modules with identical facts:

- `orders["#4021"]`: Wed Sep 2, EF-101 x2, Shipped (M5 m5-l7; M9 m9-l3, desk reference)
- `stock.snapshots["stock-early-sep"]`: EF-101 34/6/50, EF-103 0/2/25 (M5; referred to by M13 and M14)
- `stock.movements["mv-sep2-4021"]`: EF-101 −2, balance 32 (M5 m5-l7; derived from #4021)
- `returns["Return #229"]`: Wed Sep 2, EF-101 x2, unopened, Restock, refund issued (M11 m11-l4; M5 m5-l7, which restocks it in EF-101's tracker; decision R1)
- `stock.inbound["inbound-ef103-sep6"]`: EF-103 25, expected Sun Sep 6 (M13 m13-l5; M5 inbound column)

**Module-local** (stay in their modules): Module 4's orders, tracking, customers and PO example; #4022; #5192; #5310; Module 5's day (except the shared rows, #4021 and Return #229); the Module 9 week; M12 and M13 report figures.

**Candidates, not migrated** (needs your call when the owning modules convert):

- The "damaged EF-101, third report this week" pattern (M7 l6, l10 #5192; M13 l6; M14 t6). If Module 7's conversion makes it one case, it becomes `cases[...]` and M13 and M14 refer to it.
- M5's kit math says "Recall", but nothing earlier teaches the recipe. Consider stating it in Module 2 or 3 when those convert. The recipe is in `productFacts` either way.

**Rules**

1. Records are frozen. Nothing a learner does in any module writes to them, and no module derives shared state from learner work. A Module 5 "adjustment" lives only in Module 5's desk storage. Module 13 still shows the authored figures.
2. Shared records hold facts only: no `correct`, `accept`, feedback, hints, options, or anything a desk validator checks against. The checker rejects those keys, and rejects any exercise text copied into a shared file.
3. A record moves into the shared file only when a second module needs the same record. Convenience is not a reason.
4. Legacy modules keep their inline text for now. The checker keeps that text equal to the shared record. A converted module renders from the shared record instead of restating it.
5. Modules don't load `everfield-records.js` yet. The first converted module that shows a shared record adds the script tag.

Also noted, not Everfield data: the hub says "13 portfolio deliverables" and also "a 14-piece beginner portfolio". This is outside this task's scope, and the hub was not modified.

## 8. Validation

`node tools/everfield-check.js` (also the first step of `tests/run_all.sh`). It checks:

| Check | Catches |
| --- | --- |
| Shared data is deep-frozen | Runtime mutation of shared facts or records |
| No learner-state fields | `answers`, `attempts`, `drafts`, `progress`… keys; any browser-storage access in shared files |
| No answer keys or exercise text | `correct`, `accept`, `hash`, `feedback`, `options`… keys; any option/finding/choice text copied from a lesson |
| Shared record IDs unique | One ID defined twice across record kinds |
| Records used by two modules are shared | An order/return/PO/tracking ID in two modules that isn't a shared record; a shared record used somewhere its `src` doesn't list |
| Shared records match module text | The module text no longer states the record's date, SKU, quantity, status, balance or stock figures; references to missing records or lessons |
| Product IDs and names | Unknown SKUs; a SKU given another product's name |
| Product facts | A `productFacts` value not stated in its source (a lesson, or the approved product canon in §6); dimensions that differ from the SKU's record; a kit recipe that differs |
| Variants | Any colour or size variant implied for a SKU |
| People and roles | Data file vs hub; a lesson giving someone another role; briefs from unknown people; new named managers not on the team |
| Dates | Weekday and date disagree; a numeric date not on the timeline; desk clock vs `calendar`; desk records dated after the desk day |
| Module 5 day stays in its ranges | A Module 5 order outside #4023–#4027 (except the shared #4021), or any return other than the shared Return #229 |
| Module 9 week stays in its ranges | A Module 9 order outside #5450–#5462 (except #4021/#4022), tracking outside CP-7731-06xx, or any EF-102, EF-103 or EF-106 in Module 9 |

Each check was confirmed to fail on an injected defect (17 mutations, all caught). Current result: all checks pass, plus one deferred warning (correction #4, Module 7).
