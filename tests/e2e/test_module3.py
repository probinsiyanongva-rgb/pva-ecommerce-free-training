"""Module 3 Work Desk regression + adversarial suite (browser), modelled on Module 2's.

Run from the repo root with a static server on :8765 (see tests/README.md):
    python3 tests/e2e/test_module3.py
Answers come from decoding the shipped content at run time (desk_helpers.decode). The
"recompute" checks derive every accepted listing value, call and change from the records
and the shared product canon; the "source rule" checks (decision D4) prove a listing only
ever states what the approved, current record states; the cross-module checks decode
Modules 2, 4, 5, 6, 7, 9 and 13 to prove Module 3 prints none of their graded answers. So
nothing answer-bearing is stored here."""
import os, sys, re, json, subprocess
from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from desk_helpers import *  # noqa

SRC = decode("module-3")
M3 = BASE + "/module-3/index.html"
M7 = BASE + "/module-7/index.html"
TASKS = SRC["tasks"]
IDS = [t["id"] for t in TASKS]
ALL = [(ti, s) for ti, t in enumerate(TASKS) for s in t["stages"]]
KEY = "pva-ecom-ft-m3-desk"
DATA = json.loads(subprocess.run(["node", "-e", "process.stdout.write(JSON.stringify(require('./shared/everfield-data.js')))"], cwd=ROOT, capture_output=True, text=True).stdout)
FACTS, NAMES = DATA["productFacts"], DATA["products"]
DASH = "—"
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


def is_approved_current(r):
    t = r.get("title", "") + " " + r.get("label", "")
    return bool(re.search(r"approved", t, re.I)) and not re.search(r"draft|superseded|not a product record|never published", t, re.I)


B1, D1 = stage_by_id(SRC, "l1-a"), stage_by_id(SRC, "l1-b")
I2, W2 = stage_by_id(SRC, "l2-a"), stage_by_id(SRC, "l2-b")
Q3, P3 = stage_by_id(SRC, "l3-a"), stage_by_id(SRC, "l3-b")
EVERY = " ".join(learner_text(t) for t in TASKS)
REC = next(r for r in group_records(B1, "ttl") if is_approved_current(r))
RECV = {k: v["Value"] for k, v in table_rows(REC).items()}
LEAVE = next(o["label"] for f in B1["fields"] for o in f["options"] if o["label"].startswith("Leave off"))
LIB = next(r for r in I2["records"] if "asset library" in r.get("title", ""))
FRONT = next(f for f, v in table_rows(LIB).items() if re.search(r"One EF-101 bin.*white background", v["What it shows"]))


def desc_text(st, g, f, labels):
    return "A stackable storage bin for keeping shelves and closets tidy. It measures %s and weighs %s." % (RECV["Dimensions"], RECV["Weight"])


def solve(pg, st):
    open_all(pg)
    if st["type"] == "decision": answer_decision(pg, st)
    elif st["type"] == "triage": answer_triage(pg, st)
    else:
        fill_compose(pg, st, compose_values(st, desc_text)); confirm_all(pg); submit(pg)


def fail_once(pg, st):
    open_all(pg)
    if st["type"] == "decision":
        cf = correct_findings(st)
        answer_decision(pg, st, findings=cf[1:] + distractors(st)[:1], option=(wrong_options(st) or [None])[0])
    elif st["type"] == "triage": answer_triage(pg, st, wrong=True)
    else:
        vals = compose_values(st, desc_text)
        sel = next((x for x in st["fields"] if x["type"] == "select"), None)
        if sel: vals[sel["id"]] = first_unaccepted(sel)
        else: vals["desc.text"] = "This is a great product that you will really love and use every day in your home."
        fill_compose(pg, st, vals); confirm_all(pg); submit(pg)


