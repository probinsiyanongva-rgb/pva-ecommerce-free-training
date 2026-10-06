"""Module 5 Work Desk regression + adversarial suite (browser), modelled on Module 9's.

Run from the repo root with a static server on :8765 (see tests/README.md):
    python3 tests/e2e/test_module5.py
Answers come from decoding the shipped content at run time (desk_helpers.decode); the
arithmetic checks recompute every accepted answer from the evidence itself, so nothing
answer-bearing is stored here."""
import os, sys, re
from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from desk_helpers import *  # noqa

SRC = decode("module-5")
M5 = BASE + "/module-5/index.html"
M9 = BASE + "/module-9/index.html"
TASKS = SRC["tasks"]
IDS = [t["id"] for t in TASKS]
ALL = [(ti, s) for ti, t in enumerate(TASKS) for s in t["stages"]]
KEY = "pva-ecom-ft-m5-desk"
results = []


def check(area, name, cond, detail=""):
    results.append((area, name, bool(cond), str(detail)))
    print(("PASS " if cond else "FAIL ") + "[" + area + "] " + name + ((" -- " + str(detail)[:200]) if detail and not cond else ""))


def field(st, fid): return next(f for f in st["fields"] if f["id"] == fid)
def label_of(f, v): return next(o["label"] for o in f["options"] if o["value"] == v)
def fields_of(rec): return dict((k, v) for k, v in rec.get("fields", []))


def m5_text(st, g, f, labels):
    """A terse, accurate tracker note built from the accepted balances only."""
    closing = field(st, "m3.bal")["accept"][0]
    return "EF-101 ended the day at %s available. Maya approved writing off one damaged unit, and it is logged." % closing


def solve(pg, st):
    open_all(pg)
    if st["type"] == "decision": answer_decision(pg, st)
    elif st["type"] == "triage": answer_triage(pg, st)
    else:
        fill_compose(pg, st, compose_values(st, m5_text)); confirm_all(pg); submit(pg)


def fail_once(pg, st):
    open_all(pg)
    if st["type"] == "decision":
        cf = correct_findings(st)
        answer_decision(pg, st, findings=cf[1:] + distractors(st)[:1], option=(wrong_options(st) or [None])[0])
    elif st["type"] == "triage": answer_triage(pg, st, wrong=True)
    else:
        vals = compose_values(st, m5_text)
        num = next(x for x in st["fields"] if x["type"] == "number")
        vals[num["id"]] = str(int(num["accept"][0]) + 1)
        fill_compose(pg, st, vals); confirm_all(pg); submit(pg)


def to_stage(pg, ti, sid):
    goto(pg, M5 + "#task-%d" % (ti + 1), 1)
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


