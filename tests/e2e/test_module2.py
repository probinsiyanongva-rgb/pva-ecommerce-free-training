"""Module 2 Work Desk regression + adversarial suite (browser), modelled on Module 6's.

Run from the repo root with a static server on :8765 (see tests/README.md):
    python3 tests/e2e/test_module2.py
Answers come from decoding the shipped content at run time (desk_helpers.decode). The
"recompute" checks derive every accepted match, call and field value from the records and
the shared product canon, the "approved source" checks (decision D6) prove that only an
approved, current document ever authorizes a value, and the cross-module checks decode
Modules 4, 5, 6, 7, 9 and 13 to prove Module 2 prints none of their graded answers, so
nothing answer-bearing is stored here."""
import os, sys, re, json, subprocess
from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from desk_helpers import *  # noqa

SRC = decode("module-2")
M2 = BASE + "/module-2/index.html"
M7 = BASE + "/module-7/index.html"
TASKS = SRC["tasks"]
IDS = [t["id"] for t in TASKS]
ALL = [(ti, s) for ti, t in enumerate(TASKS) for s in t["stages"]]
KEY = "pva-ecom-ft-m2-desk"
DATA = json.loads(subprocess.run(["node", "-e", "process.stdout.write(JSON.stringify(require('./shared/everfield-data.js')))"], cwd=ROOT, capture_output=True, text=True).stdout)
FACTS, NAMES = DATA["productFacts"], DATA["products"]
results = []


def check(area, name, cond, detail=""):
    results.append((area, name, bool(cond), str(detail)))
    print(("PASS " if cond else "FAIL ") + "[" + area + "] " + name + ((" -- " + str(detail)[:200]) if detail and not cond else ""))


def field(st, fid): return next(f for f in st["fields"] if f["id"] == fid)
def label_of(f, v): return next(o["label"] for o in f["options"] if o["value"] == v)
def acc_label(st, fid): f = field(st, fid); return label_of(f, f["accept"][0])
def value_of(f, label): return next(o["value"] for o in f["options"] if o["label"] == label)
def fields_of(rec): return dict((k, v) for k, v in rec.get("fields", []))
def strip(s): return re.sub(r"<[^>]+>", " ", s)


def records_of(st):
    if st["type"] == "decision": return st["records"]
    if st["type"] == "triage": return st["rows"]
    return [r for g in st["groups"] for r in g["records"]]


def group_records(st, gid): return next(g for g in st["groups"] if g["id"] == gid)["records"]


def rec_text(r):
    parts = [r.get("title", ""), r.get("caption", ""), r.get("note", ""), r.get("logTitle", ""), r.get("label", "")]
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


def table_rows(r): return {row[0]: dict(zip(r["columns"][1:], row[1:])) for row in r.get("rows", [])}


A1, B1 = stage_by_id(SRC, "l1-a"), stage_by_id(SRC, "l1-b")
W2, N2, C2 = stage_by_id(SRC, "l2-a"), stage_by_id(SRC, "l2-b"), stage_by_id(SRC, "l2-c")
S3 = stage_by_id(SRC, "l3-a")
NR = next(o["label"] for f in S3["fields"] for o in f["options"] if o["label"].startswith("Not recorded"))
# facts the example note needs, read from the decoded records
ROWS = table_rows(next(r for r in W2["records"] if r.get("kind") == "table"))
KIT_SKU = next(s for s, v in ROWS.items() if v["Weight"] != "—" and any(o != s and w["Weight"] == v["Weight"] for o, w in ROWS.items()) and "kit" in NAMES[s].lower())
BIN_SKU = next(s for s, v in ROWS.items() if s != KIT_SKU and v["Weight"] == ROWS[KIT_SKU]["Weight"])


def note_text(st, g, f, labels):
    return "The declared weight is %s's recorded weight, which only repeats one %s's. The kit's real weight isn't on file, so it needs weighing before the record changes." % (KIT_SKU, BIN_SKU)


def solve(pg, st):
    open_all(pg)
    if st["type"] == "decision": answer_decision(pg, st)
    elif st["type"] == "triage": answer_triage(pg, st)
    else:
        fill_compose(pg, st, compose_values(st, note_text)); confirm_all(pg); submit(pg)


def fail_once(pg, st):
    open_all(pg)
    if st["type"] == "decision":
        cf = correct_findings(st)
        answer_decision(pg, st, findings=cf[1:] + distractors(st)[:1], option=(wrong_options(st) or [None])[0])
    else:
        vals = compose_values(st, note_text)
        sel = next((x for x in st["fields"] if x["type"] == "select"), None)
        if sel: vals[sel["id"]] = first_unaccepted(sel)
        else: vals["note.text"] = "Thanks so much for flagging this, Maya! I really appreciate you looping me in on it."
        fill_compose(pg, st, vals); confirm_all(pg); submit(pg)


def to_stage(pg, ti, sid):
    goto(pg, M2 + "#task-%d" % (ti + 1), 1)
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


def is_approved_current(r):
    t = r.get("title", "")
    return bool(re.search(r"approved|current", t, re.I)) and not re.search(r"superseded|draft", t, re.I)


