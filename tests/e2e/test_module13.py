"""Module 13 Work Desk regression + adversarial suite (browser), modelled on Module 5's.

Run from the repo root with a static server on :8765 (see tests/README.md):
    python3 tests/e2e/test_module13.py
Answers come from decoding the shipped content at run time (desk_helpers.decode). The
"recompute" checks derive every accepted answer from the evidence itself, and the
cross-module checks decode Modules 4, 5, 7 and 9 to prove Module 13 prints none of their
graded answers (design map W1-a), so nothing answer-bearing is stored here."""
import os, sys, re, json, subprocess
from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from desk_helpers import *  # noqa

SRC = decode("module-13")
M13 = BASE + "/module-13/index.html"
M9 = BASE + "/module-9/index.html"
TASKS = SRC["tasks"]
IDS = [t["id"] for t in TASKS]
ALL = [(ti, s) for ti, t in enumerate(TASKS) for s in t["stages"]]
KEY = "pva-ecom-ft-m13-desk"
results = []


def check(area, name, cond, detail=""):
    results.append((area, name, bool(cond), str(detail)))
    print(("PASS " if cond else "FAIL ") + "[" + area + "] " + name + ((" -- " + str(detail)[:200]) if detail and not cond else ""))


def field(st, fid): return next(f for f in st["fields"] if f["id"] == fid)
def label_of(f, v): return next(o["label"] for o in f["options"] if o["value"] == v)
def fields_of(rec): return dict((k, v) for k, v in rec.get("fields", []))
def strip(s): return re.sub(r"<[^>]+>", " ", s)


def m13_text(st, g, f, labels): return SUMMARY  # SUMMARY is built from the decoded evidence below


def solve(pg, st):
    open_all(pg)
    if st["type"] == "decision": answer_decision(pg, st)
    elif st["type"] == "triage": answer_triage(pg, st)
    else:
        fill_compose(pg, st, compose_values(st, m13_text)); confirm_all(pg); submit(pg)


def fail_once(pg, st):
    open_all(pg)
    if st["type"] == "decision":
        cf = correct_findings(st)
        answer_decision(pg, st, findings=cf[1:] + distractors(st)[:1], option=(wrong_options(st) or [None])[0])
    elif st["type"] == "triage": answer_triage(pg, st, wrong=True)
    else:
        vals = compose_values(st, m13_text)
        sel = next(x for x in st["fields"] if x["type"] == "select")
        vals[sel["id"]] = first_unaccepted(sel)
        fill_compose(pg, st, vals); confirm_all(pg); submit(pg)


def to_stage(pg, ti, sid):
    goto(pg, M13 + "#task-%d" % (ti + 1), 1)
    for s in TASKS[ti]["stages"]:
        if s["id"] == sid: return
        if not pg.is_enabled("#btnNext"):
            solve(pg, s)
        pg.click("#btnNext"); pg.wait_for_timeout(60)


def fresh(br, **kw):
    ctx = br.new_context(**kw); pg = ctx.new_page()
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    return ctx, pg, errs


def fb_text(pg):
    r = panel(pg).locator(".desk-fb")
    return r.last.inner_text() if r.count() else ""


def revise(pg):
    b = panel(pg).get_by_role("button", name="Revise your work")
    if b.count(): b.click(); pg.wait_for_timeout(40)


def records_of(st):
    if st["type"] == "decision": return st["records"]
    if st["type"] == "triage": return st["rows"]
    return [r for g in st["groups"] for r in g["records"]]


def rec_text(r):
    """Everything a learner can read on one record card."""
    parts = [r.get("title", ""), r.get("caption", ""), r.get("note", ""), r.get("logTitle", "")]
    parts += [str(v) for kv in r.get("fields", []) for v in kv] + list(r.get("log", []))
    parts += [str(c) for row in r.get("rows", []) for c in row] + list(r.get("columns", []))
    parts += [str(v) for kv in r.get("meta", []) for v in kv] + list(r.get("body", [])) + list(r.get("paragraphs", [])) + list(r.get("items", []))
    return " ".join(parts)


def table(st, title_start):
    return next(r for r in records_of(st) if r.get("kind") == "table" and r["title"].startswith(title_start))


def learner_text(task):
    """All learner-facing text of a task before any submission: brief, reference, stage
    intros, prompts, records, field labels and option labels (never feedback)."""
    out = [task["title"], task["objective"], task["brief"]["subject"]] + task["brief"]["body"] + [strip(x) for x in task.get("reference", [])]
    for s in task["stages"]:
        out += [s.get("intro", ""), s.get("prompt", ""), s.get("findingsPrompt", ""), s.get("actionPrompt", ""), s.get("now", "")]
        out += [rec_text(r) for r in records_of(s)]
        out += [c["label"] for c in s.get("choices", [])]
        out += [f["text"] for f in s.get("findings", [])] + [o["text"] for o in s.get("options", [])]
        for f in s.get("fields", []):
            out += [f["label"]] + [o["label"] for o in f.get("options", [])]
    return " ".join(out)


# Facts the example summaries need, read from the decoded evidence (never stored here).
WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
_R3 = stage_by_id(SRC, "l3-a")
_rec = [r for g in _R3["groups"] for r in g["records"]]
_contacts = next(r for r in _rec if r.get("kind") == "table" and r["title"].startswith("Customer contacts"))
_tracker = next(r for r in _rec if r.get("kind") == "table" and r["title"].startswith("Verified Operations Tracker"))
_PAT = re.compile(r"(EF-\d{3}) [A-Z][\w ]*: .*clips")
_pat = [_PAT.match(r[1]).group(1) for r in _contacts["rows"] if _PAT.match(r[1])]
SKU = max(set(_pat), key=_pat.count)                       # the SKU whose reports repeat
N = WORDS[_pat.count(SKU)]
OUTROW = next(r for r in _tracker["rows"] if int(r[1]) == 0)
LOWROW = next(r for r in _tracker["rows"] if 0 < int(r[1]) < int(r[4]))
OUT, LOW = OUTROW[0].split(" ")[0], LOWROW[0].split(" ")[0]
LATE = re.search(r"(\d+) shipped late", _tracker["note"]).group(1)
def fx(t): return t.format(SKU=SKU, N=N, Ncap=N.capitalize(), OUT=OUT, LOW=LOW, OUTROW=OUTROW[0], LATE=LATE)
SUMMARY = fx("{SKU} had {N} reports of missing clips this week; Daniel is checking with the supplier. The September invoice query is still open with ClearPath.")

