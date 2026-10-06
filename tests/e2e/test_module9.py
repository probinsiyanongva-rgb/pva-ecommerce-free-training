"""Module 9 Work Desk regression + adversarial suite (browser), modelled on Module 7's.

Run from the repo root with a static server on :8765 (see tests/README.md):
    python3 tests/e2e/test_module9.py
Answers come from decoding the shipped content at run time (desk_helpers.decode); the
arithmetic checks recompute every accepted number from the evidence tables themselves,
so nothing answer-bearing is stored here."""
import os, sys, re
from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from desk_helpers import *  # noqa

SRC = decode("module-9")
M9 = BASE + "/module-9/index.html"
M4 = BASE + "/module-4/index.html"
M7 = BASE + "/module-7/index.html"
TASKS = SRC["tasks"]
IDS = [t["id"] for t in TASKS]
ALL = [(ti, s) for ti, t in enumerate(TASKS) for s in t["stages"]]
KEY = "pva-ecom-ft-m9-desk"
results = []


def check(area, name, cond, detail=""):
    results.append((area, name, bool(cond), str(detail)))
    print(("PASS " if cond else "FAIL ") + "[" + area + "] " + name + ((" -- " + str(detail)[:200]) if detail and not cond else ""))


def field(st, fid): return next(f for f in st["fields"] if f["id"] == fid)
def label_of(f, v): return next(o["label"] for o in f["options"] if o["value"] == v)


def m9_text(st, g, f, labels):
    """A terse, accurate note built from the accepted structured values only."""
    out = [label_of(field(st, "stock.out"), v).split(" ")[0] for v in field(st, "stock.out")["accept"][0]]
    disc = [label_of(field(st, "open.disc"), v).split(":")[0] for v in field(st, "open.disc")["accept"][0]]
    return "Out of stock today: " + " and ".join(out) + ". Still open: the " + " and ".join(disc) + " gap, waiting on ClearPath."


def solve(pg, st):
    open_all(pg)
    if st["type"] == "decision": answer_decision(pg, st)
    else:
        fill_compose(pg, st, compose_values(st, m9_text)); confirm_all(pg); submit(pg)


def wrong_number(f):
    v = float(f["accept"][0]); d = f.get("decimals", 0)
    return ("%." + str(d) + "f") % (v + 1)


def fail_once(pg, st):
    open_all(pg)
    if st["type"] == "decision":
        cf = correct_findings(st)
        answer_decision(pg, st, findings=cf[1:] + distractors(st)[:1], option=(wrong_options(st) or [None])[0])
    else:
        vals = compose_values(st, m9_text)
        nums = [x for x in st["fields"] if x["type"] == "number"]
        if nums: vals[nums[0]["id"]] = wrong_number(nums[0])
        else:
            f = next(x for x in st["fields"] if x["type"] == "select")
            vals[f["id"]] = first_unaccepted(f)
        fill_compose(pg, st, vals); confirm_all(pg); submit(pg)


def to_stage(pg, ti, sid):
    goto(pg, M9 + "#task-%d" % (ti + 1), 1)
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


# ---------- the evidence, read back from the shipped content ----------
def records_of(st):
    if st["type"] == "decision": return st["records"]
    return [r for g in st["groups"] for r in g["records"]]


def table(st, title_part):
    return next(r for r in records_of(st) if r.get("kind") == "table" and title_part in r["title"])


def lead_int(s):
    m = re.match(r"\s*(\d+)", s); return int(m.group(1)) if m else 0


def time_after_noon(date):  # "Fri Sep 25 · 2:15 PM"
    m = re.search(r"(\d+):(\d+) (AM|PM)", date); h = int(m.group(1)) % 12 + (12 if m.group(3) == "PM" else 0)
    return h >= 12