with sync_playwright() as p:
    br = p.chromium.launch()
    A1, B1 = stage_by_id(SRC, "l1-a"), stage_by_id(SRC, "l1-b")
    A2, B2 = stage_by_id(SRC, "l2-a"), stage_by_id(SRC, "l2-b")
    A3, B3 = stage_by_id(SRC, "l3-a"), stage_by_id(SRC, "l3-b")
    T4 = stage_by_id(SRC, "l4-a")

    # ---------- structure: the approved design ----------
    check("design", "4 tasks with the approved ids (I1-a)", IDS == ["m5-l2", "m5-l8", "m5-l6", "m5-l7"], IDS)
    check("design", "titles follow the design map", [t["title"] for t in TASKS] == ["Can We Sell It Today?", "What Needs Attention?", "When Two Counts Disagree", "Keeping the Inventory Tracker"])
    kinds = {t["id"]: [s["type"] for s in t["stages"]] for t in TASKS}
    check("design", "stage types match the map", kinds == {"m5-l2": ["triage", "compose"], "m5-l8": ["triage", "decision"],
                                                         "m5-l6": ["decision", "decision"], "m5-l7": ["compose"]}, kinds)
    check("design", "only Lesson 4 is a portfolio task", [t["id"] for t in TASKS if t.get("portfolio")] == ["m5-l7"])
    check("design", "requesters follow the work: Sofia asks the sales question, Maya the rest", [t["brief"]["from"] for t in TASKS] == ["sofia", "maya", "maya", "maya"])
    nums = [(s["id"], f) for _, s in ALL if s["type"] == "compose" for f in s["fields"] if f["type"] == "number"]
    check("numbers", "four typed numbers: one in Lesson 1, three balances in Lesson 4", [s for s, _ in nums] == ["l1-b", "l4-a", "l4-a", "l4-a"], [s for s, _ in nums])
    check("numbers", "no number passes alone: every stage with a number also asks for a choice",
          all(any(f["type"] in ("select", "multi") for f in stage_by_id(SRC, sid)["fields"]) for sid, _ in nums))
    every = " ".join(str(v) for v in [SRC])
    check("repair", "M5-DATA-04: the unused kit recipe is gone from Module 5", not re.search(r"kit recipe|\d x EF-\d{3}", every, re.I))
    check("repair", "M5-DATA-04: the recipe survives as product canon in the continuity doc",
          "2 x EF-101, 1 x EF-102, 1 x EF-103" in open(os.path.join(ROOT, "docs", "everfield-continuity.md"), encoding="utf-8").read())
    rule = [re.sub(r"<[^>]+>", "", r) for r in TASKS[1]["reference"] if "Tell Maya now" in r or "inventory note" in r or "reconciliation" in r.lower() and "Log it" in r]
    check("repair", "M5-INST-03: Task 2's reference states the decision rule for every call", len(rule) >= 3 and all(c["label"].split(" ")[0] in " ".join(rule) for c in A2["choices"]), rule)
    check("repair", "M5-INST-03: the rule names no SKU and no figure, so it gives no card's answer", not re.search(r"EF-\d{3}|\d", " ".join(rule)), " ".join(rule)[:200])
    check("canon", "the legacy #4021 tracking row survives word for word", "date 9/2, SKU EF-101, quantity -2, event 'customer shipment', reference 'Order #4021', resulting balance 32" in " ".join(TASKS[3]["reference"]))
    check("canon", "EF-103's arrival is shown as a weekday, not a date after the desk day (C2)", "due Sun" in every and not re.search(r"Sep (?:[3-9]|[1-3]\d)\b", every))
    check("canon", "no supplier contact, purchase order or Daniel Brooks as a requester", all(t["brief"]["from"] != "daniel" for t in TASKS))
    acc = [f["accept"][0] for _, f in nums]
    refs = " ".join(" ".join(t.get("reference", [])) + " " + t["brief"]["subject"] + " " + " ".join(t["brief"]["body"]) for t in TASKS)
    check("leakage", "no reference text or brief contains a typed answer", not [a for a in set(acc) if re.search(r"(?<![\d./:#-])" + re.escape(a) + r"(?![\d./:])", refs)])

    # ---------- arithmetic: every accepted answer recomputed from the evidence ----------
    def card_nums(r):
        fd = fields_of(r); g = lambda k: int(re.match(r"\d+", fd[k]).group(0))
        return g("Available"), g("Reserved"), g("Inbound"), g("Alert at")
    def state(av, rs, inb, al): return ("coming" if inb else "nothing") if av == 0 else ("below" if av < al else "instock")
    check("arithmetic", "Lesson 1A: every call follows from its own card", all(r["answer"] == state(*card_nums(r)) for r in A1["rows"]),
          [(r["title"], r["answer"]) for r in A1["rows"]])
    calls = set(r["answer"] for r in A1["rows"])
    check("design", "Lesson 1A uses all four states, and two SKUs at zero differ only by Inbound", calls == {"instock", "below", "coming", "nothing"} and
          len([r for r in A1["rows"] if card_nums(r)[0] == 0]) == 2)
    ef101 = next(r for r in B1["groups"][0]["records"] if r.get("fields"))
    check("arithmetic", "Lesson 1B: units that can go out today = Available on the card", field(B1, "b2b.units")["accept"] == [str(card_nums(ef101)[0])])
    def l2call(r):
        fd = fields_of(r)
        if "ClearPath count, 7:00 AM" in fd:
            mine = sum(int(x) for x in re.findall(r"(\d+) (?:available|reserved)", fd["Our record"]))
            return "none" if mine == int(re.match(r"\d+", fd["ClearPath count, 7:00 AM"]).group(0)) else "log"
        av, rs, inb, al = card_nums(r); waiting = fd.get("Orders waiting for stock", "None") != "None"
        if av == 0 and waiting and inb == 0: return "now"
        if av == 0 or av < al: return "note"
        return "none"
    check("arithmetic", "Lesson 2A: every call follows from its card's figures", all(r["answer"] == l2call(r) for r in A2["rows"]), [(r["title"], r["answer"]) for r in A2["rows"]])
    check("design", "Lesson 2A: only one issue goes to Maya now", [r["answer"] for r in A2["rows"]].count("now") == 1)
    def shelf_vs_count(st, sku):
        card = next(r for r in st["records"] if r.get("title", "").startswith(sku) and r.get("fields"))
        av, rs, _, _ = card_nums(card)
        cnt = next(r for r in st["records"] if r.get("kind") == "table")
        counted = int(next(row[1] for row in cnt["rows"] if row[0] == sku))
        return av + rs, counted
    s104, c104 = shelf_vs_count(A3, "EF-104"); s200, c200 = shelf_vs_count(B3, "EF-200")
    check("arithmetic", "Lesson 3: EF-104 really differs on a like-for-like basis; EF-200 only appears to", s104 != c104 and s200 == c200, (s104, c104, s200, c200))
    tbl = next(r for r in T4["groups"][0]["records"] if r.get("kind") == "table" and "tracker" in r["title"].lower())
    bal = int(tbl["rows"][-1][-1])
    ret = next(r for g in T4["groups"] for r in g["records"] if r.get("title", "").startswith("Return"))
    o4024 = next(r for g in T4["groups"] for r in g["records"] if r.get("title", "").startswith("Order"))
    wo = next(r for g in T4["groups"] for r in g["records"] if r.get("kind") == "message")
    steps = [int(re.search(r"× (\d+)", fields_of(ret)["Item"]).group(1)),
             0 if any("reserved" in l and l.startswith("Tue") for l in o4024["log"]) else -int(re.search(r"× (\d+)", fields_of(o4024)["Item"]).group(1)),
             -int(re.search(r"(\d+) unit", " ".join(wo["body"])).group(1))]
    want = []
    for d in steps: bal += d; want.append(str(bal))
    got = [field(T4, g + ".bal")["accept"][0] for g in ("m1", "m2", "m3")]
    check("arithmetic", "Lesson 4: each balance follows from the record before it (a reserved shipment leaves Available unchanged)", got == want, (got, want))

    # ---------- normal flow, completion, work sample ----------
    ctx, pg, errs = fresh(br); goto(pg, M5)
    check("page", "desk bar shows Wed, Sep 2 and the task count", pg.text_content("#deskDate") == "Wed, Sep 2" and pg.inner_text("#lessonKicker") == "Task 1 of 4")
    for ti, t in enumerate(TASKS):
        goto(pg, M5 + "#task-%d" % (ti + 1), 1); ok = True
        for st in t["stages"]:
            solve(pg, st)
            if not pg.is_enabled("#btnNext"): ok = False; break
            pg.click("#btnNext"); pg.wait_for_timeout(60)
        check("flow", "task %d completes through the UI" % (ti + 1), ok)
    prog = pg.evaluate("JSON.parse(localStorage.getItem('pva-ecom-ft-progress'))")
    check("progress", "verified work marks all four lessons in the legacy progress store", all(prog["lessons"].get(i) for i in IDS))
    check("flow", "completion banner", "Module 5 complete" in pg.inner_text("#doneBanner"))
    keys = pg.evaluate("Object.keys(localStorage).sort()")
    check("isolation", "only the Module 5 desk key and the legacy progress key are written", keys == [KEY, "pva-ecom-ft-progress"], keys)
    vw = pg.evaluate("PVADesk.verifiedWork()")
    check("verified-work", "verifiedWork() reports all four tasks verified and the one earned sample",
          all(v["verified"] for v in vw.values()) and vw["m5-l7"]["samplesEarned"] == ["l4-a"] and not any(v["samplesEarned"] for k, v in vw.items() if k != "m5-l7"), vw)
    goto(pg, BASE + "/index.html")
    card = pg.locator(".module-card").nth(4).inner_text()
    check("progress", "course map shows Module 5 Completed", "Inventory Basics" in card and "Completed" in card, card)
    goto(pg, M5 + "#task-4", 1)
    ev = pg.locator(".ws-preview").inner_text() if pg.locator(".ws-preview").count() else ""
    check("work-sample", "Inventory Tracker survives reload with an honest training header",
          ev.startswith("TRAINING WORK SAMPLE\nEverfield Goods — Inventory Tracker (EF-101, Wed Sep 2)") and "fictional company" in ev and
          "Work date: Wed, Sep 2 (simulated)" in ev and "Maya Collins" in ev and "human review" in ev, ev[:300])
    check("work-sample", "the sample prints each movement with its balance", all(("Available after: %s units" % b) in ev for b in got) and "Return #229" in ev, ev[:600])
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

    # ---------- numeric integrity ----------
    NO_DIRECTION = re.compile(r"(higher|lower|too (many|few|high|low|big|small)|more than|less than|fewer|bigger|smaller|close|nearly|almost|off by)", re.I)
    ctx, pg, _ = fresh(br)
    to_stage(pg, 0, "l1-b"); open_all(pg); st = B1
    def attempt(stg, **over):
        v = compose_values(stg, m5_text); v.update(over)
        fill_compose(pg, stg, v); confirm_all(pg); submit(pg)
        okk = pg.is_enabled("#btnNext"); fbx = fb_text(pg)
        if okk: revise(pg)
        else: open_all(pg)
        return okk, fbx
    units = field(st, "b2b.units")["accept"][0]
    av, rs, inb, al = card_nums(ef101)
    for fmt in [" " + units + " ", units + ".0", units + ".00"]:
        check("numbers", "equivalent entry %r of the right figure passes" % fmt, attempt(st, **{"b2b.units": fmt})[0])
    for slip, val in [("reserved counted as sellable", av + rs), ("inbound counted as sellable", av + inb), ("the buyer's whole order", 40)]:
        okk, fbx = attempt(st, **{"b2b.units": str(val)})
        check("numbers", "l1-b: %s fails" % slip, not okk and "EF-101 units" in fbx, fbx[:160])
        check("numbers", "l1-b: the miss never states the value or a direction (%s)" % slip, units not in re.sub(r"Attempt \d+", "", fbx) and not NO_DIRECTION.search(fbx), fbx[:200])
    for bad in ["thirty-four", units + " units", units + ",5", "", "-" + units]:
        okk, fbx = attempt(st, **{"b2b.units": bad})
        check("numbers", "malformed or negative entry %r is refused" % bad, not okk)
    check("numbers", "l1-b: right number, wrong reply fails", not attempt(st, **{"b2b.reply": first_unaccepted(field(st, "b2b.reply"))})[0])
    to_stage(pg, 3, "l4-a"); open_all(pg); st = T4
    b1, b2, b3 = (field(st, g + ".bal")["accept"][0] for g in ("m1", "m2", "m3"))
    check("numbers", "l4-a: taking #4024 out of Available again fails", not attempt(st, **{"m2.bal": str(int(b1) - 3)})[0])
    check("numbers", "l4-a: leaving the write-off out fails", not attempt(st, **{"m3.bal": b2})[0])
    check("numbers", "l4-a: a right balance with the wrong event fails", not attempt(st, **{"m2.event": first_unaccepted(field(st, "m2.event"))})[0])
    check("numbers", "l4-a: a right balance with the wrong reference fails", not attempt(st, **{"m1.ref": first_unaccepted(field(st, "m1.ref"))})[0])
    dom = pg.content()
    check("leakage", "no typed answer sits in the DOM as an input value before a correct submission", not re.search(r'value="(%s|%s)"' % (b1, b3), dom))
    ctx.close()

    # ---------- decisions: transfer and principle-only feedback ----------
    ctx, pg, _ = fresh(br)
    for ti, st in ALL:
        if st["type"] != "decision": continue
        to_stage(pg, ti, st["id"]); open_all(pg)
        answer_decision(pg, st, findings=correct_findings(st)[:-1])
        check("transfer", "%s: right action without the full reading of the evidence fails" % st["id"], not pg.is_enabled("#btnNext"))
    to_stage(pg, 2, "l3-b"); open_all(pg)
    answer_decision(pg, B3, option="copy")
    fbx = fb_text(pg)
    check("transfer", "l3-b: reusing EF-104's answer fails and points back to the comparison", not pg.is_enabled("#btnNext") and "reusing" in fbx.lower(), fbx[:160])
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
    STATE_WORDS = re.compile(r"in stock|out of stock|stockout|below (its|the) alert|on the way|nothing coming|is low|running low", re.I)
    l2_cards = " ".join(" ".join(str(v) for kv in r["fields"] for v in kv) + " " + r["title"] for r in A2["rows"]) + " " + \
               " ".join(" ".join(str(v) for kv in r.get("fields", []) for v in kv) + " " + " ".join(" ".join(x) for x in r.get("rows", [])) for r in B2["records"])
    check("later-first", "Lesson 2's cards and records show figures, never Lesson 1's state words or categories",
          not STATE_WORDS.search(l2_cards) and not [l for l in l1_labels if l in l2_cards], STATE_WORDS.findall(l2_cards))
    l4_text = str(records_of(T4)) + " " + " ".join(o["label"] for f in T4["fields"] if f.get("options") for o in f["options"])
    l3_counts = [row for r in A3["records"] if r.get("kind") == "table" for row in r["rows"]]
    check("later-first", "Lesson 4 shows no Lesson 3 cycle count, reconciliation call or count figure",
          not re.search(r"cycle count|reconciliation|on the shelf", l4_text, re.I) and not any(("'%s', '%s'" % (row[0], row[1])) in l4_text for row in l3_counts))
    l1_answers_in_l3 = str(A3["records"]) + str(B3["records"])
    check("later-first", "Lesson 3 shows no Lesson 1 or Lesson 4 answers (no EF-101 figures)", "EF-101" not in l1_answers_in_l3)
    ctx, pg, errs = fresh(br)
    goto(pg, M5); pg.locator(".lesson-pill").nth(1).click(); pg.wait_for_timeout(100)
    pg.click("#btnNext"); pg.wait_for_timeout(60); open_all(pg)
    dom = pg.inner_text("#stagePanel")
    check("later-first", "a fresh learner opening Lesson 2 first sees no Lesson 1 state words", not [l for l in l1_labels if l in dom.split("What happens with it")[0]] and not STATE_WORDS.search(dom), STATE_WORDS.findall(dom)[:4])
    solve(pg, A2)
    check("later-first", "Lesson 2 stays usable when opened first", pg.is_enabled("#btnNext"))
    check("later-first", "no JS errors", not errs, errs)
    ctx.close()

    # ---------- shortcut attempts, derived completion, the note ----------
    ctx, pg, _ = fresh(br); goto(pg, M5)
    pg.evaluate("""localStorage.setItem('%s', JSON.stringify({v:1,tasks:{'m5-l7':{completed:true,verified:true,views:1,
      stages:{'l4-a':{passed:true,answer:{values:{},confirms:[true,true]}}},drafts:{'l4-a:v':{'m3.note':'x'}}}}}))""" % KEY)
    goto(pg, M5 + "#task-4")
    st4 = pg.evaluate("PVADesk.taskStatus(PVADesk.decode(window.PVA_DESK_MODULES.m5.payload).tasks[3])")
    check("integrity", "forged completed/verified/passed flags count for nothing", st4["passed"] == 0, st4)
    check("integrity", "forged state never reaches the legacy progress store", not (pg.evaluate("JSON.parse(localStorage.getItem('pva-ecom-ft-progress')||'{}')").get("lessons") or {}).get("m5-l7"))
    goto(pg, M5 + "#task-4", 1)
    check("work-sample", "no work sample exists before the work verifies", panel(pg).locator(".ws-preview").count() == 0)
    open_all(pg); st = T4
    fill_compose(pg, st, compose_values(st, m5_text)); confirm_all(pg)
    panel(pg).locator("section.desk-group").first.get_by_label(number_label(field(st, "m1.bal")), exact=True).fill("1")
    check("self-check", "changing work after confirming clears the confirmations", not any(x.is_checked() for x in panel(pg).locator(".desk-selfcheck input").all()))
    def note(text):
        v = compose_values(st, m5_text); v["m3.note"] = text
        fill_compose(pg, st, v); confirm_all(pg); submit(pg)
        okk = pg.is_enabled("#btnNext"); fbx = fb_text(pg)
        if okk: revise(pg)
        else: open_all(pg)
        return okk, fbx
    GOOD = [
        ("terse", "EF-101 ended the day at %s available. Maya approved writing off one damaged bin." % b3),
        ("different wording", "We finished the day with %s bins free to sell. The damaged unit you approved is logged as an adjustment." % b3),
        ("explains the reserved shipment", "#4024 didn't reduce Available because its units were reserved yesterday. EF-101 closes at %s after the approved write-off." % b3),
        ("no numbers", "EF-101's closing balance is in the last row. One unit was written off with your approval after ClearPath reported it damaged."),
    ]
    for why, t in GOOD:
        check("l4-note", "passes -- %s" % why, note(t)[0], t)
    BAD = [
        ("is filler", "Everything went fine today and the tracker is all up to date now."),
        ("leaves out what Maya approved", "EF-101 ended the day at %s available after a few movements today." % b3),
        ("leaves out where EF-101 ended", "One bin was damaged and Maya approved writing it off. All rows are logged."),
        ("guesses how the unit was damaged", "EF-101 closes at %s. ClearPath probably dropped the bin, so it was written off." % b3),
        ("says #4024 reduced Available", "EF-101 closes at %s. Order #4024 reduced Available by 3 when it shipped, and one unit was written off." % b3),
        ("says the return wasn't restocked", "EF-101 closes at %s after the write-off. Return #229 was not restocked today." % b3),
        ("says nothing moved", "Nothing moved on EF-101 today apart from the write-off, so the balance is unchanged."),
    ]
    for why, t in BAD:
        check("l4-note", "rejected -- a note that %s" % why, not note(t)[0], t)
    # M5-UX-05: reporting the source faithfully passes; inventing who caused the damage fails
    src_line = " ".join(next(r for g in T4["groups"] for r in g["records"] if r.get("kind") == "message")["body"]).split(". Approved")[0]
    END = " EF-101 ended the day at %s available." % b3
    ATTRIB_OK = [
        ("the source's exact wording", src_line + ", and Maya approved the write-off." + END),
        ("\"ClearPath damaged report\" as a noun phrase", "ClearPath damaged report: one bin written off with Maya's approval." + END),
        ("\"reported damaged by ClearPath\"", "One bin was reported damaged by ClearPath; Maya approved the write-off." + END),
        ("\"Available dropped\"", "Available dropped after Maya approved writing off the damaged bin ClearPath reported. That closes the day at %s." % b3),
    ]
    for why, t in ATTRIB_OK:
        okk, fbx = note(t)
        check("l4-attribution", "passes -- %s" % why, okk, (t, fbx[:160]))
    ATTRIB_BAD = [
        ("ClearPath damaged the bin", "ClearPath damaged the bin in storage, so Maya approved a write-off." + END),
        ("damaged by ClearPath", "The bin was damaged by ClearPath, so Maya approved writing it off." + END),
        ("a picker dropped it", "A picker dropped one bin during picking and Maya approved the write-off." + END),
        ("the carrier crushed it", "The carrier crushed a bin, so Maya approved the write-off." + END),
        ("ClearPath's fault", "The damage is ClearPath's fault; Maya approved the write-off." + END),
    ]
    for why, t in ATTRIB_BAD:
        okk, fbx = note(t)
        check("l4-attribution", "rejected -- invents a cause: %s" % why, not okk and "how the unit was damaged" in fbx, (t, fbx[:160]))
    okk, fbx = note("Everything went fine today and the tracker is all up to date now.")
    check("l4-note", "note feedback names the principle, never the figure to type", not okk and b3 not in re.sub(r"Attempt \d+", "", fbx), fbx[:200])
    ctx.close()

    # ---------- answer encoding / leakage ----------
    ctx, pg, _ = fresh(br)
    shipped = "".join(pg.request.get(BASE + uu).text() for uu in ["/module-5/index.html", "/module-5/desk-data.js", "/shared/workdesk.js", "/shared/workdesk-ui.js", "/shared/workdesk-page.js", "/shared/everfield-data.js"])
    markers = ['"correct"', "correct: true", '"accept"', '"answer":', '"correctOrder"']
    check("leakage", "no plaintext answer markers in any shipped engine or content file", not any(m in shipped for m in markers), [m for m in markers if m in shipped])
    texts = [option_text(s, correct_option(s)) for _, s in ALL if s["type"] == "decision"]
    check("leakage", "no correct option text appears in shipped source", not any(t in shipped for t in texts))
    goto(pg, M5 + "#task-3", 1); open_all(pg)
    check("leakage", "rendered DOM carries no correctness attributes before submission", not re.search(r'(class|data-[a-z-]+)="[^"]*(correct|answer|right)', pg.content()))
    vals_dom = []
    for ti in range(len(TASKS)):
        goto(pg, M5 + "#task-%d" % (ti + 1), 1); open_all(pg)
        vals_dom += pg.evaluate("Array.from(document.querySelectorAll('#stagePanel input,#stagePanel option')).map(e=>e.value)")
    check("leakage", "no control value names the answer", not [x for x in vals_dom if re.match(r"^(correct|right|wrong|[fx]_)", x)], vals_dom)
    dec = pg.evaluate("JSON.stringify(PVADesk.decode(window.PVA_DESK_MODULES.m5.payload))")
    check("leakage", "no option, finding or value id names the answer", not re.search(r'"(id|value)":"(correct|right|wrong|[fx]_[a-z]+)"', dec))
    check("leakage", "decoded payload holds hashed keys only", '"correct"' not in dec and '"accept"' not in dec and '"answer"' not in dec)
    ctx.close()

    # ---------- persistence ----------
    ctx, pg, _ = fresh(br)
    to_stage(pg, 0, "l1-a"); open_all(pg)
    panel(pg).locator("select.desk-select").first.select_option(A1["rows"][0]["answer"])
    pg.reload(); pg.wait_for_timeout(150); pg.click("#btnNext"); pg.wait_for_timeout(80)
    check("persistence", "an unsubmitted triage call survives refresh", panel(pg).locator("select.desk-select").first.input_value() == A1["rows"][0]["answer"])
    to_stage(pg, 0, "l1-b"); open_all(pg)
    panel(pg).get_by_label(number_label(field(B1, "b2b.units")), exact=True).fill("1 2")
    pg.reload(); pg.wait_for_timeout(150)
    for _ in range(2): pg.click("#btnNext"); pg.wait_for_timeout(80)
    check("persistence", "a typed number survives an immediate refresh", panel(pg).get_by_label(number_label(field(B1, "b2b.units")), exact=True).input_value() == "1 2")
    ctx.close()

    # ---------- legacy progress compatibility (I1-a: existing ids only) ----------
    ctx, pg, _ = fresh(br); goto(pg, BASE + "/index.html")
    legacy = {"lessons": {"m5-l%d" % i: True for i in range(1, 9)}, "modules": {}}
    pg.evaluate("v => localStorage.setItem('pva-ecom-ft-progress', JSON.stringify(v))", legacy)
    goto(pg, M5 + "#task-1")
    check("legacy", "all four lessons keep their earlier checkmarks", pg.locator(".lesson-pill.done").count() == 4)
    check("legacy", "the status line separates legacy completion from new work", "earlier version" in pg.inner_text("#taskStatus"))
    vw = pg.evaluate("PVADesk.verifiedWork()")
    check("legacy", "legacy completion is not verified work", not any(v["verified"] for v in vw.values()) and not any(v["samplesEarned"] for v in vw.values()))
    goto(pg, BASE + "/index.html")
    check("legacy", "someone who finished old Module 5 still sees it Completed on the course map", pg.locator(".module-status").nth(4).inner_text() == "Completed")
    ctx.close()

    # ---------- isolation and shared authored state ----------
    ctx, pg, _ = fresh(br)
    goto(pg, M9 + "#task-1", 1); open_all(pg)
    m9a = decode("module-9")["tasks"][0]["stages"][0]
    fill_compose(pg, m9a, compose_values(m9a, lambda *a: "x")); confirm_all(pg); submit(pg)
    to_stage(pg, 0, "l1-a"); solve(pg, A1)
    keys = pg.evaluate("Object.keys(localStorage).sort()")
    check("isolation", "Module 5 and Module 9 keep separate desk keys, and nothing else is written", set(keys) - {"pva-ecom-ft-progress"} == {KEY, "pva-ecom-ft-m9-desk"}, keys)
    m9store = pg.evaluate("JSON.parse(localStorage.getItem('pva-ecom-ft-m9-desk'))")
    check("isolation", "Module 5 work writes nothing into Module 9's store", list(m9store["tasks"].keys()) == ["m9-l3"], list(m9store["tasks"].keys()))
    goto(pg, M5)
    mut = pg.evaluate("(()=>{try{EVERFIELD.calendar.m5.date='Y'; EVERFIELD.productFacts['EF-200'].kit['EF-101']=9;}catch(e){} return [EVERFIELD.calendar.m5.date, EVERFIELD.productFacts['EF-200'].kit['EF-101']]})()")
    check("everfield", "shared Everfield reference cannot be mutated from Module 5", mut == ["Wed, Sep 2", 2], mut)
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
    for n in (1, 2, 4):
        goto(pg, M5 + "#task-%d" % n); check("deep-link", "#task-%d opens task %d" % (n, n), pg.inner_text("#lessonKicker") == "Task %d of 4" % n)
    ctx.close()

    # ---------- contrast, sticky top bar, phone widths (E3 engine fix) ----------
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
    goto(pg, M5 + "#task-1"); low += pg.evaluate(CONTRAST)
    pg.click("#btnNext"); pg.wait_for_timeout(60); open_all(pg); low += pg.evaluate(CONTRAST)
    fail_once(pg, A1); low += pg.evaluate(CONTRAST)
    to_stage(pg, 2, "l3-a"); fail_once(pg, A3); low += pg.evaluate(CONTRAST)
    panel(pg).get_by_role("button", name="Reconsider and try again").click(); fail_once(pg, A3); low += pg.evaluate(CONTRAST)
    to_stage(pg, 3, "l4-a"); open_all(pg); solve(pg, T4); low += pg.evaluate(CONTRAST)
    check("contrast", "all enabled text meets WCAG AA in brief, triage, decision, feedback, pause, compose and work-sample states", not low, sorted(set(low))[:8])
    ctx.close()
    STICKY = """() => { var top=document.querySelector('.topbar').getBoundingClientRect().bottom;
     var els=Array.from(document.querySelectorAll('#stagePanel select,#stagePanel input,#stagePanel textarea,#stagePanel button,#btnNext,#btnPrev')).filter(e=>e.offsetParent);
     return els.filter(e=>{ e.scrollIntoView({block:'start', behavior:'instant'}); return e.getBoundingClientRect().top < top-1; }).length; }"""
    for w in (320, 375):
        ctx, pg, _ = fresh(br, viewport={"width": w, "height": 700}, is_mobile=True, has_touch=True)
        hidden = 0
        for ti, sid in [(0, "l1-a"), (2, "l3-a"), (3, "l4-a")]:
            to_stage(pg, ti, sid); open_all(pg); hidden += pg.evaluate(STICKY)
        check("sticky", "%dpx: no control is left under the sticky top bar when navigated to" % w, hidden == 0, hidden)
        ctx.close()
    # M5-RESP-01/02: every table's information stays readable at every width
    RESP = """(()=>{
     var ov=document.documentElement.scrollWidth-innerWidth;
     var wraps=Array.from(document.querySelectorAll('#stagePanel .desk-table-wrap')).filter(w=>w.scrollWidth>w.clientWidth+1).length;
     var cells=Array.from(document.querySelectorAll('#stagePanel .desk-table tbody td, #stagePanel .desk-table tbody th')).filter(c=>c.scrollWidth>c.clientWidth+1).length;
     function hit(a,b){var x=a.getBoundingClientRect(),y=b.getBoundingClientRect();return x.width&&y.width&&x.left<y.right-1&&y.left<x.right-1&&x.top<y.bottom-1&&y.top<x.bottom-1;}
     var heads=Array.from(document.querySelectorAll('#stagePanel .desk-ev-head')).filter(h=>{var t=h.querySelector('.desk-record-title');return t&&Array.from(h.children).filter(c=>!c.contains(t)).some(c=>hit(t,c));}).length;
     var unlabelled=innerWidth<=640?Array.from(document.querySelectorAll('#stagePanel .desk-table tbody td')).filter(c=>getComputedStyle(c,'::before').content.replace(/"/g,'')!==c.getAttribute('data-label')).length:0;
     return [ov,wraps,cells,heads,unlabelled];})()"""
    for w in (320, 375, 390, 768, 1100):
        ctx, pg, _ = fresh(br, viewport={"width": w, "height": 812}, device_scale_factor=2 if w < 700 else 1, is_mobile=w < 700, has_touch=w < 700)
        for ti, st in ALL:
            to_stage(pg, ti, st["id"]); open_all(pg); pg.wait_for_timeout(60)
            r = pg.evaluate(RESP)
            check("responsive", "%s at %dpx: no sideways scroll, no hidden column, no clipped cell, no overlapping card header%s" % (st["id"], w, ", every value labelled" if w <= 640 else ""), not any(r), r)
        ctx.close()
    ctx, pg, _ = fresh(br, viewport={"width": 1100, "height": 900})
    to_stage(pg, 3, "l4-a"); open_all(pg)
    check("responsive", "desktop keeps the column-header table layout", pg.evaluate("getComputedStyle(document.querySelector('#stagePanel .desk-table thead')).position") != "absolute" and
          pg.evaluate("getComputedStyle(document.querySelector('#stagePanel .desk-table tbody tr')).display") == "table-row")
    ctx.close()
    br.close()

fails = [r for r in results if not r[2]]
print("\n%d checks, %d failed" % (len(results), len(fails)))
sys.exit(1 if fails else 0)