with sync_playwright() as p:
    br = p.chromium.launch()
    A1, B1 = stage_by_id(SRC, "l1-a"), stage_by_id(SRC, "l1-b")
    A2, B2 = stage_by_id(SRC, "l2-a"), stage_by_id(SRC, "l2-b")
    R3 = stage_by_id(SRC, "l3-a")

    # ---------- structure: the approved design ----------
    check("design", "3 tasks with the approved ids (I1-a)", IDS == ["m13-l2", "m13-l5", "m13-l8"], IDS)
    check("design", "titles follow the design map", [t["title"] for t in TASKS] == ["What Gets Reported, and When?", "Lines Someone Can Use", "The Weekly Operations Report"])
    kinds = {t["id"]: [s["type"] for s in t["stages"]] for t in TASKS}
    check("design", "stage types match the map", kinds == {"m13-l2": ["triage", "decision"], "m13-l5": ["decision", "compose"], "m13-l8": ["compose"]}, kinds)
    check("design", "only Lesson 3 is a portfolio task, with the unchanged portfolio label",
          [(t["id"], t.get("portfolio")) for t in TASKS if t.get("portfolio")] == [("m13-l8", "Portfolio piece: Weekly E-commerce Operations Report")])
    check("design", "Maya asks for all three (A1); the report is for Sofia", [t["brief"]["from"] for t in TASKS] == ["maya", "maya", "maya"] and
          "Sofia" in R3["evidence"]["requestedBy"] and "Maya Collins" in R3["evidence"]["requestedBy"])
    check("design", "Lesson 1 runs midweek (Wed, Sep 30); the report lessons on the calendar day",
          [t.get("workDate") for t in TASKS] == ["Wed, Sep 30", None, None] and all(s["now"].startswith("Wed, Sep 30") for s in TASKS[0]["stages"]) and
          all(s["now"].startswith("Fri, Oct 2") for t in TASKS[1:] for s in t["stages"]))
    check("design", "Lesson 1A uses every call, with one same-day item", set(r["answer"] for r in A1["rows"]) == set(c["id"] for c in A1["choices"]) and
          [r["answer"] for r in A1["rows"]].count(A1["choices"][0]["id"]) == 1)
    nums = [(s["id"], f) for _, s in ALL if s["type"] == "compose" for f in s["fields"] if f["type"] == "number"]
    check("numbers", "one typed number in the module: Lesson 2's returns count", [(s, f["id"]) for s, f in nums] == [("l2-b", "ret.count")], [(s, f["id"]) for s, f in nums])
    check("numbers", "the typed count can't pass alone: the same group asks for its interpretation", any(f["group"] == "ret" and f["type"] == "select" for f in B2["fields"]))
    titles = [g["sampleHead"] for g in R3["groups"]]
    check("design", "the report has the map's six sections, in order", titles == ["Completed work", "Needs your attention", "Inventory", "Metrics, interpreted", "Next actions", "Summary for Sofia"], titles)
    check("design", "Lesson 3 declares a self-check and human review", len(R3["confirm"]) >= 2 and R3.get("humanReview"))

    # ---------- D6 clarification: the verified tracker is explicit and learner-facing ----------
    L3 = TASKS[2]
    brief = " ".join(L3["brief"]["body"])
    check("d6", "Lesson 3's work request names the verified Operations Tracker", "verified Operations Tracker" in brief, brief[:200])
    check("d6", "the request says it has already been checked and is to be used, not re-verified",
          re.search(r"already been checked", brief) and re.search(r"use it as it is", brief) and re.search(r"re-verify", brief), brief)
    check("d6", "the stage intro repeats it (not only in a reference drawer)", "verified Operations Tracker" in R3["intro"] and re.search(r"already been checked", R3["intro"]) and "audit" in R3["intro"], R3["intro"])
    trk = table(R3, "Verified Operations Tracker")
    check("d6", "the tracker card itself is titled verified and says to use its figures as they are", "Already checked" in trk.get("caption", "") and "signed off" in trk["note"])
    check("d6", "a reference card in the first section explains the division of labour with Module 9",
          any(r.get("kind") == "reference" and "verified Operations Tracker" in rec_text(r) and "Module 9" in rec_text(r) for r in R3["groups"][0]["records"]))
    check("d6", "nothing in Module 13 asks the learner to recount or verify a tracker figure",
          not any(f["type"] == "number" for f in R3["fields"]) and not re.search(r"\b(recount|re-verify|reconcile|check the totals)\b", " ".join(f["label"] for f in R3["fields"]), re.I))

    # ---------- C2 and continuity ----------
    every = learner_text(TASKS[0]) + learner_text(TASKS[1]) + learner_text(TASKS[2])
    l2ref = " ".join(strip(x) for x in TASKS[1]["reference"])
    check("canon", "C2: the EF-103 earlier-week line survives in Lesson 2's reference",
          "EF-103: 0 available, 25 inbound expected 9/6" in l2ref and "earlier week" in l2ref)
    no_ref = every.replace(l2ref, "")
    check("canon", "C2: EF-103 appears nowhere else in Module 13", "EF-103" not in no_ref and "EF-103" not in json.dumps([t["stages"] for t in TASKS]))
    check("canon", "the legacy example lines that are the answers' pattern are not in any reference (map: shortcut table)",
          not re.search(r"Updated and QA'd 6 product listings|3 stockouts this week, up from 0", " ".join(" ".join(t.get("reference", [])) for t in TASKS)))
    orders = set(int(x) for x in re.findall(r"#(\d{4})\b", every))
    check("canon", "orders stay in #5465-#5482", orders and all(5465 <= n <= 5482 for n in orders), sorted(orders))
    rets = set(int(x) for x in re.findall(r"(?:Return )?#(\d{3})\b", every))
    check("canon", "returns stay at #241 onward", rets and all(n >= 241 for n in rets), sorted(rets))
    trk_ids = set(re.findall(r"CP-\d{4}-\d{4}", every))
    check("canon", "tracking stays in CP-7731-07xx", trk_ids and all(re.match(r"CP-7731-07\d\d$", t) for t in trk_ids), trk_ids)
    out = subprocess.run(["node", os.path.join(ROOT, "tools", "everfield-check.js")], capture_output=True, text=True)
    check("continuity", "the continuity checker passes, with the Module 13 range check and month-aware dates",
          out.returncode == 0 and "ok   Module 13 week stays in its ranges" in out.stdout and "ok   dates agree with the Everfield calendar" in out.stdout, out.stdout[-400:])
    data = open(os.path.join(ROOT, "shared", "everfield-data.js"), encoding="utf-8").read()
    check("continuity", "calendar.m13 is Fri, Oct 2 and the timeline period spans September – October",
          'm13: { date: "Fri, Oct 2" }' in data and 'period: "September – October"' in data)

    # ---------- recompute: every accepted answer derived from the evidence ----------
    rows = {r["id"]: r for r in A1["rows"]}
    def l1call(r):
        fd = fields_of(r); txt = rec_text(r)
        if "Customer notifications" in fd and fd["Customer notifications"].startswith("None") and "still on our dock" in txt: return "today"
        if r.get("log"):
            kind = re.search(r"(EF-\d{3})", fd.get("Order", "")).group(1)
            same = [l for l in r["log"] if kind in l and "missing" in l]
            return "attention" if len(same) >= 2 else "omit"
        if "Requested" in fd and "Done" in fd: return "work"
        if fd.get("Refund", "").startswith("Issued") or "delivered" in fd.get("Tracking", ""): return "omit"
        return "?"
    names = {"today": "Tell Maya today", "attention": "Friday's report: needs attention", "work": "Friday's report: completed work", "omit": "Leave it out"}
    lab = {c["id"]: c["label"] for c in A1["choices"]}
    derived = {k: names[l1call(r)] for k, r in rows.items()}
    check("recompute", "Lesson 1A: every call follows from its own card (and the EF-104 card's contacts log)",
          all(lab[r["answer"]] == derived[k] for k, r in rows.items()), (derived, {k: lab[r["answer"]] for k, r in rows.items()}))
    ef104 = next(r for r in A1["rows"] if r.get("log"))
    check("recompute", "Lesson 1A: the EF-104 card looks routine on its own (handled) and only its log shows the pattern",
          "Replacement clips sent" in fields_of(ef104)["Handled"] and len([l for l in ef104["log"] if SKU in l]) == WORDS.index(N))
    check("recompute", "Lesson 1: nothing on a Wednesday card is dated after Wednesday", not re.search(r"Oct \d|Thu(rsday)? Oct", learner_text(TASKS[0]).replace(" ".join(strip(x) for x in TASKS[0]["reference"]), "")))
    pk = table(B1, "Orders packed")
    check("recompute", "Lesson 1B: the order list matches the notice's range, and no customer has been told",
          len(pk["rows"]) == 11 and pk["rows"][0][0] == "#5470" and pk["rows"][-1][0] == "#5480" and all(r[-1] == "No" for r in pk["rows"]) and
          "#5470–#5480" in option_text(B1, correct_option(B1)))
    retlog = table(B2, "Returns log")
    received = [r for r in retlog["rows"] if re.match(r"(Mon|Tue|Wed|Thu|Fri) ", r[1])]
    check("recompute", "Lesson 2: the typed count = returns actually received this week (a label-only return isn't one)",
          field(B2, "ret.count")["accept"] == [str(len(received))] and len(received) < len(retlog["rows"]), (field(B2, "ret.count")["accept"], len(received)))
    wow = table(B2, "Week-on-week")
    last = int(next(r for r in wow["rows"] if r[0] == "Returns received")[1])
    routine = all(r[4] == "Restock" and r[5] == "Issued" for r in received)
    want = "Up on last week, but all routine" if len(received) > last and routine else "?"
    check("recompute", "Lesson 2: the accepted interpretation follows from the count, last week and each return's disposition",
          label_of(field(B2, "ret.means"), field(B2, "ret.means")["accept"][0]).startswith(want))
    contacts = table(B2, "Customer contacts")
    clip_rows = [r for r in contacts["rows"] if SKU in r[1] and "clips" in r[1]]
    exc = table(B2, "Exceptions log")
    clip_exc = next(r for r in exc["rows"] if SKU in r[1])
    check("recompute", "Lesson 2: EF-104's accepted state matches the contacts log (the repeated reports) and the exceptions log (open)",
          WORDS[len(clip_rows)] == N and clip_exc[3].startswith("Open") and label_of(field(B2, "e104.state"), field(B2, "e104.state")["accept"][0]).startswith(N.capitalize() + " customers"))
    check("recompute", "Lesson 2: EF-104's attention names the owner in the exceptions log", clip_exc[2] in label_of(field(B2, "e104.need"), field(B2, "e104.need")["accept"][0]))
    work = table(B2, "VA work log")
    lst = field(B2, "lst.items")
    listing = [lst["options"][i]["value"] for i, r in enumerate(work["rows"]) if "listing" in r[1]]
    check("recompute", "Lesson 2: the listing line covers exactly the log's listing entries", sorted(lst["accept"][0]) == sorted(listing), (lst["accept"], listing))
    wk3 = table(R3, "VA work log"); done = field(R3, "done.items")
    asked = [done["options"][i]["value"] for i, r in enumerate(wk3["rows"]) if r[2] != "—"]
    check("recompute", "Lesson 3: completed work = entries someone asked for or will notice (each has a reference); routine stays out", sorted(done["accept"][0]) == sorted(asked), (done["accept"], asked))
    exc3 = table(R3, "Exceptions log"); attn = field(R3, "attn.items")
    open_rows = [r for r in exc3["rows"] if r[3].startswith("Open")]
    def is_open(lbl):  # an option is open if its SKU, or a distinctive word of it, is in an open exception
        keys = re.findall(r"EF-\d{3}", lbl) or [w for w in re.findall(r"[\w']+", lbl) if len(w) > 6]
        return any(k in r[1] for k in keys for r in open_rows)
    check("recompute", "Lesson 3: needs-attention = the exceptions still open", sorted(attn["accept"][0]) == sorted(o["value"] for o in attn["options"] if is_open(o["label"])) and len(open_rows) == 2,
          [o["value"] for o in attn["options"] if is_open(o["label"])])
    stk = field(R3, "stock.flags")
    flag = [o["value"] for o, r in zip(stk["options"], trk["rows"]) if int(r[1]) < int(r[4])]
    check("recompute", "Lesson 3: flagged stock = the verified tracker's rows below their alert level (including zero)", sorted(stk["accept"][0]) == sorted(flag), (stk["accept"], flag))
    late_this = int(next(r for r in table(R3, "Week-on-week")["rows"] if r[0] == "Orders shipped late")[2])
    pickup = next(r for r in exc3["rows"] if "pickup" in r[1])
    check("recompute", "Lesson 3: every late order this week is the one missed pickup, now closed",
          ("%d orders" % late_this) in pickup[1] and pickup[3].startswith("Closed") and "one missed pickup" in label_of(field(R3, "met.late"), field(R3, "met.late")["accept"][0]))
    wow3 = table(R3, "Week-on-week")["rows"]; cl = next(r for r in wow3 if r[0] == "Customer contacts")
    c3 = table(R3, "Customer contacts")
    check("recompute", "Lesson 3: contacts are level with last week, and the log behind the total holds the EF-104 pattern",
          cl[1] == cl[2] == str(len(c3["rows"])) and len([r for r in c3["rows"] if SKU in r[1] and "clips" in r[1]]) == WORDS.index(N) and
          "hides a pattern" in label_of(field(R3, "met.contacts"), field(R3, "met.contacts")["accept"][0]))
    nxt = field(R3, "next.pairs"); acc_labels = [label_of(nxt, v) for v in nxt["accept"][0]]
    owners = {"EF-104": clip_exc[2], "invoice": next(r for r in exc3["rows"] if "invoice" in r[1])[2]}
    low102 = LOWROW
    check("recompute", "Lesson 3: next actions = open items with their logged owners, plus the low SKU's reorder decision with procurement",
          len(acc_labels) == len(open_rows) + 1 and any(SKU in l and owners["EF-104"] in l for l in acc_labels) and any("invoice" in l and owners["invoice"] in l for l in acc_labels) and
          any(LOW in l and "Daniel Brooks" in l for l in acc_labels) and int(low102[1]) < int(low102[4]) and not any(l.endswith("— VA") for l in acc_labels), acc_labels)

    # ---------- normal flow, work dates, completion, work sample ----------
    ctx, pg, errs = fresh(br); goto(pg, M13)
    check("page", "Task 1 shows its own work date (Wed, Sep 30) and the task count", pg.text_content("#deskDate") == "Wed, Sep 30" and pg.inner_text("#lessonKicker") == "Task 1 of 3")
    for ti, t in enumerate(TASKS):
        goto(pg, M13 + "#task-%d" % (ti + 1), 1); ok = True
        check("page", "task %d shows work date %s" % (ti + 1, t.get("workDate") or "Fri, Oct 2"), pg.text_content("#deskDate") == (t.get("workDate") or "Fri, Oct 2"))
        for st in t["stages"]:
            solve(pg, st)
            if not pg.is_enabled("#btnNext"): ok = False; break
            pg.click("#btnNext"); pg.wait_for_timeout(60)
        check("flow", "task %d completes through the UI" % (ti + 1), ok)
    check("flow", "completion banner", "Module 13 complete" in pg.inner_text("#doneBanner"), pg.inner_text("#doneBanner"))
    pg.locator(".lesson-pill").nth(0).click(); pg.wait_for_timeout(80)
    d1 = pg.text_content("#deskDate")
    pg.locator(".lesson-pill").nth(2).click(); pg.wait_for_timeout(80)
    check("page", "switching lessons with the pills switches the work date both ways", d1 == "Wed, Sep 30" and pg.text_content("#deskDate") == "Fri, Oct 2")
    prog = pg.evaluate("JSON.parse(localStorage.getItem('pva-ecom-ft-progress'))")
    check("progress", "verified work marks all three lessons in the legacy progress store", all(prog["lessons"].get(i) for i in IDS))
    keys = pg.evaluate("Object.keys(localStorage).sort()")
    check("isolation", "only the Module 13 desk key and the legacy progress key are written", keys == [KEY, "pva-ecom-ft-progress"], keys)
    vw = pg.evaluate("PVADesk.verifiedWork()")
    check("verified-work", "verifiedWork() reports all three tasks verified and the one earned sample",
          all(v["verified"] for v in vw.values()) and vw["m13-l8"]["samplesEarned"] == ["l3-a"] and not any(v["samplesEarned"] for k, v in vw.items() if k != "m13-l8"), vw)
    goto(pg, BASE + "/index.html")
    card = pg.locator(".module-card").nth(12).inner_text()
    check("progress", "course map shows Module 13 Completed (3 lessons)", "Client Communication" in card and "Completed" in card, card)
    goto(pg, M13 + "#task-3", 1)
    ev = pg.locator(".ws-preview").inner_text() if pg.locator(".ws-preview").count() else ""
    check("work-sample", "the Weekly Operations Report survives reload with an honest training header",
          ev.startswith("TRAINING WORK SAMPLE\nEverfield Goods — Weekly Operations Report (Mon Sep 28 – Fri Oct 2)") and "fictional company" in ev and
          "Work date: Fri, Oct 2 (simulated)" in ev and "Maya Collins" in ev and "For: Sofia Ramirez" in ev and "human review" in ev, ev[:400])
    check("work-sample", "the sample carries every section and the learner's own summary",
          all(h in ev for h in titles) and SUMMARY in ev and LOWROW[0] in ev, ev[:900])
    check("flow", "no JS errors", not errs, errs)
    ctx.close()

    # ---------- evidence gate (every stage) ----------
    ctx, pg, _ = fresh(br)
    for ti, st in ALL:
        to_stage(pg, ti, st["id"]); r = panel(pg)
        if st["type"] == "triage":
            gated = all(x.is_disabled() for x in r.locator("select.desk-select").all())
        elif st["type"] == "compose":
            gated = r.locator("section.desk-group select, section.desk-group input, section.desk-group textarea").first.is_disabled() and all(c.is_disabled() for c in r.locator(".desk-selfcheck input").all())
        else:
            gated = r.locator(".desk-actions button").first.is_disabled()
        pg.evaluate("document.querySelectorAll('#stagePanel button,#stagePanel select,#stagePanel input').forEach(e=>e.disabled=false); var b=document.querySelector('#stagePanel .desk-actions button'); b && b.click();")
        pg.wait_for_timeout(40)
        att = pg.evaluate("((JSON.parse(localStorage.getItem('%s'))||{tasks:{}}).tasks['%s']||{stages:{}}).stages['%s']" % (KEY, TASKS[ti]["id"], st["id"]))
        check("evidence-gate", "%s: controls gated and a forced submit is refused before evidence is opened" % st["id"], gated and not att, att)
    ctx.close()

    # ---------- wrong answer, feedback safety, retry, pause, re-open (every stage) ----------
    ctx, pg, _ = fresh(br)
    for ti, st in ALL:
        to_stage(pg, ti, st["id"]); r = panel(pg)
        fail_once(pg, st)
        fb = fb_text(pg)
        check("feedback", "%s: wrong attempt gets explanatory feedback, next stays locked" % st["id"],
              len(fb) > 60 and not pg.is_enabled("#btnNext") and r.locator(".desk-pause").count() == 0, fb[:120])
        if st["type"] == "decision":
            leaks = [finding_text(st, f) for f in correct_findings(st) if finding_text(st, f) in fb]
            if option_text(st, correct_option(st)) in fb: leaks.append("correct option")
            check("feedback-safety", "%s: feedback reveals no correct finding or option" % st["id"], not leaks, leaks)
        if st["type"] == "triage":
            labels = [c["label"] for c in st["choices"]]
            check("feedback-safety", "%s: per-row pointers never name a category" % st["id"], not [l for l in labels if l in fb.split("WHY")[0]], fb[:200])
        if st["type"] == "compose":
            acc = [label_of(f, f["accept"][0]) for f in st["fields"] if f["type"] == "select"]
            check("feedback-safety", "%s: feedback never quotes an accepted choice" % st["id"], not [a for a in acc if a in fb], fb[:200])
        retry = r.get_by_role("button", name="Reconsider and try again")
        if retry.count(): retry.click(); pg.wait_for_timeout(30)
        fail_once(pg, st)
        paused = r.locator(".desk-pause").count() == 1 and r.locator(".desk-evidence-card.is-recheck").count() >= 1
        blocked = (r.get_by_role("button", name="Reconsider and try again").is_disabled() if st["type"] == "decision"
                   else (r.locator(".desk-actions button").first.is_disabled() if st["type"] == "compose" else
                         any(x.is_disabled() for x in r.locator("select.desk-select").all())))
        check("retry", "%s: second miss pauses and blocks the next attempt until evidence is re-opened" % st["id"], paused and blocked)
        open_all(pg); pg.wait_for_timeout(30)
        retry = r.get_by_role("button", name="Reconsider and try again")
        if retry.count():
            check("retry", "%s: re-opening evidence re-enables retry" % st["id"], retry.is_enabled())
            retry.click(); pg.wait_for_timeout(30)
        solve(pg, st)
        check("retry", "%s: corrected attempt passes with no attempt limit" % st["id"], pg.is_enabled("#btnNext"))
    ctx.close()

    # ---------- numeric integrity (Lesson 2's count) ----------
    NO_DIRECTION = re.compile(r"(higher|lower|too (many|few|high|low|big|small)|more than|less than|fewer|bigger|smaller|close|nearly|almost|off by)", re.I)
    ctx, pg, _ = fresh(br)
    to_stage(pg, 1, "l2-b"); open_all(pg); st = B2
    def attempt(stg, **over):
        v = compose_values(stg, m13_text); v.update(over)
        fill_compose(pg, stg, v); confirm_all(pg); submit(pg)
        okk = pg.is_enabled("#btnNext"); fbx = fb_text(pg)
        if okk: revise(pg)
        else: open_all(pg)
        return okk, fbx
    cnt = field(st, "ret.count")["accept"][0]
    for fmt in [" " + cnt + " ", cnt + ".0"]:
        check("numbers", "equivalent entry %r of the right count passes" % fmt, attempt(st, **{"ret.count": fmt})[0])
    units = sum(int(re.search(r"× (\d+)", r[2]).group(1)) for r in received)
    for slip, val in [("the label-only return counted", len(retlog["rows"])), ("units counted instead of returns", units), ("both weeks added", len(received) + last)]:
        okk, fbx = attempt(st, **{"ret.count": str(val)})
        check("numbers", "l2-b: %s fails" % slip, not okk and "Returns received" in fbx, fbx[:160])
        check("numbers", "l2-b: the miss never states the count or a direction (%s)" % slip, not re.search(r"(?<![\d#])%s(?!\d)" % cnt, re.sub(r"Attempt \d+|tried this \d+ times?", "", fbx)) and not NO_DIRECTION.search(fbx), fbx[:200])
    for bad in ["five", cnt + " returns", "", "-" + cnt]:
        check("numbers", "malformed or negative entry %r is refused" % bad, not attempt(st, **{"ret.count": bad})[0])
    check("numbers", "l2-b: the right count with the wrong interpretation fails", not attempt(st, **{"ret.means": "quality"})[0])
    check("numbers", "l2-b: the right count read as 'up = alarming' fails", not attempt(st, **{"ret.means": first_unaccepted(field(st, "ret.means"))})[0])
    check("leakage", "no typed answer sits in the DOM as an input value before a correct submission", not re.search(r'value="%s"' % cnt, pg.content()))
    ctx.close()

    # ---------- decisions and triage: transfer, and principle-only feedback ----------
    ctx, pg, _ = fresh(br)
    for ti, st in ALL:
        if st["type"] != "decision": continue
        to_stage(pg, ti, st["id"]); open_all(pg)
        answer_decision(pg, st, findings=correct_findings(st)[:-1])
        check("transfer", "%s: right action without the full reading of the evidence fails" % st["id"], not pg.is_enabled("#btnNext"))
    to_stage(pg, 1, "l2-a"); open_all(pg)
    answer_decision(pg, A2, findings=correct_findings(A2) + ["short"])
    check("transfer", "l2-a: calling a short but complete line vague fails (length is not the test)", not pg.is_enabled("#btnNext"))
    ctx.close()
    ctx, pg, _ = fresh(br)
    to_stage(pg, 0, "l1-a"); open_all(pg)
    for i, r in enumerate(A1["rows"]):
        v = "skip" if r.get("log") else r["answer"]
        panel(pg).locator("select.desk-select").nth(i).select_option(v)
    panel(pg).locator("button[type=submit]").first.click(); pg.wait_for_timeout(60)
    check("transfer", "l1-a: reading the EF-104 email at face value (leave it out) fails", not pg.is_enabled("#btnNext"))
    ctx.close()
    ctx, pg, _ = fresh(br)
    VERDICT = re.compile(r"(invalid|(action|choice|decision|answer|option) (is|was) (wrong|incorrect)|not the right|isn't the right|good answer|may be reasonable|correct option|wrong option|you selected)", re.I)
    for ti, st in ALL:
        if st["type"] != "decision": continue
        to_stage(pg, ti, st["id"]); open_all(pg)
        texts = []
        for oid in wrong_options(st):
            answer_decision(pg, st, option=oid)
            texts.append(fb_text(pg))
            open_all(pg); panel(pg).get_by_role("button", name="Reconsider and try again").click(); pg.wait_for_timeout(20)
        answer_decision(pg, st, findings=correct_findings(st)[:-1] + distractors(st)[:1])
        texts.append(fb_text(pg))
        bad = [VERDICT.search(t).group(0) for t in texts if VERDICT.search(t)]
        named = [finding_text(st, f) for f in distractors(st) if any(finding_text(st, f).rstrip(".") in t.split("What you missed", 1)[-1] for t in texts)]
        check("feedback-principle", "%s: miss feedback states principles only; no choice is declared invalid or named" % st["id"], not bad and not named, (bad, named))
    ctx.close()

    # ---------- opening a later lesson first gives no shortcut to an earlier one ----------
    l1_labels = [c["label"] for c in A1["choices"]]
    CALLS = re.compile(r"same day|same-day|told Maya|sent to Maya|escalat|tell Maya today|Friday's report|leave it out|left out of the report", re.I)
    l2_ev = " ".join(rec_text(r) for s in TASKS[1]["stages"] for r in records_of(s))
    l3_ev = " ".join(rec_text(r) for r in records_of(R3))
    check("later-first", "Lessons 2 and 3's records never state a Lesson 1 call", not CALLS.search(l2_ev) and not CALLS.search(l3_ev), (CALLS.findall(l2_ev), CALLS.findall(l3_ev)))
    l2_acc = [label_of(f, f["accept"][0]) for f in B2["fields"] if f["type"] == "select"]
    l3_all = learner_text(TASKS[2])
    check("later-first", "Lesson 3 never prints Lesson 2's accepted line wording", not [a for a in l2_acc if a in l3_all], [a for a in l2_acc if a in l3_all])
    check("later-first", "Lesson 3 never prints this week's returns count (Lesson 2's typed answer)",
          "Returns received" not in l3_all and not re.search(r"\b%s (returns|received)" % cnt, l3_all))
    l1_acc_opt = option_text(B1, correct_option(B1))
    check("later-first", "Lessons 2 and 3 never print Lesson 1B's action (asking whether Sofia wants customers contacted)",
          not re.search(r"customers? (contacted|told|notified|emailed)|delay notice", l2_ev + " " + l3_ev, re.I) and l1_acc_opt not in l2_ev + l3_ev)
    ctx, pg, errs = fresh(br)
    goto(pg, M13); pg.locator(".lesson-pill").nth(2).click(); pg.wait_for_timeout(100)
    pg.click("#btnNext"); pg.wait_for_timeout(60); open_all(pg)
    dom = pg.inner_text("#stagePanel")
    check("later-first", "a fresh learner opening Lesson 3 first sees no Lesson 1 call and no Lesson 2 accepted line",
          not [l for l in l1_labels if l in dom] and not [a for a in l2_acc if a in dom] and not CALLS.search(dom), CALLS.findall(dom)[:4])
    solve(pg, R3)
    check("later-first", "Lesson 3 stays usable when opened first", pg.is_enabled("#btnNext"))
    goto(pg, M13); pg.locator(".lesson-pill").nth(1).click(); pg.wait_for_timeout(100)
    pg.click("#btnNext"); pg.wait_for_timeout(60); open_all(pg)
    dom2 = pg.inner_text("#stagePanel")
    check("later-first", "a fresh learner opening Lesson 2 first sees no Lesson 1 call", not CALLS.search(dom2) and not [l for l in l1_labels if l in dom2])
    check("later-first", "no JS errors", not errs, errs)
    ctx.close()

    # ---------- cross-module (W1-a): Module 13 prints no other module's graded answers ----------
    m13_all = every + " " + " ".join(rec_text(r) for _, s in ALL for r in records_of(s))
    leaks = []
    for mod in ("module-4", "module-5", "module-7", "module-9"):
        other = decode(mod)
        for t in other["tasks"]:
            for s in t["stages"]:
                if s["type"] == "decision":
                    for o in s.get("options", []):
                        if o.get("correct") and o["text"][:60] in m13_all: leaks.append((mod, s["id"], "option"))
                    for f in s.get("findings", []):
                        if f.get("correct") and len(f["text"]) > 24 and f["text"] in m13_all: leaks.append((mod, s["id"], f["id"]))
                for f in s.get("fields", []):
                    if f["type"] == "number":
                        for a in f.get("accept", []):
                            # a figure, not a calendar day ("Sep 28") or an ID
                            if float(a) >= 10 and re.search(r"(?<![\d.#$/:-])(?<!Sep )(?<!Oct )%s(?![\d./:])" % re.escape(a), m13_all): leaks.append((mod, s["id"], f["id"], a))
                    if f["type"] in ("select", "multi"):
                        accs = f.get("accept", [])
                        vals = [v for a in accs for v in (a if isinstance(a, list) else [a])]
                        for v in vals:
                            lbl = next((o["label"] for o in f["options"] if o["value"] == v), "")
                            catalog = re.match(r"^EF-\d{3} [A-Z][\w ]+$", lbl)  # a plain product name is not an answer
                            if len(lbl) > 24 and not catalog and lbl in m13_all: leaks.append((mod, s["id"], f["id"], lbl[:40]))
                if s["type"] == "triage":
                    pass  # triage answers are categories, shown only as choices in their own module
    check("cross-module", "no correct option, finding, accepted label or typed figure (>= 10) from Modules 4, 5, 7 or 9 appears in Module 13", not leaks, leaks[:6])
    m9 = decode("module-9"); m9txt = json.dumps(m9)
    check("cross-module", "Module 13 reports a different week from Module 9 (no Sep 21-25 record, no #5450-#5462 order)",
          not re.search(r"#54(5\d|6[0-2])\b", m13_all) and not re.search(r"(Mon|Tue|Wed|Thu|Fri) Sep 2[1-5],", m13_all))
    check("cross-module", "the EF-104 pattern is new: no damaged EF-106 (Module 7) or damaged EF-101 (capstone) case", not re.search(r"damag", m13_all, re.I))

    # ---------- shortcut attempts, derived completion, the summary ----------
    ctx, pg, _ = fresh(br); goto(pg, M13)
    pg.evaluate("""localStorage.setItem('%s', JSON.stringify({v:1,tasks:{'m13-l8':{completed:true,verified:true,views:1,
      stages:{'l3-a':{passed:true,answer:{values:{},confirms:[true,true,true]}}},drafts:{'l3-a:v':{'sum.text':'x'}}}}}))""" % KEY)
    goto(pg, M13 + "#task-3")
    st3 = pg.evaluate("PVADesk.taskStatus(PVADesk.decode(window.PVA_DESK_MODULES.m13.payload).tasks[2])")
    check("integrity", "forged completed/verified/passed flags count for nothing", st3["passed"] == 0, st3)
    check("integrity", "forged state never reaches the legacy progress store", not (pg.evaluate("JSON.parse(localStorage.getItem('pva-ecom-ft-progress')||'{}')").get("lessons") or {}).get("m13-l8"))
    goto(pg, M13 + "#task-3", 1)
    check("work-sample", "no work sample exists before the work verifies", panel(pg).locator(".ws-preview").count() == 0)
    open_all(pg); st = R3
    fill_compose(pg, st, compose_values(st, m13_text)); confirm_all(pg)
    panel(pg).get_by_label(field(st, "sum.text")["label"], exact=True).fill(SUMMARY + " ")
    check("self-check", "changing work after confirming clears the confirmations", not any(x.is_checked() for x in panel(pg).locator(".desk-selfcheck input").all()))
    def summ(text):
        v = compose_values(st, m13_text); v["sum.text"] = text
        fill_compose(pg, st, v); confirm_all(pg); submit(pg)
        okk = pg.is_enabled("#btnNext"); fbx = fb_text(pg)
        if okk: revise(pg)
        else: open_all(pg)
        return okk, fbx
    GOOD = [
        ("terse", fx("{SKU}: {N} missing-clip reports, supplier check open. {LOW} is below its alert level and needs a reorder decision.")),
        ("different wording", fx("{Ncap} customers found clips missing from {SKU} sets. Maya is querying an unexpected storage charge on ClearPath's invoice.")),
        ("stock instead of the invoice", fx("{SKU} clips went missing on {N} orders this week. {OUT} is out of stock until next week's delivery.")),
        ("fuller", fx("The main thing this week is {SKU}: {N} separate customers reported missing clips, and Daniel Brooks is looking into it with the supplier. Wednesday's missed pickup is closed; the orders went out a day late. Maya is querying a storage charge on the September invoice.")),
        ("negations", fx("The {SKU} clip problem isn't resolved yet; the supplier check is still open. The missed pickup is no longer open, and the invoice query is pending with ClearPath.")),
        ("'nothing to decide' is not an all-clear", fx("Nothing for you to decide yet on {SKU}, but {N} customers reported missing clips and Daniel is checking. The storage charge on the invoice is still being queried.")),
    ]
    for why, t in GOOD:
        okk, fbx = summ(t)
        check("l3-summary", "passes -- %s" % why, okk, (t, fbx[:200]))
    BAD = [
        ("is filler", fx("It was a busy week and the team did a good job overall. Let me know if you have any questions.")),
        ("is an all-clear", fx("No issues this week apart from routine work. Everything has been resolved with ClearPath.")),
        ("only repeats labels", ". ".join(o["label"] for o in field(R3, "attn.items")["options"][2:4]) + ". " + OUTROW[0] + "."),
        ("names items without states", fx("This week's report covers {SKU} and the September invoice. Both are in the sections below.")),
        ("calls {SKU} settled", fx("{SKU}'s missing clips are resolved now that replacements went out. The invoice query is still open.")),
        ("calls {SKU} a one-off", fx("One isolated {SKU} clip report this week, already handled. The invoice query is open with ClearPath.")),
        ("guesses a cause", fx("{SKU} had {N} missing-clip reports, probably a packing error at the supplier. The invoice query is open.")),
        ("states an unknown cause as fact", fx("The supplier has been shipping {SKU} sets without clips, {N} reports so far. The invoice query is still open.")),
        ("calls the missed pickup open", fx("{SKU} had {N} missing-clip reports and Daniel is checking. The missed pickup is still open and needs chasing with ClearPath.")),
        ("turns one miss into a trend", fx("{SKU} had {N} missing-clip reports. ClearPath's shipping is getting worse, with {LATE} late orders this week.")),
        ("contradicts the verified tracker", fx("{SKU} had {N} missing-clip reports. {OUT} is in stock and selling well.")),
        ("leaves out {SKU}", fx("The September invoice query is open with ClearPath, and {OUT} is out of stock until next week.")),
        ("has nothing else for Sofia", fx("{SKU} had {N} reports of missing clips this week. Daniel is checking with the supplier now.")),
    ]
    for why, t in BAD:
        check("l3-summary", "rejected -- a summary that %s" % why, not summ(t)[0], t)
    okk, fbx = summ(fx("{SKU} had {N} missing-clip reports, probably a packing error at the supplier. The invoice query is open."))
    check("l3-summary", "summary feedback names the principle, never an accepted section choice", not okk and "cause" in fbx and
          not [label_of(f, v) for f in st["fields"] if f["type"] == "multi" for v in f["accept"][0] if label_of(f, v) in fbx], fbx[:200])
    ctx.close()

    # ---------- answer encoding / leakage ----------
    ctx, pg, _ = fresh(br)
    shipped = "".join(pg.request.get(BASE + uu).text() for uu in ["/module-13/index.html", "/module-13/desk-data.js", "/shared/workdesk.js", "/shared/workdesk-ui.js", "/shared/workdesk-page.js", "/shared/everfield-data.js"])
    markers = ['"correct"', "correct: true", '"accept"', '"answer":', '"correctOrder"']
    check("leakage", "no plaintext answer markers in any shipped engine or content file", not any(m in shipped for m in markers), [m for m in markers if m in shipped])
    texts = [option_text(s, correct_option(s)) for _, s in ALL if s["type"] == "decision"]
    check("leakage", "no correct option text appears in shipped source", not any(t in shipped for t in texts))
    vals_dom = []
    for ti in range(len(TASKS)):
        goto(pg, M13 + "#task-%d" % (ti + 1), 1); open_all(pg)
        check("leakage", "task %d: rendered DOM carries no correctness attributes before submission" % (ti + 1), not re.search(r'(class|data-[a-z-]+)="[^"]*(correct|answer|right)', pg.content()))
        vals_dom += pg.evaluate("Array.from(document.querySelectorAll('#stagePanel input,#stagePanel option')).map(e=>e.value)")
    check("leakage", "no control value names the answer", not [x for x in vals_dom if re.match(r"^(correct|right|wrong|[fx]_)", x)], vals_dom)
    dec = pg.evaluate("JSON.stringify(PVADesk.decode(window.PVA_DESK_MODULES.m13.payload))")
    check("leakage", "no option, finding or value id names the answer", not re.search(r'"(id|value)":"(correct|right|wrong|[fx]_[a-z]+)"', dec))
    check("leakage", "decoded payload holds hashed keys only", '"correct"' not in dec and '"accept"' not in dec and '"answer"' not in dec)
    sel = [(s["id"], f) for _, s in ALL if s["type"] == "compose" for f in s["fields"] if f["type"] == "select"]
    longest = [f["id"] for _, f in sel if len(label_of(f, f["accept"][0])) == max(len(o["label"]) for o in f["options"])]
    positions = set(next(i for i, o in enumerate(f["options"]) if o["value"] == f["accept"][0]) for _, f in sel)
    check("leakage", "accepted select options are not the longest (at most a quarter of selects) and sit in varied positions",
          len(longest) <= max(1, len(sel) // 4) and len(positions) >= 3, (longest, positions))
    ctx.close()

    # ---------- persistence ----------
    ctx, pg, _ = fresh(br)
    to_stage(pg, 0, "l1-a"); open_all(pg)
    panel(pg).locator("select.desk-select").first.select_option(A1["rows"][0]["answer"])
    pg.reload(); pg.wait_for_timeout(150); pg.click("#btnNext"); pg.wait_for_timeout(80)
    check("persistence", "an unsubmitted triage call survives refresh", panel(pg).locator("select.desk-select").first.input_value() == A1["rows"][0]["answer"])
    to_stage(pg, 1, "l2-b"); open_all(pg)
    panel(pg).get_by_label(number_label(field(B2, "ret.count")), exact=True).fill("1 2")
    pg.reload(); pg.wait_for_timeout(150)
    for _ in range(2): pg.click("#btnNext"); pg.wait_for_timeout(80)
    check("persistence", "a typed number survives an immediate refresh", panel(pg).get_by_label(number_label(field(B2, "ret.count")), exact=True).input_value() == "1 2")
    to_stage(pg, 2, "l3-a"); open_all(pg)
    panel(pg).get_by_label(field(R3, "sum.text")["label"], exact=True).fill("Draft summary for Sofia")
    pg.reload(); pg.wait_for_timeout(150); pg.click("#btnNext"); pg.wait_for_timeout(80)
    check("persistence", "an unsent summary survives refresh", panel(pg).get_by_label(field(R3, "sum.text")["label"], exact=True).input_value() == "Draft summary for Sofia")
    ctx.close()

    # ---------- legacy progress compatibility (I1-a: existing ids only) ----------
    ctx, pg, _ = fresh(br); goto(pg, BASE + "/index.html")
    legacy = {"lessons": {"m13-l%d" % i: True for i in range(1, 9)}, "modules": {}}
    pg.evaluate("v => localStorage.setItem('pva-ecom-ft-progress', JSON.stringify(v))", legacy)
    goto(pg, M13 + "#task-1")
    check("legacy", "all three lessons keep their earlier checkmarks", pg.locator(".lesson-pill.done").count() == 3)
    check("legacy", "the status line separates legacy completion from new work", "earlier version" in pg.inner_text("#taskStatus"))
    vw = pg.evaluate("PVADesk.verifiedWork()")
    check("legacy", "legacy completion is not verified work", not any(v["verified"] for v in vw.values()) and not any(v["samplesEarned"] for v in vw.values()))
    goto(pg, BASE + "/index.html")
    check("legacy", "someone who finished old Module 13 still sees it Completed on the course map", pg.locator(".module-status").nth(12).inner_text() == "Completed")
    partial = {"lessons": {"m13-l2": True, "m13-l5": True}, "modules": {}}
    pg.evaluate("v => localStorage.setItem('pva-ecom-ft-progress', JSON.stringify(v))", partial)
    goto(pg, BASE + "/index.html")
    check("legacy", "the course map counts Module 13 against its three lessons", "2 of 3" in pg.locator(".module-card").nth(12).inner_text(), pg.locator(".module-card").nth(12).inner_text())
    ctx.close()
    port = open(os.path.join(ROOT, "portfolio", "index.html"), encoding="utf-8").read()
    check("portfolio", "the portfolio points at Module 13, Lesson 3", "From Module 13, Lesson 3 -- The Weekly Operations Report" in port and "Lesson 8 -- Writing a Useful Client Update" not in port)

    # ---------- isolation and shared authored state ----------
    ctx, pg, _ = fresh(br)
    goto(pg, M9 + "#task-1", 1); open_all(pg)
    m9a = m9["tasks"][0]["stages"][0]
    fill_compose(pg, m9a, compose_values(m9a, lambda *a: "x")); confirm_all(pg); submit(pg)
    to_stage(pg, 0, "l1-a"); solve(pg, A1)
    keys = pg.evaluate("Object.keys(localStorage).sort()")
    check("isolation", "Module 13 and Module 9 keep separate desk keys, and nothing else is written", set(keys) - {"pva-ecom-ft-progress"} == {KEY, "pva-ecom-ft-m9-desk"}, keys)
    m9store = pg.evaluate("JSON.parse(localStorage.getItem('pva-ecom-ft-m9-desk'))")
    check("isolation", "Module 13 work writes nothing into Module 9's store", list(m9store["tasks"].keys()) == ["m9-l3"], list(m9store["tasks"].keys()))
    goto(pg, M13)
    mut = pg.evaluate("(()=>{try{EVERFIELD.calendar.m13.date='Y'; EVERFIELD.timeline.period='Z';}catch(e){} return [EVERFIELD.calendar.m13.date, EVERFIELD.timeline.period]})()")
    check("everfield", "shared Everfield reference cannot be mutated from Module 13", mut == ["Fri, Oct 2", "September – October"], mut)
    ctx.close()

    # ---------- accessibility, deep links ----------
    ctx, pg, _ = fresh(br)
    for ti, st in ALL:
        to_stage(pg, ti, st["id"]); open_all(pg)
        unnamed = pg.evaluate("""Array.from(document.querySelectorAll('#stagePanel select,#stagePanel input,#stagePanel textarea,#stagePanel button')).filter(e=>{var n=(e.labels&&e.labels.length)||e.getAttribute('aria-label')||e.getAttribute('aria-labelledby')||(e.tagName==='BUTTON'&&e.innerText.trim());return !n}).length""")
        if unnamed: check("a11y", "%s: every control has an accessible name" % st["id"], False, unnamed)
    check("a11y", "every control in every stage has an accessible name", not any(r for r in results if r[0] == "a11y" and not r[2]))
    check("a11y", "evidence toggles expose aria-expanded and aria-controls",
          pg.evaluate("Array.from(document.querySelectorAll('.desk-ev-head button')).every(b=>b.hasAttribute('aria-expanded')&&b.hasAttribute('aria-controls'))"))
    for n in (1, 2, 3):
        goto(pg, M13 + "#task-%d" % n); check("deep-link", "#task-%d opens task %d with its work date" % (n, n), pg.inner_text("#lessonKicker") == "Task %d of 3" % n and
                                              pg.text_content("#deskDate") == (TASKS[n - 1].get("workDate") or "Fri, Oct 2"))
    ctx.close()

    # ---------- contrast, sticky top bar, five widths ----------
    CONTRAST = r"""() => {
     function rgb(s){var m=s.match(/[\d.]+/g);return m?m.map(Number):[0,0,0,0];}
     function lum(c){var a=c.slice(0,3).map(v=>{v/=255;return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4)});return 0.2126*a[0]+0.7152*a[1]+0.0722*a[2];}
     function bg(e){while(e){var c=rgb(getComputedStyle(e).backgroundColor);if(c.length<4||c[3]>0.5)return c;e=e.parentElement;}return [255,255,255,1];}
     var out=[];
     document.querySelectorAll('body *').forEach(e=>{
      if(!e.offsetParent || e.disabled || e.closest('button:disabled')) return;
      if(![].some.call(e.childNodes,n=>n.nodeType===3&&n.textContent.trim())) return;
      var cs=getComputedStyle(e), L1=lum(rgb(cs.color)), L2=lum(bg(e)), r=(Math.max(L1,L2)+0.05)/(Math.min(L1,L2)+0.05);
      var size=parseFloat(cs.fontSize), large=size>=24||(parseInt(cs.fontWeight)>=700&&size>=18.66);
      if(r<(large?3:4.5)) out.push((e.className||e.tagName)+' '+r.toFixed(2));
     }); return out; }"""
    ctx, pg, _ = fresh(br); low = []
    goto(pg, M13 + "#task-1"); low += pg.evaluate(CONTRAST)
    pg.click("#btnNext"); pg.wait_for_timeout(60); open_all(pg); low += pg.evaluate(CONTRAST)
    fail_once(pg, A1); low += pg.evaluate(CONTRAST)
    to_stage(pg, 1, "l2-a"); fail_once(pg, A2); low += pg.evaluate(CONTRAST)
    panel(pg).get_by_role("button", name="Reconsider and try again").click(); fail_once(pg, A2); low += pg.evaluate(CONTRAST)
    to_stage(pg, 2, "l3-a"); open_all(pg); solve(pg, R3); low += pg.evaluate(CONTRAST)
    check("contrast", "all enabled text meets WCAG AA in brief, triage, decision, feedback, pause, compose and work-sample states", not low, sorted(set(low))[:8])
    ctx.close()
    STICKY = """() => { var top=document.querySelector('.topbar').getBoundingClientRect().bottom;
     var els=Array.from(document.querySelectorAll('#stagePanel select,#stagePanel input,#stagePanel textarea,#stagePanel button,#btnNext,#btnPrev')).filter(e=>e.offsetParent);
     return els.filter(e=>{ e.scrollIntoView({block:'start', behavior:'instant'}); return e.getBoundingClientRect().top < top-1; }).length; }"""
    for w in (320, 375):
        ctx, pg, _ = fresh(br, viewport={"width": w, "height": 700}, is_mobile=True, has_touch=True)
        hidden = 0
        for ti, sid in [(0, "l1-a"), (1, "l2-b"), (2, "l3-a")]:
            to_stage(pg, ti, sid); open_all(pg); hidden += pg.evaluate(STICKY)
        check("sticky", "%dpx: no control is left under the sticky top bar when navigated to" % w, hidden == 0, hidden)
        ctx.close()
    RESP = """(()=>{
     var ov=document.documentElement.scrollWidth-innerWidth;
     var wraps=Array.from(document.querySelectorAll('#stagePanel .desk-table-wrap')).filter(w=>w.scrollWidth>w.clientWidth+1).length;
     var cells=Array.from(document.querySelectorAll('#stagePanel .desk-table tbody td, #stagePanel .desk-table tbody th')).filter(c=>c.scrollWidth>c.clientWidth+1).length;
     function hit(a,b){var x=a.getBoundingClientRect(),y=b.getBoundingClientRect();return x.width&&y.width&&x.left<y.right-1&&y.left<x.right-1&&x.top<y.bottom-1&&y.top<x.bottom-1;}
     var heads=Array.from(document.querySelectorAll('#stagePanel .desk-ev-head')).filter(h=>{var t=h.querySelector('.desk-record-title');return t&&Array.from(h.children).filter(c=>!c.contains(t)).some(c=>hit(t,c));}).length;
     var unlabelled=innerWidth<=640?Array.from(document.querySelectorAll('#stagePanel .desk-table tbody td')).filter(c=>getComputedStyle(c,'::before').content.replace(/"/g,'')!==c.getAttribute('data-label')).length:0;
     var bar=document.querySelector('.desk-bar'); var barov=bar?bar.scrollWidth-bar.clientWidth>1:false;
     return [ov,wraps,cells,heads,unlabelled,barov?1:0];})()"""
    for w in (320, 375, 390, 768, 1100):
        ctx, pg, _ = fresh(br, viewport={"width": w, "height": 812}, device_scale_factor=2 if w < 700 else 1, is_mobile=w < 700, has_touch=w < 700)
        for ti, st in ALL:
            to_stage(pg, ti, st["id"]); open_all(pg); pg.wait_for_timeout(60)
            r = pg.evaluate(RESP)
            check("responsive", "%s at %dpx: no sideways scroll, no hidden column, no clipped cell, no overlapping card header%s" % (st["id"], w, ", every value labelled" if w <= 640 else ""), not any(r), r)
        ctx.close()
    ctx, pg, _ = fresh(br, viewport={"width": 1100, "height": 900})
    to_stage(pg, 2, "l3-a"); open_all(pg)
    check("responsive", "desktop keeps the column-header table layout", pg.evaluate("getComputedStyle(document.querySelector('#stagePanel .desk-table thead')).position") != "absolute" and
          pg.evaluate("getComputedStyle(document.querySelector('#stagePanel .desk-table tbody tr')).display") == "table-row")
    ctx.close()
    br.close()

fails = [r for r in results if not r[2]]
print("\n%d checks, %d failed" % (len(results), len(fails)))
sys.exit(1 if fails else 0)
