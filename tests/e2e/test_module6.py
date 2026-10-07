"""Module 6 Work Desk regression + adversarial suite (browser), modelled on Module 13's.

Run from the repo root with a static server on :8765 (see tests/README.md):
    python3 tests/e2e/test_module6.py
Answers come from decoding the shipped content at run time (desk_helpers.decode). The
"recompute" checks derive every accepted call and reply from the records themselves, and
the cross-module checks decode Modules 4, 5, 7, 9 and 13 to prove Module 6 prints none of
their graded answers, so nothing answer-bearing is stored here."""
import os, sys, re, json, subprocess
from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from desk_helpers import *  # noqa

SRC = decode("module-6")
M6 = BASE + "/module-6/index.html"
M7 = BASE + "/module-7/index.html"
TASKS = SRC["tasks"]
IDS = [t["id"] for t in TASKS]
ALL = [(ti, s) for ti, t in enumerate(TASKS) for s in t["stages"]]
KEY = "pva-ecom-ft-m6-desk"
DATA = json.loads(subprocess.run(["node", "-e", "process.stdout.write(JSON.stringify(require('./shared/everfield-data.js')))"], cwd=ROOT, capture_output=True, text=True).stdout)
results = []


def check(area, name, cond, detail=""):
    results.append((area, name, bool(cond), str(detail)))
    print(("PASS " if cond else "FAIL ") + "[" + area + "] " + name + ((" -- " + str(detail)[:200]) if detail and not cond else ""))


def field(st, fid): return next(f for f in st["fields"] if f["id"] == fid)
def label_of(f, v): return next(o["label"] for o in f["options"] if o["value"] == v)
def acc_label(st, fid): f = field(st, fid); return label_of(f, f["accept"][0])
def fields_of(rec): return dict((k, v) for k, v in rec.get("fields", []))
def strip(s): return re.sub(r"<[^>]+>", " ", s)


def records_of(st):
    if st["type"] == "decision": return st["records"]
    if st["type"] == "triage": return st["rows"]
    return [r for g in st["groups"] for r in g["records"]]


def group_records(st, gid): return next(g for g in st["groups"] if g["id"] == gid)["records"]


def rec_text(r):
    parts = [r.get("title", ""), r.get("caption", ""), r.get("note", ""), r.get("logTitle", "")]
    parts += [str(v) for kv in r.get("fields", []) for v in kv] + list(r.get("log", []))
    parts += [str(c) for row in r.get("rows", []) for c in row] + list(r.get("columns", []))
    parts += [str(v) for kv in r.get("meta", []) for v in kv] + list(r.get("body", [])) + list(r.get("paragraphs", [])) + list(r.get("items", []))
    return " ".join(parts)


def learner_text(task):
    out = [task["title"], task["objective"], task["brief"]["subject"]] + task["brief"]["body"] + [strip(x) for x in task.get("reference", [])]
    for s in task["stages"]:
        out += [s.get("intro", ""), s.get("prompt", ""), s.get("findingsPrompt", ""), s.get("actionPrompt", ""), s.get("now", "")]
        out += [rec_text(r) for r in records_of(s)]
        out += [c["label"] for c in s.get("choices", [])]
        out += [f["text"] for f in s.get("findings", [])] + [o["text"] for o in s.get("options", [])]
        for f in s.get("fields", []):
            out += [f["label"]] + [o["label"] for o in f.get("options", [])]
    return " ".join(out)


A1, B1 = stage_by_id(SRC, "l1-a"), stage_by_id(SRC, "l1-b")
C2 = stage_by_id(SRC, "l2-a")
A3, B3 = stage_by_id(SRC, "l3-a"), stage_by_id(SRC, "l3-b")
# facts the example texts need, read from the decoded records
ORD2 = fields_of(next(r for r in group_records(C2, "ord") if r.get("title", "").startswith("Order")))
ESC = next(r for r in group_records(B3, "esc") if r.get("title", "").startswith("Order"))
ESC_ORDER = ESC["title"].split(" ")[1]
ESC_SKU = re.search(r"EF-\d{3}", fields_of(ESC)["Item"]).group(0)
KIM = next(r for r in group_records(C2, "ord") if r.get("kind") == "message")["meta"][0][1].split(" ")[0]


def reply_text(st, g, f, labels):
    if f["id"] == "ord.reply":
        return "Hi %s, your order is being prepared at our warehouse and hasn't shipped yet. I'll send you the tracking details as soon as it ships." % KIM
    return "The customer on order %s (%s) says the item damaged his desk and that he's speaking to a lawyer. I've told him it's with you and promised nothing." % (ESC_ORDER, ESC_SKU)


def solve(pg, st):
    open_all(pg)
    if st["type"] == "decision": answer_decision(pg, st)
    elif st["type"] == "triage": answer_triage(pg, st)
    else:
        fill_compose(pg, st, compose_values(st, reply_text)); confirm_all(pg); submit(pg)