with sync_playwright() as p:
    br = p.chromium.launch()

    # ---------- structure: the approved design ----------
    check("design", "3 tasks with the approved ids (D9)", IDS == ["m2-l1", "m2-l7", "m2-l2"], IDS)
    check("design", "titles follow the design map", [t["title"] for t in TASKS] == ["Which Product Is It?", "When Product Data Goes Wrong", "The Product Master Sheet"])
    kinds = {t["id"]: [s["type"] for s in t["stages"]] for t in TASKS}
    check("design", "stage types match the map", kinds == {"m2-l1": ["compose", "decision"], "m2-l7": ["decision", "compose", "decision"], "m2-l2": ["compose"]}, kinds)
    check("design", "only Lesson 3 is a portfolio task, with the unchanged portfolio label",
          [(t["id"], t.get("portfolio")) for t in TASKS if t.get("portfolio")] == [("m2-l2", "Portfolio piece: Product Master Sheet")])
    check("design", "briefs come from Sofia, Maya and Sofia, and Sofia requests the master sheet",
          [t["brief"]["from"] for t in TASKS] == ["sofia", "maya", "sofia"] and "Sofia Ramirez" in S3["evidence"]["requestedBy"])
    check("design", "one product-desk day: every clock reads Tue, Sep 8, and no lesson declares its own work date",
          all(s["now"].startswith("Tue, Sep 8") for _, s in ALL) and not any(t.get("workDate") for t in TASKS))
    texts = [(s["id"], f["id"]) for _, s in ALL if s["type"] == "compose" for f in s["fields"] if f["type"] == "text"]
    check("design", "exactly one own-words field: Lesson 2's note to Maya (D7)", texts == [("l2-b", "note.text")], texts)
    check("design", "no typed numbers anywhere", not any(f["type"] == "number" for _, s in ALL if s["type"] == "compose" for f in s["fields"]))
    check("design", "the master sheet declares a self-check and human review", len(S3["confirm"]) >= 2 and S3.get("humanReview"))
    check("design", "two master-sheet rows, EF-103 and EF-101 (D10)", [g["id"] for g in S3["groups"]] == ["t103", "t101"] and
          [g["title"].split(" ")[0] for g in S3["groups"]] == ["EF-103", "EF-101"])
    check("design", "every master-sheet field offers 'Not recorded: flag it'", all(NR in [o["label"] for o in f["options"]] for f in S3["fields"]))
    check("design", "Lesson 1 offers a 'no single SKU' choice on every reference", all(any(o["label"].startswith("No single SKU") for o in f["options"]) for f in A1["fields"]))
    refs3 = " ".join(strip(x) for x in TASKS[2]["reference"])
    check("design", "Daniel Brooks is named in Lesson 3's reference as the holder of supplier details (D8)", "Daniel Brooks" in refs3 and "supplier" in refs3.lower())

    # ---------- D3: titles, assets and tags belong to Module 3 ----------
    every = " ".join(learner_text(t) for t in TASKS)
    graded = " ".join([f["label"] + " " + " ".join(o["label"] for o in f.get("options", [])) for _, s in ALL if s["type"] == "compose" for f in s["fields"]] +
                      [o["text"] for _, s in ALL for o in s.get("options", [])] + [f["text"] for _, s in ALL for f in s.get("findings", [])])
    check("d3", "no graded field, option or finding is about listing titles, images or tags (they moved to Module 3)",
          not re.search(r"\b(title|image|photo|asset|tag|keyword)s?\b", graded, re.I), re.findall(r"\b(title|image|photo|asset|tag|keyword)s?\b", graded, re.I)[:5])

    # ---------- D6: only an approved, current source authorizes a value ----------
    rule = next(strip(x) for x in TASKS[1]["reference"] if "Correcting a product record" in x)
    check("d6", "the learner-facing rule: correct only from a source that is both approved and current, then tell Sofia",
          re.search(r"only when a source that is both approved and current", rule) and "tell Sofia" in rule, rule)
    check("d6", "the rule says finding a value somewhere is not enough, and names what is never an approved source",
          "Finding a value somewhere is not enough" in rule and all(x in rule for x in ["draft", "superseded", "marketing copy", "another SKU's row", "work out yourself"]), rule)
    check("d6", "the rule says to leave the field unchanged and flag it when no approved source holds the value, never estimate",
          "leave the field unchanged" in rule and "flag" in rule and "never fill it with an estimate" in rule)
    approved = next(r for r in C2["records"] if r.get("kind") == "table" and r["title"].startswith("Approved"))
    draft = next(r for r in C2["records"] if r.get("kind") == "table" and r["title"].startswith("Draft"))
    row105 = table_rows(next(r for r in C2["records"] if "EF-105 row" in r.get("title", "")))
    fix = option_text(C2, correct_option(C2))
    check("d6", "l2-c: the value the learner may correct to comes from the approved, current catalog, never the superseded draft",
          is_approved_current(approved) and not is_approved_current(draft) and "SUPERSEDED" in draft["title"] and
          table_rows(approved)["EF-105"]["Category"] in fix and table_rows(draft)["EF-105"]["Category"] not in fix and "approved catalog" in fix and "tell Sofia" in fix, fix)
    check("d6", "l2-c: the draft agrees with the wrong row, so agreement between documents is no authority",
          table_rows(draft)["EF-105"]["Category"] == row105["Category"]["Value"] if "Category" in row105 else True)
    flag = option_text(W2, correct_option(W2))
    check("d6", "l2-a: with no approved weight anywhere, the accepted action changes nothing and asks for a measured figure",
          re.search(r"isn't on file|needs weighing", flag) and not re.search(r"\b(change|delete|update|correct)\b", flag, re.I) and not re.search(r"\d+(\.\d+)? ?lb", flag), flag)
    srcs = {g["id"]: group_records(S3, g["id"]) for g in S3["groups"]}
    offered_from_bad = []
    for f in S3["fields"]:
        a = acc_label(S3, f["id"])
        if a == NR: continue
        good = [r for r in srcs[f["group"]] if is_approved_current(r) and a in rec_text(r)]
        if not good: offered_from_bad.append(f["id"])
    check("d6", "every accepted master-sheet value appears in an approved, current document", not offered_from_bad, offered_from_bad)
    stale = [v for r in srcs["t103"] if re.search(r"superseded", r.get("title", ""), re.I) for k, v in r.get("fields", []) if k not in ("Product", "Status")]
    check("d6", "no accepted value comes from the superseded quote or the supplier's marketing copy",
          stale and not [v for v in stale if v in [acc_label(S3, f["id"]) for f in S3["fields"]]] and
          not [f["id"] for f in S3["fields"] if acc_label(S3, f["id"]).lower() in (next(r for r in srcs["t103"] if "specification" in r["title"]).get("note", "").lower())])

    # ---------- canon and continuity ----------
    orders = set(int(x) for x in re.findall(r"#(\d{4})\b", every))
    check("canon", "orders stay in #5496-#5498", orders and all(5496 <= n <= 5498 for n in orders), sorted(orders))
    check("canon", "no returns anywhere", not re.search(r"Return #|#\d{3}\b", every))
    trk = set(re.findall(r"CP-\d{4}-\d{4}", every))
    check("canon", "tracking stays in CP-7731-09xx", trk and all(re.match(r"CP-7731-09\d\d$", t) for t in trk), trk)
    mkt = set(re.findall(r"MKT-\d+", every))
    check("canon", "marketplace listing IDs stay module-local MKT-44xx (D4)", mkt and all(re.match(r"MKT-44\d\d$", m) for m in mkt), mkt)
    check("canon", "no stock figures (available / reserved / inbound / on hand)", not re.search(r"\b\d+ available\b|\bAvailable\b|\bInbound\b|\bReserved\b|\bon hand\b", every))
    check("canon", "module-local identifiers never enter shared product canon (D4)", "MKT-" not in json.dumps(DATA) and "PM-BT" not in json.dumps(DATA))
    check("canon", "intentionally undefined facts stay undefined: EF-200 weight, EF-103 cost, EF-101 supplier and lead time",
          not any(re.search("weight", k, re.I) for k in FACTS["EF-200"]) and not any(re.search("cost", k, re.I) for k in FACTS["EF-103"]) and
          not any(re.search("supplier|lead", k, re.I) for k in FACTS["EF-101"]))
    check("canon", "every catalog name printed matches the catalog", all(NAMES[s] in every for s in NAMES) and
          not [m for m in re.findall(r"(EF-\d{3}) ([A-Z][a-z]+(?: [A-Z][a-z]+)+)", every) if m[0] in NAMES and not NAMES[m[0]].startswith(m[1].split(" ")[0])
               and m[1] not in set(v.get("category", "") for v in FACTS.values() if isinstance(v, dict))])
    out = subprocess.run(["node", os.path.join(ROOT, "tools", "everfield-check.js")], capture_output=True, text=True)
    check("continuity", "the continuity checker passes, with the Module 2 range check",
          out.returncode == 0 and "ok   Module 2 day stays in its ranges" in out.stdout, out.stdout[-400:])
    check("continuity", "calendar.m2 is Tue, Sep 8", DATA["calendar"]["m2"]["date"] == "Tue, Sep 8")
    check("continuity", "product facts once sourced to retired lessons are re-pointed to live ones (D5)",
          not re.search(r"module-2 m2-l[3-6]\b", json.dumps(DATA)))

    # ---------- recompute: every accepted answer derived from the evidence ----------
    xref_html = next(x for x in TASKS[0]["reference"] if "cross-reference" in x)
    XREF = dict(re.findall(r"<td>(MKT-\d+)</td><td>(EF-\d{3})</td>", xref_html))
    cat_note = strip(next(x for x in TASKS[0]["reference"] if "Everfield catalog" in x))
    def l1match(r):
        fd, txt = fields_of(r), rec_text(r)
        if "Listing" in fd: return XREF.get(fd["Listing"], "?")
        hits = [s for s in NAMES if NAMES[s] in txt]
        if len(hits) == 1: return hits[0]
        if re.search(r"\bin (red|blue|green|black|white|grey|gray)\b", txt) and "no size or colour variants" in cat_note: return "none"
        m = re.search(r"(\w+) pack, (\d+) pieces", txt)
        if m:
            fit = [s for s in NAMES if FACTS.get(s, {}).get("pack", "").startswith(m.group(2)) and m.group(1).rstrip("s").lower() in NAMES[s].lower()]
            return fit[0] if len(fit) == 1 else "?"
        m = re.search(r"the (\w+) we ordered", txt)
        if m and len([s for s in NAMES if m.group(1)[:7].lower() in NAMES[s].lower()]) > 1: return "none"
        return "?"
    got, want = {}, {}
    for g, f in zip(A1["groups"], A1["fields"]):
        d = l1match(g["records"][0]); got[g["id"]] = d
        want[g["id"]] = label_of(f, f["accept"][0])
    check("recompute", "Lesson 1: every match follows from its own reference, through the catalog, the cross-reference, the canon pack size or the no-variants rule",
          all((want[k].startswith("No single") if got[k] == "none" else want[k].startswith(got[k] + " ")) for k in got) and "?" not in got.values(), (got, want))
    typo = next(g for g in A1["groups"] if "EF-1O4" in rec_text(g["records"][0]))
    check("recompute", "Lesson 1: the mistyped code (letter O for zero) resolves by the name beside it, not by the code", "EF-1O4" not in NAMES and
          acc_label(A1, typo["id"] + ".sku").startswith("EF-104 ") and NAMES["EF-104"] in rec_text(typo["records"][0]))
    row = table_rows(next(r for r in B1["records"] if r.get("kind") == "table"))
    spec = fields_of(next(r for r in B1["records"] if "specification" in r["title"]))
    keep = option_text(B1, correct_option(B1))
    check("recompute", "Lesson 1B: EF-103 is what every system uses, so the accepted answer keeps it and stores the supplier's code beside it",
          "Orders" in row["Used by"]["Value"] and "Keep EF-103" in keep and spec["Supplier item code"] in keep and "supplier item code field" in keep, keep)
    check("recompute", "Lesson 2A: the kit's recorded weight repeats one bin's, the kit holds more than one, and no measured kit weight exists",
          ROWS[KIT_SKU]["Weight"] == FACTS[BIN_SKU]["weight"] and FACTS[KIT_SKU]["kit"][BIN_SKU] >= 2 and
          "No weight for the assembled kit has been measured" in " ".join(rec_text(r) for r in W2["records"]))
    notice = " ".join(rec_text(r) for r in W2["records"] if r.get("kind") == "message")
    check("recompute", "Lesson 2A: the notice's declared weight is the kit row's weight", ROWS[KIT_SKU]["Weight"] in notice)
    check("recompute", "Lesson 2C: the approved catalog's EF-105 category is the shared product canon, and the master row disagrees",
          table_rows(approved)["EF-105"]["Category"] == FACTS["EF-105"]["category"] != row105["Category"]["Value"])
    der = {}
    for f in S3["fields"]:
        sku = "EF-" + f["group"][1:]; lab = f["label"]; val = None
        for r in srcs[f["group"]]:
            if not is_approved_current(r): continue
            if r.get("kind") == "table" and r["columns"][0] == "SKU":
                v = table_rows(r).get(sku, {}).get(lab)
            else:
                fd = fields_of(r)
                applies = sku in r["title"] or fd.get("Product") == NAMES[sku]
                v = fd.get(lab) if applies else None
            if v: val = v
        der[f["id"]] = val or NR
    check("recompute", "Lesson 3: every accepted field is the approved, current document's value, or 'Not recorded' where none records it",
          all(acc_label(S3, k) == v for k, v in der.items()), {k: (v, acc_label(S3, k)) for k, v in der.items() if acc_label(S3, k) != v})
    canon_map = {"t103.cat": FACTS["EF-103"]["category"], "t103.sup": FACTS["EF-103"]["supplier"], "t103.lead": FACTS["EF-103"]["leadTime"], "t103.unit": FACTS["EF-103"]["unit"],
                 "t101.cat": FACTS["EF-101"]["category"], "t101.cost": FACTS["EF-101"]["unitCost"], "t101.dims": FACTS["EF-101"]["dimensions"], "t101.weight": FACTS["EF-101"]["weight"]}
    check("recompute", "Lesson 3: every recorded value equals the shared product canon", all(acc_label(S3, k) == v for k, v in canon_map.items()))

    # ---------- normal flow, completion, work sample ----------
    ctx, pg, errs = fresh(br); goto(pg, M2)
    check("page", "desk bar shows Tue, Sep 8 and the task count", pg.text_content("#deskDate") == "Tue, Sep 8" and pg.inner_text("#lessonKicker") == "Task 1 of 3")
    for ti, t in enumerate(TASKS):
        goto(pg, M2 + "#task-%d" % (ti + 1), 1); ok = True
        for st in t["stages"]:
            solve(pg, st)
            if not pg.is_enabled("#btnNext"): ok = False; break
            pg.click("#btnNext"); pg.wait_for_timeout(60)
        check("flow", "task %d completes through the UI" % (ti + 1), ok)
    check("flow", "completion banner", "Module 2 complete" in pg.inner_text("#doneBanner"), pg.inner_text("#doneBanner"))
    prog = pg.evaluate("JSON.parse(localStorage.getItem('pva-ecom-ft-progress'))")
    check("progress", "verified work marks all three lessons in the legacy progress store", all(prog["lessons"].get(i) for i in IDS))
    keys = pg.evaluate("Object.keys(localStorage).sort()")
    check("isolation", "only the Module 2 desk key and the legacy progress key are written", keys == [KEY, "pva-ecom-ft-progress"], keys)
    vw = pg.evaluate("PVADesk.verifiedWork()")
    check("verified-work", "verifiedWork() reports all three tasks verified and the one earned sample",
          all(v["verified"] for v in vw.values()) and vw["m2-l2"]["samplesEarned"] == ["l3-a"] and not any(v["samplesEarned"] for k, v in vw.items() if k != "m2-l2"), vw)
    goto(pg, BASE + "/index.html")
    card = pg.locator(".module-card").nth(1).inner_text()
    check("progress", "course map shows Module 2 Completed", "Products, SKUs" in card and "Completed" in card, card)
    goto(pg, M2 + "#task-3", 2)
    ev = pg.locator(".ws-preview").inner_text() if pg.locator(".ws-preview").count() else ""
    check("work-sample", "the Product Master Sheet survives reload with an honest training header",
          ev.startswith("TRAINING WORK SAMPLE\nEverfield Goods — Product Master Sheet") and "fictional company" in ev and
          "Work date: Tue, Sep 8 (simulated)" in ev and "Sofia Ramirez" in ev and "human review" in ev, ev[:400])
    check("work-sample", "the sheet carries both rows and every field's value, flags included",
          all(g["sampleHead"] in ev for g in S3["groups"]) and all(acc_label(S3, f["id"]) in ev for f in S3["fields"]) and ev.count(NR) == sum(1 for f in S3["fields"] if acc_label(S3, f["id"]) == NR), ev[:900])
    check("flow", "no JS errors", not errs, errs)
    ctx.close()

    # ---------- evidence gate (every stage) ----------
    ctx, pg, _ = fresh(br)
    for ti, st in ALL:
        to_stage(pg, ti, st["id"]); r = panel(pg)
        if st["type"] == "compose":
            gated = r.locator("section.desk-group select, section.desk-group input, section.desk-group textarea").first.is_disabled() and all(c.is_disabled() for c in r.locator(".desk-selfcheck input").all())
        else:
            gated = r.locator(".desk-actions button").first.is_disabled()
        pg.evaluate("document.querySelectorAll('#stagePanel button,#stagePanel select,#stagePanel input,#stagePanel textarea').forEach(e=>e.disabled=false); var b=document.querySelector('#stagePanel .desk-actions button'); b && b.click();")
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
        if st["type"] == "compose":
            acc = [acc_label(st, f["id"]) for f in st["fields"] if f["type"] == "select"]
            check("feedback-safety", "%s: feedback never quotes an accepted choice" % st["id"], not [a for a in acc if a in fb], fb[:200])
        retry = r.get_by_role("button", name="Reconsider and try again")
        if retry.count(): retry.click(); pg.wait_for_timeout(30)
        fail_once(pg, st)
        if st["type"] == "compose" and not any(f["type"] == "select" for f in st["fields"]):
            # a writing problem is not an evidence miss: the engine never pauses on it, and there is no attempt limit
            check("retry", "%s: a second weak note gets feedback again, with no pause and no lock-out" % st["id"],
                  r.locator(".desk-pause").count() == 0 and len(fb_text(pg)) > 60 and not pg.is_enabled("#btnNext"))
            solve(pg, st)
            check("retry", "%s: corrected attempt passes with no attempt limit" % st["id"], pg.is_enabled("#btnNext"))
            continue
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

    # ---------- transfer, approved-source traps and principle-only feedback ----------
    ctx, pg, _ = fresh(br)
    for ti, st in ALL:
        if st["type"] != "decision": continue
        to_stage(pg, ti, st["id"]); open_all(pg)
        answer_decision(pg, st, findings=correct_findings(st)[:-1])
        check("transfer", "%s: right action without the full reading of the evidence fails" % st["id"], not pg.is_enabled("#btnNext"))
    ctx.close()
    ctx, pg, _ = fresh(br)
    for ti, st, oid, why in [(1, W2, "double", "working out a weight from the kit recipe"), (1, W2, "blank", "deleting the field instead of flagging it"),
                             (1, C2, "draft", "keeping the superseded draft's value because two documents agree"), (1, C2, "ask", "refusing a correction the approved catalog authorizes")]:
        to_stage(pg, ti, st["id"]); open_all(pg)
        answer_decision(pg, st, option=oid)
        check("d6-trap", "%s: %s fails, even with every finding right" % (st["id"], why), not pg.is_enabled("#btnNext"))
    ctx.close()
    ctx, pg, _ = fresh(br)
    to_stage(pg, 2, "l3-a"); open_all(pg)
    def attempt(**over):
        v = compose_values(S3, note_text); v.update(over)
        fill_compose(pg, S3, v); confirm_all(pg); submit(pg)
        okk = pg.is_enabled("#btnNext"); fbx = fb_text(pg)
        if okk: revise(pg)
        else: open_all(pg)
        return okk, fbx
    quote = fields_of(next(r for r in srcs["t103"] if re.search("superseded", r["title"], re.I)))
    traps = [("t103.lead", quote["Lead time"], "the superseded quote's lead time"),
             ("t103.cost", next(o["label"] for o in field(S3, "t103.cost")["options"] if o["label"].startswith("Estimated")), "an estimated cost for a SKU with no approved cost"),
             ("t103.cost", FACTS["EF-101"]["unitCost"], "another SKU's approved cost"),
             ("t101.sup", FACTS["EF-103"]["supplier"], "another SKU's supplier"),
             ("t101.lead", next(o["label"] for o in field(S3, "t101.lead")["options"] if "EF-103" in o["label"]), "another SKU's lead time")]
    for fid, lab, why in traps:
        okk, fbx = attempt(**{fid: value_of(field(S3, fid), lab)})
        check("d6-trap", "l3-a: filling %s with %s fails, though a value was 'found somewhere'" % (fid, why), not okk, lab)
    for fid in [f["id"] for f in S3["fields"] if acc_label(S3, f["id"]) != NR][:4]:
        check("d6-trap", "l3-a: flagging %s, which an approved document does record, also fails" % fid, not attempt(**{fid: value_of(field(S3, fid), NR)})[0])
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
    later = " ".join(learner_text(t) for t in TASKS[1:])
    l1_listings = [g["records"][0]["fields"][0][1] for g in A1["groups"] if fields_of(g["records"][0]).get("Listing")]
    check("later-first", "Lessons 2 and 3 never print a Lesson 1 listing ID", not [m for m in l1_listings if m in later], l1_listings)
    check("later-first", "Lessons 2 and 3 never print Lesson 1's mistyped code or its ambiguous and variant cases",
          not re.search(r"EF-1O4|in blue|organizer we ordered", later))
    l2_acc = [option_text(s, correct_option(s)) for s in (W2, C2)]
    check("later-first", "Lesson 3 never prints Lesson 2's accepted actions or its cases", not [a for a in l2_acc if a[:50] in learner_text(TASKS[2])] and
          not re.search(r"EF-200|EF-105", json.dumps(S3["fields"])))
    ctx, pg, errs = fresh(br)
    goto(pg, M2); pg.locator(".lesson-pill").nth(2).click(); pg.wait_for_timeout(100)
    pg.click("#btnNext"); pg.wait_for_timeout(60); open_all(pg)
    dom = pg.inner_text("#stagePanel")
    check("later-first", "a fresh learner opening Lesson 3 first sees no Lesson 1 listing ID", not [m for m in l1_listings if m in dom])
    solve(pg, S3)
    check("later-first", "Lesson 3 stays usable when opened first", pg.is_enabled("#btnNext"))
    check("later-first", "no JS errors", not errs, errs)
    ctx.close()

    # ---------- cross-module: Module 2 prints no other module's graded answers ----------
    m2_all = every + " " + " ".join(rec_text(r) for _, s in ALL for r in records_of(s))
    leaks, mkt_elsewhere = [], []
    for mod in ("module-4", "module-5", "module-6", "module-7", "module-9", "module-13"):
        dm = decode(mod)
        if re.search(r"MKT-\d+|PM-BT", json.dumps(dm)): mkt_elsewhere.append(mod)
        for t in dm["tasks"]:
            for s in t["stages"]:
                for o in s.get("options", []):
                    if o.get("correct") and o["text"][:60] in m2_all: leaks.append((mod, s["id"], "option"))
                for f in s.get("findings", []):
                    if f.get("correct") and len(f["text"]) > 24 and f["text"] in m2_all: leaks.append((mod, s["id"], f["id"]))
                for f in s.get("fields", []):
                    if f["type"] == "number":
                        for a in f.get("accept", []):
                            if float(a) >= 10 and re.search(r"(?<![\d.#$/:-])(?<!Sep )(?<!Oct )%s(?![\d./:])" % re.escape(a), m2_all): leaks.append((mod, s["id"], f["id"], a))
                    if f["type"] in ("select", "multi"):
                        vals = [v for a in f.get("accept", []) for v in (a if isinstance(a, list) else [a])]
                        for v in vals:
                            lbl = next((o["label"] for o in f["options"] if o["value"] == v), "")
                            if len(lbl) > 24 and not re.match(r"^EF-\d{3} [A-Z][\w ]+$", lbl) and lbl in m2_all: leaks.append((mod, s["id"], f["id"], lbl[:40]))
    check("cross-module", "no correct option, finding, accepted label or typed figure (>= 10) from Modules 4, 5, 6, 7, 9 or 13 appears in Module 2", not leaks, leaks[:6])
    check("cross-module", "Module 2's listing IDs and supplier code appear in no other module (D4: module-local)", not mkt_elsewhere, mkt_elsewhere)

    # ---------- shortcut attempts, derived completion, the note ----------
    ctx, pg, _ = fresh(br); goto(pg, M2)
    pg.evaluate("""localStorage.setItem('%s', JSON.stringify({v:1,tasks:{'m2-l2':{completed:true,verified:true,views:1,
      stages:{'l3-a':{passed:true,answer:{values:{},confirms:[true,true]}}},drafts:{}}}}))""" % KEY)
    goto(pg, M2 + "#task-3")
    st3 = pg.evaluate("PVADesk.taskStatus(PVADesk.decode(window.PVA_DESK_MODULES.m2.payload).tasks[2])")
    check("integrity", "forged completed/verified/passed flags count for nothing", st3["passed"] == 0, st3)
    check("integrity", "forged state never reaches the legacy progress store", not (pg.evaluate("JSON.parse(localStorage.getItem('pva-ecom-ft-progress')||'{}')").get("lessons") or {}).get("m2-l2"))
    ctx.close()
    ctx, pg, _ = fresh(br)
    to_stage(pg, 1, "l2-b"); open_all(pg)
    def note(t):
        v = compose_values(N2, note_text); v["note.text"] = t
        fill_compose(pg, N2, v); confirm_all(pg); submit(pg)
        okk = pg.is_enabled("#btnNext"); fbx = fb_text(pg)
        if okk: revise(pg)
        else: open_all(pg)
        return okk, fbx
    k, b, w = KIT_SKU, BIN_SKU, ROWS[KIT_SKU]["Weight"]
    GOOD = [("terse", "Declared weight = %s's record. That value was never measured for the kit. Needs weighing." % k),
            ("plain wording, no codes", "The kit record repeats one bin's weight. The real kit weight is not recorded. Please ask ClearPath to weigh a kit."),
            ("quotes the recorded figure", "Our %s weight field holds a single bin's %s. Nobody has measured the kit; can we get one weighed?" % (k, w)),
            ("says the carrier was right", "The carrier was right; our %s weight is too low because it is one bin's weight. The kit hasn't been weighed, so we should get it measured." % k)]
    for why, t in GOOD:
        okk, fbx = note(t)
        check("l2-note", "passes -- %s" % why, okk, (t, fbx[:200]))
    BAD = [("is filler", "Thanks so much for flagging this, Maya! I really appreciate you looping me in and I'm happy to help."),
           ("invents a kit weight", "The declared weight is %s's recorded weight. The kit actually weighs about 5.5 lb, so it needs updating." % k),
           ("works a weight out from the recipe", "%s's weight is wrong. The kit weight should be double %s's weight because it holds two bins." % (k, b)),
           ("blames the carrier", "The kit weight on the notice looks off. This is a carrier error and ClearPath should dispute it."),
           ("guesses how it happened", "%s's declared weight came from our record. I think someone probably copied it, and it needs weighing." % k),
           ("claims the record was changed without an approved source", "The declared weight came from %s's record, which wasn't measured. I've updated the weight on the record now." % k),
           ("never says where the weight came from", "Please ask ClearPath to get a kit weighed. It needs to be measured before anything changes."),
           ("never says what's needed", "The declared weight came from %s's record, which is the same as one %s's weight. That's where it comes from." % (k, b))]
    for why, t in BAD:
        check("l2-note", "rejected -- a note that %s" % why, not note(t)[0], t)
    ctx.close()

    # ---------- answer encoding / leakage ----------
    ctx, pg, _ = fresh(br)
    shipped = "".join(pg.request.get(BASE + uu).text() for uu in ["/module-2/index.html", "/module-2/desk-data.js", "/shared/workdesk.js", "/shared/workdesk-ui.js", "/shared/workdesk-page.js", "/shared/everfield-data.js"])
    markers = ['"correct"', "correct: true", '"accept"', '"answer":', '"correctOrder"']
    check("leakage", "no plaintext answer markers in any shipped engine or content file", not any(m in shipped for m in markers), [m for m in markers if m in shipped])
    check("leakage", "no correct option text appears in shipped source", not any(option_text(s, correct_option(s)) in shipped for _, s in ALL if s["type"] == "decision"))
    vals_dom = []
    for ti in range(len(TASKS)):
        goto(pg, M2 + "#task-%d" % (ti + 1), 1); open_all(pg)
        check("leakage", "task %d: rendered DOM carries no correctness attributes before submission" % (ti + 1), not re.search(r'(class|data-[a-z-]+)="[^"]*(correct|answer|right)', pg.content()))
        vals_dom += pg.evaluate("Array.from(document.querySelectorAll('#stagePanel input,#stagePanel option')).map(e=>e.value)")
    check("leakage", "no control value names the answer", not [x for x in vals_dom if re.match(r"^(correct|right|wrong|[fx]_)", x)], [x for x in vals_dom if re.match(r"^(correct|right|wrong|[fx]_)", x)])
    dec = pg.evaluate("JSON.stringify(PVADesk.decode(window.PVA_DESK_MODULES.m2.payload))")
    check("leakage", "decoded payload holds hashed keys only", '"correct"' not in dec and '"accept"' not in dec and '"answer"' not in dec)
    sel = [f for f in S3["fields"]]
    longest = [f["id"] for f in sel if len(label_of(f, f["accept"][0])) == max(len(o["label"]) for o in f["options"])]
    positions = [next(i for i, o in enumerate(f["options"]) if o["value"] == f["accept"][0]) for f in sel]
    check("leakage", "Lesson 3: accepted options are not the longest (at most a quarter) and spread across every position",
          len(longest) <= len(sel) // 4 and len(set(positions)) == 4 and max(positions.count(i) for i in range(4)) <= len(sel) // 2, (longest, positions))
    dl = [(s["id"], [len(o["text"]) for o in s["options"]], next(i for i, o in enumerate(s["options"]) if o.get("correct"))) for _, s in ALL if s["type"] == "decision"]
    check("leakage", "no decision's correct option is its longest", not [d for d in dl if d[1][d[2]] == max(d[1])], dl)
    ctx.close()

    # ---------- persistence ----------
    ctx, pg, _ = fresh(br)
    to_stage(pg, 0, "l1-a"); open_all(pg)
    f0 = A1["fields"][0]
    panel(pg).locator("section.desk-group").first.get_by_label(f0["label"], exact=True).select_option(f0["accept"][0])
    pg.reload(); pg.wait_for_timeout(150); pg.click("#btnNext"); pg.wait_for_timeout(80)
    check("persistence", "an unsubmitted match survives refresh", panel(pg).locator("section.desk-group").first.get_by_label(f0["label"], exact=True).input_value() == f0["accept"][0])
    to_stage(pg, 1, "l2-b"); open_all(pg)
    panel(pg).get_by_label(field(N2, "note.text")["label"], exact=True).fill("Draft note to Maya")
    pg.reload(); pg.wait_for_timeout(150); pg.click("#btnNext"); pg.wait_for_timeout(80); pg.click("#btnNext"); pg.wait_for_timeout(80)
    check("persistence", "an unsent note survives refresh", panel(pg).get_by_label(field(N2, "note.text")["label"], exact=True).input_value() == "Draft note to Maya")
    ctx.close()

    # ---------- legacy progress compatibility (D9: existing ids only) ----------
    ctx, pg, _ = fresh(br); goto(pg, BASE + "/index.html")
    pg.evaluate("v => localStorage.setItem('pva-ecom-ft-progress', JSON.stringify(v))", {"lessons": {"m2-l%d" % i: True for i in range(1, 8)}, "modules": {}})
    goto(pg, M2 + "#task-1")
    check("legacy", "all three lessons keep their earlier checkmarks", pg.locator(".lesson-pill.done").count() == 3)
    check("legacy", "the status line separates legacy completion from new work", "earlier version" in pg.inner_text("#taskStatus"))
    vw = pg.evaluate("PVADesk.verifiedWork()")
    check("legacy", "legacy completion is not verified work", not any(v["verified"] for v in vw.values()) and not any(v["samplesEarned"] for v in vw.values()))
    goto(pg, BASE + "/index.html")
    check("legacy", "someone who finished old Module 2 still sees it Completed on the course map", pg.locator(".module-status").nth(1).inner_text() == "Completed")
    pg.evaluate("v => localStorage.setItem('pva-ecom-ft-progress', JSON.stringify(v))", {"lessons": {"m2-l1": True, "m2-l7": True}, "modules": {}})
    goto(pg, BASE + "/index.html")
    check("legacy", "the course map counts Module 2 against its three lessons", "2 of 3" in pg.locator(".module-card").nth(1).inner_text(), pg.locator(".module-card").nth(1).inner_text())
    ctx.close()
    port = open(os.path.join(ROOT, "portfolio", "index.html"), encoding="utf-8").read()
    check("portfolio", "the portfolio points at Module 2, Lesson 3", "From Module 2, Lesson 3 -- The Product Master Sheet" in port and "Lesson 2 -- Product Attributes" not in port)

    # ---------- isolation and shared authored state ----------
    ctx, pg, _ = fresh(br)
    goto(pg, M7 + "#task-1", 1); open_all(pg)
    m7a = decode("module-7")["tasks"][0]["stages"][0]
    answer_triage(pg, m7a)
    to_stage(pg, 0, "l1-a"); solve(pg, A1)
    keys = pg.evaluate("Object.keys(localStorage).sort()")
    check("isolation", "Module 2 and Module 7 keep separate desk keys, and nothing else is written", set(keys) - {"pva-ecom-ft-progress"} == {KEY, "pva-ecom-ft-m7-desk"}, keys)
    m7store = pg.evaluate("JSON.parse(localStorage.getItem('pva-ecom-ft-m7-desk'))")
    check("isolation", "Module 2 work writes nothing into Module 7's store", list(m7store["tasks"].keys()) == ["m7-l1"], list(m7store["tasks"].keys()))
    goto(pg, M2)
    mut = pg.evaluate("(()=>{try{EVERFIELD.calendar.m2.date='Y'; EVERFIELD.productFacts['EF-101'].weight='Z';}catch(e){} return [EVERFIELD.calendar.m2.date, EVERFIELD.productFacts['EF-101'].weight]})()")
    check("everfield", "shared Everfield reference cannot be mutated from Module 2", mut == ["Tue, Sep 8", FACTS["EF-101"]["weight"]], mut)
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
        goto(pg, M2 + "#task-%d" % n); check("deep-link", "#task-%d opens task %d" % (n, n), pg.inner_text("#lessonKicker") == "Task %d of 3" % n and pg.text_content("#deskDate") == "Tue, Sep 8")
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
    goto(pg, M2 + "#task-1"); low += pg.evaluate(CONTRAST)
    pg.click("#btnNext"); pg.wait_for_timeout(60); open_all(pg); low += pg.evaluate(CONTRAST)
    fail_once(pg, A1); low += pg.evaluate(CONTRAST)
    to_stage(pg, 0, "l1-b"); fail_once(pg, B1); low += pg.evaluate(CONTRAST)
    panel(pg).get_by_role("button", name="Reconsider and try again").click(); fail_once(pg, B1); low += pg.evaluate(CONTRAST)
    to_stage(pg, 1, "l2-b"); fail_once(pg, N2); low += pg.evaluate(CONTRAST)
    to_stage(pg, 2, "l3-a"); open_all(pg); solve(pg, S3); low += pg.evaluate(CONTRAST)
    check("contrast", "all enabled text meets WCAG AA in brief, compose, decision, feedback, pause, note and work-sample states", not low, sorted(set(low))[:8])
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
    br.close()

fails = [r for r in results if not r[2]]
print("\n%d checks, %d failed" % (len(results), len(fails)))
sys.exit(1 if fails else 0)
