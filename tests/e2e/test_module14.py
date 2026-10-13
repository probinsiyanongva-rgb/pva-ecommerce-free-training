"""Module 14 (capstone) Work Desk regression + adversarial suite (browser), modelled on Modules 11-13.

Run from the repo root with a static server on :8765 (see tests/README.md):
    python3 tests/e2e/test_module14.py
Answers come from decoding the shipped content at run time. The recompute checks derive every
Monday call from its card, every return/exception call from its record, the Friday counts from the
export and returns tables, and the open items from the open-items log. The transfer checks prove no
capstone case or accepted answer repeats an earlier module's. Nothing answer-bearing is stored here."""
import os, sys, re, json, subprocess
from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from desk_helpers import *  # noqa

SRC = decode("module-14")
M14 = BASE + "/module-14/index.html"
M13 = BASE + "/module-13/index.html"
TASKS = SRC["tasks"]
IDS = [t["id"] for t in TASKS]
ALL = [(ti, s) for ti, t in enumerate(TASKS) for s in t["stages"]]
KEY = "pva-ecom-ft-m14-desk"
DATA = json.loads(subprocess.run(["node", "-e", "process.stdout.write(JSON.stringify(require('./shared/everfield-data.js')))"], cwd=ROOT, capture_output=True, text=True).stdout)
HR = "This course checks required facts, decisions, and structure against defined criteria. Use your judgment to evaluate the quality of the work you produce."
results = []


def check(area, name, cond, detail=""):
    results.append((area, name, bool(cond), str(detail)))
    print(("PASS " if cond else "FAIL ") + "[" + area + "] " + name + ((" -- " + str(detail)[:220]) if detail and not cond else ""))


def field(st, fid): return next(f for f in st["fields"] if f["id"] == fid)
def label_of(f, v): return next(o["label"] for o in f["options"] if o["value"] == v)
def fields_of(rec): return dict((k, v) for k, v in rec.get("fields", []))
def strip(s): return re.sub(r"<[^>]+>", " ", s)
def records_of(st):
    if st["type"] == "decision": return st["records"]
    if st["type"] == "triage": return st["rows"]
    return [r for g in st["groups"] for r in g["records"]]
def rec_text(r):
    parts = [r.get("title", "") or "", r.get("note", ""), r.get("logTitle", ""), r.get("label", "")]
    parts += [str(v) for kv in r.get("fields", []) for v in kv] + list(r.get("log", []))
    parts += [str(c) for row in r.get("rows", []) for c in row] + list(r.get("columns", []))
    parts += [str(v) for kv in r.get("meta", []) for v in kv] + list(r.get("body", [])) + list(r.get("paragraphs", [])) + list(r.get("items", []))
    return " ".join(parts)
def learner_text(task):
    out = [task["title"], task["objective"], task["brief"]["subject"]] + task["brief"]["body"] + [strip(x) for x in task.get("reference", [])]
    for s in task["stages"]:
        out += [s.get("intro", ""), s.get("prompt", ""), s.get("findingsPrompt", ""), s.get("actionPrompt", ""), s.get("now", "")]
        out += [rec_text(r) for r in records_of(s)] + [c["label"] for c in s.get("choices", [])]
        out += [f["text"] for f in s.get("findings", [])] + [o["text"] for o in s.get("options", [])]
        for f in s.get("fields", []): out += [f["label"]] + [o["label"] for o in f.get("options", [])]
    return " ".join(out)

Q1, D1 = stage_by_id(SRC, "t1-a"), stage_by_id(SRC, "t1-b")
R2, B2, C2 = stage_by_id(SRC, "t2-a"), stage_by_id(SRC, "t2-b"), stage_by_id(SRC, "t2-c")
A3, P3 = stage_by_id(SRC, "t3-a"), stage_by_id(SRC, "t3-b")
EVERY = " ".join(learner_text(t) for t in TASKS)
TEXTS = {
 "note.text": "Order #5557's EF-102 labels arrived creased and torn, with photos. A refund or replacement is your decision, and the customer has been told it's with you. I gave Maya the three damage reports as a possible pattern.",
 "sum.text": "We shipped 9 orders and received 4 returns this week. #5567 still hasn't shipped and is with Maya, EF-104 is below its alert level, and a bulk buyer's price request is waiting for you.",
 "ov.text": "This portfolio shows my training work on Everfield Goods, a simulated company used in PVA Free Training. It covers product data, listings, orders, inventory, customer support and reporting. These are training work samples, not paid client work."}


def vals_for(st, **over):
    v = {}
    for f in st["fields"]:
        if f["type"] == "text": v[f["id"]] = TEXTS[f["id"]]
        elif "accept" in f: v[f["id"]] = list(f["accept"][0]) if f["type"] == "multi" else f["accept"][0]
        elif f["type"] == "multi": v[f["id"]] = [o["value"] for o in f["options"][:3]]
        else: v[f["id"]] = f["options"][0]["value"]
    v.update(over)
    return v


def solve(pg, st):
    open_all(pg)
    if st["type"] == "decision": answer_decision(pg, st)
    elif st["type"] == "triage": answer_triage(pg, st)
    else: fill_compose(pg, st, vals_for(st)); confirm_all(pg); submit(pg)


