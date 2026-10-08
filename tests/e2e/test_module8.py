"""Module 8 Work Desk regression + adversarial suite (browser), modelled on Module 3's.

Run from the repo root with a static server on :8765 (see tests/README.md):
    python3 tests/e2e/test_module8.py
Answers come from decoding the shipped content at run time (desk_helpers.decode). The
"recompute" checks derive every accepted call, comparable set, per-unit price, range and
finding from the simulated listings and the shared EF-101 record; the simulated-data checks
(decisions D5/D6) prove every outside store, price and review is labelled as fictional
training data; the cross-module checks decode Modules 2, 3, 4, 5, 6, 7, 9 and 13 to prove
Module 8 prints none of their graded answers. So nothing answer-bearing is stored here."""
import os, sys, re, json, subprocess
from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from desk_helpers import *  # noqa

SRC = decode("module-8")
M8 = BASE + "/module-8/index.html"
M7 = BASE + "/module-7/index.html"
TASKS = SRC["tasks"]
IDS = [t["id"] for t in TASKS]
ALL = [(ti, s) for ti, t in enumerate(TASKS) for s in t["stages"]]
KEY = "pva-ecom-ft-m8-desk"
DATA = json.loads(subprocess.run(["node", "-e", "process.stdout.write(JSON.stringify(require('./shared/everfield-data.js')))"], cwd=ROOT, capture_output=True, text=True).stdout)
FACTS, NAMES = DATA["productFacts"], DATA["products"]
DASH = "—"
SIM = " · simulated store"
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


A1, S1 = stage_by_id(SRC, "l1-a"), stage_by_id(SRC, "l1-b")
C2, K2 = stage_by_id(SRC, "l2-a"), stage_by_id(SRC, "l2-b")
R3, P3 = stage_by_id(SRC, "l3-a"), stage_by_id(SRC, "l3-b")
EVERY = " ".join(learner_text(t) for t in TASKS)
REC_HTML = next(x for x in TASKS[0]["reference"] if "Product record · EF-101" in x)
RECV = dict(re.findall(r"<tr><td>([^<]+)</td><td>([^<]+)</td></tr>", REC_HTML))
DIMS = [int(x) for x in re.findall(r"\d+", RECV["Dimensions"])]


def listing(r):
    f = fields_of(r); m = re.match(r"\$(\d+\.\d\d)(?: for (\d+))?$", f["Price"])
    return {"store": f["Store"].replace(SIM, ""), "item": f["Item"], "price": float(m.group(1)), "units": int(m.group(2) or 1),
            "ship": 0.0 if f["Shipping"] == "Free" else float(f["Shipping"].lstrip("$")), "claim": f.get("Listing says")}


LISTINGS = {r["id"][1:]: listing(r) for r in group_records(C2, "set") if r.get("title", "").endswith("· listing")}


def comparable(l):
    if not l["item"].lower().startswith("stackable storage bin"): return False
    d = [int(x) for x in re.findall(r"(\d+) x (\d+) x (\d+)", l["item"])[0]]
    return all(abs(a - b) <= 1 for a, b in zip(d, DIMS))


COMP = {k: v for k, v in LISTINGS.items() if comparable(v)}
PER = {k: "%.2f" % (round(v["price"] / v["units"] * 100) / 100) for k, v in COMP.items()}
LOW, HIGH = min(PER.values(), key=float), max(PER.values(), key=float)


def obs_text(st, g, f, labels):
    return "Comparable bins sell for $%s to $%s per unit before shipping, and shipping varies by store. Three reviews at different stores mention corners cracking when stacked." % (LOW, HIGH)


def solve(pg, st):
    open_all(pg)
    if st["type"] == "decision": answer_decision(pg, st)
    elif st["type"] == "triage": answer_triage(pg, st)
    else:
        fill_compose(pg, st, compose_values(st, obs_text)); confirm_all(pg); submit(pg)


def fail_once(pg, st):
    open_all(pg)
    if st["type"] == "decision":
        cf = correct_findings(st)
        answer_decision(pg, st, findings=cf[1:] + distractors(st)[:1], option=(wrong_options(st) or [None])[0])
    elif st["type"] == "triage": answer_triage(pg, st, wrong=True)
    else:
        vals = compose_values(st, obs_text)
        sel = next((x for x in st["fields"] if x["type"] == "select"), None)
        if sel: vals[sel["id"]] = first_unaccepted(sel)
        else: vals["obs.text"] = "I looked at a lot of listings today and found some interesting things in them."
        fill_compose(pg, st, vals); confirm_all(pg); submit(pg)


def to_stage(pg, ti, sid):
    goto(pg, M8 + "#task-%d" % (ti + 1), 1)
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


def attempt_in(pg, st, **over):
    v = compose_values(st, obs_text); v.update(over)
    fill_compose(pg, st, v); confirm_all(pg); submit(pg)
    okk = pg.is_enabled("#btnNext"); fbx = fb_text(pg)
    if okk: revise(pg)
    else: open_all(pg)
    return okk, fbx