with sync_playwright() as p:
    br = p.chromium.launch()

    # ---------- structure: the approved four-lesson design ----------
    check("design", "4 tasks with the approved ids (I1-a)", IDS == ["m9-l3", "m9-l9", "m9-l11", "m9-l10"], IDS)
    check("design", "titles follow the design map", [t["title"] for t in TASKS] == ["Answering a Numbers Question", "Can This Number Be Trusted?", "When Two Numbers Disagree", "The Week in Numbers"])
    kinds = {t["id"]: [s["type"] for s in t["stages"]] for t in TASKS}
    check("design", "stage types match the map", kinds == {"m9-l3": ["compose", "compose"], "m9-l9": ["decision", "compose"],
                                                         "m9-l11": ["compose", "decision"], "m9-l10": ["compose"]}, kinds)
    check("design", "only Lesson 4 is a portfolio task", [t["id"] for t in TASKS if t.get("portfolio")] == ["m9-l10"])
    nums = [(s["id"], f) for _, s in ALL if s["type"] == "compose" for f in s["fields"] if f["type"] == "number"]
    check("numbers", "typed numbers are used where they matter (Lessons 1, 2 and 4)", sorted(set(s for s, _ in nums)) == ["l1-a", "l1-b", "l2-b", "l4-a"], [s for s, _ in nums])
    check("numbers", "at most three typed numbers per stage", all(sum(1 for s, _ in nums if s == sid) <= 3 for sid, _ in nums))
    check("numbers", "every number field states its unit and a bounded range", all(f.get("unit") and isinstance(f.get("max"), (int, float)) for _, f in nums))
    check("numbers", "no number passes alone: every stage with a number also asks for a choice about it",
          all(any(f["type"] in ("select", "multi") for f in stage_by_id(SRC, sid)["fields"]) for sid, _ in nums))
    check("numbers", "only Lesson 1's cost takes cents", [f["id"] for _, f in nums if f.get("decimals")] == ["cost.total"])
    tables = [r for _, s in ALL for r in records_of(s) if r.get("kind") == "table"]
    check("ux", "no table is wider than six columns or longer than fifteen rows", all(len(t["columns"]) <= 6 and len(t["rows"]) <= 15 for t in tables))
    acc_big = [f["accept"][0] for _, f in nums if float(f["accept"][0]) > 3]
    cells = [str(c) for t in tables for row in t["rows"] for c in row] + [str(v) for _, s in ALL for r in records_of(s) for _, v in r.get("fields", [])]
    check("leakage", "no evidence cell or record field shows a typed answer", not [a for a in acc_big if a in cells], [a for a in acc_big if a in cells])
    refs = " ".join(" ".join(t.get("reference", [])) for t in TASKS) + " " + " ".join(t["brief"]["subject"] + " " + " ".join(t["brief"]["body"]) for t in TASKS)
    check("leakage", "no Learn/reference text or brief contains a typed answer", not [a for a in acc_big if re.search(r"(?<![\d./:#,])" + re.escape(a) + r"(?![\d./:,])", refs)])
    every = " ".join(str(v) for v in [SRC])
    check("canon", "the week never shows EF-102, EF-103 or EF-106 (W1)", not re.search(r"EF-10[236]\b", every))
    check("canon", "Marcus Lee appears, as the person Maya raises ClearPath gaps with (N1)", "Marcus Lee" in every)
    check("canon", "the unit-cost card states the canon costs (D5)", "$4.20" in every and "$3.85" in every)
    check("canon", "the shared record #4021 stays cited in Lesson 1's reference",
          re.search(r"4021</td><td>9/2</td><td>EF-101</td><td>2</td><td>Shipped", " ".join(TASKS[0]["reference"])) is not None)

    # ---------- arithmetic: every accepted number is recomputed from the evidence ----------
    a, b = stage_by_id(SRC, "l1-a"), stage_by_id(SRC, "l1-b")
    ex = table(a, "checked copy")["rows"]
    tue = [r for r in ex if r[1].startswith("Tue") and r[5] == "Shipped"]
    check("arithmetic", "Lesson 1A: orders and units shipped Tuesday match the export",
          field(a, "tue.orders")["accept"] == [str(len({r[0] for r in tue}))] and field(a, "tue.units")["accept"] == [str(sum(int(r[4]) for r in tue))])
    costs = {m.group(1): float(m.group(2)) for i in next(r for r in records_of(b) if r.get("kind") == "reference")["items"] for m in [re.match(r"(EF-\d+).*\$(\d+\.\d+)", i)]}
    u = {s: sum(int(r[4]) for r in ex if r[3] == s and r[5] == "Shipped") for s in costs}
    check("arithmetic", "Lesson 1B: units and cost match the export and the cost card",
          field(b, "cost.u101")["accept"] == [str(u["EF-101"])] and field(b, "cost.u105")["accept"] == [str(u["EF-105"])] and
          field(b, "cost.total")["accept"] == ["%.2f" % round(sum(u[s] * costs[s] for s in costs), 2)])
    c = stage_by_id(SRC, "l2-b"); pt = table(c, "as pulled"); pr = pt["rows"]
    summary = int(re.search(r"Status = Shipped\) = (\d+)", pt["note"]).group(1))
    check("arithmetic", "Lesson 2: the export's summary is what a spreadsheet total gives (text skipped, exact Shipped only)",
          summary == sum(int(r[4]) for r in pr if r[5] == "Shipped" and re.fullmatch(r"\d+", r[4])))
    dedup = [r for i, r in enumerate(pr) if r not in pr[:i]]
    recq = {r["title"].split()[-1]: lead_int(re.search(r"× (\d+)", dict(r["fields"])["Item"]).group(1)) for r in records_of(c) if r.get("kind", "record") == "record"}
    fixed = sum((recq.get(r[0], lead_int(r[4]))) for r in dedup if r[5].lower().startswith("shi") and r[5] != "Processing")
    check("arithmetic", "Lesson 2: the recounted figure fixes every fault and matches the checked export",
          field(c, "fix.units")["accept"] == [str(fixed)] and fixed == sum(int(r[4]) for r in ex if r[5] == "Shipped"), fixed)
    check("arithmetic", "Lesson 2: the direction follows from the two figures",
          field(c, "fix.dir")["accept"] == [("under" if summary < fixed else "over" if summary > fixed else "exact")])
    d = stage_by_id(SRC, "l3-a"); calls_ok = True
    for g in d["groups"]:
        sl = next(r for r in g["records"] if r.get("kind") == "table")["rows"]
        cp = int(dict(next(r for r in g["records"] if "ClearPath" in r.get("title", "") and r.get("fields"))["fields"])["Units shipped"])
        ours = sum(int(r[2]) for r in sl if r[3] == "Shipped")
        acc = field(d, g["id"] + ".call")["accept"][0]
        late = any(r[3] == "Shipped" and r[1].startswith("Fri") and time_after_noon(r[1]) for r in sl)
        if (ours == cp) != (acc == "same") or (acc == "cutoff") != (late and ours != cp): calls_ok = False
    check("arithmetic", "Lesson 3: 'they match' exactly where the figures agree, and the cutoff call exactly where a shipment falls after noon", calls_ok)
    e = stage_by_id(SRC, "l4-a"); log = table(e, "Open-items")["rows"]
    gone = {m.group(0) for r in log if "cancelled before pick" in r[1] for m in [re.search(r"#\d{4}", r[1])]}
    live = [r for r in ex if r[5] == "Shipped" and r[0] not in gone]
    check("arithmetic", "Lesson 4: the week's totals carry the log's correction forward",
          field(e, "vol.orders")["accept"] == [str(len({r[0] for r in live}))] and field(e, "vol.units")["accept"] == [str(sum(int(r[4]) for r in live))])
    stock = table(e, "Stock")["rows"]
    check("arithmetic", "Lesson 4: stockouts are exactly the rows at zero available, inbound or not",
          sorted(field(e, "stock.out")["accept"][0]) == sorted(r[0].split()[0].replace("-", "").lower() for r in stock if r[1] == "0"))
    check("arithmetic", "Lesson 4: only the log's still-open entry counts as an open discrepancy",
          len([r for r in log if r[3].startswith("Open")]) == 1 and len(field(e, "open.disc")["accept"][0]) == 1)

    # ---------- normal flow, completion, work sample ----------
    ctx, pg, errs = fresh(br); goto(pg, M9)
    check("page", "desk bar shows Fri, Sep 25 and the task count", pg.text_content("#deskDate") == "Fri, Sep 25" and pg.inner_text("#lessonKicker") == "Task 1 of 4")
    check("page", "page states the Spreadsheet Basics prerequisite and that no formulas are needed", "Spreadsheet Basics" in pg.inner_text("main") and "No formulas" in pg.inner_text("main"))
    for ti, t in enumerate(TASKS):
        goto(pg, M9 + "#task-%d" % (ti + 1), 1); ok = True
        for st in t["stages"]:
            solve(pg, st)
            if not pg.is_enabled("#btnNext"): ok = False; break
            pg.click("#btnNext"); pg.wait_for_timeout(60)
        check("flow", "task %d completes through the UI" % (ti + 1), ok)
    prog = pg.evaluate("JSON.parse(localStorage.getItem('pva-ecom-ft-progress'))")
    check("progress", "verified work marks all four lessons in the legacy progress store", all(prog["lessons"].get(i) for i in IDS))
    check("flow", "completion banner", "Module 9 complete" in pg.inner_text("#doneBanner"))
    keys = pg.evaluate("Object.keys(localStorage).sort()")
    check("isolation", "only the Module 9 desk key and the legacy progress key are written", keys == [KEY, "pva-ecom-ft-progress"], keys)
    vw = pg.evaluate("PVADesk.verifiedWork()")
    check("verified-work", "verifiedWork() reports all four tasks verified and the one earned sample",
          all(v["verified"] for v in vw.values()) and vw["m9-l10"]["samplesEarned"] == ["l4-a"] and
          not any(v["samplesEarned"] for k, v in vw.items() if k != "m9-l10"), vw)
    goto(pg, BASE + "/index.html")
    card = pg.locator(".module-card").nth(8).inner_text()
    check("progress", "course map shows Module 9 (working title) Completed", "Operational Data: Verify Before You Report" in card and "Completed" in card, card)
    goto(pg, M9 + "#task-4", 1)
    ev = pg.locator(".ws-preview").inner_text() if pg.locator(".ws-preview").count() else ""
    check("work-sample", "Operations Tracker survives reload with an honest training header",
          ev.startswith("TRAINING WORK SAMPLE\nEverfield Goods — Operations Tracker (Weekly Summary)") and "fictional company" in ev and
          "Work date: Fri, Sep 25 (simulated)" in ev and "Maya Collins" in ev and "human review" in ev, ev[:300])
    check("work-sample", "the sample keeps the three tracker headings",
          all(h in ev for h in ["Overall volume this week", "Any stockouts or inventory issues", "What's still open or flagged for next week"]))
    check("work-sample", "the sample prints the typed figures with their units",
          ("Orders shipped: " + field(e, "vol.orders")["accept"][0] + " orders") in ev and ("Units shipped: " + field(e, "vol.units")["accept"][0] + " units") in ev, ev[:500])
    check("flow", "no JS errors", not errs, errs)
    ctx.close()

    # ---------- evidence gate (every stage) ----------
    ctx, pg, _ = fresh(br)
    for ti, st in ALL:
        to_stage(pg, ti, st["id"]); r = panel(pg)
        if st["type"] == "compose":
            gated = r.locator("section.desk-group select, section.desk-group input, section.desk-group textarea").first.is_disabled() and all(x.is_disabled() for x in r.locator(".desk-selfcheck input").all())
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
            co = option_text(st, correct_option(st))
            if co in fb: leaks.append(co)
            check("feedback-safety", "%s: feedback reveals no correct finding or option" % st["id"], not leaks, leaks)
        retry = r.get_by_role("button", name="Reconsider and try again")
        if retry.count(): retry.click(); pg.wait_for_timeout(30)
        fail_once(pg, st)
        paused = r.locator(".desk-pause").count() == 1 and r.locator(".desk-evidence-card.is-recheck").count() >= 1
        blocked = (r.get_by_role("button", name="Reconsider and try again").is_disabled() if st["type"] == "decision"
                   else r.locator(".desk-actions button").first.is_disabled())
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
    to_stage(pg, 0, "l1-b"); open_all(pg); st = b
    def try_cost(**over):
        v = compose_values(st, m9_text); v.update(over)
        fill_compose(pg, st, v); confirm_all(pg); submit(pg)
        ok = pg.is_enabled("#btnNext"); fbx = fb_text(pg)
        if ok: revise(pg)
        else: open_all(pg)
        return ok, fbx
    cost = field(st, "cost.total")["accept"][0]; u101 = field(st, "cost.u101")["accept"][0]
    for fmt in ["$" + cost, " " + cost + " ", "$ " + cost, cost + "0"]:
        check("numbers", "equivalent entry %r of the right cost passes" % fmt, try_cost(**{"cost.total": fmt})[0])
    check("numbers", "a whole number typed with '.0' passes ('%s.0')" % u101, try_cost(**{"cost.u101": u101 + ".0"})[0])
    for bad, why in [("%.2f" % (float(cost) + 0.01), "one cent off"), ("%.2f" % (float(cost) - 1), "a dollar off")]:
        ok, fbx = try_cost(**{"cost.total": bad})
        check("numbers", "a cost %s fails" % why, not ok and "What those units cost" in fbx, fbx[:160])
        check("numbers", "the miss never states the value or a direction (%s)" % why, cost not in fbx and not NO_DIRECTION.search(fbx), fbx[:200])
    for bad in [cost + "5", cost.replace(".", ","), "eighty-five", cost + " dollars", "", u101 + ".5"]:
        target = "cost.u101" if bad.endswith(".5") and bad.startswith(u101) else "cost.total"
        ok, fbx = try_cost(**{target: bad})
        check("numbers", "malformed entry %r is refused with a format message, never rounded into a pass" % bad, not ok and "digits only" in fbx, fbx[:160])
    ok, fbx = try_cost(**{"cost.u101": "-" + u101})
    check("numbers", "a negative count fails", not ok)
    meaning = field(st, "cost.means")
    check("numbers", "the right cost with the wrong meaning fails", not try_cost(**{"cost.means": first_unaccepted(meaning)})[0])
    check("numbers", "the right meaning with a wrong cost fails", not try_cost(**{"cost.total": "%.2f" % (float(cost) + 1)})[0])
    # transfer: reusing stage A's approach (count orders, not units) fails on stage B
    orders101 = str(len({r[0] for r in ex if r[3] == "EF-101" and r[5] == "Shipped"}))
    check("transfer", "l1-b: counting EF-101 orders (stage A's approach) instead of units fails", orders101 != u101 and not try_cost(**{"cost.u101": orders101})[0])
    # common slips each give a different, failing figure
    with_proc = str(sum(int(r[4]) for r in ex if r[3] == "EF-101" and r[5] != "Cancelled"))
    check("numbers", "including Processing lines fails", not try_cost(**{"cost.u101": with_proc})[0])
    one_cost = "%.2f" % ((int(u101) + int(field(st, "cost.u105")["accept"][0])) * costs["EF-101"])
    check("numbers", "one unit cost for both SKUs fails", not try_cost(**{"cost.total": one_cost})[0])
    dom = pg.content()
    check("leakage", "no typed answer sits in the DOM before a correct submission", 'value="' + cost + '"' not in dom)
    # Lesson 1A: rows-as-orders and the units-for-orders swap fail; right numbers + wrong meaning fails
    to_stage(pg, 0, "l1-a"); revise(pg); open_all(pg); st = a
    def try_a(**over):
        v = compose_values(st, m9_text); v.update(over)
        fill_compose(pg, st, v); confirm_all(pg); submit(pg); okk = pg.is_enabled("#btnNext")
        if okk: revise(pg)
        else: open_all(pg)
        return okk
    check("numbers", "l1-a: counting Tuesday's rows instead of orders fails", not try_a(**{"tue.orders": str(len(tue))}))
    check("numbers", "l1-a: entering units where orders were asked fails", not try_a(**{"tue.orders": field(st, "tue.units")["accept"][0]}))
    check("numbers", "l1-a: right numbers, wrong figure for the buyer fails", not try_a(**{"tue.answer": first_unaccepted(field(st, "tue.answer"))}))
    # Lesson 2B: the export's own total is not the recount; right number + wrong direction fails
    to_stage(pg, 1, "l2-b"); open_all(pg); st = c
    def try_c(**over):
        v = compose_values(st, m9_text); v.update(over)
        fill_compose(pg, st, v); confirm_all(pg); submit(pg); okk = pg.is_enabled("#btnNext")
        if okk: revise(pg)
        else: open_all(pg)
        return okk
    check("numbers", "l2-b: re-entering the export's summary total fails", not try_c(**{"fix.units": str(summary)}))
    check("numbers", "l2-b: fixing only the repeated line fails", not try_c(**{"fix.units": str(summary - 1)}))
    check("numbers", "l2-b: right figure, wrong direction fails", not try_c(**{"fix.dir": next(o["value"] for o in field(st, "fix.dir")["options"] if o["value"] not in field(st, "fix.dir")["accept"] and o["value"] != "exact")}))
    # Lesson 4: counting the cancelled-but-Shipped order fails
    to_stage(pg, 3, "l4-a"); open_all(pg); st = e
    def try_e(**over):
        v = compose_values(st, m9_text); v.update(over)
        fill_compose(pg, st, v); confirm_all(pg); submit(pg); okk = pg.is_enabled("#btnNext")
        if okk: revise(pg)
        else: open_all(pg)
        return okk
    stale_units = str(sum(int(r[4]) for r in ex if r[5] == "Shipped"))
    check("numbers", "l4-a: counting the order the log shows cancelled fails", not try_e(**{"vol.units": stale_units}))
    def sku_value(row): return row[0].split()[0].replace("-", "").lower()
    inbound_out = next(sku_value(r) for r in stock if r[1] == "0" and r[3] != "0")
    few_left = next(sku_value(r) for r in stock if r[1] not in ("0",) and int(r[1]) <= 3)
    so, dsc, flg = field(st, "stock.out"), field(st, "open.disc"), field(st, "open.flags")
    check("numbers", "l4-a: a SKU at zero available with stock inbound is still a stockout", not try_e(**{"stock.out": [v for v in so["accept"][0] if v != inbound_out]}))
    check("numbers", "l4-a: a SKU with a few units left is not a stockout", not try_e(**{"stock.out": so["accept"][0] + [few_left]}))
    closed = next(o["value"] for o in dsc["options"] if o["value"] not in dsc["accept"][0] and "cancelled" in o["label"])
    check("numbers", "l4-a: calling a closed item an open discrepancy fails", not try_e(**{"open.disc": dsc["accept"][0] + [closed]}))
    timing = next(o["value"] for o in flg["options"] if "timing" in o["label"])
    check("numbers", "l4-a: flagging the timing difference for ClearPath fails", not try_e(**{"open.flags": flg["accept"][0] + [timing]}))
    check("numbers", "l4-a: every accepted set of flags passes", len(flg["accept"]) > 1 and all(try_e(**{"open.flags": list(x)}) for x in flg["accept"]))
    ctx.close()

    # ---------- decisions: transfer and principle-only feedback ----------
    ctx, pg, _ = fresh(br)
    for ti, st in ALL:
        if st["type"] != "decision": continue
        to_stage(pg, ti, st["id"]); open_all(pg)
        answer_decision(pg, st, findings=correct_findings(st)[:-1])
        check("transfer", "%s: right action without the full reading of the evidence fails" % st["id"], not pg.is_enabled("#btnNext"))
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
    # compose: a wrong call names no category
    to_stage(pg, 2, "l3-a"); revise(pg); open_all(pg); st = d
    v = compose_values(st, m9_text)
    for f in st["fields"]: v[f["id"]] = first_unaccepted(f)
    fill_compose(pg, st, v); confirm_all(pg); submit(pg); fbx = fb_text(pg)
    labels = [o["label"] for o in st["fields"][0]["options"]]
    check("feedback-principle", "l3-a: a wrong call's feedback points at the evidence and names no category", not pg.is_enabled("#btnNext") and not [l for l in labels if l.lower() in fbx.lower()], fbx[:200])
    ctx.close()

    # ---------- shortcut attempts, derived completion, work sample, the note ----------
    ctx, pg, _ = fresh(br); goto(pg, M9)
    pg.evaluate("""localStorage.setItem('%s', JSON.stringify({v:1,tasks:{'m9-l10':{completed:true,verified:true,views:1,
      stages:{'l4-a':{passed:true,answer:{values:{},confirms:[true,true]}}},drafts:{'l4-a:v':{'open.note':'x'}}}}}))""" % KEY)
    goto(pg, M9 + "#task-4")
    st4 = pg.evaluate("PVADesk.taskStatus(PVADesk.decode(window.PVA_DESK_MODULES.m9.payload).tasks[3])")
    check("integrity", "forged completed/verified/passed flags count for nothing", st4["passed"] == 0, st4)
    check("integrity", "forged state never reaches the legacy progress store", not (pg.evaluate("JSON.parse(localStorage.getItem('pva-ecom-ft-progress')||'{}')").get("lessons") or {}).get("m9-l10"))
    goto(pg, M9 + "#task-4", 1)
    check("work-sample", "no work sample exists before the work verifies", panel(pg).locator(".ws-preview").count() == 0)
    open_all(pg); st = e
    fill_compose(pg, st, compose_values(st, m9_text)); confirm_all(pg)
    panel(pg).get_by_label(number_label(field(st, "vol.orders")), exact=True).fill("1")
    check("self-check", "changing work after confirming clears the confirmations", not any(x.is_checked() for x in panel(pg).locator(".desk-selfcheck input").all()))
    def note(text):
        v = compose_values(st, m9_text); v["open.note"] = text
        fill_compose(pg, st, v); confirm_all(pg); submit(pg)
        okk = pg.is_enabled("#btnNext"); fbx = fb_text(pg)
        if okk: revise(pg)
        else: open_all(pg)
        return okk, fbx
    out_skus = [label_of(field(st, "stock.out"), x).split(" ")[0] for x in field(st, "stock.out")["accept"][0]]
    disc_sku = label_of(field(st, "open.disc"), field(st, "open.disc")["accept"][0][0]).split(":")[0]
    disc_order = re.search(r"#\d{4}", label_of(field(st, "open.disc"), field(st, "open.disc")["accept"][0][0])).group(0)
    closed_order = re.search(r"#\d{4}", next(o["label"] for o in field(st, "open.disc")["options"] if "cancelled" in o["label"])).group(0)
    late_sku = next(o["label"] for o in field(st, "open.disc")["options"] if "cutoff" in o["label"]).split(":")[0]
    S = " and ".join(out_skus)
    TERSE = [
        "%s out of stock. %s gap still with ClearPath." % (S, disc_sku),
        "Stockouts: %s. Open: %s on %s, waiting on Marcus." % (S, disc_sku, disc_order),
        "%s are at zero available; one has stock inbound. The only open item is the %s gap, which Maya raised with ClearPath." % (S, disc_sku),
        "%s isn't resolved yet and is with ClearPath. %s sold out this week." % (disc_sku, S),
        "%s at zero. %s timing difference needs no action; %s is still open with ClearPath." % (S, late_sku, disc_sku),
    ]
    for t in TERSE:
        check("l4-note", "terse but accurate note passes: %r" % t[:60], note(t)[0])
    BAD = [
        ("guesses a cause", "%s out of stock. ClearPath probably lost the %s units." % (S, disc_sku)),
        ("blames without evidence", "%s out of stock. The %s gap is ClearPath's mistake." % (S, disc_sku)),
        ("calls a closed item open", "%s out of stock. %s is open with ClearPath and %s is still open too." % (S, disc_sku, closed_order)),
        ("wants the timing raised", "%s out of stock. %s is open. Please raise the %s timing difference with Marcus as well." % (S, disc_sku, late_sku)),
        ("calls the open item settled", "%s out of stock. The %s gap is resolved now." % (S, disc_sku)),
        ("says ClearPath confirmed", "%s out of stock. ClearPath confirmed the %s units shipped." % (S, disc_sku)),
        ("adds a stockout the list doesn't have", "%s out of stock, and EF-107 is out of stock too. %s is open." % (S, disc_sku)),
        ("denies any stockout", "No stockouts this week. %s gap is open with ClearPath for now." % disc_sku),
        ("leaves out the open item", "Shipped well this week overall. %s are out of stock and need a restock." % S),
        ("leaves out the stockouts", "A good week for orders overall. The %s gap is still open with ClearPath." % disc_sku),
        ("keyword salad", "%s %s %s clearpath open gap stockout" % (out_skus[0], out_skus[-1], disc_sku)),
    ]
    for why, t in BAD:
        okk, fbx = note(t)
        check("l4-note", "a note that %s is rejected" % why, not okk, t)
    okk, fbx = note("A good week for orders overall. The " + disc_sku + " gap is still open with ClearPath.")
    check("l4-note", "note feedback names the principle, never the words to type", not okk and not any(sk.lower() in fbx.lower() for sk in out_skus), fbx[:200])
    ctx.close()

    # ---------- answer encoding / leakage ----------
    ctx, pg, _ = fresh(br)
    shipped = "".join(pg.request.get(BASE + uu).text() for uu in ["/module-9/index.html", "/module-9/desk-data.js", "/shared/workdesk.js", "/shared/workdesk-ui.js", "/shared/workdesk-page.js", "/shared/everfield-data.js"])
    markers = ['"correct"', "correct: true", '"accept"', '"answer":', '"correctOrder"']
    check("leakage", "no plaintext answer markers in any shipped engine or content file", not any(m in shipped for m in markers), [m for m in markers if m in shipped])
    texts = [option_text(s, correct_option(s)) for _, s in ALL if s["type"] == "decision"]
    check("leakage", "no correct option text appears in shipped source", not any(t in shipped for t in texts))
    check("leakage", "the cost answer appears nowhere in shipped source", cost not in shipped)
    goto(pg, M9 + "#task-2", 1); open_all(pg)
    dom = pg.content()
    check("leakage", "rendered DOM carries no correctness attributes before submission", not re.search(r'(class|data-[a-z-]+)="[^"]*(correct|answer|right)', dom))
    vals_dom = []
    for ti in range(len(TASKS)):
        goto(pg, M9 + "#task-%d" % (ti + 1), 1); open_all(pg)
        vals_dom += pg.evaluate("Array.from(document.querySelectorAll('#stagePanel input,#stagePanel option')).map(e=>e.value)")
    check("leakage", "no control value names the answer (correct/right/wrong, fact/distractor prefixes)",
          not [x for x in vals_dom if re.match(r"^(correct|right|wrong|[fx]_)", x)], vals_dom)
    dec = pg.evaluate("JSON.stringify(PVADesk.decode(window.PVA_DESK_MODULES.m9.payload))")
    check("leakage", "no option, finding or value id names the answer",
          not re.search(r'"(id|value)":"(correct|right|wrong|[fx]_[a-z]+)"', dec), re.findall(r'"(?:id|value)":"(?:correct|right|wrong|[fx]_[a-z]+)"', dec)[:5])
    check("leakage", "decoded payload holds hashed keys only", '"correct"' not in dec and '"accept"' not in dec and '"answer"' not in dec)
    other = " ".join(str(decode(m)) for m in ("module-4", "module-7"))
    check("isolation", "Module 4 and Module 7 content carry no Module 9 orders or tracking", not re.search(r"#54[5-6]\d|CP-7731-06", other))
    ctx.close()

    # ---------- persistence ----------
    ctx, pg, _ = fresh(br)
    to_stage(pg, 0, "l1-a"); open_all(pg)
    panel(pg).get_by_label(number_label(field(a, "tue.units")), exact=True).fill("4 2")
    pg.reload(); pg.wait_for_timeout(150); pg.click("#btnNext"); pg.wait_for_timeout(80)
    check("persistence", "a typed number survives an immediate refresh", panel(pg).get_by_label(number_label(field(a, "tue.units")), exact=True).input_value() == "4 2")
    check("persistence", "opened evidence survives refresh", panel(pg).locator(".desk-ev-head button[aria-expanded='false']").count() == 0)
    to_stage(pg, 3, "l4-a"); open_all(pg)
    panel(pg).locator("textarea").first.fill("Draft text that must survive an instant refresh")
    pg.reload(); pg.wait_for_timeout(150); pg.click("#btnNext"); pg.wait_for_timeout(80)
    check("persistence", "typed note survives an immediate refresh", "must survive" in panel(pg).locator("textarea").first.input_value())
    ctx.close()

    # ---------- legacy progress compatibility (I1-a) ----------
    ctx, pg, _ = fresh(br); goto(pg, BASE + "/index.html")
    legacy = {"lessons": {"m9-l%d" % i: True for i in range(1, 11)}, "modules": {}}
    pg.evaluate("v => localStorage.setItem('pva-ecom-ft-progress', JSON.stringify(v))", legacy)
    goto(pg, M9 + "#task-1")
    check("legacy", "descendant lessons keep their checkmarks (m9-l3, m9-l9, m9-l10); the new m9-l11 has none",
          pg.locator(".lesson-pill.done").count() == 3 and "done" not in (pg.locator(".lesson-pill").nth(2).get_attribute("class") or ""))
    check("legacy", "the status line separates legacy completion from new work", "earlier version" in pg.inner_text("#taskStatus"))
    vw = pg.evaluate("PVADesk.verifiedWork()")
    check("legacy", "legacy completion is not verified work", not any(v["verified"] for v in vw.values()) and not any(v["samplesEarned"] for v in vw.values()))
    pg.click("#btnNext"); solve(pg, a)
    check("legacy", "desk work never rewrites legacy progress", pg.evaluate("JSON.parse(localStorage.getItem('pva-ecom-ft-progress'))")["lessons"] == {**legacy["lessons"]} or
          all(pg.evaluate("JSON.parse(localStorage.getItem('pva-ecom-ft-progress'))")["lessons"].get(k) for k in legacy["lessons"]))
    goto(pg, BASE + "/index.html")
    st9 = pg.locator(".module-status").nth(8).inner_text()
    check("legacy", "course map counts old Module 9 completion against the four listed lessons (new Lesson 3 still to do)", st9 == "3 of 4 lessons done", st9)
    ctx.close()

    # ---------- module isolation and shared authored state ----------
    ctx, pg, _ = fresh(br)
    goto(pg, M7 + "#task-1", 1); m7st = decode("module-7")["tasks"][0]["stages"][0]
    open_all(pg); answer_triage(pg, m7st)
    to_stage(pg, 0, "l1-a"); solve(pg, a)
    keys = pg.evaluate("Object.keys(localStorage).sort()")
    check("isolation", "Module 7 and Module 9 keep separate desk keys", keys == ["pva-ecom-ft-m7-desk", KEY, "pva-ecom-ft-progress"], keys)
    m7store = pg.evaluate("JSON.parse(localStorage.getItem('pva-ecom-ft-m7-desk'))")
    check("isolation", "Module 9 work writes nothing into Module 7's store", list(m7store["tasks"].keys()) == ["m7-l1"], list(m7store["tasks"].keys()))
    goto(pg, M9)
    mut = pg.evaluate("(()=>{try{EVERFIELD.calendar.m9.date='Y'; EVERFIELD.productFacts['EF-101'].unitCost='$0';}catch(e){} return [EVERFIELD.calendar.m9.date, EVERFIELD.productFacts['EF-101'].unitCost]})()")
    check("everfield", "shared Everfield reference cannot be mutated from Module 9", mut == ["Fri, Sep 25", "$4.20"], mut)
    clash = pg.evaluate("(()=>{try{PVADeskCore.createDesk({moduleId:'m10',salt:'x',storageKey:'%s'});return 'created'}catch(e){return e.message}})()" % KEY)
    check("isolation", "another module cannot take Module 9's storage key", "already used" in clash, clash)
    ctx.close()

    # ---------- keyboard + accessibility basics ----------
    ctx, pg, _ = fresh(br); goto(pg, M9 + "#task-1")
    def tab_until(js, limit=200):
        for _ in range(limit):
            pg.keyboard.press("Tab")
            if pg.evaluate(js): return True
        return False
    tab_until("document.activeElement.id==='btnNext'"); pg.keyboard.press("Enter"); pg.wait_for_timeout(80)
    pg.evaluate("document.activeElement.blur()")
    opened = 1 if tab_until("document.activeElement.getAttribute('aria-expanded')==='false'") else 0
    if opened: pg.keyboard.press("Enter")
    want = {number_label(field(a, "tue.orders")): field(a, "tue.orders")["accept"][0], number_label(field(a, "tue.units")): field(a, "tue.units")["accept"][0]}
    typed = 0
    for _ in range(80):
        pg.keyboard.press("Tab")
        info = pg.evaluate("(()=>{var x=document.activeElement;return {tag:x.tagName,label:x.labels&&x.labels[0]?x.labels[0].innerText:'',type:x.type,text:x.innerText}})()")
        if info["tag"] == "INPUT" and info["label"] in want: pg.keyboard.type(want[info["label"]]); typed += 1
        if info["tag"] == "SELECT":
            for _ in range(8):
                if pg.evaluate("document.activeElement.value") == field(a, "tue.answer")["accept"][0]: break
                pg.keyboard.press("ArrowDown")
        if info["type"] == "checkbox": pg.keyboard.press("Space")
        if info["tag"] == "BUTTON" and info["text"].startswith("Send"): pg.keyboard.press("Enter"); break
    pg.wait_for_timeout(80)
    check("keyboard", "open evidence, type numbers and submit using the keyboard", opened == 1 and typed == 2 and pg.is_enabled("#btnNext"), (opened, typed))
    for ti, st in ALL:
        to_stage(pg, ti, st["id"]); open_all(pg)
        unnamed = pg.evaluate("""Array.from(document.querySelectorAll('#stagePanel select,#stagePanel input,#stagePanel textarea,#stagePanel button')).filter(e=>{var n=(e.labels&&e.labels.length)||e.getAttribute('aria-label')||e.getAttribute('aria-labelledby')||(e.tagName==='BUTTON'&&e.innerText.trim());return !n}).length""")
        if unnamed: check("a11y", "%s: every control has an accessible name" % st["id"], False, unnamed)
    check("a11y", "every control in every stage has an accessible name", not any(r for r in results if r[0] == "a11y" and not r[2]))
    goto(pg, M9 + "#task-1", 1); open_all(pg)
    check("a11y", "number inputs: text type, numeric inputmode, unit in the accessible name",
          pg.evaluate("Array.from(document.querySelectorAll('#stagePanel input.desk-number')).every(i=>i.type==='text'&&i.inputMode==='numeric'&&/\\(\\w+\\)$/.test(i.labels[0].innerText))"))
    check("a11y", "evidence toggles expose aria-expanded and aria-controls",
          pg.evaluate("Array.from(document.querySelectorAll('.desk-ev-head button')).every(b=>b.hasAttribute('aria-expanded')&&b.hasAttribute('aria-controls'))"))
    for n in (1, 3, 4):
        goto(pg, M9 + "#task-%d" % n); check("deep-link", "#task-%d opens task %d" % (n, n), pg.inner_text("#lessonKicker") == "Task %d of 4" % n)
    ctx.close()

    # ---------- contrast, sticky top bar ----------
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
    goto(pg, M9 + "#task-1"); low += pg.evaluate(CONTRAST)
    pg.click("#btnNext"); pg.wait_for_timeout(60); low += pg.evaluate(CONTRAST); open_all(pg); low += pg.evaluate(CONTRAST)
    fail_once(pg, a); low += pg.evaluate(CONTRAST)
    to_stage(pg, 1, "l2-a"); st = stage_by_id(SRC, "l2-a"); fail_once(pg, st); low += pg.evaluate(CONTRAST)
    panel(pg).get_by_role("button", name="Reconsider and try again").click(); fail_once(pg, st); low += pg.evaluate(CONTRAST)
    to_stage(pg, 2, "l3-a"); open_all(pg); low += pg.evaluate(CONTRAST)
    to_stage(pg, 3, "l4-a"); open_all(pg); solve(pg, e); low += pg.evaluate(CONTRAST)
    check("contrast", "all enabled text meets WCAG AA (4.5:1, 3:1 large) in brief, evidence, feedback, pause, compose and work-sample states", not low, sorted(set(low))[:8])
    ctx.close()
    STICKY = """() => { var top=document.querySelector('.topbar').getBoundingClientRect().bottom;
     var els=Array.from(document.querySelectorAll('#stagePanel select,#stagePanel input,#stagePanel textarea,#stagePanel button,#btnNext,#btnPrev')).filter(e=>e.offsetParent);
     return els.filter(e=>{ e.scrollIntoView({block:'start', behavior:'instant'}); return e.getBoundingClientRect().top < top-1; }).length; }"""
    for w in (320, 375):
        ctx, pg, _ = fresh(br, viewport={"width": w, "height": 700}, is_mobile=True, has_touch=True)
        hidden = 0
        for ti, sid in [(0, "l1-b"), (2, "l3-a"), (3, "l4-a")]:
            to_stage(pg, ti, sid); open_all(pg); hidden += pg.evaluate(STICKY)
        check("sticky", "%dpx: no control is left under the sticky top bar when navigated to (scroll-padding)" % w, hidden == 0, hidden)
        ctx.close()

    # ---------- mobile ----------
    for w in (320, 375):
        ctx, pg, _ = fresh(br, viewport={"width": w, "height": 812}, device_scale_factor=2, is_mobile=True, has_touch=True)
        for ti, sid in [(0, "l1-a"), (0, "l1-b"), (1, "l2-a"), (2, "l3-a"), (2, "l3-b"), (3, "l4-a")]:
            to_stage(pg, ti, sid); open_all(pg); pg.wait_for_timeout(60)
            ov = pg.evaluate("document.documentElement.scrollWidth - window.innerWidth")
            check("mobile", "%s: no horizontal overflow at %dpx" % (sid, w), ov <= 0, ov)
        if w == 320: ctx.close()
    wraps = pg.evaluate("Array.from(document.querySelectorAll('.desk-table-wrap')).every(w=>getComputedStyle(w).overflowX!=='visible')")
    check("mobile", "wide tables scroll inside their own region", wraps)
    ctx.close()
    br.close()

fails = [r for r in results if not r[2]]
print("\n%d checks, %d failed" % (len(results), len(fails)))
sys.exit(1 if fails else 0)