def fail_once(pg, st):
    open_all(pg)
    if st["type"] == "decision":
        cf = correct_findings(st); answer_decision(pg, st, findings=cf[1:] + distractors(st)[:1], option=(wrong_options(st) or [None])[0])
    elif st["type"] == "triage": answer_triage(pg, st, wrong=True)
    else:
        sel = next(x for x in st["fields"] if x["type"] == "select" and x.get("accept"))
        fill_compose(pg, st, vals_for(st, **{sel["id"]: first_unaccepted(sel)})); confirm_all(pg); submit(pg)


def to_stage(pg, ti, sid):
    goto(pg, M14 + "#task-%d" % (ti + 1), 1)
    for s in TASKS[ti]["stages"]:
        if s["id"] == sid: return
        if not pg.is_enabled("#btnNext"): solve(pg, s)
        pg.click("#btnNext"); pg.wait_for_timeout(60)


def fresh(br, **kw):
    ctx = br.new_context(**kw); pg = ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    return ctx, pg, errs
def fb_text(pg):
    r = panel(pg).locator(".desk-fb"); return r.last.inner_text() if r.count() else ""
def earned(pg): return pg.evaluate("PVADesk.verifiedWork()")["m14-t10"]["samplesEarned"]


def attempt_in(pg, st, confirms=True, **over):
    fill_compose(pg, st, vals_for(st, **over))
    if confirms: confirm_all(pg)
    if panel(pg).locator("button[type=submit]").first.is_disabled(): return False, "submit disabled", earned(pg)
    submit(pg)
    okk = pg.is_enabled("#btnNext"); fbx = fb_text(pg); got = earned(pg)
    b = panel(pg).get_by_role("button", name=re.compile("Revise|Reconsider", re.I))
    if b.count(): b.first.click(); pg.wait_for_timeout(30)
    open_all(pg)
    return okk, fbx, got


def triage_attempt(pg, st, override):
    root = panel(pg); open_all(pg)
    for i, r in enumerate(st["rows"]): root.locator("select.desk-select").nth(i).select_option(override.get(r["id"], r["answer"]))
    root.locator("button[type=submit]").first.click(); pg.wait_for_timeout(60)
    okk = pg.is_enabled("#btnNext")
    if not okk:
        b = root.get_by_role("button", name=re.compile("Reconsider|Try again|Revise", re.I))
        if b.count(): b.first.click(); pg.wait_for_timeout(40)
    return okk