with sync_playwright() as p:
    br = p.chromium.launch()

    # ---------- structure: the approved design ----------
    check("design", "3 tasks with the approved ids (D3)", IDS == ["m8-l1", "m8-l4", "m8-l7"], IDS)
    check("design", "titles follow the design map", [t["title"] for t in TASKS] == ["Is It a Research Question?", "A Fair Comparison", "Report What You Found"])
    kinds = {t["id"]: [s["type"] for s in t["stages"]] for t in TASKS}
    check("design", "stage types match the map", kinds == {"m8-l1": ["triage", "decision"], "m8-l4": ["compose", "decision"], "m8-l7": ["triage", "compose"]}, kinds)
    check("design", "only Lesson 3 is a portfolio task, with the unchanged portfolio label",
          [(t["id"], t.get("portfolio")) for t in TASKS if t.get("portfolio")] == [("m8-l7", "Portfolio piece: Mini Competitive Research Report")])
    check("design", "Sofia asks for all three lessons and the report", [t["brief"]["from"] for t in TASKS] == ["sofia", "sofia", "sofia"] and "Sofia Ramirez" in P3["evidence"]["requestedBy"])
    check("design", "one research-desk day: every clock reads Fri, Sep 11, and no lesson declares its own work date",
          all(s["now"].startswith("Fri, Sep 11") for _, s in ALL) and not any(t.get("workDate") for t in TASKS))
    texts = [(s["id"], f["id"]) for _, s in ALL if s["type"] == "compose" for f in s["fields"] if f["type"] == "text"]
    check("design", "exactly one own-words field: the report's observation (D8)", texts == [("l3-b", "obs.text")], texts)
    nums = [(s["id"], f["id"]) for _, s in ALL if s["type"] == "compose" for f in s["fields"] if f["type"] == "number"]
    paired = all(any(f["type"] == "select" and "basis" in f["id"] for f in s["fields"]) for _, s in ALL if s["type"] == "compose" and any(x["type"] == "number" for x in s["fields"]))
    check("design", "typed per-unit prices, each stage pairing them with a choice about what the figures are (D7)", len(nums) == 5 and paired, nums)
    check("design", "the report declares a self-check and human review", len(P3["confirm"]) >= 2 and P3.get("humanReview"))
    check("design", "both triage stages use every call", all(set(r["answer"] for r in st["rows"]) == set(c["id"] for c in st["choices"]) for st in (A1, R3)))
    check("design", "one research question across the day: EF-101's category (D4)", all("EF-101" in learner_text(t) for t in TASKS) and "stackable" in EVERY.lower())

    # ---------- D5 / D6: simulated outside data, no Everfield price ----------
    outside = [r for _, s in ALL for r in records_of(s) if re.search(r"\$\d", rec_text(r)) or SIM in rec_text(r) or "Review" in r.get("title", "")]
    check("d6", "every outside listing, search result and review card is labelled as simulated training data",
          outside and all(re.search(r"simulated", rec_text(r), re.I) for r in outside), [r.get("title") for r in outside if not re.search("simulated", rec_text(r), re.I)])
    check("d6", "every lesson with outside data carries the 'not real market information' note in its reference",
          all(any("simulated training data" in x and "real" in x for x in t["reference"]) for t in TASKS[1:]))
    check("d6", "the module page says the outside stores, prices and reviews are fictional",
          "fictional training data" in open(os.path.join(ROOT, "module-8", "index.html"), encoding="utf-8").read())
    check("d6", "the work sample's company line and note say the outside data is fictional",
          "fictional training data" in SRC["config"]["sample"]["companyLine"] and "fictional training data" in P3["evidence"]["note"])
    check("d5", "no Everfield retail price or unit cost anywhere; the EF-101 record has no price line",
          not re.search(r"\$4\.20|\$3\.85", json.dumps(SRC)) and "Price" not in RECV and not re.search(r"price|retail", json.dumps(FACTS), re.I))
    check("d5", "every dollar figure sits on an outside (simulated) listing or a typed field, never on an Everfield record",
          not [r for _, s in ALL for r in records_of(s) if re.search(r"\$\d", rec_text(r)) and not re.search("simulated", rec_text(r), re.I)])
    check("d5", "outside data never enters shared canon", not any(l["store"] in json.dumps(DATA) for l in LISTINGS.values()))

    # ---------- D7 / D8 / D9 / D11 / D12 ----------
    ref2 = " ".join(strip(x) for x in TASKS[1]["reference"])
    check("d7", "the reference defines per-unit price: pack price ÷ units, before shipping, shipping recorded separately",
          "pack price divided by the number of units in the pack, before shipping" in ref2 and "never folded into the per-unit figure" in ref2)
    check("d7", "the shipping trap is real: folding shipping in changes at least one multi-pack's figure",
          any("%.2f" % ((v["price"] + v["ship"]) / v["units"]) != PER[k] for k, v in COMP.items() if v["units"] > 1))
    banned = json.dumps(P3.get("banned", []))
    check("d8", "the observation's validator guards against recommendations and the claim as fact, never against wording",
          re.search(r"recommend", banned) and "50" in banned and not re.search(r"keyword", banned, re.I))
    check("d9", "reviews are about outside listings only: no Everfield product-quality claim", not re.search(r"EF-10\d|EF-200", " ".join(rec_text(r) for r in R3["rows"])))
    check("d11", "EF-107's pack fact now cites a live lesson (m6-l9), and no data cites a retired Module 8 lesson",
          "module-6 m6-l9" in FACTS["EF-107"]["src"] and not re.search(r"module-8 m8-l\d", json.dumps(DATA)))
    check("d11", "the retired legacy implications are gone (EF-103 material, EF-104 adhesive)", not re.search(r"EF-104|adhesive|EF-103", EVERY))
    check("d12", "the capstone's research case never appears (EF-105's category, a slogan-only entry)", not re.search(r"EF-105|EF-107|slogan", EVERY, re.I))

    # ---------- canon and continuity ----------
    check("canon", "no Everfield orders, returns, tracking numbers, marketplace IDs or stock figures",
          not re.search(r"#\d{3,}\b|CP-\d{4}-\d{4}|MKT-\d+|\b\d+ available\b|\bAvailable\b|\bInbound\b|\bReserved\b|\bon hand\b", EVERY))
    check("canon", "the EF-101 record in the reference is the shared canon, with supplier and lead time left blank",
          RECV["Product name"] == NAMES["EF-101"] and RECV["Category"] == FACTS["EF-101"]["category"] and RECV["Dimensions"] == FACTS["EF-101"]["dimensions"] and
          RECV["Weight"] == FACTS["EF-101"]["weight"] and RECV["Supplier"] == DASH and RECV["Lead time"] == DASH and not FACTS["EF-101"].get("supplier"))
    out = subprocess.run(["node", os.path.join(ROOT, "tools", "everfield-check.js")], capture_output=True, text=True)
    check("continuity", "the continuity checker passes, with the Module 8 range check", out.returncode == 0 and "ok   Module 8 day stays in its ranges" in out.stdout, out.stdout[-400:])
    check("continuity", "calendar.m8 is Fri, Sep 11, after M6's Thu Sep 10 and before M4's Tue Sep 15",
          DATA["calendar"]["m8"]["date"] == "Fri, Sep 11" and DATA["calendar"]["m6"]["date"] == "Thu, Sep 10" and DATA["calendar"]["m4"]["date"] == "Tue, Sep 15")

    # ---------- recompute: every accepted answer derived from the evidence ----------
    KEYW = {"category": "Category", "lead time": "Lead time", "weigh": "Weight", "supplies": "Supplier"}
    lab1 = {c["id"]: c["label"] for c in A1["choices"]}
    def l1call(q):
        ql = q.lower()
        if re.search(r"\bshould\b", ql): return "Sofia's decision"
        if re.search(r"other stores|elsewhere", ql): return "Needs outside research"
        k = next(v for w, v in KEYW.items() if w in ql)
        return "Answered by the record" if RECV[k] != DASH else "Ask the person who holds it"
    got1 = {r["id"]: l1call(fields_of(r)["Sofia asks"]) for r in A1["rows"]}
    check("recompute", "Lesson 1A: every call follows from EF-101's record and what the question asks",
          all(lab1[r["answer"]].startswith(got1[r["id"]]) for r in A1["rows"]), (got1, {r["id"]: lab1[r["answer"]] for r in A1["rows"]}))
    check("recompute", "Lesson 1A: the questions are worded alike, so the record decides (two record lines filled, two blank)",
          sorted(got1.values()).count("Answered by the record") == 2 and sorted(got1.values()).count("Ask the person who holds it") == 2)
    srch = table_rows(next(r for r in S1["records"] if "Search results" in r.get("title", "")))
    check("recompute", "Lesson 1B: the search mixes comparable bins with other product types, and the accepted scope is EF-101's type and size",
          any(not v["Item"].lower().startswith("stackable") for v in srch.values()) and "close to EF-101's size" in option_text(S1, correct_option(S1)) and "per-unit" in option_text(S1, correct_option(S1)))
    sf = field(C2, "set.items")
    check("recompute", "Lesson 2A: the accepted comparable set is every stackable bin within an inch of EF-101's size",
          sorted(sf["accept"][0]) == sorted(COMP.keys()) and len(COMP) < len(LISTINGS), (sf["accept"][0], list(COMP)))
    check("recompute", "Lesson 2A: the shipping set is every comparable listing that charges shipping",
          sorted(field(C2, "set.ship")["accept"][0]) == sorted(k for k, v in COMP.items() if v["ship"] > 0))
    per_f = {f["id"].split(".")[1]: f["accept"][0] for f in C2["fields"] if f["type"] == "number"}
    check("recompute", "Lesson 2A: every typed per-unit figure is pack price ÷ units, before shipping",
          per_f and all(per_f[k] == PER[k] for k in per_f) and set(per_f) == {k for k, v in COMP.items() if v["units"] > 1}, (per_f, PER))
    check("recompute", "Lesson 2A/3B: the accepted basis is 'item price per unit, before shipping'",
          acc_label(C2, "unit.basis") == acc_label(P3, "rng.basis") == "Item price per unit, before shipping")
    claimer = next(v for v in LISTINGS.values() if v["claim"])
    spec = fields_of(next(r for r in K2["records"] if "specifications" in r.get("title", "")))
    check("recompute", "Lesson 2B: the load figure is only in the listing's own words; its specifications state none; the accepted action keeps it as an unverified claim",
          "50 lb" in claimer["claim"] and spec["Maximum load"] == "Not stated" and "unverified" in option_text(K2, correct_option(K2)) and "keep its price" in option_text(K2, correct_option(K2)))
    def rev(r): return (r["title"].split(" · ")[1].replace(" · simulated store", "").strip() if " · " in r["title"] else ""), fields_of(r)["Review"].lower()
    revs = {r["id"]: rev(r) for r in R3["rows"]}
    corner = {k for k, v in revs.items() if re.search(r"corner", v[1])}
    stores = {revs[k][0] for k in corner}
    lab3 = {c["id"]: c["label"] for c in R3["choices"]}
    def l3call(k):
        if re.search(r"parcel|seller|deliver", revs[k][1]): return "Not about the product"
        return "Part of a pattern" if k in corner and len(corner) >= 3 and len(stores) >= 3 else "A one-off opinion"
    check("recompute", "Lesson 3A: the pattern is the issue raised in three reviews at three stores; delivery and seller remarks aren't about the product",
          all(lab3[r["answer"]].startswith(l3call(r["id"])) for r in R3["rows"]), {r["id"]: (l3call(r["id"]), lab3[r["answer"]]) for r in R3["rows"]})
    check("recompute", "Lesson 3B: the range is the lowest and highest per-unit price across the comparable listings",
          field(P3, "rng.low")["accept"][0] == LOW and field(P3, "rng.high")["accept"][0] == HIGH, (LOW, HIGH))
    check("recompute", "Lesson 3B: the review finding names the pattern and its spread; the claim is the store's own, unverified",
          "Corners" in acc_label(P3, "fnd.rev") and "three" in acc_label(P3, "fnd.rev") and claimer["store"] in acc_label(P3, "fnd.claim") and "unverified" in acc_label(P3, "fnd.claim"))

    # ---------- normal flow, completion, work sample ----------
    ctx, pg, errs = fresh(br); goto(pg, M8)
    check("page", "desk bar shows Fri, Sep 11 and the task count", pg.text_content("#deskDate") == "Fri, Sep 11" and pg.inner_text("#lessonKicker") == "Task 1 of 3")
    for ti, t in enumerate(TASKS):
        goto(pg, M8 + "#task-%d" % (ti + 1), 1); ok = True
        for st in t["stages"]:
            solve(pg, st)
            if not pg.is_enabled("#btnNext"): ok = False; break
            pg.click("#btnNext"); pg.wait_for_timeout(60)
        check("flow", "task %d completes through the UI" % (ti + 1), ok)
    check("flow", "completion banner", "Module 8 complete" in pg.inner_text("#doneBanner"), pg.inner_text("#doneBanner"))
    prog = pg.evaluate("JSON.parse(localStorage.getItem('pva-ecom-ft-progress'))")
    check("progress", "verified work marks all three lessons in the legacy progress store", all(prog["lessons"].get(i) for i in IDS))
    keys = pg.evaluate("Object.keys(localStorage).sort()")
    check("isolation", "only the Module 8 desk key and the legacy progress key are written", keys == [KEY, "pva-ecom-ft-progress"], keys)
    vw = pg.evaluate("PVADesk.verifiedWork()")
    check("verified-work", "verifiedWork() reports all three tasks verified and the one earned sample",
          all(v["verified"] for v in vw.values()) and vw["m8-l7"]["samplesEarned"] == ["l3-b"] and not any(v["samplesEarned"] for k, v in vw.items() if k != "m8-l7"), vw)
    goto(pg, BASE + "/index.html")
    card = pg.locator(".module-card").nth(7).inner_text()
    check("progress", "course map shows Module 8 Completed", "Research" in card and "Completed" in card, card)
    goto(pg, M8 + "#task-3", 2)
    ev = pg.locator(".ws-preview").inner_text() if pg.locator(".ws-preview").count() else ""
    check("work-sample", "the report survives reload with an honest training header that says the outside data is fictional",
          ev.startswith("TRAINING WORK SAMPLE\nEverfield Goods — Mini Competitive Research Report") and "fictional training data" in ev and
          "Work date: Fri, Sep 11 (simulated)" in ev and "Sofia Ramirez" in ev and "human review" in ev, ev[:400])
    check("work-sample", "the report carries the range, the basis, the findings and the learner's observation",
          all(x in ev for x in [LOW, HIGH, acc_label(P3, "rng.basis"), acc_label(P3, "fnd.rev"), acc_label(P3, "fnd.claim"), obs_text(0, 0, 0, 0)]), ev[:900])
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
        if st["type"] == "triage":
            labels = [c["label"] for c in st["choices"]]
            check("feedback-safety", "%s: per-row pointers never name a call" % st["id"], not [l for l in labels if l in fb.split("WHY")[0]], fb[:200])
        if st["type"] == "compose":
            acc = [acc_label(st, f["id"]) for f in st["fields"] if f["type"] == "select"]
            check("feedback-safety", "%s: feedback never quotes an accepted choice" % st["id"], not [a for a in acc if a in fb], fb[:200])
        retry = r.get_by_role("button", name="Reconsider and try again")
        if retry.count(): retry.click(); pg.wait_for_timeout(30)
        fail_once(pg, st)
        if st["type"] == "compose" and not any(f["type"] != "text" for f in st["fields"]):
            # a writing problem is not an evidence miss: the engine never pauses on it, and there is no attempt limit
            check("retry", "%s: a second weak description gets feedback again, with no pause and no lock-out" % st["id"],
                  r.locator(".desk-pause").count() == 0 and len(fb_text(pg)) > 60 and not pg.is_enabled("#btnNext"))
            solve(pg, st)
            check("retry", "%s: corrected attempt passes with no attempt limit" % st["id"], pg.is_enabled("#btnNext"))
            continue
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


    # ---------- transfer, principle-only feedback ----------
    ctx, pg, _ = fresh(br)
    for ti, st in ALL:
        if st["type"] != "decision": continue
        to_stage(pg, ti, st["id"]); open_all(pg)
        answer_decision(pg, st, findings=correct_findings(st)[:-1])
        check("transfer", "%s: right action without the full reading of the evidence fails" % st["id"], not pg.is_enabled("#btnNext"))
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

    # ---------- research-discipline traps (D5-D8) ----------
    ctx, pg, _ = fresh(br)
    for ti, st, oid, why in [(0, S1, "category", "scoping to every storage product"), (0, S1, "single", "leaving out multi-packs to avoid the unit arithmetic"),
                             (1, K2, "fact", "reporting the listing's own load figure as fact"), (1, K2, "listing", "putting an outside claim on Everfield's listing")]:
        to_stage(pg, ti, st["id"]); open_all(pg)
        answer_decision(pg, st, option=oid)
        check("trap", "%s: %s fails, even with every finding right" % (st["id"], why), not pg.is_enabled("#btnNext"))
    ctx.close()
    ctx, pg, _ = fresh(br)
    to_stage(pg, 1, "l2-a"); open_all(pg)
    other = [k for k in LISTINGS if k not in COMP]
    check("trap", "l2-a: counting a different product type as comparable fails", not attempt_in(pg, C2, **{"set.items": sorted(list(COMP) + other[:1])})[0])
    check("trap", "l2-a: leaving a comparable bin out fails", not attempt_in(pg, C2, **{"set.items": sorted(list(COMP)[1:])})[0])
    mk = next(k for k, v in COMP.items() if v["units"] > 1 and "%.2f" % ((v["price"] + v["ship"]) / v["units"]) != PER[k])
    v = COMP[mk]
    check("trap", "l2-a: a per-unit figure with shipping folded in fails (D7)", not attempt_in(pg, C2, **{"unit." + mk: "%.2f" % ((v["price"] + v["ship"]) / v["units"])})[0])
    check("trap", "l2-a: the pack's sticker price typed as a per-unit price fails", not attempt_in(pg, C2, **{"unit." + mk: "%.2f" % v["price"]})[0])
    check("trap", "l2-a: calling the figures 'per unit with shipping added' fails", not attempt_in(pg, C2, **{"unit.basis": "deliv"})[0])
    check("trap", "l2-a: the per-unit price passes however it is typed ($, trailing zero)", attempt_in(pg, C2, **{"unit." + mk: "$" + PER[mk]})[0] and attempt_in(pg, C2, **{"unit." + mk: PER[mk].rstrip("0")})[0])
    ctx.close()
    ctx, pg, _ = fresh(br)
    to_stage(pg, 2, "l3-b"); open_all(pg)
    noncomp_hi = "%.2f" % max(LISTINGS[k]["price"] / LISTINGS[k]["units"] for k in other)
    check("trap", "l3-b: a range stretched by a non-comparable item fails", not attempt_in(pg, P3, **{"rng.high": noncomp_hi})[0])
    check("trap", "l3-b: the load claim reported as a fact fails", not attempt_in(pg, P3, **{"fnd.claim": "fact"})[0])
    check("trap", "l3-b: the claim called 'verified by the specifications' fails", not attempt_in(pg, P3, **{"fnd.claim": "verified"})[0])
    check("trap", "l3-b: a one-off opinion reported as the review finding fails", not attempt_in(pg, P3, **{"fnd.rev": "colour"})[0])
    ctx.close()
    ctx, pg, _ = fresh(br)
    to_stage(pg, 0, "l1-a"); open_all(pg)
    rec_id = next(c["id"] for c in A1["choices"] if c["label"].startswith("Answered by the record"))
    res_id = next(c["id"] for c in A1["choices"] if c["label"].startswith("Needs outside research"))
    dec_id = next(c["id"] for c in A1["choices"] if c["label"].startswith("Sofia's decision"))
    for i, rw in enumerate(A1["rows"]):
        panel(pg).locator("select.desk-select").nth(i).select_option(res_id if rw["answer"] == rec_id else rw["answer"])
    panel(pg).locator("button[type=submit]").first.click(); pg.wait_for_timeout(60)
    check("trap", "l1-a: researching what the record already answers fails", not pg.is_enabled("#btnNext"))
    goto(pg, M8 + "#task-1", 1); open_all(pg)
    for i, rw in enumerate(A1["rows"]):
        panel(pg).locator("select.desk-select").nth(i).select_option(res_id if rw["answer"] == dec_id else rw["answer"])
    panel(pg).locator("button[type=submit]").first.click(); pg.wait_for_timeout(60)
    check("trap", "l1-a: treating a pricing decision as a research question fails", not pg.is_enabled("#btnNext"))
    ctx.close()

    # ---------- opening a later lesson first gives no shortcut to an earlier one ----------
    later = " ".join(learner_text(t) for t in TASKS[1:])
    l3 = learner_text(TASKS[2])
    check("later-first", "Lessons 2 and 3 never print a Lesson 1 call", not [c["label"] for c in A1["choices"] if c["label"] in later])
    check("later-first", "Lesson 3 never prints a Lesson 2 per-unit answer or the accepted claim action",
          not [PER[k] for k, v in COMP.items() if v["units"] > 1 and ("$" + PER[k]) in l3] and option_text(K2, correct_option(K2))[:50] not in l3)
    check("later-first", "Lessons 1 and 2 never print the report's range", not re.search(r"\$%s|\$%s" % (re.escape(LOW), re.escape(HIGH)), learner_text(TASKS[0]) + learner_text(TASKS[1])))
    ctx, pg, errs = fresh(br)
    goto(pg, M8); pg.locator(".lesson-pill").nth(2).click(); pg.wait_for_timeout(100)
    pg.click("#btnNext"); pg.wait_for_timeout(60); open_all(pg)
    solve(pg, R3)
    check("later-first", "Lesson 3 stays usable when opened first", pg.is_enabled("#btnNext"))
    check("later-first", "no JS errors", not errs, errs)
    ctx.close()

    # ---------- cross-module: Module 8 prints no other module's graded answers ----------
    TEAM = set("%s, %s" % (p["name"], p["role"]) for p in DATA["team"].values())  # canon identities, not answers
    m8_all = EVERY + " " + " ".join(rec_text(r) for _, s in ALL for r in records_of(s))
    leaks, stores_elsewhere = [], []
    store_names = {v["store"] for v in LISTINGS.values()}
    for mod in ("module-2", "module-3", "module-4", "module-5", "module-6", "module-7", "module-9", "module-13"):
        dm = decode(mod)
        if [n for n in store_names if n in json.dumps(dm)]: stores_elsewhere.append(mod)
        for t in dm["tasks"]:
            for s in t["stages"]:
                for o in s.get("options", []):
                    if o.get("correct") and o["text"][:60] in m8_all: leaks.append((mod, s["id"], "option"))
                for f in s.get("findings", []):
                    if f.get("correct") and len(f["text"]) > 24 and f["text"] in m8_all: leaks.append((mod, s["id"], f["id"]))
                for f in s.get("fields", []):
                    if f["type"] == "number":
                        for a in f.get("accept", []):
                            if float(a) >= 10 and re.search(r"(?<![\d.#$/:-])(?<!Sep )(?<!Oct )%s(?![\d./:])" % re.escape(a), m8_all): leaks.append((mod, s["id"], f["id"], a))
                    if f["type"] in ("select", "multi"):
                        vals = [v for a in f.get("accept", []) for v in (a if isinstance(a, list) else [a])]
                        for v in vals:
                            lbl = next((o["label"] for o in f["options"] if o["value"] == v), "")
                            if len(lbl) > 24 and not re.match(r"^EF-\d{3} [A-Z][\w ]+$", lbl) and lbl not in TEAM and lbl in m8_all: leaks.append((mod, s["id"], f["id"], lbl[:40]))
    check("cross-module", "no correct option, finding, accepted label or typed figure (>= 10) from Modules 2-7, 9 or 13 appears in Module 8", not leaks, leaks[:6])
    check("cross-module", "Module 8's simulated stores appear in no other module", not stores_elsewhere, stores_elsewhere)
    check("cross-module", "Module 8 writes no customer reply, listing copy or AI draft (M6, M3, M12 own those)", not re.search(r"\bAI\b|ChatGPT|Dear customer|Hi [A-Z][a-z]+,", EVERY))

    # ---------- shortcut attempts, derived completion, the observation ----------
    ctx, pg, _ = fresh(br); goto(pg, M8)
    pg.evaluate("""localStorage.setItem('%s', JSON.stringify({v:1,tasks:{'m8-l7':{completed:true,verified:true,views:1,
      stages:{'l3-a':{passed:true},'l3-b':{passed:true,answer:{values:{},confirms:[true,true]}}},drafts:{}}}}))""" % KEY)
    goto(pg, M8 + "#task-3")
    st3 = pg.evaluate("PVADesk.taskStatus(PVADesk.decode(window.PVA_DESK_MODULES.m8.payload).tasks[2])")
    check("integrity", "forged completed/verified/passed flags count for nothing", st3["passed"] == 0, st3)
    check("integrity", "forged state never reaches the legacy progress store", not (pg.evaluate("JSON.parse(localStorage.getItem('pva-ecom-ft-progress')||'{}')").get("lessons") or {}).get("m8-l7"))
    ctx.close()
    ctx, pg, _ = fresh(br)
    to_stage(pg, 2, "l3-b"); open_all(pg)
    st_name = claimer["store"]
    GOOD = [("both findings", obs_text(0, 0, 0, 0)),
            ("range alone, with its basis", "Per-unit prices for comparable bins run from %s to %s before shipping. Shipping is listed separately for each store." % (LOW, HIGH)),
            ("the pattern alone", "Corners cracking is the one real pattern in the reviews. It came up at three separate stores."),
            ("the claim reported as a claim", "The four comparable listings range from $%s to $%s a unit, shipping not included. One store claims its bins hold 50 lb, but nothing verifies that." % (LOW, HIGH))]
    for why, t in GOOD:
        okk, fbx = attempt_in(pg, P3, **{"obs.text": t})
        check("l3-observation", "passes -- %s" % why, okk, (t, fbx[:200]))
    BAD = [("is filler", "I looked at a lot of listings today and found some interesting things. It was a useful exercise overall."),
           ("recommends a price cut", "Comparable bins sell for $%s to $%s per unit. We should lower our price to stay competitive." % (LOW, HIGH)),
           ("recommends matching", "Prices run from $%s to $%s per unit before shipping. I recommend matching the lowest price." % (LOW, HIGH)),
           ("tells Sofia what to do", "Three stores' reviews mention cracked corners. Sofia should look at a stronger bin."),
           ("states the claim as fact", "Comparable bins range from $%s to $%s per unit and hold up to 50 lb. Corners crack in some reviews." % (LOW, HIGH)),
           ("gives no finding", "The research is done and the listings are in the table. Shipping is shown separately for each store."),
           ("adds hype", "Corners crack at three stores! Prices are $%s to $%s per unit before shipping." % (LOW, HIGH))]
    for why, t in BAD:
        check("l3-observation", "rejected -- an observation that %s" % why, not attempt_in(pg, P3, **{"obs.text": t})[0], t)
    ctx.close()

    # ---------- answer encoding / leakage ----------
    ctx, pg, _ = fresh(br)
    shipped = "".join(pg.request.get(BASE + uu).text() for uu in ["/module-8/index.html", "/module-8/desk-data.js", "/shared/workdesk.js", "/shared/workdesk-ui.js", "/shared/workdesk-page.js", "/shared/everfield-data.js"])
    markers = ['"correct"', "correct: true", '"accept"', '"answer":', '"correctOrder"']
    check("leakage", "no plaintext answer markers in any shipped engine or content file", not any(m in shipped for m in markers), [m for m in markers if m in shipped])
    check("leakage", "no correct option text appears in shipped source", not any(option_text(s, correct_option(s)) in shipped for _, s in ALL if s["type"] == "decision"))
    vals_dom = []
    for ti in range(len(TASKS)):
        goto(pg, M8 + "#task-%d" % (ti + 1), 1); open_all(pg)
        check("leakage", "task %d: rendered DOM carries no correctness attributes before submission" % (ti + 1), not re.search(r'(class|data-[a-z-]+)="[^"]*(correct|answer|right)', pg.content()))
        vals_dom += pg.evaluate("Array.from(document.querySelectorAll('#stagePanel input,#stagePanel option')).map(e=>e.value)")
    badv = [x for x in vals_dom if re.match(r"^(correct|right|wrong|[fx]_)", x)]
    check("leakage", "no control value names the answer", not badv, badv)
    dec = pg.evaluate("JSON.stringify(PVADesk.decode(window.PVA_DESK_MODULES.m8.payload))")
    check("leakage", "decoded payload holds hashed keys only", '"correct"' not in dec and '"accept"' not in dec and '"answer"' not in dec)
    sel = [f for _, s in ALL if s["type"] == "compose" for f in s["fields"] if f["type"] == "select"]
    longest = [f["id"] for f in sel if len(label_of(f, f["accept"][0])) == max(len(o["label"]) for o in f["options"])]
    positions = [next(i for i, o in enumerate(f["options"]) if o["value"] == f["accept"][0]) for f in sel]
    check("leakage", "accepted select options are not the longest (at most a quarter) and spread across every position",
          len(longest) <= len(sel) // 4 and len(set(positions)) == 4 and max(positions.count(i) for i in range(4)) <= len(sel) // 2, (longest, positions))
    dl = [(s["id"], [len(o["text"]) for o in s["options"]], next(i for i, o in enumerate(s["options"]) if o.get("correct"))) for _, s in ALL if s["type"] == "decision"]
    check("leakage", "no decision's correct option is its longest", not [x for x in dl if x[1][x[2]] == max(x[1])], dl)
    ctx.close()


    # ---------- persistence ----------
    ctx, pg, _ = fresh(br)
    to_stage(pg, 0, "l1-a"); open_all(pg)
    panel(pg).locator("select.desk-select").first.select_option(A1["rows"][0]["answer"])
    pg.reload(); pg.wait_for_timeout(150); pg.click("#btnNext"); pg.wait_for_timeout(80)
    check("persistence", "an unsubmitted triage call survives refresh", panel(pg).locator("select.desk-select").first.input_value() == A1["rows"][0]["answer"])
    to_stage(pg, 2, "l3-b"); open_all(pg)
    panel(pg).get_by_label(field(P3, "obs.text")["label"], exact=True).fill("Draft observation")
    pg.reload(); pg.wait_for_timeout(150); pg.click("#btnNext"); pg.wait_for_timeout(80)
    if not panel(pg).get_by_label(field(P3, "obs.text")["label"], exact=True).count(): pg.click("#btnNext"); pg.wait_for_timeout(80)
    check("persistence", "an unsent observation survives refresh", panel(pg).get_by_label(field(P3, "obs.text")["label"], exact=True).input_value() == "Draft observation")
    ctx.close()

    # ---------- legacy progress compatibility (D3: existing ids only) ----------
    ctx, pg, _ = fresh(br); goto(pg, BASE + "/index.html")
    pg.evaluate("v => localStorage.setItem('pva-ecom-ft-progress', JSON.stringify(v))", {"lessons": {"m8-l%d" % i: True for i in range(1, 9)}, "modules": {}})
    goto(pg, M8 + "#task-1")
    check("legacy", "all three lessons keep their earlier checkmarks", pg.locator(".lesson-pill.done").count() == 3)
    check("legacy", "the status line separates legacy completion from new work", "earlier version" in pg.inner_text("#taskStatus"))
    vw = pg.evaluate("PVADesk.verifiedWork()")
    check("legacy", "legacy completion is not verified work", not any(v["verified"] for v in vw.values()) and not any(v["samplesEarned"] for v in vw.values()))
    goto(pg, BASE + "/index.html")
    check("legacy", "someone who finished old Module 8 still sees it Completed on the course map", pg.locator(".module-status").nth(7).inner_text() == "Completed")
    pg.evaluate("v => localStorage.setItem('pva-ecom-ft-progress', JSON.stringify(v))", {"lessons": {"m8-l1": True, "m8-l7": True}, "modules": {}})
    goto(pg, BASE + "/index.html")
    check("legacy", "the course map counts Module 8 against its three lessons", "2 of 3" in pg.locator(".module-card").nth(7).inner_text(), pg.locator(".module-card").nth(7).inner_text())
    ctx.close()
    port = open(os.path.join(ROOT, "portfolio", "index.html"), encoding="utf-8").read()
    check("portfolio", "the portfolio points at Module 8, Lesson 3", "From Module 8, Lesson 3 -- Report What You Found" in port and "Lesson 7 -- Organizing Findings" not in port)

    # ---------- isolation and shared authored state ----------
    ctx, pg, _ = fresh(br)
    goto(pg, M7 + "#task-1", 1); open_all(pg)
    m7a = decode("module-7")["tasks"][0]["stages"][0]
    answer_triage(pg, m7a)
    to_stage(pg, 0, "l1-a"); solve(pg, A1)
    keys = pg.evaluate("Object.keys(localStorage).sort()")
    check("isolation", "Module 8 and Module 7 keep separate desk keys, and nothing else is written", set(keys) - {"pva-ecom-ft-progress"} == {KEY, "pva-ecom-ft-m7-desk"}, keys)
    m7store = pg.evaluate("JSON.parse(localStorage.getItem('pva-ecom-ft-m7-desk'))")
    check("isolation", "Module 8 work writes nothing into Module 7's store", list(m7store["tasks"].keys()) == ["m7-l1"], list(m7store["tasks"].keys()))
    goto(pg, M8)
    mut = pg.evaluate("(()=>{try{EVERFIELD.calendar.m8.date='Y'; EVERFIELD.productFacts['EF-101'].dimensions='Z';}catch(e){} return [EVERFIELD.calendar.m8.date, EVERFIELD.productFacts['EF-101'].dimensions]})()")
    check("everfield", "shared Everfield reference cannot be mutated from Module 8", mut == ["Fri, Sep 11", FACTS["EF-101"]["dimensions"]], mut)
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
        goto(pg, M8 + "#task-%d" % n); check("deep-link", "#task-%d opens task %d" % (n, n), pg.inner_text("#lessonKicker") == "Task %d of 3" % n and pg.text_content("#deskDate") == "Fri, Sep 11")
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
    goto(pg, M8 + "#task-1"); low += pg.evaluate(CONTRAST)
    pg.click("#btnNext"); pg.wait_for_timeout(60); open_all(pg); low += pg.evaluate(CONTRAST)
    fail_once(pg, A1); low += pg.evaluate(CONTRAST)
    to_stage(pg, 0, "l1-b"); fail_once(pg, S1); low += pg.evaluate(CONTRAST)
    panel(pg).get_by_role("button", name="Reconsider and try again").click(); fail_once(pg, S1); low += pg.evaluate(CONTRAST)
    to_stage(pg, 1, "l2-a"); fail_once(pg, C2); low += pg.evaluate(CONTRAST)
    to_stage(pg, 2, "l3-b"); open_all(pg); solve(pg, P3); low += pg.evaluate(CONTRAST)
    check("contrast", "all enabled text meets WCAG AA in brief, compose, decision, triage, feedback, pause and work-sample states", not low, sorted(set(low))[:8])
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