def fail_once(pg, st):
    open_all(pg)
    if st["type"] == "decision":
        cf = correct_findings(st)
        answer_decision(pg, st, findings=cf[1:] + distractors(st)[:1], option=(wrong_options(st) or [None])[0])
    elif st["type"] == "triage": answer_triage(pg, st, wrong=True)
    else:
        vals = compose_values(st, reply_text)
        sel = next(x for x in st["fields"] if x["type"] == "select")
        vals[sel["id"]] = first_unaccepted(sel)
        fill_compose(pg, st, vals); confirm_all(pg); submit(pg)


def to_stage(pg, ti, sid):
    goto(pg, M6 + "#task-%d" % (ti + 1), 1)
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


with sync_playwright() as p:
    br = p.chromium.launch()

    # ---------- structure: the approved design ----------
    check("design", "3 tasks with the approved ids (D8)", IDS == ["m6-l2", "m6-l4", "m6-l9"], IDS)
    check("design", "titles follow the design map", [t["title"] for t in TASKS] == ["Read the Inbox", "Reply from the Record", "Not Yours to Decide"])
    kinds = {t["id"]: [s["type"] for s in t["stages"]] for t in TASKS}
    check("design", "stage types match the map", kinds == {"m6-l2": ["triage", "decision"], "m6-l4": ["compose"], "m6-l9": ["decision", "compose"]}, kinds)
    check("design", "only Lesson 3 is a portfolio task, with the unchanged portfolio label",
          [(t["id"], t.get("portfolio")) for t in TASKS if t.get("portfolio")] == [("m6-l9", "Portfolio piece: E-commerce Customer Response Pack")])
    check("design", "Sofia asks for all three lessons and the pack", [t["brief"]["from"] for t in TASKS] == ["sofia", "sofia", "sofia"] and "Sofia Ramirez" in B3["evidence"]["requestedBy"])
    check("design", "one support day: every clock reads Thu, Sep 10, and no lesson declares its own work date",
          all(s["now"].startswith("Thu, Sep 10") for _, s in ALL) and not any(t.get("workDate") for t in TASKS))
    check("design", "Lesson 1A uses every call", set(r["answer"] for r in A1["rows"]) == set(c["id"] for c in A1["choices"]))
    check("design", "no typed numbers anywhere (the skill is the reply, not arithmetic)", not any(f["type"] == "number" for _, s in ALL if s["type"] == "compose" for f in s["fields"]))
    texts = [(s["id"], f["id"]) for _, s in ALL if s["type"] == "compose" for f in s["fields"] if f["type"] == "text"]
    check("design", "one own-words field per compose lesson: Lesson 2's reply and Lesson 3's handoff (D7a)", texts == [("l2-a", "ord.reply"), ("l3-b", "esc.note")], texts)
    check("design", "the pack declares a self-check and human review", len(B3["confirm"]) >= 2 and B3.get("humanReview"))
    check("design", "the pack holds the legacy pack's three response types: order status, product, escalation",
          [g["sampleHead"].split(" · ")[0] for g in B3["groups"]] == ["Reply 1", "Reply 2", "Escalation"])

    # ---------- D5 / D6: reference only ----------
    graded = " ".join([f["label"] + " " + " ".join(o["label"] for o in f.get("options", [])) for _, s in ALL if s["type"] == "compose" for f in s["fields"]] +
                      [c["label"] for c in A1["choices"]] + [o["text"] for _, s in ALL for o in s.get("options", [])] + [f["text"] for _, s in ALL for f in s.get("findings", [])])
    refs = " ".join(strip(x) for t in TASKS for x in t.get("reference", []))
    check("d5-d6", "address changes and marketplace messaging appear only as reference text, never as a graded case",
          "address" in refs and "marketplace" in refs.lower() and not re.search(r"address|marketplace", graded, re.I))

    # ---------- D2: M6 replies and hands off; it never decides an M7 outcome ----------
    accepted = [acc_label(s, f["id"]) for _, s in ALL if s["type"] == "compose" for f in s["fields"] if f["type"] == "select"] + \
               [option_text(s, correct_option(s)) for _, s in ALL if s["type"] == "decision"]
    check("boundary", "no accepted answer processes, approves or promises a refund, replacement, repair or exchange",
          not [a for a in accepted if re.search(r"\b(refund|replace|replacement|repair|exchange|cover the cost)\b", a, re.I) and not re.search(r"no outcome|promising no|can't promise", a, re.I)], accepted)
    canon = {}
    for line in open(os.path.join(ROOT, "docs", "everfield-continuity.md"), encoding="utf-8"):
        m = re.match(r"^\| (P\d+) \| (.+?) \| [^|]*\|\s*$", line)
        if m: canon[m.group(1)] = m.group(2)
    cards = [x for t in TASKS for x in t.get("reference", []) if re.match(r"^P\d+ · ", x)] + \
            [i for _, s in ALL for r in records_of(s) for i in r.get("items", []) if re.match(r"^P\d+ · ", i)]
    check("boundary", "policy cards quote canon P5, P7 and P8 word for word, and only those", sorted(set(c.split(" · ")[0] for c in cards)) == ["P5", "P7", "P8"] and
          all(canon[c.split(" · ")[0]] == c.split(" · ", 1)[1] for c in cards), cards)

    # ---------- continuity ----------
    every = " ".join(learner_text(t) for t in TASKS)
    orders = set(int(x) for x in re.findall(r"#(\d{4})\b", every))
    check("canon", "orders stay in #5483-#5495", orders and all(5483 <= n <= 5495 for n in orders), sorted(orders))
    check("canon", "the only return is the shared Return #229", set(re.findall(r"(?:Return )?#(\d{3})\b", every)) == {"229"})
    trk = set(re.findall(r"CP-\d{4}-\d{4}", every))
    check("canon", "tracking stays in CP-7731-08xx", trk and all(re.match(r"CP-7731-08\d\d$", t) for t in trk), trk)
    check("canon", "EF-103 never appears", "EF-103" not in json.dumps(TASKS))
    r229 = next(r for r in A1["rows"] if "Return #229" in r["title"])
    check("canon", "Return #229 is quoted with its shared facts (EF-101 x2, unopened, Restock, refund issued, Wed Sep 2)",
          all(x in rec_text(r229) for x in ["EF-101", "× 2", "Unopened", "Restock", "Issued", "Wed, Sep 2"]), rec_text(r229)[-200:])
    out = subprocess.run(["node", os.path.join(ROOT, "tools", "everfield-check.js")], capture_output=True, text=True)
    check("continuity", "the continuity checker passes, with the Module 6 range check",
          out.returncode == 0 and "ok   Module 6 day stays in its ranges" in out.stdout, out.stdout[-400:])
    check("continuity", "calendar.m6 is Thu, Sep 10", DATA["calendar"]["m6"]["date"] == "Thu, Sep 10")

    # ---------- recompute: every accepted answer derived from the evidence ----------
    def l1call(r):
        fd = fields_of(r); msg = fd["Message"].lower()
        if "Product record" in fd: return "check" if "not recorded" in fd["Product record"] else "answer"
        if fd.get("Attachments") == "None" and re.search(r"torn|broken|damaged|crushed", msg): return "ask"
        if "refund" in msg and "keeping" in msg: return "escalate"
        if "Return record" in fd and "refund Issued" in fd["Return record"]: return "answer"
        if "Status" in fd: return "answer"
        return "?"
    NAMES = {"answer": "Answer now", "ask": "Ask the customer", "check": "Check with someone", "escalate": "Escalate"}
    lab = {c["id"]: c["label"] for c in A1["choices"]}
    derived = {r["id"]: l1call(r) for r in A1["rows"]}
    check("recompute", "Lesson 1A: every call follows from its own card (record, attachments, what is asked)",
          all(lab[r["answer"]].startswith(NAMES[derived[r["id"]]]) for r in A1["rows"]), (derived, {r["id"]: lab[r["answer"]] for r in A1["rows"]}))
    stock = fields_of(next(r for r in B1["records"] if r.get("title", "").startswith("Stock")))
    check("recompute", "Lesson 1B: the stock card shows zero available and stock on order with no date, and the accepted reply promises no date",
          stock["Available"] == "0" and "no arrival date" in stock["Inbound"] and not re.search(r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun)|Sep|next week", stock["Inbound"]) and
          re.search(r"no date", option_text(B1, correct_option(B1))) and not re.search(r"next week|will be back|set one aside", option_text(B1, correct_option(B1))))
    check("recompute", "Lesson 2: the order is Processing with no tracking, and the accepted status says it hasn't shipped",
          ORD2["Status"] == "Processing" and ORD2["Tracking"] == "—" and "hasn't shipped" in acc_label(C2, "ord.status"))
    check("recompute", "Lesson 2: the accepted promise names no date and no compensation",
          not re.search(r"monday|tuesday|wednesday|thursday|friday|weekend|tomorrow|refund|free|discount", acc_label(C2, "ord.promise"), re.I) and "tracking" in acc_label(C2, "ord.promise").lower())
    dims = fields_of(next(r for r in group_records(C2, "dim") if r.get("title", "").startswith("Product record")))["Dimensions"]
    check("recompute", "Lesson 2: EF-101's accepted dimensions are the product record's, which are the shared product canon",
          acc_label(C2, "dim.answer") == dims == DATA["productFacts"]["EF-101"]["dimensions"])
    div = fields_of(next(r for r in group_records(C2, "div") if r.get("title", "").startswith("Product record")))
    owner = re.search(r"([A-Z][a-z]+ [A-Z][a-z]+), [^,.]+, owns Everfield's product listings", " ".join(TASKS[1]["reference"])).group(1)
    check("recompute", "Lesson 2 transfer: EF-106's piece count is blank in the record and undefined in canon, so the accepted reply gives no number",
          div["Pieces per set"] == "—" and not any(re.search(r"piece|pack|count", k, re.I) for k in DATA["productFacts"].get("EF-106", {})) and
          "doesn't say" in acc_label(C2, "div.answer") and not re.search(r"\d|four|six|two", acc_label(C2, "div.answer")))
    check("recompute", "Lesson 2: the person you confirm with is the listings owner named in the reference", owner in acc_label(C2, "div.who"), (owner, acc_label(C2, "div.who")))
    o3 = fields_of(next(r for r in group_records(B3, "trk") if r.get("title", "").startswith("Order")))
    check("recompute", "Lesson 3: the accepted tracking number is the one on his order record, and the order has shipped",
          acc_label(B3, "trk.number") in o3["Tracking"] and o3["Status"] == "Shipped" and "shipped" in acc_label(B3, "trk.state").lower())
    pack = fields_of(next(r for r in group_records(B3, "bag") if r.get("title", "").startswith("Product record")))["Pack"]
    check("recompute", "Lesson 3: the accepted product answer quotes the record's pack line", pack in acc_label(B3, "bag.answer") and pack == DATA["productFacts"]["EF-107"]["pack"])
    auth = next(rec_text(r) for r in group_records(B3, "esc") if r.get("kind") == "reference")
    legal_owner = re.search(r"goes to ([A-Z][a-z]+ [A-Z][a-z]+)", auth).group(1)
    esc_msg = " ".join(next(r for r in group_records(B3, "esc") if r.get("kind") == "message")["body"])
    check("recompute", "Lesson 3: a legal threat goes to the person the authority card names, for the reason in his message",
          "legal threat" in auth and legal_owner in acc_label(B3, "esc.to") and "lawyer" in esc_msg and "lawyer" in acc_label(B3, "esc.why"))
    e_msg = " ".join(next(r for r in A3["records"] if r.get("kind") == "message")["body"])
    pol = " ".join(rec_text(r) for r in A3["records"] if r.get("kind") == "reference")
    check("recompute", "Lesson 3A: a refund on items she keeps is Sofia's under P8, and the accepted action hands it on without promising an outcome",
          "keeping" in e_msg and "refund" in e_msg and canon["P8"] in pol and re.search(r"promising no outcome|no outcome", option_text(A3, correct_option(A3))))

    # ---------- normal flow, completion, work sample ----------
    ctx, pg, errs = fresh(br); goto(pg, M6)
    check("page", "desk bar shows Thu, Sep 10 and the task count", pg.text_content("#deskDate") == "Thu, Sep 10" and pg.inner_text("#lessonKicker") == "Task 1 of 3")
    for ti, t in enumerate(TASKS):
        goto(pg, M6 + "#task-%d" % (ti + 1), 1); ok = True
        for st in t["stages"]:
            solve(pg, st)
            if not pg.is_enabled("#btnNext"): ok = False; break
            pg.click("#btnNext"); pg.wait_for_timeout(60)
        check("flow", "task %d completes through the UI" % (ti + 1), ok)
    check("flow", "completion banner", "Module 6 complete" in pg.inner_text("#doneBanner"), pg.inner_text("#doneBanner"))
    prog = pg.evaluate("JSON.parse(localStorage.getItem('pva-ecom-ft-progress'))")
    check("progress", "verified work marks all three lessons in the legacy progress store", all(prog["lessons"].get(i) for i in IDS))
    keys = pg.evaluate("Object.keys(localStorage).sort()")
    check("isolation", "only the Module 6 desk key and the legacy progress key are written", keys == [KEY, "pva-ecom-ft-progress"], keys)
    vw = pg.evaluate("PVADesk.verifiedWork()")
    check("verified-work", "verifiedWork() reports all three tasks verified and the one earned sample",
          all(v["verified"] for v in vw.values()) and vw["m6-l9"]["samplesEarned"] == ["l3-b"] and not any(v["samplesEarned"] for k, v in vw.items() if k != "m6-l9"), vw)
    goto(pg, BASE + "/index.html")
    card = pg.locator(".module-card").nth(5).inner_text()
    check("progress", "course map shows Module 6 Completed", "Customer Support" in card and "Completed" in card, card)
    goto(pg, M6 + "#task-3", 2)
    ev = pg.locator(".ws-preview").inner_text() if pg.locator(".ws-preview").count() else ""
    check("work-sample", "the Customer Response Pack survives reload with an honest training header",
          ev.startswith("TRAINING WORK SAMPLE\nEverfield Goods — Customer Response Pack (Thu Sep 10)") and "fictional company" in ev and
          "Work date: Thu, Sep 10 (simulated)" in ev and "Sofia Ramirez" in ev and "human review" in ev, ev[:400])
    check("work-sample", "the pack carries all three replies and the learner's own handoff note",
          all(g["sampleHead"] in ev for g in B3["groups"]) and reply_text(None, None, {"id": "esc.note"}, None) in ev and acc_label(B3, "trk.number") in ev, ev[:900])
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
            acc = [acc_label(st, f["id"]) for f in st["fields"] if f["type"] == "select"]
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

    # ---------- transfer and principle-only feedback ----------
    ctx, pg, _ = fresh(br)
    for ti, st in ALL:
        if st["type"] != "decision": continue
        to_stage(pg, ti, st["id"]); open_all(pg)
        answer_decision(pg, st, findings=correct_findings(st)[:-1])
        check("transfer", "%s: right action without the full reading of the evidence fails" % st["id"], not pg.is_enabled("#btnNext"))
    ctx.close()
    ctx, pg, _ = fresh(br)
    to_stage(pg, 1, "l2-a"); open_all(pg)
    def attempt(stg, **over):
        v = compose_values(stg, reply_text); v.update(over)
        fill_compose(pg, stg, v); confirm_all(pg); submit(pg)
        okk = pg.is_enabled("#btnNext"); fbx = fb_text(pg)
        if okk: revise(pg)
        else: open_all(pg)
        return okk, fbx
    for v in [o["value"] for o in field(C2, "div.answer")["options"] if o["value"] not in field(C2, "div.answer")["accept"]]:
        check("transfer", "l2-a: giving EF-106 a piece count the record doesn't hold fails (%s), even with EF-101 answered exactly" % v, not attempt(C2, **{"div.answer": v})[0])
    check("transfer", "l2-a: a vague size for EF-101, where the record is exact, fails", not attempt(C2, **{"dim.answer": first_unaccepted(field(C2, "dim.answer"))})[0])
    ctx.close()
    ctx, pg, _ = fresh(br)
    to_stage(pg, 0, "l1-a"); open_all(pg)
    esc_id = next(c["id"] for c in A1["choices"] if c["label"].startswith("Escalate"))
    ans_id = next(c["id"] for c in A1["choices"] if c["label"].startswith("Answer"))
    for i, r in enumerate(A1["rows"]):
        panel(pg).locator("select.desk-select").nth(i).select_option(ans_id if r["answer"] == esc_id else r["answer"])
    panel(pg).locator("button[type=submit]").first.click(); pg.wait_for_timeout(60)
    check("transfer", "l1-a: treating the refund-on-kept-items message as a routine answer fails", not pg.is_enabled("#btnNext"))
    ctx.close()
    ctx, pg, _ = fresh(br)
    VERDICT = re.compile(r"(invalid|(action|choice|decision|answer|option) (is|was) (wrong|incorrect)|not the right|isn't the right|good answer|may be reasonable|correct option|wrong option|you selected)", re.I)
    for ti, st in ALL:
        if st["type"] != "decision": continue
        to_stage(pg, ti, st["id"]); open_all(pg)
        texts_fb = []
        for oid in wrong_options(st):
            answer_decision(pg, st, option=oid)
            texts_fb.append(fb_text(pg))
            open_all(pg); panel(pg).get_by_role("button", name="Reconsider and try again").click(); pg.wait_for_timeout(20)
        answer_decision(pg, st, findings=correct_findings(st)[:-1] + distractors(st)[:1])
        texts_fb.append(fb_text(pg))
        bad = [VERDICT.search(t).group(0) for t in texts_fb if VERDICT.search(t)]
        named = [finding_text(st, f) for f in distractors(st) if any(finding_text(st, f).rstrip(".") in t.split("What you missed", 1)[-1] for t in texts_fb)]
        check("feedback-principle", "%s: miss feedback states principles only; no choice is declared invalid or named" % st["id"], not bad and not named, (bad, named))
    ctx.close()

    # ---------- opening a later lesson first gives no shortcut to an earlier one ----------
    l1_labels = [c["label"] for c in A1["choices"]]
    l1_orders = set(re.findall(r"#\d{4}", " ".join(rec_text(r) for r in A1["rows"])))
    later = " ".join(learner_text(t) for t in TASKS[1:])
    check("later-first", "Lessons 2 and 3 never print a Lesson 1 call", not [l for l in l1_labels if l in later])
    check("later-first", "Lessons 2 and 3 reuse none of Lesson 1's orders", not [o for o in l1_orders if o in later], l1_orders)
    l2_acc = [acc_label(C2, f["id"]) for f in C2["fields"] if f["type"] == "select"]
    check("later-first", "Lesson 3 never prints Lesson 2's accepted replies", not [a for a in l2_acc if a in learner_text(TASKS[2])])
    ctx, pg, errs = fresh(br)
    goto(pg, M6); pg.locator(".lesson-pill").nth(2).click(); pg.wait_for_timeout(100)
    pg.click("#btnNext"); pg.wait_for_timeout(60); open_all(pg)
    dom = pg.inner_text("#stagePanel")
    check("later-first", "a fresh learner opening Lesson 3 first sees no Lesson 1 call", not [l for l in l1_labels if l in dom])
    solve(pg, A3)
    check("later-first", "Lesson 3 stays usable when opened first", pg.is_enabled("#btnNext"))
    check("later-first", "no JS errors", not errs, errs)
    ctx.close()

    # ---------- cross-module: Module 6 prints no other module's graded answers ----------
    m6_all = every + " " + " ".join(rec_text(r) for _, s in ALL for r in records_of(s))
    leaks = []
    for mod in ("module-4", "module-5", "module-7", "module-9", "module-13"):
        for t in decode(mod)["tasks"]:
            for s in t["stages"]:
                for o in s.get("options", []):
                    if o.get("correct") and o["text"][:60] in m6_all: leaks.append((mod, s["id"], "option"))
                for f in s.get("findings", []):
                    if f.get("correct") and len(f["text"]) > 24 and f["text"] in m6_all: leaks.append((mod, s["id"], f["id"]))
                for f in s.get("fields", []):
                    if f["type"] == "number":
                        for a in f.get("accept", []):
                            if float(a) >= 10 and re.search(r"(?<![\d.#$/:-])(?<!Sep )(?<!Oct )%s(?![\d./:])" % re.escape(a), m6_all): leaks.append((mod, s["id"], f["id"], a))
                    if f["type"] in ("select", "multi"):
                        vals = [v for a in f.get("accept", []) for v in (a if isinstance(a, list) else [a])]
                        for v in vals:
                            lbl = next((o["label"] for o in f["options"] if o["value"] == v), "")
                            if len(lbl) > 24 and not re.match(r"^EF-\d{3} [A-Z][\w ]+$", lbl) and lbl in m6_all: leaks.append((mod, s["id"], f["id"], lbl[:40]))
    check("cross-module", "no correct option, finding, accepted label or typed figure (>= 10) from Modules 4, 5, 7, 9 or 13 appears in Module 6", not leaks, leaks[:6])
    check("cross-module", "Module 6 decides no M7 case: no disposition, carrier claim or reship is offered as an accepted action",
          not [a for a in accepted if re.search(r"disposition|carrier claim|reship|intercept", a, re.I)])

    # ---------- shortcut attempts, derived completion, the replies ----------
    ctx, pg, _ = fresh(br); goto(pg, M6)
    pg.evaluate("""localStorage.setItem('%s', JSON.stringify({v:1,tasks:{'m6-l9':{completed:true,verified:true,views:1,
      stages:{'l3-a':{passed:true},'l3-b':{passed:true,answer:{values:{},confirms:[true,true,true]}}},drafts:{}}}}))""" % KEY)
    goto(pg, M6 + "#task-3")
    st3 = pg.evaluate("PVADesk.taskStatus(PVADesk.decode(window.PVA_DESK_MODULES.m6.payload).tasks[2])")
    check("integrity", "forged completed/verified/passed flags count for nothing", st3["passed"] == 0, st3)
    check("integrity", "forged state never reaches the legacy progress store", not (pg.evaluate("JSON.parse(localStorage.getItem('pva-ecom-ft-progress')||'{}')").get("lessons") or {}).get("m6-l9"))
    ctx.close()
    ctx, pg, _ = fresh(br)
    to_stage(pg, 1, "l2-a"); open_all(pg)
    def reply(t):
        v = compose_values(C2, reply_text); v["ord.reply"] = t
        fill_compose(pg, C2, v); confirm_all(pg); submit(pg)
        okk = pg.is_enabled("#btnNext"); fbx = fb_text(pg)
        if okk: revise(pg)
        else: open_all(pg)
        return okk, fbx
    GOOD = [("terse", "Your order is being prepared at our warehouse and hasn't shipped yet. I'll send tracking as soon as it ships."),
            ("different wording", "Thanks for your patience. Your order is still processing with our warehouse, so there's no tracking number yet. We'll email it once it's shipped."),
            ("future tense is not a claim", "Your order hasn't left our warehouse yet; it's being packed. As soon as it is on its way, you'll get tracking.")]
    for why, t in GOOD:
        okk, fbx = reply(t)
        check("l2-reply", "passes -- %s" % why, okk, (t, fbx[:200]))
    BAD = [("is filler", "Thanks so much for reaching out to us today! We really appreciate your business and your patience."),
           ("says it has shipped", "Your order has shipped and is on its way. You'll have tracking soon."),
           ("invents a delivery date", "Your order is being prepared at our warehouse. It will arrive by Monday at the latest."),
           ("offers something nobody approved", "Your order is still being prepared. Sorry for the wait; here's a discount code for your next order."),
           ("guesses a reason", "Your order is still being prepared. The warehouse is probably just busy this week."),
           ("never says where the order is", "Thanks for your message. I'll send you tracking details as soon as I have them for you.")]
    for why, t in BAD:
        check("l2-reply", "rejected -- a reply that %s" % why, not reply(t)[0], t)
    ctx.close()
    ctx, pg, _ = fresh(br)
    to_stage(pg, 2, "l3-b"); open_all(pg)
    def note(t):
        v = compose_values(B3, reply_text); v["esc.note"] = t
        fill_compose(pg, B3, v); confirm_all(pg); submit(pg)
        okk = pg.is_enabled("#btnNext"); fbx = fb_text(pg)
        if okk: revise(pg)
        else: open_all(pg)
        return okk, fbx
    o, k = ESC_ORDER, ESC_SKU
    GOODN = [("terse", "Legal threat on %s. He says the %s set scratched his desk and he is talking to his lawyer. I haven't promised him anything." % (o, k)),
             ("reports his claim faithfully", "The customer on %s claims the set is faulty and ruined his desk, and mentions his lawyer. This is beyond my authority, so it's with you." % o),
             ("'I promised nothing' is not a promise", "He says the %s set damaged his desk and he's consulting an attorney. Order %s. I promised nothing." % (k, o))]
    for why, t in GOODN:
        okk, fbx = note(t)
        check("l3-handoff", "passes -- %s" % why, okk, (t, fbx[:200]))
    BADN = [("is filler", "Hi, please see the message below. Let me know what you think when you get a chance."),
            ("leaves out the legal threat", "Order %s: the customer says the %s set damaged his desk. Please advise on next steps." % (o, k)),
            ("leaves out the order facts", "A customer says he's speaking to his lawyer about some damage. Passing it to you as it's beyond my authority."),
            ("records a promise", "He mentions a lawyer about desk damage on %s. I told him we will cover the repair." % o),
            ("states a conclusion as fact", "Order %s: the set is defective and damaged his desk. He's mentioned a lawyer." % o),
            ("admits liability", "He mentions his lawyer on %s. The set damaged his desk, so we're liable here." % o),
            ("plays it down", "Order %s: he mentions a lawyer, but it's not a big deal, just an angry customer." % o)]
    for why, t in BADN:
        check("l3-handoff", "rejected -- a note that %s" % why, not note(t)[0], t)
    ctx.close()

    # ---------- answer encoding / leakage ----------
    ctx, pg, _ = fresh(br)
    shipped = "".join(pg.request.get(BASE + uu).text() for uu in ["/module-6/index.html", "/module-6/desk-data.js", "/shared/workdesk.js", "/shared/workdesk-ui.js", "/shared/workdesk-page.js", "/shared/everfield-data.js"])
    markers = ['"correct"', "correct: true", '"accept"', '"answer":', '"correctOrder"']
    check("leakage", "no plaintext answer markers in any shipped engine or content file", not any(m in shipped for m in markers), [m for m in markers if m in shipped])
    check("leakage", "no correct option text appears in shipped source", not any(option_text(s, correct_option(s)) in shipped for _, s in ALL if s["type"] == "decision"))
    vals_dom = []
    for ti in range(len(TASKS)):
        goto(pg, M6 + "#task-%d" % (ti + 1), 1); open_all(pg)
        check("leakage", "task %d: rendered DOM carries no correctness attributes before submission" % (ti + 1), not re.search(r'(class|data-[a-z-]+)="[^"]*(correct|answer|right)', pg.content()))
        vals_dom += pg.evaluate("Array.from(document.querySelectorAll('#stagePanel input,#stagePanel option')).map(e=>e.value)")
    check("leakage", "no control value names the answer", not [x for x in vals_dom if re.match(r"^(correct|right|wrong|[fx]_)", x)], vals_dom)
    dec = pg.evaluate("JSON.stringify(PVADesk.decode(window.PVA_DESK_MODULES.m6.payload))")
    check("leakage", "decoded payload holds hashed keys only", '"correct"' not in dec and '"accept"' not in dec and '"answer"' not in dec)
    sel = [(s["id"], f) for _, s in ALL if s["type"] == "compose" for f in s["fields"] if f["type"] == "select"]
    longest = [f["id"] for _, f in sel if len(label_of(f, f["accept"][0])) == max(len(o["label"]) for o in f["options"])]
    positions = set(next(i for i, o in enumerate(f["options"]) if o["value"] == f["accept"][0]) for _, f in sel)
    check("leakage", "accepted select options are not the longest (at most a quarter) and sit in varied positions", len(longest) <= max(1, len(sel) // 4) and len(positions) >= 3, (longest, positions))
    ctx.close()

    # ---------- persistence ----------
    ctx, pg, _ = fresh(br)
    to_stage(pg, 0, "l1-a"); open_all(pg)
    panel(pg).locator("select.desk-select").first.select_option(A1["rows"][0]["answer"])
    pg.reload(); pg.wait_for_timeout(150); pg.click("#btnNext"); pg.wait_for_timeout(80)
    check("persistence", "an unsubmitted triage call survives refresh", panel(pg).locator("select.desk-select").first.input_value() == A1["rows"][0]["answer"])
    to_stage(pg, 1, "l2-a"); open_all(pg)
    panel(pg).get_by_label(field(C2, "ord.reply")["label"], exact=True).fill("Draft reply to the customer")
    pg.reload(); pg.wait_for_timeout(150); pg.click("#btnNext"); pg.wait_for_timeout(80)
    check("persistence", "an unsent reply survives refresh", panel(pg).get_by_label(field(C2, "ord.reply")["label"], exact=True).input_value() == "Draft reply to the customer")
    ctx.close()

    # ---------- legacy progress compatibility (D8: existing ids only) ----------
    ctx, pg, _ = fresh(br); goto(pg, BASE + "/index.html")
    pg.evaluate("v => localStorage.setItem('pva-ecom-ft-progress', JSON.stringify(v))", {"lessons": {"m6-l%d" % i: True for i in range(1, 10)}, "modules": {}})
    goto(pg, M6 + "#task-1")
    check("legacy", "all three lessons keep their earlier checkmarks", pg.locator(".lesson-pill.done").count() == 3)
    check("legacy", "the status line separates legacy completion from new work", "earlier version" in pg.inner_text("#taskStatus"))
    vw = pg.evaluate("PVADesk.verifiedWork()")
    check("legacy", "legacy completion is not verified work", not any(v["verified"] for v in vw.values()) and not any(v["samplesEarned"] for v in vw.values()))
    goto(pg, BASE + "/index.html")
    check("legacy", "someone who finished old Module 6 still sees it Completed on the course map", pg.locator(".module-status").nth(5).inner_text() == "Completed")
    pg.evaluate("v => localStorage.setItem('pva-ecom-ft-progress', JSON.stringify(v))", {"lessons": {"m6-l2": True, "m6-l4": True}, "modules": {}})
    goto(pg, BASE + "/index.html")
    check("legacy", "the course map counts Module 6 against its three lessons", "2 of 3" in pg.locator(".module-card").nth(5).inner_text(), pg.locator(".module-card").nth(5).inner_text())
    ctx.close()
    port = open(os.path.join(ROOT, "portfolio", "index.html"), encoding="utf-8").read()
    check("portfolio", "the portfolio points at Module 6, Lesson 3", "From Module 6, Lesson 3 -- Not Yours to Decide" in port and "Lesson 9 -- Escalation" not in port)

    # ---------- isolation and shared authored state ----------
    ctx, pg, _ = fresh(br)
    goto(pg, M7 + "#task-1", 1); open_all(pg)
    m7a = decode("module-7")["tasks"][0]["stages"][0]
    answer_triage(pg, m7a)
    to_stage(pg, 0, "l1-a"); solve(pg, A1)
    keys = pg.evaluate("Object.keys(localStorage).sort()")
    check("isolation", "Module 6 and Module 7 keep separate desk keys, and nothing else is written", set(keys) - {"pva-ecom-ft-progress"} == {KEY, "pva-ecom-ft-m7-desk"}, keys)
    m7store = pg.evaluate("JSON.parse(localStorage.getItem('pva-ecom-ft-m7-desk'))")
    check("isolation", "Module 6 work writes nothing into Module 7's store", list(m7store["tasks"].keys()) == ["m7-l1"], list(m7store["tasks"].keys()))
    goto(pg, M6)
    mut = pg.evaluate("(()=>{try{EVERFIELD.calendar.m6.date='Y'; EVERFIELD.productFacts['EF-101'].dimensions='Z';}catch(e){} return [EVERFIELD.calendar.m6.date, EVERFIELD.productFacts['EF-101'].dimensions]})()")
    check("everfield", "shared Everfield reference cannot be mutated from Module 6", mut == ["Thu, Sep 10", DATA["productFacts"]["EF-101"]["dimensions"]], mut)
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
        goto(pg, M6 + "#task-%d" % n); check("deep-link", "#task-%d opens task %d" % (n, n), pg.inner_text("#lessonKicker") == "Task %d of 3" % n and pg.text_content("#deskDate") == "Thu, Sep 10")
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
    goto(pg, M6 + "#task-1"); low += pg.evaluate(CONTRAST)
    pg.click("#btnNext"); pg.wait_for_timeout(60); open_all(pg); low += pg.evaluate(CONTRAST)
    fail_once(pg, A1); low += pg.evaluate(CONTRAST)
    to_stage(pg, 0, "l1-b"); fail_once(pg, B1); low += pg.evaluate(CONTRAST)
    panel(pg).get_by_role("button", name="Reconsider and try again").click(); fail_once(pg, B1); low += pg.evaluate(CONTRAST)
    to_stage(pg, 2, "l3-b"); open_all(pg); solve(pg, B3); low += pg.evaluate(CONTRAST)
    check("contrast", "all enabled text meets WCAG AA in brief, triage, decision, feedback, pause, compose and work-sample states", not low, sorted(set(low))[:8])
    ctx.close()
    STICKY = """() => { var top=document.querySelector('.topbar').getBoundingClientRect().bottom;
     var els=Array.from(document.querySelectorAll('#stagePanel select,#stagePanel input,#stagePanel textarea,#stagePanel button,#btnNext,#btnPrev')).filter(e=>e.offsetParent);
     return els.filter(e=>{ e.scrollIntoView({block:'start', behavior:'instant'}); return e.getBoundingClientRect().top < top-1; }).length; }"""
    for w in (320, 375):
        ctx, pg, _ = fresh(br, viewport={"width": w, "height": 700}, is_mobile=True, has_touch=True)
        hidden = 0
        for ti, sid in [(0, "l1-a"), (1, "l2-a"), (2, "l3-b")]:
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
    br.close()

fails = [r for r in results if not r[2]]
print("\n%d checks, %d failed" % (len(results), len(fails)))
sys.exit(1 if fails else 0)