with sync_playwright() as p:
    br = p.chromium.launch()

    # ---------- design ----------
    check("design", "three tasks with the approved ids, in order", IDS == ["m14-t1", "m14-t6", "m14-t10"], IDS)
    check("design", "stage types: triage+decision; triage+decision+compose; compose+compose",
          [[s["type"] for s in t["stages"]] for t in TASKS] == [["triage", "decision"], ["triage", "decision", "compose"], ["compose", "compose"]])
    check("design", "work dates Mon Oct 5 and Wed Oct 7; capstone day Fri Oct 9",
          [t.get("workDate") for t in TASKS] == ["Mon, Oct 5", "Wed, Oct 7", None] and DATA["calendar"]["m14"]["date"] == "Fri, Oct 9" and
          all(s["now"].startswith(TASKS[ti].get("workDate") or "Fri, Oct 9") for ti, s in ALL))
    check("design", "Maya, Sofia, Maya request the three tasks", [t["brief"]["from"] for t in TASKS] == ["maya", "sofia", "maya"])
    check("design", "only Task 3 carries the portfolio piece, earned only by t3-b", [bool(t.get("portfolio")) for t in TASKS] == [False, False, True] and [s["id"] for _, s in ALL if s.get("evidence")] == ["t3-b"])
    check("design", "t3-b declares self-check and human review", len(P3["confirm"]) >= 2 and P3.get("humanReview"))
    check("design", "the timeline fixes the capstone week and drops 'not yet fixed'",
          any(e["date"] == "Mon, Sep 28 - Fri, Oct 9" for e in DATA["timeline"]["entries"]) and not any("not yet fixed" in e["what"] for e in DATA["timeline"]["entries"]))

    # ---------- corrections from the audit ----------
    flow = next(strip(x) for x in TASKS[1]["reference"] if "return flow" in x)
    check("fixes", "return flow has all six steps, inventory action before refund status",
          all(w in flow for w in ("Log the return", "reason", "condition", "disposition", "inventory action", "refund status")) and flow.index("inventory action") < flow.index("refund status"))
    acc2b = option_text(B2, correct_option(B2))
    check("fixes", "P7's two parts: the accepted 2b action documents for Sofia and sends the pattern to Maya, removing the promise",
          "Sofia" in acc2b and "Maya" in acc2b and "pattern" in acc2b and "promise" in acc2b)
    check("fixes", "2c grades Sofia as the one who decides and the pattern to Maya", field(C2, "case.decides")["accept"] == ["sofia"] and field(C2, "case.pattern")["accept"] == ["maya"])
    check("fixes", "no EF-106 count anywhere, and no 'correct it to match' an EF-106 count",
          not re.search(r"(EF-106|Closet Divider)(?:(?!EF-\d{3})[^.]){0,80}\b(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)[- ]?(?:[a-z]+ ){0,2}(?:pack|pieces?|dividers)\b", EVERY, re.I) and "Correct it to match" not in EVERY)
    pieces = next(r for r in records_of(P3) if r["id"] == "g-list")
    check("fixes", "the portfolio checklist has 13 pieces and nothing says '12 work samples'", len(pieces["fields"]) == 13 and "12 individual" not in EVERY and "12 work samples" not in EVERY)

    # ---------- canon ----------
    canon = {}
    for line in open(os.path.join(ROOT, "docs", "everfield-continuity.md"), encoding="utf-8"):
        m = re.match(r"^\| (P\d+) \| (.+?) \| [^|]*\|\s*$", line)
        if m: canon[m.group(1)] = m.group(2)
    pl = re.findall(r"\b(P\d+) · ([^\n]+?)(?=$|\n)", "\n".join(strip(x) for t in TASKS for x in t["reference"]) + "\n" + "\n".join(x for _, s in ALL for r in records_of(s) for x in r.get("items", [])), re.M)
    check("canon", "every policy line quotes the approved clause word for word", pl and all(canon.get(k) == v for k, v in pl), [k for k, v in pl if canon.get(k) != v])
    pol = fields_of(next(r for r in records_of(C2) if r["id"] == "e-pol"))
    check("canon", "2c's clause card quotes the clauses word for word", all(canon[k] == v for k, v in pol.items()))
    q = {r["id"]: fields_of(r) for r in Q1["rows"]}
    check("canon", "EF-107 is a 3-piece set and the kit recipe matches product canon",
          "3-piece set" in q["q1"]["Approved product record"] and "2 × EF-101, 1 × EF-102, 1 × EF-103" in q["q2"]["Approved kit recipe"] and DATA["productFacts"]["EF-200"])
    nums = [int(n) for n in re.findall(r"#(\d{4})", EVERY)]
    check("canon", "orders stay in #5536-#5569, returns in #250-#259, tracking in CP-7731-14xx",
          nums and all(5536 <= n <= 5569 for n in nums) and all(250 <= int(n) <= 259 for n in re.findall(r"#(\d{3})\b", EVERY)) and all(t.startswith("14") for t in re.findall(r"CP-7731-(\d{4})", EVERY)))
    check("canon", "no dollar amounts, marketplace IDs or EF-104 pack count", not re.search(r"\$\s?\d|MKT-\d", EVERY) and not re.search(r"(EF-104|Cable Management Set)[^.]{0,80}\b\d+[- ]?(piece|pieces|pack)\b", EVERY, re.I))
    check("canon", "the AI output is titled 'AI draft · simulated' wherever it appears", all(r["title"].startswith("AI draft · simulated") for _, s in ALL for r in records_of(s) if "ships today" in rec_text(r)))

    # ---------- transfer: new cases only ----------
    old = ["#5310", "#5414", "#5192", "#5502", "#5503", "#5506", "#5515", "#5516", "#5517", "#5518", "#5519"]
    check("transfer", "no earlier lesson's or old capstone's case numbers reappear", not [o for o in old if o in EVERY])
    others = {m: decode("module-%d" % m) for m in (2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13)}
    acc_texts = []
    for m, srcm in others.items():
        for t in srcm["tasks"]:
            for s in t["stages"]:
                acc_texts += [o["text"] for o in s.get("options", []) if o.get("correct")] + [f["text"] for f in s.get("findings", []) if f.get("correct")]
                for f in s.get("fields", []):
                    if f["type"] in ("select", "multi"):
                        for a in f.get("accept", []):
                            for v in (a if isinstance(a, list) else [a]):
                                lbl = next((o["label"] for o in f["options"] if o["value"] == v), "")
                                if len(lbl) > 24 and not re.match(r"^EF-\d{3} [A-Z][\w ]+$", lbl): acc_texts.append(lbl)
    TEAM = [m["name"] + ", " + m["role"] for m in DATA["team"].values()]
    leaks = [x[:60] for x in acc_texts if len(x) > 24 and x in EVERY and x not in TEAM]
    check("transfer", "no graded answer from Modules 2-13 appears in the capstone", not leaks, leaks[:6])
    t3txt = learner_text(TASKS[2])
    check("transfer", "Task 3 never shows a Task 1-2 answer (no EF-103 routing, EF-102 pattern or EF-107 fix in Friday's records)",
          "EF-103" not in t3txt and "EF-102" not in t3txt and "4-Piece" not in t3txt and "#5557" not in t3txt)

    # ---------- recompute from evidence ----------
    def call1(r):
        f = fields_of(r); t = rec_text(r)
        if "Approved product record" in f or "Approved kit recipe" in f: return "fix"
        if "Sofia's approved note" in f: return "ok"
        if "discount" in t.lower(): return "sofia"
        if "Orders waiting for EF-103" in f: return "maya"
        if "Stock card · EF-105" in t: return "answer"
        if "Sofia's approved note" in f: return "ok"
        if f.get("Platform status") == "Shipped" and f.get("Tracking") == "—": return "record"
        if "no scan since" in f.get("Latest carrier event", ""): return "maya"
        if f.get("Platform status") == "Processing" and "picking" in f.get("ClearPath", ""): return "ok"
    got = {r["id"]: call1(r) for r in Q1["rows"]}
    check("recompute", "Monday: every call follows from its card", all(got[r["id"]] == r["answer"] for r in Q1["rows"]), got)
    pr = q["q9"]
    check("recompute", "AUTUMN15 as set up matches Sofia's note (15%, EF-105/EF-107, one per customer, Mon-Sun)",
          "15%" in pr["Discount (as set up)"] and "EF-105, EF-107" in pr["Discount (as set up)"] and pr["Limit (as set up)"] == "1 per customer" and pr["Starts"].startswith("Mon") and pr["Ends"].startswith("Sun"))
    def call2(r):
        f = fields_of(r); t = rec_text(r)
        if f.get("Disposition") == "Restock" and f.get("Condition") == "Unopened": return "p5"
        if f.get("Disposition") == "Inspection Required": return "p6"
        if "keeping them" in t: return "p8"
        if "swap" in t and "0 available" in t: return "p9"
        if "Returned to sender" in t: return "p12"
        if "Delivered" in f.get("Latest carrier event", ""): return "p11"
    got = {r["id"]: call2(r) for r in R2["rows"]}
    check("recompute", "Midweek: every policy call follows from its record", all(got[r["id"]] == r["answer"] for r in R2["rows"]), got)
    exp = next(r for r in records_of(A3) if r["id"] == "f-exp")["rows"]
    shipped = {row[0] for row in exp if row[2] in ("Shipped", "Delivered")}
    rets = next(r for r in records_of(A3) if r["id"] == "f-ret")["rows"]
    check("recompute", "Friday: shipped = distinct shipped/delivered orders; returns = received only",
          field(A3, "num.ship")["accept"] == [str(len(shipped))] and field(A3, "num.ret")["accept"] == [str(len([x for x in rets if x[2].startswith("Received")]))])
    check("recompute", "the export really holds the traps (a duplicate line, a cancellation, unshipped orders)",
          len(exp) - len({r[0] for r in exp}) == 1 and any(r[2] == "Cancelled" for r in exp) and sum(r[2].startswith("Processing") for r in exp) == 2)

    # ---------- flow, completion, sample ----------
    ctx, pg, errs = fresh(br); goto(pg, M14)
    check("page", "desk bar, three tasks and the training note", pg.text_content("#deskDate") == "Mon, Oct 5" and pg.inner_text("#lessonKicker") == "Task 1 of 3" and pg.locator("#trainingNote").is_visible())
    for ti, t in enumerate(TASKS):
        goto(pg, M14 + "#task-%d" % (ti + 1), 1); ok = True
        if t.get("workDate"): check("page", "task %d's desk bar shows its work date" % (ti + 1), pg.text_content("#deskDate") == t["workDate"], pg.text_content("#deskDate"))
        for st in t["stages"]:
            solve(pg, st)
            if not pg.is_enabled("#btnNext"): ok = False; break
            pg.click("#btnNext"); pg.wait_for_timeout(60)
        check("flow", "task %d completes through the UI" % (ti + 1), ok, fb_text(pg)[:200])
    check("flow", "completion banner", "Capstone complete" in pg.inner_text("#doneBanner"))
    prog = pg.evaluate("JSON.parse(localStorage.getItem('pva-ecom-ft-progress'))")
    check("progress", "verified work marks all three lessons", all(prog["lessons"].get(i) for i in IDS))
    vw = pg.evaluate("PVADesk.verifiedWork()")
    check("verified-work", "all three tasks verified, one earned sample (t3-b)", all(v["verified"] for v in vw.values()) and vw["m14-t10"]["samplesEarned"] == ["t3-b"])
    goto(pg, M14 + "#task-3", 2)
    sample = pg.locator(".ws-preview").inner_text() if pg.locator(".ws-preview").count() else ""
    check("work-sample", "the Final Portfolio sample: honest title, label, pieces, overview, and the new shared review line",
          "Final E-commerce VA Portfolio (training work sample)" in sample and "not paid client work" in sample and TEXTS["ov.text"] in sample and HR in sample and "human review at certification" not in sample, sample[-700:])
    goto(pg, BASE + "/index.html")
    check("progress", "course map shows the capstone Completed", "Completed" in pg.locator(".module-card").nth(13).inner_text())
    check("flow", "no JS errors", not errs, errs)
    ctx.close()

    for n, sid in ((3, "t3-a"), (2, "t2-a")):
        ctx, pg, errs = fresh(br)
        goto(pg, M14 + "#task-%d" % n, 1); ok = True
        for st in TASKS[n - 1]["stages"]:
            solve(pg, st)
            if not pg.is_enabled("#btnNext"): ok = False; break
            pg.click("#btnNext"); pg.wait_for_timeout(60)
        vw = pg.evaluate("PVADesk.verifiedWork()")
        check("independence", "task %d completes first in fresh storage, other tasks untouched" % n, ok and vw[IDS[n - 1]]["verified"] and sum(v["verified"] for v in vw.values()) == 1, vw)
        ctx.close()

    # ---------- piece 14 earned only by validated work ----------
    ctx, pg, _ = fresh(br)
    to_stage(pg, 2, "t3-b"); open_all(pg)
    okk, fbx, got = attempt_in(pg, P3)
    check("portfolio", "the accepted cover note passes and earns piece 14", okk and got == ["t3-b"], fbx[:200])
    ctx.close(); ctx, pg, _ = fresh(br)
    to_stage(pg, 2, "t3-b"); open_all(pg)
    for why, over in (("a dishonest label", {"lab.label": "client"}), ("a credential label", {"lab.label": "cert"}), ("only two pieces", {"pf.pieces": ["p01", "p02"]}),
                      ("a blank overview", {"ov.text": ""}), ("a filler overview", {"ov.text": "good good good good good good good good good good good good good good good good good good good good good good good good good"})):
        okk, fbx, got = attempt_in(pg, P3, **over)
        check("portfolio", "piece 14 is withheld for %s" % why, not okk and not got, fbx[:120])
    fill_compose(pg, P3, vals_for(P3)); confirm_all(pg)
    boxes = panel(pg).locator(".desk-selfcheck input[type=checkbox]"); blocked = []
    for i in range(boxes.count()):
        boxes.nth(i).uncheck(); pg.wait_for_timeout(30); blocked.append(panel(pg).locator("button[type=submit]").first.is_disabled()); boxes.nth(i).check(); pg.wait_for_timeout(30)
    check("portfolio", "each unticked self-check line blocks submission", blocked and all(blocked) and not earned(pg))
    GOOD = [("plain", "These are training work samples from a simulated company in a free course. They show listings, orders, inventory and reporting work. None of it is paid client work."),
            ("negated claims", "This portfolio is training work on a fictional company, not paid client work and not a credential. It includes my Listing Pack and Order Log. I'm not an expert yet, and these pieces show what I practised.")]
    for why, t in GOOD:
        okk, fbx, _ = attempt_in(pg, P3, **{"ov.text": t}); check("note-3b", "passes -- %s" % why, okk, (t, fbx[:200]))
    BAD = [("claims client work", "I worked for Everfield as their e-commerce VA. These training samples show listings, orders and reporting from that job. They are the work I did there for the team.", "real client work"),
           ("claims to be an expert", "I am an expert e-commerce VA. These training samples show my listings, orders and reporting work. They come from a simulated company in this course.", "credential, experience or results"),
           ("claims results", "These training samples show how I increased sales for a simulated store. They cover listings, orders and reporting work. All of it was done in this course.", "credential, experience or results"),
           ("no skill named", "This is my portfolio from the course, a simulated company. It is training work and I am proud of it. Thank you for looking at it today.", "name at least one skill"),
           ("not labelled as training", "My portfolio shows listings, orders, inventory and reporting work for Everfield Goods. I built each piece carefully. I am proud of every one of them.", "training work on a simulated company")]
    for why, t, want in BAD:
        okk, fbx, got = attempt_in(pg, P3, **{"ov.text": t}); check("note-3b", "rejected -- a note that %s" % why, not okk and not got and want in fbx.lower(), (t, fbx[:220]))
    ctx.close()

    # ---------- the handoff (2c) and the report (3a) ----------
    ctx, pg, _ = fresh(br)
    to_stage(pg, 1, "t2-c"); open_all(pg)
    def att(st, **over):
        fill_compose(pg, st, vals_for(st, **over)); confirm_all(pg); submit(pg)
        okk = pg.is_enabled("#btnNext"); fbx = fb_text(pg)
        b = panel(pg).get_by_role("button", name=re.compile("Revise|Reconsider", re.I))
        if b.count(): b.first.click(); pg.wait_for_timeout(30)
        open_all(pg); return okk, fbx
    for f in [x for x in C2["fields"] if x.get("accept")]:
        bad = first_unaccepted(f) if f["type"] == "select" else ["p7", "p8"]
        okk, _ = att(C2, **{f["id"]: bad}); check("2c", "a wrong %s fails" % f["id"], not okk)
    GOOD2 = [("terse", "#5557 arrived damaged with photos; it's your decision whether to refund or replace. Maya has the three reports as a pattern."),
             ("reports the AI promise was removed", "EF-102 on #5557 arrived torn, photos attached. I removed the replacement promise from the draft, so it's yours to decide. Maya has the pattern.")]
    for why, t in GOOD2:
        okk, fbx = att(C2, **{"note.text": t}); check("2c-note", "passes -- %s" % why, okk, (t, fbx[:200]))
    PROM, CAUSE = "nothing is decided until sofia decides", "don't show what caused"
    BAD2 = [("promises a replacement", "#5557 arrived damaged with photos. A replacement is on its way to her, and Maya has the pattern; it's your decision on anything else.", PROM),
            ("says we offered a refund", "#5557 arrived damaged with photos. I've offered her a refund already, so it's your decision to confirm it. Maya has the pattern.", PROM),
            ("guesses a cause", "#5557 arrived damaged, probably packed badly at ClearPath. It's your decision what to do, and Maya has the pattern.", CAUSE),
            ("leaves Sofia out", "#5557 arrived damaged with photos attached. Maya has the three reports as a pattern now.", "sofia's to decide"),
            ("leaves the pattern out", "#5557 arrived damaged with photos attached. It's your decision whether to refund or replace it.", "went to maya")]
    for why, t, want in BAD2:
        okk, fbx = att(C2, **{"note.text": t}); check("2c-note", "rejected -- a note that %s" % why, not okk and want in fbx.lower(), (t, fbx[:220]))
    to_stage(pg, 2, "t3-a"); open_all(pg)
    for why, over in (("counting the duplicate line", {"num.ship": "10"}), ("counting rows", {"num.shipread": "rows"}), ("counting a label-only return", {"num.ret": "5"}),
                      ("refunds as returns", {"num.retread": "refunds"}), ("#5567 to Sofia", {"work.open": ["n2", "n3", "n5"]}), ("the VA reorders EF-104", {"work.open": ["n1", "n4", "n5"]}),
                      ("reporting a routine return", {"work.open": ["n1", "n3", "n5", "n7"]}), ("claiming unfinished work", {"work.done": ["w1", "w2", "w3", "w4"]})):
        okk, _ = att(A3, **over); check("3a", "the report fails for %s" % why, not okk)
    GOOD3 = [("terse", "Nine orders shipped and four returns came back. #5567 is still open with Maya, and the bulk price request is yours."),
             ("negation", "We shipped 9 orders this week. #5567 hasn't shipped yet and Maya is following it; EF-104 is low and not reordered yet.")]
    for why, t in GOOD3:
        okk, fbx = att(A3, **{"sum.text": t}); check("3a-note", "passes -- %s" % why, okk, (t, fbx[:200]))
    BAD3 = [("guesses a cause", "We shipped 9 orders. #5567 is late, probably because ClearPath is short-staffed this week.", "don't show a cause"),
            ("invents a trend", "We shipped 9 orders, more than last week. Four returns came back this week as well.", "no earlier week"),
            ("says #5567 shipped", "We shipped 9 orders, and #5567 shipped this morning in the end. EF-104 is with Maya.", "contradicts the open-items log"),
            ("says EF-104 was reordered", "We shipped 9 orders this week. EF-104 has been reordered and the bulk request is with you.", "contradicts the open-items log"),
            ("names nothing", "It was a normal week at the store and everything went well. The team handled everything without issue.", "name at least one")]
    for why, t, want in BAD3:
        okk, fbx = att(A3, **{"sum.text": t}); check("3a-note", "rejected -- a summary that %s" % why, not okk and want in fbx.lower(), (t, fbx[:220]))
    ctx.close()

    # ---------- traps ----------
    ctx, pg, _ = fresh(br)
    T1 = [("the listing fix sent to Sofia", {"q1": "sofia"}), ("the kit listing left alone", {"q2": "ok"}), ("the tracking gap sent to Maya", {"q3": "maya"}), ("the stall to Sofia", {"q4": "sofia"}),
          ("the stock question sent on", {"q5": "sofia"}), ("a discount granted by the VA", {"q6": "fix"}), ("EF-103 'fixed' by the VA", {"q7": "fix"}), ("a fine order flagged", {"q8": "record"}), ("the promotion changed", {"q9": "fix"})]
    for why, ov in T1:
        to_stage(pg, 0, "t1-a"); check("traps", "t1-a fails when %s" % why, not triage_attempt(pg, Q1, ov))
    T2 = [("Inspection Required refunded", {"r2": "p5"}), ("a kept item refunded", {"r3": "p5"}), ("an exchange with no stock promised", {"r4": "p12"}), ("missing parcel reshipped", {"r5": "p12"}), ("returned parcel left with the customer", {"r6": "p11"})]
    for why, ov in T2:
        to_stage(pg, 1, "t2-a"); check("traps", "t2-a fails when %s" % why, not triage_attempt(pg, R2, ov))
    ctx.close()
    for st, ti in ((D1, 0), (B2, 1)):
        for wo in wrong_options(st):
            ctx, pg, _ = fresh(br); to_stage(pg, ti, st["id"]); open_all(pg); answer_decision(pg, st, option=wo)
            check("traps", "%s: '%s' fails" % (st["id"], option_text(st, wo)[:50]), not pg.is_enabled("#btnNext")); ctx.close()

    # ---------- gates, feedback, pause ----------
    ctx, pg, _ = fresh(br)
    for ti, st in ALL:
        to_stage(pg, ti, st["id"]); r = panel(pg)
        if st["type"] == "triage": gated = all(x.is_disabled() for x in r.locator("select.desk-select").all())
        elif st["type"] == "compose":
            gated = (all(x.is_disabled() for x in r.locator("section.desk-group select, section.desk-group input").all()) and
                     all(x.get_attribute("readonly") is not None for x in r.locator("section.desk-group textarea").all()) and all(c.is_disabled() for c in r.locator(".desk-selfcheck input").all()))
        else: gated = r.locator(".desk-actions button").first.is_disabled()
        pg.evaluate("document.querySelectorAll('#stagePanel button,#stagePanel select,#stagePanel input,#stagePanel textarea').forEach(e=>e.disabled=false); var b=document.querySelector('#stagePanel .desk-actions button'); b && b.click();")
        pg.wait_for_timeout(40)
        att = pg.evaluate("((JSON.parse(localStorage.getItem('%s'))||{tasks:{}}).tasks['%s']||{stages:{}}).stages['%s']" % (KEY, TASKS[ti]["id"], st["id"]))
        check("evidence-gate", "%s: controls gated and a forced submit refused before evidence is opened" % st["id"], gated and not att, att)
    check("evidence-gate", "every compose group with fields has its own gated card",
          all(any(x.get("kind") != "reference" for x in g["records"]) for _, s in ALL if s["type"] == "compose" for g in s["groups"] if any(f["group"] == g["id"] for f in s["fields"])))
    ctx.close(); ctx, pg, _ = fresh(br)
    for ti, st in ALL:
        to_stage(pg, ti, st["id"]); fail_once(pg, st); fb = fb_text(pg)
        check("feedback", "%s: wrong attempt gets feedback, next stays locked" % st["id"], fb and not pg.is_enabled("#btnNext"), fb[:120])
        leak = []
        if st["type"] == "decision": leak = [option_text(st, correct_option(st))] + [finding_text(st, f) for f in correct_findings(st)]
        if st["type"] == "triage": leak = [next(c["label"] for c in st["choices"] if c["id"] == r["answer"]) + " -- " for r in st["rows"]]
        check("feedback", "%s: feedback never quotes a correct option or finding" % st["id"], not any(x in fb for x in leak if len(x) > 20))
        b = panel(pg).get_by_role("button", name=re.compile("Reconsider|Revise", re.I))
        if b.count(): b.first.click(); pg.wait_for_timeout(40)
        fail_once(pg, st); pg.wait_for_timeout(40); r = panel(pg)
        check("pause", "%s: second miss pauses and closes the evidence" % st["id"], r.locator(".desk-pause").count() == 1 and r.locator(".desk-evidence-card.is-recheck").count() >= 1)
        open_all(pg)
        for nm in ("Reconsider and try again", "Revise your work"):
            bb = r.get_by_role("button", name=nm)
            if bb.count(): bb.click(); pg.wait_for_timeout(30)
        solve(pg, st)
        check("pause", "%s: after re-opening, the right answer passes" % st["id"], pg.is_enabled("#btnNext"), fb_text(pg)[:120])
    ctx.close()

    # ---------- integrity, leakage, legacy, isolation ----------
    ctx, pg, _ = fresh(br); goto(pg, M14)
    pg.evaluate("""localStorage.setItem('%s', JSON.stringify({v:1,tasks:{'m14-t10':{completed:true,verified:true,views:1,stages:{'t3-a':{passed:true},'t3-b':{passed:true,answer:{values:{},confirms:[true,true]}}},drafts:{}}}}))""" % KEY)
    goto(pg, M14 + "#task-3")
    check("integrity", "forged flags count for nothing", pg.evaluate("PVADesk.verifiedWork()")["m14-t10"]["stagesVerified"] == 0 and not earned(pg))
    shipped_src = "".join(pg.request.get(BASE + u).text() for u in ["/module-14/index.html", "/module-14/desk-data.js"])
    check("leakage", "no plaintext answer markers in shipped files", not any(m in shipped_src for m in ['"correct"', "correct: true", '"accept"', '"answer":']))
    check("leakage", "no plaintext source file in the repository", not any(f.endswith(".src.json") for _, _, fs in os.walk(ROOT) for f in fs))
    sel = [f for _, s in ALL if s["type"] == "compose" for f in s["fields"] if f["type"] == "select" and f.get("accept")]
    strict = [f["id"] for f in sel if len(label_of(f, f["accept"][0])) > max(len(o["label"]) for o in f["options"] if o["value"] != f["accept"][0])]
    check("leakage", "no select's accepted option is strictly its longest", not strict, strict)
    dl = [(s["id"], [len(o["text"]) for o in s["options"]], next(i for i, o in enumerate(s["options"]) if o.get("correct"))) for _, s in ALL if s["type"] == "decision"]
    check("leakage", "no decision's correct option is strictly its longest, and positions differ", not [x for x in dl if x[1][x[2]] > max(l for i, l in enumerate(x[1]) if i != x[2])] and len({x[2] for x in dl}) == 2, dl)
    vals_dom = []
    for ti in range(3):
        goto(pg, M14 + "#task-%d" % (ti + 1), 1); open_all(pg)
        vals_dom += pg.evaluate("Array.from(document.querySelectorAll('#stagePanel input,#stagePanel option')).map(e=>e.value)")
    check("leakage", "no control value names the answer", not [x for x in vals_dom if re.match(r"^(correct|right|wrong)", x)])
    ctx.close()
    ctx, pg, _ = fresh(br); goto(pg, BASE + "/index.html")
    pg.evaluate("v => localStorage.setItem('pva-ecom-ft-progress', JSON.stringify(v))", {"lessons": dict([("m14-brief", True)] + [("m14-t%d" % i, True) for i in range(1, 11)]), "modules": {}})
    goto(pg, M14 + "#task-1")
    check("legacy", "all three tasks keep their earlier checkmarks", pg.locator(".lesson-pill.done").count() == 3)
    check("legacy", "legacy completion is not verified work", not any(v["verified"] for v in pg.evaluate("PVADesk.verifiedWork()").values()))
    goto(pg, BASE + "/index.html")
    check("legacy", "someone who finished the old capstone still sees it Completed", pg.locator(".module-status").nth(13).inner_text() == "Completed")
    ctx.close()
    hub = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read(); port = open(os.path.join(ROOT, "portfolio", "index.html"), encoding="utf-8").read()
    check("hub", "the course map lists m14-t1, m14-t6, m14-t10 and links the Progress page, not the certificate", 'lessonIds: ["m14-t1","m14-t6","m14-t10"]' in hub and "progress/index.html" in hub and "certificate/" not in hub)
    check("portfolio", "piece 14 points at Module 14, Lesson 3, and the portfolio keeps 14 pieces", "From Module 14, Lesson 3 -- Report the Week and Package Your Portfolio" in port and len(re.findall(r'class="portfolio-num"', port)) == 14 and "certificate/" not in port)
    ctx, pg, _ = fresh(br)
    goto(pg, M13 + "#task-1", 1); open_all(pg); to_stage(pg, 0, "t1-a"); solve(pg, Q1)
    keys = pg.evaluate("Object.keys(localStorage).sort()")
    check("isolation", "Module 14 writes only its own desk key", set(keys) - {"pva-ecom-ft-progress", "pva-ecom-ft-m13-desk"} == {KEY}, keys)
    for ti, st in ALL:
        to_stage(pg, ti, st["id"]); open_all(pg)
        unnamed = pg.evaluate("""Array.from(document.querySelectorAll('#stagePanel select,#stagePanel input,#stagePanel textarea,#stagePanel button')).filter(e=>{var n=(e.labels&&e.labels.length)||e.getAttribute('aria-label')||e.getAttribute('aria-labelledby')||(e.tagName==='BUTTON'&&e.innerText.trim());return !n}).length""")
        check("a11y", "%s: every control has an accessible name" % st["id"], not unnamed, unnamed)
    ctx.close()

    # ---------- contrast and five widths ----------
    CONTRAST = r"""() => {
     function rgb(s){var m=s.match(/[\d.]+/g);return m?m.map(Number):[0,0,0,0];}
     function lum(c){var a=c.slice(0,3).map(v=>{v/=255;return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4)});return 0.2126*a[0]+0.7152*a[1]+0.0722*a[2];}
     function bg(e){while(e){var c=rgb(getComputedStyle(e).backgroundColor);if(c.length<4||c[3]>0.5)return c;e=e.parentElement;}return [255,255,255,1];}
     var out=[]; document.querySelectorAll('body *').forEach(e=>{ if(!e.offsetParent || e.disabled || e.closest('button:disabled')) return;
      if(![].some.call(e.childNodes,n=>n.nodeType===3&&n.textContent.trim())) return;
      var cs=getComputedStyle(e), L1=lum(rgb(cs.color)), L2=lum(bg(e)), r=(Math.max(L1,L2)+0.05)/(Math.min(L1,L2)+0.05);
      var size=parseFloat(cs.fontSize), large=size>=24||(parseInt(cs.fontWeight)>=700&&size>=18.66); if(r<(large?3:4.5)) out.push((e.className||e.tagName)+' '+r.toFixed(2)); }); return out; }"""
    ctx, pg, _ = fresh(br); low = []
    goto(pg, M14 + "#task-1"); low += pg.evaluate(CONTRAST)
    to_stage(pg, 0, "t1-a"); open_all(pg); fail_once(pg, Q1); low += pg.evaluate(CONTRAST)
    to_stage(pg, 2, "t3-b"); open_all(pg); solve(pg, P3); low += pg.evaluate(CONTRAST)
    check("contrast", "all enabled text meets WCAG AA", not low, sorted(set(low))[:8]); ctx.close()
    RESP = """(()=>{ var ov=document.documentElement.scrollWidth-innerWidth;
     var cells=Array.from(document.querySelectorAll('#stagePanel .desk-table tbody td, #stagePanel .desk-table tbody th')).filter(c=>c.scrollWidth>c.clientWidth+1).length;
     function hit(a,b){var x=a.getBoundingClientRect(),y=b.getBoundingClientRect();return x.width&&y.width&&x.left<y.right-1&&y.left<x.right-1&&x.top<y.bottom-1&&y.top<x.bottom-1;}
     var heads=Array.from(document.querySelectorAll('#stagePanel .desk-ev-head')).filter(h=>{var t=h.querySelector('.desk-record-title');return t&&Array.from(h.children).filter(c=>!c.contains(t)).some(c=>hit(t,c));}).length;
     return [ov>1?ov:0,cells,heads];})()"""
    for w in (320, 375, 390, 768, 1100):
        ctx, pg, _ = fresh(br, viewport={"width": w, "height": 812}, device_scale_factor=2 if w < 700 else 1, is_mobile=w < 700, has_touch=w < 700)
        for ti, st in ALL:
            to_stage(pg, ti, st["id"]); open_all(pg); pg.wait_for_timeout(60)
            r = pg.evaluate(RESP); check("responsive", "%s at %dpx: no sideways scroll, clipped cell or overlapping header" % (st["id"], w), not any(r), r)
        ctx.close()
    br.close()

fails = [r for r in results if not r[2]]
print("\n%d checks, %d failed" % (len(results), len(fails)))
sys.exit(1 if fails else 0)