def to_stage(pg, ti, sid):
    goto(pg, M3 + "#task-%d" % (ti + 1), 1)
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
    check("design", "3 tasks with the approved ids (D3)", IDS == ["m3-l2", "m3-l3", "m3-l8"], IDS)
    check("design", "titles follow the design map", [t["title"] for t in TASKS] == ["From Record to Listing", "Words and Pictures That Match", "Listing QA"])
    kinds = {t["id"]: [s["type"] for s in t["stages"]] for t in TASKS}
    check("design", "stage types match the map", kinds == {"m3-l2": ["compose", "decision"], "m3-l3": ["decision", "compose"], "m3-l8": ["triage", "compose"]}, kinds)
    check("design", "only Lesson 3 is a portfolio task, with the unchanged portfolio label",
          [(t["id"], t.get("portfolio")) for t in TASKS if t.get("portfolio")] == [("m3-l8", "Portfolio piece: Listing Pack")])
    check("design", "Sofia, who owns the listings, asks for all three lessons and the pack",
          [t["brief"]["from"] for t in TASKS] == ["sofia", "sofia", "sofia"] and "Sofia Ramirez" in P3["evidence"]["requestedBy"])
    check("design", "one listing-desk day: every clock reads Wed, Sep 9, and no lesson declares its own work date",
          all(s["now"].startswith("Wed, Sep 9") for _, s in ALL) and not any(t.get("workDate") for t in TASKS))
    texts = [(s["id"], f["id"]) for _, s in ALL if s["type"] == "compose" for f in s["fields"] if f["type"] == "text"]
    check("design", "exactly one own-words field: Lesson 2's description; titles are built from choices (D7)", texts == [("l2-b", "desc.text")], texts)
    check("design", "no typed numbers anywhere", not any(f["type"] == "number" for _, s in ALL if s["type"] == "compose" for f in s["fields"]))
    check("design", "the Listing Pack declares a self-check and human review", len(P3["confirm"]) >= 2 and P3.get("humanReview"))
    check("design", "every Lesson 1 spec line offers 'Leave off: not recorded'", all(LEAVE in [o["label"] for o in f["options"]] for f in B1["fields"] if f["group"] == "spc"))
    check("design", "Lesson 3's queue uses every call", set(r["answer"] for r in Q3["rows"]) == set(c["id"] for c in Q3["choices"]))
    check("design", "images are text cards: file names and what each shows, no image assets (D9)",
          "File" in " ".join(LIB["columns"]) and not re.search(r"<img|\.png\"|data:image", json.dumps(SRC)))

    # ---------- D4 source rule, D5 prices, D6 authority, D8 keywords ----------
    refs = " ".join(strip(x) for t in TASKS for x in t.get("reference", []))
    rule = next(strip(x) for x in TASKS[0]["reference"] if "Where listing facts come from" in x)
    check("d4", "the learner-facing rule: a listing states only what the approved, current record states",
          "only what the approved, current product record states" in rule and all(x in rule for x in ["marketing copy", "old draft", "competitor's listing", "work out yourself"]), rule)
    check("d4", "the rule says to leave a silent field off and flag it, and never change the record from the listing desk",
          "leave the claim off the listing and flag" in rule and "Never change the product record from the listing desk" in rule)
    check("d4", "every lesson carries the rule", all(any("Where listing facts come from" in x for x in t["reference"]) for t in TASKS))
    check("d5", "no price or cost appears anywhere in Module 3", not re.search(r"\$\s?\d", json.dumps(SRC)))
    check("d5", "the price line is 'Set by Sofia' and its only graded choice keeps it that way", acc_label(P3, "pk.price") == "Set by Sofia")
    check("d6", "the reference splits authority: the VA fixes a listing to match the record; prices, publishing and unsupported claims are Sofia's",
          re.search(r"You may fix a listing so it matches the approved record", refs) and re.search(r"Prices, publishing and any claim the record doesn't support are her decisions", refs))
    rules_txt = json.dumps([r for f in W2["fields"] for r in f.get("rules", [])] + W2.get("banned", []))
    check("d8", "keyword awareness is reference text only; no validator mentions keywords or search terms",
          "keyword" in refs.lower() and not re.search(r"keyword|search term|seo", rules_txt, re.I))

    # ---------- D11 / D12: canon and capstone separation ----------
    countrx = r"(EF-106|Closet Divider)[^.]{0,80}\b\d+[- ]?(pack|pieces?|dividers)\b"
    outside = [s["id"] for _, s in ALL if re.search(countrx, json.dumps(dict(s, records=[])), re.I)] + \
              [t["id"] for t in TASKS if re.search(countrx, " ".join(t["reference"]) + " ".join(t["brief"]["body"]), re.I)]
    check("d11", "an EF-106 count appears only as unapproved draft evidence in Lesson 1, never in canon or an accepted answer",
          not outside and not any(re.search("pack|piece|count", k, re.I) for k in FACTS.get("EF-106", {})) and
          not re.search(r"\d", option_text(D1, correct_option(D1)).replace("6-Pack", "")) and "6-Pack" in rec_text(D1["records"][0]), outside)
    check("d11", "no retired legacy-only claims survive ('Write-On', 'three sizes', 'washable', 'Channel B')", not re.search(r"Write-On|three sizes|washable|Channel B", EVERY, re.I))
    check("d12", "EF-107 never appears (the capstone owns the EF-107-with-EF-106-photo case)", "EF-107" not in json.dumps(SRC))
    prim = table_rows(next(r for r in I2["records"] if r.get("title", "").startswith("Image set")))
    pfile = next(v["File"] for k, v in prim.items() if "primary" in k)
    check("d12", "Module 3's wrong-photo case is EF-101's listing carrying EF-103's file", pfile.startswith("ef-103") and "EF-101" in I2["records"][0]["title"])

    # ---------- canon and continuity ----------
    check("canon", "no orders, returns or tracking numbers", not re.search(r"#\d{3,}\b|CP-\d{4}-\d{4}", EVERY))
    check("canon", "no marketplace listing IDs (Module 2-local) and no stock figures",
          not re.search(r"MKT-\d+", EVERY) and not re.search(r"\b\d+ available\b|\bAvailable\b|\bInbound\b|\bReserved\b|\bon hand\b", EVERY))
    check("canon", "every catalog name printed matches the catalog",
          not [m for m in re.findall(r"(EF-\d{3}) ([A-Z][a-z]+(?: [A-Z][a-z]+)+)", EVERY) if m[0] in NAMES and not NAMES[m[0]].startswith(m[1].split(" ")[0])
               and m[1] not in set(v.get("category", "") for v in FACTS.values() if isinstance(v, dict))])
    check("canon", "intentionally undefined facts stay undefined: EF-101 material and pack count, EF-200 weight, EF-106 count",
          not any(re.search("material|pack", k, re.I) for k in FACTS["EF-101"]) and not any(re.search("weight", k, re.I) for k in FACTS["EF-200"]))
    out = subprocess.run(["node", os.path.join(ROOT, "tools", "everfield-check.js")], capture_output=True, text=True)
    check("continuity", "the continuity checker passes, with the Module 3 range check", out.returncode == 0 and "ok   Module 3 day stays in its ranges" in out.stdout, out.stdout[-400:])
    check("continuity", "calendar.m3 is Wed, Sep 9, between M2's Tue Sep 8 and M6's Thu Sep 10",
          DATA["calendar"]["m3"]["date"] == "Wed, Sep 9" and DATA["calendar"]["m2"]["date"] == "Tue, Sep 8" and DATA["calendar"]["m6"]["date"] == "Thu, Sep 10")
    check("continuity", "no product fact cites a retired Module 3 lesson (D11)", not re.search(r"module-3 m3-l(1|4|5|6|7|9)\b", json.dumps(DATA)))

    # ---------- recompute: every accepted answer derived from the evidence ----------
    check("recompute", "the Lesson 1 record is the shared product canon", RECV["Product name"] == NAMES["EF-101"] and RECV["Category"] == FACTS["EF-101"]["category"] and
          RECV["Dimensions"] == FACTS["EF-101"]["dimensions"] and RECV["Weight"] == FACTS["EF-101"]["weight"] and RECV["Material"] == DASH and RECV["Pack count"] == DASH)
    want = {"ttl.type": RECV["Product name"], "ttl.detail": RECV["Dimensions"], "spc.dims": RECV["Dimensions"], "spc.weight": RECV["Weight"],
            "spc.material": LEAVE if RECV["Material"] == DASH else RECV["Material"], "cat.cat": RECV["Category"]}
    check("recompute", "Lesson 1: every title part, spec line and category is the record's value, or 'leave off' where the record is silent",
          all(acc_label(B1, k) == v for k, v in want.items()), {k: (v, acc_label(B1, k)) for k, v in want.items() if acc_label(B1, k) != v})
    check("recompute", "Lesson 1: with no pack count recorded, the title carries no quantity", RECV["Pack count"] == DASH and not re.search(r"\d|pack|set|single|individually", acc_label(B1, "ttl.qty"), re.I))
    others = [r for r in group_records(B1, "ttl") if not is_approved_current(r)]
    check("d4", "Lesson 1: no accepted value comes only from the marketing sheet or the old draft",
          others and not [k for k in want if acc_label(B1, k) not in rec_text(REC) and any(acc_label(B1, k) in rec_text(o) for o in others)])
    rec106 = table_rows(next(r for r in D1["records"] if is_approved_current(r)))
    check("recompute", "Lesson 1B: EF-106's approved record holds no pack count, so the accepted action takes it off and flags it without touching the record",
          rec106["Pack count"]["Value"] == DASH and re.search(r"out", option_text(D1, correct_option(D1))) and "flag" in option_text(D1, correct_option(D1)) and
          "record" in option_text(D1, "record") and not re.search(r"\b(add|update|change)\b[^.]*record", option_text(D1, correct_option(D1)), re.I))
    swap = option_text(I2, correct_option(I2))
    check("recompute", "Lesson 2A: the primary file is another product's, the library holds an approved EF-101 product-only shot, and the fix uses it and tells Sofia",
          pfile.startswith("ef-103") and is_approved_current(LIB) and FRONT.startswith("ef-101") and "library" in swap and "tell Sofia" in swap)
    check("recompute", "Lesson 2B: the example description uses only the record's facts", RECV["Dimensions"] in desc_text(0, 0, 0, 0) and RECV["Weight"] in desc_text(0, 0, 0, 0))
    def call(r):
        f = fields_of(r)
        if "Listing says" not in f: return "sofia"
        rv = re.sub(r"^[^:]*: ", "", f["Approved record"])
        if DASH in rv: return "off"
        return "ok" if (rv in f["Listing says"] or f["Listing says"] in rv) else "fix"
    derived = {r["id"]: call(r) for r in Q3["rows"]}
    check("recompute", "Lesson 3A: every call follows from its own line (matches, differs from the record, record silent, or a decision)",
          all(derived[r["id"]] == r["answer"] for r in Q3["rows"]), derived)
    kitline = fields_of(next(r for r in Q3["rows"] if "What's in the kit" in r["title"]))["Approved record"]
    check("recompute", "Lesson 3A: the kit's contents line is the shared kit recipe, and the kit's category line is the canon listing category",
          all(("%d × %s" % (n, s)) in kitline for s, n in FACTS["EF-200"]["kit"].items()) and
          FACTS["EF-200"]["listingCategory"] in fields_of(next(r for r in Q3["rows"] if r["title"].startswith("EF-200") and "Category" in r["title"]))["Approved record"])
    check("recompute", "Lesson 3B: the pack's title, image, specs and category come from the record and the approved library",
          acc_label(P3, "pk.title") == RECV["Product name"] + " -- " + RECV["Dimensions"] and acc_label(P3, "pk.image") == FRONT and
          acc_label(P3, "pk.specs") == "Dimensions: %s · Weight: %s" % (RECV["Dimensions"], RECV["Weight"]) and acc_label(P3, "pk.cat") == RECV["Category"])
    nt = field(P3, "nt.items"); acc_notes = [label_of(nt, v) for v in nt["accept"][0]]
    check("recompute", "Lesson 3B: the change note reports the VA's own changes only: no price, record or publishing change",
          len(acc_notes) == 3 and not [a for a in acc_notes if re.search(r"price|record updated|published", a, re.I)], acc_notes)

    # ---------- normal flow, completion, work sample ----------
    ctx, pg, errs = fresh(br); goto(pg, M3)
    check("page", "desk bar shows Wed, Sep 9 and the task count", pg.text_content("#deskDate") == "Wed, Sep 9" and pg.inner_text("#lessonKicker") == "Task 1 of 3")
    for ti, t in enumerate(TASKS):
        goto(pg, M3 + "#task-%d" % (ti + 1), 1); ok = True
        for st in t["stages"]:
            solve(pg, st)
            if not pg.is_enabled("#btnNext"): ok = False; break
            pg.click("#btnNext"); pg.wait_for_timeout(60)
        check("flow", "task %d completes through the UI" % (ti + 1), ok)
    check("flow", "completion banner", "Module 3 complete" in pg.inner_text("#doneBanner"), pg.inner_text("#doneBanner"))
    prog = pg.evaluate("JSON.parse(localStorage.getItem('pva-ecom-ft-progress'))")
    check("progress", "verified work marks all three lessons in the legacy progress store", all(prog["lessons"].get(i) for i in IDS))
    keys = pg.evaluate("Object.keys(localStorage).sort()")
    check("isolation", "only the Module 3 desk key and the legacy progress key are written", keys == [KEY, "pva-ecom-ft-progress"], keys)
    vw = pg.evaluate("PVADesk.verifiedWork()")
    check("verified-work", "verifiedWork() reports all three tasks verified and the one earned sample",
          all(v["verified"] for v in vw.values()) and vw["m3-l8"]["samplesEarned"] == ["l3-b"] and not any(v["samplesEarned"] for k, v in vw.items() if k != "m3-l8"), vw)
    goto(pg, BASE + "/index.html")
    card = pg.locator(".module-card").nth(2).inner_text()
    check("progress", "course map shows Module 3 Completed", "Product Listings" in card and "Completed" in card, card)
    goto(pg, M3 + "#task-3", 2)
    ev = pg.locator(".ws-preview").inner_text() if pg.locator(".ws-preview").count() else ""
    check("work-sample", "the Listing Pack survives reload with an honest training header",
          ev.startswith("TRAINING WORK SAMPLE\nEverfield Goods — Listing Pack") and "fictional company" in ev and
          "Work date: Wed, Sep 9 (simulated)" in ev and "Sofia Ramirez" in ev and "human review" in ev, ev[:400])
    check("work-sample", "the pack carries every listing line and the change note",
          all(acc_label(P3, f["id"]) in ev for f in P3["fields"] if f["type"] == "select") and all(a in ev for a in acc_notes), ev[:900])
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

    # ---------- transfer, source-rule traps and principle-only feedback ----------
    ctx, pg, _ = fresh(br)
    for ti, st in ALL:
        if st["type"] != "decision": continue
        to_stage(pg, ti, st["id"]); open_all(pg)
        answer_decision(pg, st, findings=correct_findings(st)[:-1])
        check("transfer", "%s: right action without the full reading of the evidence fails" % st["id"], not pg.is_enabled("#btnNext"))
    ctx.close()
    ctx, pg, _ = fresh(br)
    for ti, st, oid, why in [(0, D1, "keep", "keeping a count taken from supplier copy"), (0, D1, "record", "writing the supplier's count into the product record"),
                             (1, I2, "keep", "keeping another product's photo as 'close enough'"), (1, I2, "office", "promoting a shot where the bin is barely visible")]:
        to_stage(pg, ti, st["id"]); open_all(pg)
        answer_decision(pg, st, option=oid)
        check("d4-trap", "%s: %s fails, even with every finding right" % (st["id"], why), not pg.is_enabled("#btnNext"))
    ctx.close()
    def attempt_in(pg, st, **over):
        v = compose_values(st, desc_text); v.update(over)
        fill_compose(pg, st, v); confirm_all(pg); submit(pg)
        okk = pg.is_enabled("#btnNext"); fbx = fb_text(pg)
        if okk: revise(pg)
        else: open_all(pg)
        return okk, fbx
    ctx, pg, _ = fresh(br)
    to_stage(pg, 0, "l1-a"); open_all(pg)
    copy = " ".join(rec_text(r) for r in others)
    for fid in ["ttl.type", "ttl.detail", "ttl.qty", "spc.dims", "spc.weight", "spc.material"]:
        f = field(B1, fid)
        bad = [o for o in f["options"] if o["value"] not in f["accept"] and (o["label"] in copy or re.search(r"pack|polyprop|bpa|about", o["label"], re.I))]
        for o in bad[:1]:
            check("d4-trap", "l1-a: %s taken from the marketing sheet or old draft (%s) fails" % (fid, o["label"]), not attempt_in(pg, B1, **{fid: o["value"]})[0])
    check("d4-trap", "l1-a: leaving off a value the record does hold also fails", not attempt_in(pg, B1, **{"spc.weight": value_of(field(B1, "spc.weight"), LEAVE)})[0])
    ctx.close()
    ctx, pg, _ = fresh(br)
    to_stage(pg, 2, "l3-b"); open_all(pg)
    for fid, lab, why in [("pk.price", "Match the lowest marketplace price", "a price the VA set"), ("pk.image", pfile, "the other product's photo"),
                          ("pk.specs", next(o["label"] for o in field(P3, "pk.specs")["options"] if "Material" in o["label"]), "a material the record doesn't hold")]:
        check("d6-trap", "l3-b: %s fails" % why, not attempt_in(pg, P3, **{fid: value_of(field(P3, fid), lab)})[0])
    for extra, why in [("price", "a note claiming a price change"), ("recfix", "a note claiming a record change"), ("pub", "a note claiming the listing was published")]:
        check("d6-trap", "l3-b: %s fails" % why, not attempt_in(pg, P3, **{"nt.items": nt["accept"][0] + [extra]})[0])
    ctx.close()
    ctx, pg, _ = fresh(br)
    to_stage(pg, 2, "l3-a"); open_all(pg)
    off_id = next(c["id"] for c in Q3["choices"] if c["label"].startswith("Not in the record"))
    fix_id = next(c["id"] for c in Q3["choices"] if c["label"].startswith("Fix"))
    for i, rw in enumerate(Q3["rows"]):
        panel(pg).locator("select.desk-select").nth(i).select_option(fix_id if rw["answer"] == off_id else rw["answer"])
    panel(pg).locator("button[type=submit]").first.click(); pg.wait_for_timeout(60)
    check("d6-trap", "l3-a: 'fixing' a claim the record doesn't hold (instead of taking it off) fails", not pg.is_enabled("#btnNext"))
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
    check("later-first", "Lessons 2 and 3 never print Lesson 1's divider case", not re.search(r"EF-106|Closet Divider|6-Pack", later))
    check("later-first", "Lesson 3 never prints Lesson 2's accepted image action", option_text(I2, correct_option(I2))[:50] not in learner_text(TASKS[2]))
    check("later-first", "Lessons 2 and 3 never print Lesson 1's quantity answer as a label", acc_label(B1, "ttl.qty") not in later)
    ctx, pg, errs = fresh(br)
    goto(pg, M3); pg.locator(".lesson-pill").nth(2).click(); pg.wait_for_timeout(100)
    pg.click("#btnNext"); pg.wait_for_timeout(60); open_all(pg)
    dom = pg.inner_text("#stagePanel")
    check("later-first", "a fresh learner opening Lesson 3 first sees no Lesson 1 divider case", not re.search(r"6-Pack|Closet Divider", dom))
    solve(pg, Q3)
    check("later-first", "Lesson 3 stays usable when opened first", pg.is_enabled("#btnNext"))
    check("later-first", "no JS errors", not errs, errs)
    ctx.close()

    # ---------- cross-module: Module 3 prints no other module's graded answers ----------
    TEAM = set("%s, %s" % (p["name"], p["role"]) for p in DATA["team"].values())  # canon identities, not answers
    m3_all = EVERY + " " + " ".join(rec_text(r) for _, s in ALL for r in records_of(s))
    leaks = []
    for mod in ("module-2", "module-4", "module-5", "module-6", "module-7", "module-9", "module-13"):
        for t in decode(mod)["tasks"]:
            for s in t["stages"]:
                for o in s.get("options", []):
                    if o.get("correct") and o["text"][:60] in m3_all: leaks.append((mod, s["id"], "option"))
                for f in s.get("findings", []):
                    if f.get("correct") and len(f["text"]) > 24 and f["text"] in m3_all: leaks.append((mod, s["id"], f["id"]))
                for f in s.get("fields", []):
                    if f["type"] == "number":
                        for a in f.get("accept", []):
                            if float(a) >= 10 and re.search(r"(?<![\d.#$/:-])(?<!Sep )(?<!Oct )%s(?![\d./:])" % re.escape(a), m3_all): leaks.append((mod, s["id"], f["id"], a))
                    if f["type"] in ("select", "multi"):
                        vals = [v for a in f.get("accept", []) for v in (a if isinstance(a, list) else [a])]
                        for v in vals:
                            lbl = next((o["label"] for o in f["options"] if o["value"] == v), "")
                            if len(lbl) > 24 and not re.match(r"^EF-\d{3} [A-Z][\w ]+$", lbl) and lbl not in TEAM and lbl in m3_all: leaks.append((mod, s["id"], f["id"], lbl[:40]))
    check("cross-module", "no correct option, finding, accepted label or typed figure (>= 10) from Modules 2, 4, 5, 6, 7, 9 or 13 appears in Module 3", not leaks, leaks[:6])
    check("cross-module", "Module 3 writes no customer reply, research or AI draft (M6, M8, M12 own those)",
          not re.search(r"\bAI\b|ChatGPT|competitor research|Dear customer|Hi [A-Z][a-z]+,", EVERY))

    # ---------- shortcut attempts, derived completion, the description ----------
    ctx, pg, _ = fresh(br); goto(pg, M3)
    pg.evaluate("""localStorage.setItem('%s', JSON.stringify({v:1,tasks:{'m3-l8':{completed:true,verified:true,views:1,
      stages:{'l3-a':{passed:true},'l3-b':{passed:true,answer:{values:{},confirms:[true,true]}}},drafts:{}}}}))""" % KEY)
    goto(pg, M3 + "#task-3")
    st3 = pg.evaluate("PVADesk.taskStatus(PVADesk.decode(window.PVA_DESK_MODULES.m3.payload).tasks[2])")
    check("integrity", "forged completed/verified/passed flags count for nothing", st3["passed"] == 0, st3)
    check("integrity", "forged state never reaches the legacy progress store", not (pg.evaluate("JSON.parse(localStorage.getItem('pva-ecom-ft-progress')||'{}')").get("lessons") or {}).get("m3-l8"))
    ctx.close()
    ctx, pg, _ = fresh(br)
    to_stage(pg, 1, "l2-b"); open_all(pg)
    d, w = RECV["Dimensions"], RECV["Weight"]
    GOOD = [("plain and complete", "A stackable storage bin for keeping shelves and closets tidy. It measures %s and weighs %s." % (d, w)),
            ("one recorded fact is enough", "This bin stacks neatly to save space at home. Each one is 16 x 11 x 9 inches, so check your shelf first."),
            ("different wording and units written out", "Need somewhere to put things? This storage bin is 16 by 11 by 9 inches and stacks on another bin to save space."),
            ("terse", "A simple stacking bin for home organization. It weighs %s, so it is easy to move." % w)]
    for why, t in GOOD:
        okk, fbx = attempt_in(pg, W2, **{"desc.text": t})
        check("l2-description", "passes -- %s" % why, okk, (t, fbx[:200]))
    BAD = [("is filler", "This is a great product that you will really love and use every day in your home."),
           ("invents a pack count", "A stackable storage bin, sold as a 3-pack. Each is %s." % d),
           ("invents a material", "A sturdy plastic storage bin. It measures %s and weighs %s." % (d, w)),
           ("gets the dimensions wrong", "A stackable storage bin. It measures 16in x 11in x 11in and stacks neatly."),
           ("rounds the weight", "A stackable storage bin that weighs about 2 lb. It is %s." % d),
           ("uses a superlative", "The strongest storage bin on the market. It measures %s." % d),
           ("promises a guarantee", "A storage bin with a lifetime guarantee. It measures %s." % d),
           ("adds hype", "Get organized today with this storage bin! It measures %s." % d),
           ("gives no recorded fact", "A stackable storage bin for your home. It keeps things tidy and stacks well."),
           ("never says what the product is", "It measures %s and weighs %s. Great for closets and shelves." % (d, w))]
    for why, t in BAD:
        check("l2-description", "rejected -- a description that %s" % why, not attempt_in(pg, W2, **{"desc.text": t})[0], t)
    ctx.close()

    # ---------- answer encoding / leakage ----------
    ctx, pg, _ = fresh(br)
    shipped = "".join(pg.request.get(BASE + uu).text() for uu in ["/module-3/index.html", "/module-3/desk-data.js", "/shared/workdesk.js", "/shared/workdesk-ui.js", "/shared/workdesk-page.js", "/shared/everfield-data.js"])
    markers = ['"correct"', "correct: true", '"accept"', '"answer":', '"correctOrder"']
    check("leakage", "no plaintext answer markers in any shipped engine or content file", not any(m in shipped for m in markers), [m for m in markers if m in shipped])
    check("leakage", "no correct option text appears in shipped source", not any(option_text(s, correct_option(s)) in shipped for _, s in ALL if s["type"] == "decision"))
    vals_dom = []
    for ti in range(len(TASKS)):
        goto(pg, M3 + "#task-%d" % (ti + 1), 1); open_all(pg)
        check("leakage", "task %d: rendered DOM carries no correctness attributes before submission" % (ti + 1), not re.search(r'(class|data-[a-z-]+)="[^"]*(correct|answer|right)', pg.content()))
        vals_dom += pg.evaluate("Array.from(document.querySelectorAll('#stagePanel input,#stagePanel option')).map(e=>e.value)")
    badv = [x for x in vals_dom if re.match(r"^(correct|right|wrong|[fx]_)", x)]
    check("leakage", "no control value names the answer", not badv, badv)
    dec = pg.evaluate("JSON.stringify(PVADesk.decode(window.PVA_DESK_MODULES.m3.payload))")
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
    f0 = B1["fields"][0]
    panel(pg).locator("section.desk-group").first.get_by_label(f0["label"], exact=True).select_option(f0["accept"][0])
    pg.reload(); pg.wait_for_timeout(150); pg.click("#btnNext"); pg.wait_for_timeout(80)
    check("persistence", "an unsubmitted title choice survives refresh", panel(pg).locator("section.desk-group").first.get_by_label(f0["label"], exact=True).input_value() == f0["accept"][0])
    to_stage(pg, 1, "l2-b"); open_all(pg)
    panel(pg).get_by_label(field(W2, "desc.text")["label"], exact=True).fill("Draft description")
    pg.reload(); pg.wait_for_timeout(150); pg.click("#btnNext"); pg.wait_for_timeout(80)
    if not panel(pg).get_by_label(field(W2, "desc.text")["label"], exact=True).count(): pg.click("#btnNext"); pg.wait_for_timeout(80)
    check("persistence", "an unsent description survives refresh", panel(pg).get_by_label(field(W2, "desc.text")["label"], exact=True).input_value() == "Draft description")
    ctx.close()

    # ---------- legacy progress compatibility (D3: existing ids only) ----------
    ctx, pg, _ = fresh(br); goto(pg, BASE + "/index.html")
    pg.evaluate("v => localStorage.setItem('pva-ecom-ft-progress', JSON.stringify(v))", {"lessons": {"m3-l%d" % i: True for i in range(1, 10)}, "modules": {}})
    goto(pg, M3 + "#task-1")
    check("legacy", "all three lessons keep their earlier checkmarks", pg.locator(".lesson-pill.done").count() == 3)
    check("legacy", "the status line separates legacy completion from new work", "earlier version" in pg.inner_text("#taskStatus"))
    vw = pg.evaluate("PVADesk.verifiedWork()")
    check("legacy", "legacy completion is not verified work", not any(v["verified"] for v in vw.values()) and not any(v["samplesEarned"] for v in vw.values()))
    goto(pg, BASE + "/index.html")
    check("legacy", "someone who finished old Module 3 still sees it Completed on the course map", pg.locator(".module-status").nth(2).inner_text() == "Completed")
    pg.evaluate("v => localStorage.setItem('pva-ecom-ft-progress', JSON.stringify(v))", {"lessons": {"m3-l2": True, "m3-l8": True}, "modules": {}})
    goto(pg, BASE + "/index.html")
    check("legacy", "the course map counts Module 3 against its three lessons", "2 of 3" in pg.locator(".module-card").nth(2).inner_text(), pg.locator(".module-card").nth(2).inner_text())
    ctx.close()
    port = open(os.path.join(ROOT, "portfolio", "index.html"), encoding="utf-8").read()
    check("portfolio", "the portfolio points at Module 3, Lesson 3", "From Module 3, Lesson 3 -- Listing QA" in port and "Module 3, Lesson 8" not in port)

    # ---------- isolation and shared authored state ----------
    ctx, pg, _ = fresh(br)
    goto(pg, M7 + "#task-1", 1); open_all(pg)
    m7a = decode("module-7")["tasks"][0]["stages"][0]
    answer_triage(pg, m7a)
    to_stage(pg, 0, "l1-a"); solve(pg, B1)
    keys = pg.evaluate("Object.keys(localStorage).sort()")
    check("isolation", "Module 3 and Module 7 keep separate desk keys, and nothing else is written", set(keys) - {"pva-ecom-ft-progress"} == {KEY, "pva-ecom-ft-m7-desk"}, keys)
    m7store = pg.evaluate("JSON.parse(localStorage.getItem('pva-ecom-ft-m7-desk'))")
    check("isolation", "Module 3 work writes nothing into Module 7's store", list(m7store["tasks"].keys()) == ["m7-l1"], list(m7store["tasks"].keys()))
    goto(pg, M3)
    mut = pg.evaluate("(()=>{try{EVERFIELD.calendar.m3.date='Y'; EVERFIELD.productFacts['EF-101'].dimensions='Z';}catch(e){} return [EVERFIELD.calendar.m3.date, EVERFIELD.productFacts['EF-101'].dimensions]})()")
    check("everfield", "shared Everfield reference cannot be mutated from Module 3", mut == ["Wed, Sep 9", FACTS["EF-101"]["dimensions"]], mut)
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
        goto(pg, M3 + "#task-%d" % n); check("deep-link", "#task-%d opens task %d" % (n, n), pg.inner_text("#lessonKicker") == "Task %d of 3" % n and pg.text_content("#deskDate") == "Wed, Sep 9")
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
    goto(pg, M3 + "#task-1"); low += pg.evaluate(CONTRAST)
    pg.click("#btnNext"); pg.wait_for_timeout(60); open_all(pg); low += pg.evaluate(CONTRAST)
    fail_once(pg, B1); low += pg.evaluate(CONTRAST)
    to_stage(pg, 0, "l1-b"); fail_once(pg, D1); low += pg.evaluate(CONTRAST)
    panel(pg).get_by_role("button", name="Reconsider and try again").click(); fail_once(pg, D1); low += pg.evaluate(CONTRAST)
    to_stage(pg, 2, "l3-a"); fail_once(pg, Q3); low += pg.evaluate(CONTRAST)
    to_stage(pg, 2, "l3-b"); open_all(pg); solve(pg, P3); low += pg.evaluate(CONTRAST)
    check("contrast", "all enabled text meets WCAG AA in brief, compose, decision, triage, feedback, pause and work-sample states", not low, sorted(set(low))[:8])
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
