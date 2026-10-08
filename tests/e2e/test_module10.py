"""Module 10 Work Desk regression + adversarial suite (browser), modelled on Module 8's.

Run from the repo root with a static server on :8765 (see tests/README.md):
    python3 tests/e2e/test_module10.py
Answers come from decoding the shipped content at run time (desk_helpers.decode). The
"recompute" checks derive every accepted menu area from each admin's own help card, every
promotion setting from Sofia's approved note, and every health-check call from the status
and note lines of the finding itself; the near-miss checks prove each setting has a
suggestion, draft or last-month value beside it that fails. The cross-module checks decode
Modules 2-9 and 13 to prove Module 10 prints none of their graded answers. So nothing
answer-bearing is stored here."""
import os, sys, re, json, subprocess
from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from desk_helpers import *  # noqa

SRC = decode("module-10")
M10 = BASE + "/module-10/index.html"
M8 = BASE + "/module-8/index.html"
TASKS = SRC["tasks"]
IDS = [t["id"] for t in TASKS]
ALL = [(ti, s) for ti, t in enumerate(TASKS) for s in t["stages"]]
KEY = "pva-ecom-ft-m10-desk"
DATA = json.loads(subprocess.run(["node", "-e", "process.stdout.write(JSON.stringify(require('./shared/everfield-data.js')))"], cwd=ROOT, capture_output=True, text=True).stdout)
FACTS, NAMES = DATA["productFacts"], DATA["products"]
DATE = "Fri, Sep 18"
results = []


def check(area, name, cond, detail=""):
    results.append((area, name, bool(cond), str(detail)))
    print(("PASS " if cond else "FAIL ") + "[" + area + "] " + name + ((" -- " + str(detail)[:200]) if detail and not cond else ""))


def field(st, fid): return next(f for f in st["fields"] if f["id"] == fid)
def label_of(f, v): return next(o["label"] for o in f["options"] if o["value"] == v)
def acc_label(st, fid): f = field(st, fid); return label_of(f, f["accept"][0])
def acc_labels(st, fid): f = field(st, fid); return sorted(label_of(f, v) for v in f["accept"][0])
def value_of(f, lbl): return next(o["value"] for o in f["options"] if o["label"] == lbl)
def fields_of(rec): return dict((k, v) for k, v in rec.get("fields", []))
def strip(s): return re.sub(r"<[^>]+>", " ", s)


def records_of(st):
    if st["type"] == "decision": return st["records"]
    if st["type"] == "triage": return st["rows"]
    return [r for g in st["groups"] for r in g["records"]]


def rec_text(r):
    parts = [r.get("title", "") or "", r.get("caption", ""), r.get("note", ""), r.get("logTitle", ""), r.get("label", ""), r.get("from", "") or ""]
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


def rec(st, rid): return next(r for r in records_of(st) if r["id"] == rid)


A1, B1 = stage_by_id(SRC, "l1-a"), stage_by_id(SRC, "l1-b")
C2, D2 = stage_by_id(SRC, "l2-a"), stage_by_id(SRC, "l2-b")
R3, P3 = stage_by_id(SRC, "l3-a"), stage_by_id(SRC, "l3-b")
EVERY = " ".join(learner_text(t) for t in TASKS)
NOTE = fields_of(rec(C2, "n-sofia"))
DRAFT = fields_of(rec(C2, "n-draft"))
LAST = fields_of(rec(C2, "n-last"))
MAYA = rec_text(rec(C2, "n-maya"))


def summary(st, g, f, labels):
    return "I ended SUMMERTIDY10, took the summer banner down and published the approved EF-104 update. temp-helper's access, my Payments access and the EF-102 draft are with Sofia, and the ClearPath link is with Maya."


def solve(pg, st):
    open_all(pg)
    if st["type"] == "decision": answer_decision(pg, st)
    elif st["type"] == "triage": answer_triage(pg, st)
    else:
        fill_compose(pg, st, compose_values(st, summary)); confirm_all(pg); submit(pg)


def fail_once(pg, st):
    open_all(pg)
    if st["type"] == "decision":
        cf = correct_findings(st)
        answer_decision(pg, st, findings=cf[1:] + distractors(st)[:1], option=(wrong_options(st) or [None])[0])
    elif st["type"] == "triage": answer_triage(pg, st, wrong=True)
    else:
        vals = compose_values(st, summary)
        sel = next(x for x in st["fields"] if x["type"] == "select")
        vals[sel["id"]] = first_unaccepted(sel)
        fill_compose(pg, st, vals); confirm_all(pg); submit(pg)


def to_stage(pg, ti, sid):
    goto(pg, M10 + "#task-%d" % (ti + 1), 1)
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
    v = compose_values(st, summary); v.update(over)
    fill_compose(pg, st, v); confirm_all(pg); submit(pg)
    okk = pg.is_enabled("#btnNext"); fbx = fb_text(pg)
    if okk: revise(pg)
    else: open_all(pg)
    return okk, fbx


with sync_playwright() as p:
    br = p.chromium.launch()

    # ---------- structure: the approved design ----------
    check("design", "3 tasks with the approved ids (D3)", IDS == ["m10-l1", "m10-l6", "m10-l10"], IDS)
    check("design", "titles follow the design map", [t["title"] for t in TASKS] == ["Find It on Any Platform", "Set Up What Sofia Decided", "Store Health Check"])
    kinds = {t["id"]: [s["type"] for s in t["stages"]] for t in TASKS}
    check("design", "stage types match the map", kinds == {"m10-l1": ["compose", "decision"], "m10-l6": ["compose", "decision"], "m10-l10": ["triage", "compose"]}, kinds)
    check("design", "only Lesson 3 is a portfolio task, with the store-operations-audit label",
          [(t["id"], t.get("portfolio")) for t in TASKS if t.get("portfolio")] == [("m10-l10", "Portfolio piece: Everfield Goods E-commerce Store Operations Audit")])
    check("design", "Sofia asks for all three lessons and the audit", [t["brief"]["from"] for t in TASKS] == ["sofia", "sofia", "sofia"] and "Sofia Ramirez" in P3["evidence"]["requestedBy"])
    check("design", "one admin-desk day: every clock reads Fri, Sep 18, and no lesson declares its own work date",
          all(s["now"].startswith(DATE) for _, s in ALL) and not any(t.get("workDate") for t in TASKS))
    texts = [(s["id"], f["id"]) for _, s in ALL if s["type"] == "compose" for f in s["fields"] if f["type"] == "text"]
    check("design", "exactly one own-words field: the audit summary", texts == [("l3-b", "sum.text")], texts)
    check("design", "the audit declares a self-check and human review", len(P3["confirm"]) >= 2 and P3.get("humanReview"))
    check("design", "the triage uses every call", set(r["answer"] for r in R3["rows"]) == set(c["id"] for c in R3["choices"]))
    check("design", "no Work Desk engine change: the shared engine files match main",
          subprocess.run(["git", "diff", "--quiet", "origin/main", "--", "shared/workdesk.js", "shared/workdesk-ui.js", "shared/workdesk-page.js", "shared/workdesk.css"], cwd=ROOT).returncode == 0)

    # ---------- D7: generic simulated admins; D5: percentage and item count only ----------
    check("d7", "no real platform is named anywhere in Module 10",
          not re.search(r"Shopify|WooCommerce|Amazon|eBay|Etsy|BigCommerce|Wix|Squarespace|Magento|Lazada|Shopee", json.dumps(SRC), re.I))
    admins = [rec_text(r) for _, s in ALL for r in records_of(s) if "menu and help" in (r.get("title") or "") or (r.get("title") or "").startswith("Your role")]
    check("d7", "every admin menu, help card and role card is labelled as a simulated admin", admins and all("(simulated admin)" in a or "simulated admin" in a for a in admins))
    check("d7", "every lesson's reference says both admins are simulated and look like no real platform",
          all(any("simulated for training and look like no real platform" in strip(x) for x in t["reference"]) for t in TASKS))
    page = open(os.path.join(ROOT, "module-10", "index.html"), encoding="utf-8").read()
    check("d7", "the module page's scope note says the admins are simulated and resemble no real platform",
          "simulated training tools" in page and "resemble no real platform" in page)
    check("d5", "no dollar amount anywhere; the discount is a percentage and the minimum an item count",
          not re.search(r"\$\s?\d", json.dumps(SRC)) and field(C2, "promo.pct").get("unit") == "%" and all(re.search(r"item|minimum", label_of(field(C2, "promo.min"), o["value"]), re.I) for o in field(C2, "promo.min")["options"]))
    check("canon", "no Everfield orders, returns, tracking numbers, marketplace IDs, stock figures or refunds",
          not re.search(r"#\d{3,}\b|CP-\d{4}-\d{4}|MKT-\d+|\b\d+ available\b|\bAvailable\b|\bInbound\b|\bReserved\b|\bon hand\b|refund", EVERY, re.I))
    TITLES = " ".join(t["title"] for t in TASKS)
    check("canon", "the only people named are the canon team", not [n for n in set(x for v in re.findall(r'"((?:[^"\\]|\\.)*)"', json.dumps(SRC)) for x in re.findall(r"\b(Sofia|Maya|Daniel|Marcus) ([A-Z][a-z]+)", v))
                                                                     if "%s %s" % n not in [p["name"] for p in DATA["team"].values()] and "%s %s" % n not in TITLES])
    check("canon", "promotion products use the catalog names", all(re.sub(r"^EF-\d{3} ", "", o["label"]) == NAMES[o["label"][:6]] for o in field(C2, "promo.products")["options"]))
    out = subprocess.run(["node", os.path.join(ROOT, "tools", "everfield-check.js")], capture_output=True, text=True)
    check("continuity", "the continuity checker passes, with the Module 10 range check", out.returncode == 0 and "ok   Module 10 day stays in its ranges" in out.stdout, out.stdout[-400:])
    check("continuity", "calendar.m10 is Fri, Sep 18, after M7's Thu Sep 17 and before M9's week",
          DATA["calendar"]["m10"]["date"] == DATE and DATA["calendar"]["m7"]["date"] == "Thu, Sep 17" and DATA["calendar"]["m9"]["date"] == "Fri, Sep 25")
    check("continuity", "the promotion's future dates sit only in schedule fields (Starts / Ends / Goes live)",
          all(k in ("Starts", "Ends") for r in records_of(C2) for k, v in r.get("fields", []) if re.search(r"Sep (19|2\d|30)|Oct", v)))

    # ---------- recompute: every accepted answer derived from the evidence ----------
    # L1: the accepted area is the one whose help line describes the job, in that admin's own menu
    JOB = [(r"discount code", r"discount codes"), (r"banner", r"banner"), (r"link to clearpath", r"(links to outside|connected) services"),
           (r"who else can sign in", r"(who can sign in|people on this)"), (r"about text", r"about text")]
    bad1, menus = [], {}
    for g in A1["groups"]:
        card = fields_of(next(r for r in g["records"] if r["id"].startswith("c-")))
        helpc = next(r for r in g["records"] if r["id"].startswith("h-"))
        admin = card["Admin"]
        menus[admin.split(" (")[0]] = [row[0] for row in helpc["rows"]]
        rx = next(h for j, h in JOB if re.search(j, card["Job"], re.I))
        want = [row[0] for row in helpc["rows"] if re.search(rx, row[1], re.I)]
        f = next(x for x in A1["fields"] if x["group"] == g["id"])
        if not helpc["title"].startswith(admin.split(" (")[0]) or [o["label"] for o in f["options"]] != menus[admin.split(" (")[0]] or want != [acc_label(A1, f["id"])]:
            bad1.append((g["id"], want, acc_label(A1, f["id"])))
    check("recompute", "Lesson 1A: each accepted area is the one that admin's own help text gives for the job", not bad1, bad1)
    names = list(menus.values())
    check("recompute", "Lesson 1A: the two admins name the same jobs differently, so no area name carries over",
          len(names) == 2 and not set(names[0]) & set(names[1]), names)
    same = [acc_label(A1, f["id"]) for f in A1["fields"] if re.search("discount code", fields_of(next(r for g in A1["groups"] if g["id"] == f["group"] for r in g["records"] if r["id"].startswith("c-")))["Job"], re.I)]
    check("recompute", "Lesson 1A: the same job (discount codes) is done under a different name on each admin", len(set(same)) == 2, same)
    role = fields_of(rec(B1, "role"))
    check("recompute", "Lesson 1B: the role card can't open Payments, and the accepted action asks Sofia rather than going round it",
          "Payments" in role["Cannot open"] and "Payments" not in role["Can open"] and "ask her" in option_text(B1, correct_option(B1)))
    # L2: every accepted setting is the approved note's, and each has a near miss from Maya, the draft or last month
    pct = re.match(r"(\d+)%", NOTE["Discount"]).group(1)
    prods = sorted(re.findall(r"EF-\d{3}", NOTE["Products"].split("--")[0]))
    got = {"code": acc_label(C2, "promo.code"), "pct": field(C2, "promo.pct")["accept"][0], "start": acc_label(C2, "promo.start"), "end": acc_label(C2, "promo.end"),
           "products": sorted(l[:6] for l in acc_labels(C2, "promo.products")), "channel": acc_label(C2, "promo.channel"), "min": acc_label(C2, "promo.min")}
    want2 = {"code": NOTE["Code"], "pct": pct, "start": NOTE["Starts"], "end": NOTE["Ends"], "products": prods, "channel": NOTE["Channel"], "min": NOTE["Minimum"]}
    check("recompute", "Lesson 2A: every accepted setting is exactly the approved note's (code, %, dates, products, channel, minimum)", got == want2, (got, want2))
    check("recompute", "Lesson 2A: the discount applies as a percentage off the order, as the note says",
          "percentage off the order" in acc_label(C2, "promo.applies") and NOTE["Discount"].endswith("off the order"))
    mpct = re.search(r"(\d+)%", MAYA).group(1)
    near = {"code": [DRAFT["Code"], LAST["Code"]], "start": [DRAFT["Starts"], DATE, LAST["Starts"]], "end": [DRAFT["Ends"]],
            "channel": [LAST["Channel"]], "min": [DRAFT["Minimum"]]}
    opts = {k: [o["label"] for o in field(C2, "promo." + k)["options"]] for k in near}
    missing = [(k, v) for k, vs in near.items() for v in vs if v not in opts[k]]
    check("recompute", "Lesson 2A: every near miss (Maya's suggestion, the draft, last month, today) is offered beside the decided value", not missing, missing)
    check("recompute", "Lesson 2A: Maya's figure and kit, the draft's products and last month's settings all differ from the note",
          mpct != pct and "kit" in MAYA and "EF-200" in DRAFT["Products"] and LAST["Discount"] != NOTE["Discount"] and DRAFT["Code"] != NOTE["Code"])
    last2 = fields_of(rec(D2, "b-last"))
    check("recompute", "Lesson 2B: SUMMERTIDY10 is Active past the end in Sofia's note, and the accepted action ends it and tells her",
          last2["Status"] == "Active" and last2["Ends"] == fields_of(rec(D2, "b-note"))["Ends"] == "Sun, Sep 13" and "End the code now" in option_text(D2, correct_option(D2)))
    # L3: each call follows from the finding's own status and note lines
    lab3 = {c["id"]: c["label"] for c in R3["choices"]}

    def l3call(r):
        f = fields_of(r); s, n, item = f["Status"].lower(), f["Note"].lower(), f["Item"].lower()
        if "error" in s: return "Maya's"
        if s == "live" and "decided end" in n: return "Fix it now"
        if s == "draft" and "approved by sofia" in n: return "Fix it now"
        if "contract ended" in n or "role card" in n or "not yet reviewed" in n: return "Sofia's decision"
        if s in ("connected", "scheduled"): return "Nothing wrong"
        return "?"
    got3 = {r["id"]: l3call(r) for r in R3["rows"]}
    check("recompute", "Lesson 3A: every call follows from that finding's status and note lines",
          all(lab3[r["answer"]].startswith(got3[r["id"]]) for r in R3["rows"]), {r["id"]: (got3[r["id"]], lab3[r["answer"]]) for r in R3["rows"]})
    areas = {}
    for r in R3["rows"]: areas.setdefault(r["title"].split(" · ")[1], set()).add(r["answer"])
    check("recompute", "Lesson 3A: Storefront, Apps and Catalog each pair two different calls, so the area never decides the call (refinement 3)",
          all(len(areas[a]) >= 2 for a in ("Storefront", "Apps", "Catalog")), areas)
    team = [fields_of(r) for r in R3["rows"] if r["title"].endswith("· Team")]
    check("recompute", "Lesson 3A: the two Team findings rest on different evidence lines (a contract note; a role card against the account's settings)",
          len(team) == 2 and "contract ended" in team[0]["Note"] and "role card" in team[1]["Note"] and team[0]["Status"] != team[1]["Status"])
    fixes = {r["id"] for r in R3["rows"] if r["answer"] == "fix"}
    check("recompute", "Lesson 3B: 'fixed' is the triage's fix rows plus the summer code ended in Lesson 2",
          acc_labels(P3, "done.items") == sorted(["Took down the summer banner", "Published the approved EF-104 update", "Ended SUMMERTIDY10"]) and fixes == {"f1", "f7"})
    sofia_rows = sorted(fields_of(r)["Item"] for r in R3["rows"] if r["answer"] == "sofia")
    check("recompute", "Lesson 3B: 'waiting for Sofia' is exactly the triage's Sofia rows", len(acc_labels(P3, "wait.sofia")) == len(sofia_rows) == 3
          and any("temp-helper" in x for x in acc_labels(P3, "wait.sofia")) and any("Payments" in x for x in acc_labels(P3, "wait.sofia")) and any("EF-102" in x for x in acc_labels(P3, "wait.sofia")))
    check("recompute", "Lesson 3B: 'waiting for Maya' is the failing ClearPath link", "ClearPath" in acc_label(P3, "wait.maya") and
          [fields_of(r)["Item"] for r in R3["rows"] if r["answer"] == "maya"] == ["ClearPath Fulfillment link"])

    # ---------- normal flow, completion, work sample ----------
    ctx, pg, errs = fresh(br); goto(pg, M10)
    check("page", "desk bar shows Fri, Sep 18, Store admin and the task count",
          pg.text_content("#deskDate") == DATE and "Store admin" in pg.text_content(".desk-bar") and pg.inner_text("#lessonKicker") == "Task 1 of 3")
    for ti, t in enumerate(TASKS):
        goto(pg, M10 + "#task-%d" % (ti + 1), 1); ok = True
        for st in t["stages"]:
            solve(pg, st)
            if not pg.is_enabled("#btnNext"): ok = False; break
            pg.click("#btnNext"); pg.wait_for_timeout(60)
        check("flow", "task %d completes through the UI" % (ti + 1), ok)
    check("flow", "completion banner", "Module 10 complete" in pg.inner_text("#doneBanner"), pg.inner_text("#doneBanner"))
    prog = pg.evaluate("JSON.parse(localStorage.getItem('pva-ecom-ft-progress'))")
    check("progress", "verified work marks all three lessons in the legacy progress store", all(prog["lessons"].get(i) for i in IDS))
    keys = pg.evaluate("Object.keys(localStorage).sort()")
    check("isolation", "only the Module 10 desk key and the legacy progress key are written", keys == [KEY, "pva-ecom-ft-progress"], keys)
    vw = pg.evaluate("PVADesk.verifiedWork()")
    check("verified-work", "verifiedWork() reports all three tasks verified and the one earned sample",
          all(v["verified"] for v in vw.values()) and vw["m10-l10"]["samplesEarned"] == ["l3-b"] and not any(v["samplesEarned"] for k, v in vw.items() if k != "m10-l10"), vw)
    goto(pg, BASE + "/index.html")
    card = pg.locator(".module-card").nth(9).inner_text()
    check("progress", "course map shows Module 10 Completed", "Inside an E-commerce Store" in card and "Completed" in card, card)
    goto(pg, M10 + "#task-3", 2)
    ev = pg.locator(".ws-preview").inner_text() if pg.locator(".ws-preview").count() else ""
    check("work-sample", "the audit survives reload with an honest training header that says both admins are simulated",
          ev.startswith("TRAINING WORK SAMPLE\nEverfield Goods — E-commerce Store Operations Audit") and "simulated training tools" in ev and
          "Work date: Fri, Sep 18 (simulated)" in ev and "Sofia Ramirez" in ev and "human review" in ev, ev[:400])
    check("work-sample", "the audit carries what was fixed, what waits for whom, and the learner's summary",
          all(x in ev for x in acc_labels(P3, "done.items") + acc_labels(P3, "wait.sofia") + [acc_label(P3, "wait.maya"), summary(0, 0, 0, 0)]), ev[:900])
    check("flow", "no JS errors", not errs, errs)
    ctx.close()

    # ---------- evidence gate (every stage; Lesson 1's menus, Lesson 3's admin records) ----------
    ctx, pg, _ = fresh(br)
    for ti, st in ALL:
        to_stage(pg, ti, st["id"]); r = panel(pg)
        if st["type"] == "triage":
            gated = all(x.is_disabled() for x in r.locator("select.desk-select").all())
        elif st["type"] == "compose":
            gated = (all(x.is_disabled() for x in r.locator("section.desk-group select, section.desk-group input").all()) and
                     all(x.get_attribute("readonly") is not None for x in r.locator("section.desk-group textarea").all()) and all(c.is_disabled() for c in r.locator(".desk-selfcheck input").all()))
        else:
            gated = r.locator(".desk-actions button").first.is_disabled()
        pg.evaluate("document.querySelectorAll('#stagePanel button,#stagePanel select,#stagePanel input,#stagePanel textarea').forEach(e=>e.disabled=false); var b=document.querySelector('#stagePanel .desk-actions button'); b && b.click();")
        pg.wait_for_timeout(40)
        att = pg.evaluate("((JSON.parse(localStorage.getItem('%s'))||{tasks:{}}).tasks['%s']||{stages:{}}).stages['%s']" % (KEY, TASKS[ti]["id"], st["id"]))
        check("evidence-gate", "%s: controls gated and a forced submit is refused before evidence is opened" % st["id"], gated and not att, att)
    ctx.close()
    # refinement 1: opening one task's card does not unlock another task's area
    ctx, pg, _ = fresh(br)
    to_stage(pg, 0, "l1-a"); r = panel(pg)
    r.locator("section.desk-group").first.locator(".desk-ev-head button").first.click(); pg.wait_for_timeout(40)
    others = r.locator("section.desk-group").nth(1).locator("select")
    check("evidence-gate", "l1-a: each task's area stays locked until that task's own admin menu and help are opened (refinement 1)",
          others.count() and others.first.is_disabled())
    # refinement 3: every triage row is gated on its own record
    goto(pg, M10 + "#task-3", 1); r = panel(pg)
    r.locator(".desk-ev-head button[aria-expanded='false']").first.click(); pg.wait_for_timeout(40)
    sels = r.locator("select.desk-select")
    check("evidence-gate", "l3-a: a finding's call unlocks only once that finding's own admin record is opened (refinement 3)",
          sels.first.is_enabled() and all(sels.nth(i).is_disabled() for i in range(1, sels.count())))
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
            check("feedback-safety", "%s: feedback never quotes an accepted choice" % st["id"], not [a for a in acc if re.search(r"(?<![\w-])%s(?![\w-])" % re.escape(a), fb)], fb[:200])
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
    ctx, pg, _ = fresh(br)
    to_stage(pg, 2, "l3-b"); open_all(pg)
    for i in range(2):
        okk, fbx = attempt_in(pg, P3, **{"sum.text": "I spent the day looking around both of the admins today. It was a really useful and interesting exercise overall."})
    check("retry", "l3-b: a weak summary twice gets feedback again, with no pause and no lock-out",
          not okk and panel(pg).locator(".desk-pause").count() == 0 and len(fbx) > 40)
    check("retry", "l3-b: corrected summary passes with no attempt limit", attempt_in(pg, P3)[0])
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

    # ---------- authority traps (D1-D4, L2 exact execution) ----------
    ctx, pg, _ = fresh(br)
    for ti, st, oid, why in [(0, B1, "login", "using a shared login to get round the permission"), (0, B1, "export", "finding the payout figures another way"),
                             (0, B1, "later", "sitting on it until next week"), (1, D2, "extend", "extending the code yourself"),
                             (1, D2, "leave", "leaving an expired code running"), (1, D2, "match", "changing the old code to match the new one")]:
        to_stage(pg, ti, st["id"]); open_all(pg)
        answer_decision(pg, st, option=oid)
        check("trap", "%s: %s fails, even with every finding right" % (st["id"], why), not pg.is_enabled("#btnNext"))
    ctx.close()
    ctx, pg, _ = fresh(br)
    to_stage(pg, 1, "l2-a"); open_all(pg)
    F = lambda k: field(C2, "promo." + k)
    for why, over in [("Maya's 20%", {"promo.pct": mpct}), ("last month's 10%", {"promo.pct": re.match(r"(\d+)", LAST["Discount"]).group(1)}),
                      ("the draft's code", {"promo.code": value_of(F("code"), DRAFT["Code"])}), ("last month's code", {"promo.code": value_of(F("code"), LAST["Code"])}),
                      ("the draft's start", {"promo.start": value_of(F("start"), DRAFT["Starts"])}), ("starting today, as Maya suggests", {"promo.start": value_of(F("start"), DATE)}),
                      ("the draft's end", {"promo.end": value_of(F("end"), DRAFT["Ends"])}), ("the draft's minimum", {"promo.min": value_of(F("min"), DRAFT["Minimum"])}),
                      ("no minimum", {"promo.min": value_of(F("min"), "No minimum")}), ("last month's channel", {"promo.channel": value_of(F("channel"), LAST["Channel"])}),
                      ("adding the kit, as Maya suggests", {"promo.products": F("products")["accept"][0] + ["ef200"]}), ("leaving a decided product out", {"promo.products": F("products")["accept"][0][1:]}),
                      ("a fixed amount instead of a percentage", {"promo.applies": value_of(F("applies"), "A fixed amount off the order")})]:
        check("trap", "l2-a: %s fails" % why, not attempt_in(pg, C2, **over)[0])
    okk, fbx = attempt_in(pg, C2, **{"promo.pct": "15%"})
    check("trap", "l2-a: '15%' typed with its sign gets the number-format prompt, not a miss or a pause",
          not okk and "number" in fbx.lower() and panel(pg).locator(".desk-pause").count() == 0, fbx[:160])
    check("trap", "l2-a: the decided percentage passes however it is typed (15, 15.0)", attempt_in(pg, C2, **{"promo.pct": "15"})[0] and attempt_in(pg, C2, **{"promo.pct": "15.0"})[0])
    ctx.close()
    ctx, pg, _ = fresh(br)
    to_stage(pg, 2, "l3-b"); open_all(pg)
    D, W = field(P3, "done.items"), field(P3, "wait.sofia")
    for why, over in [("listing temp-helper's access as removed by you", {"done.items": D["accept"][0] + ["temp"]}),
                      ("listing your own Payments access as removed by you", {"done.items": D["accept"][0] + ["pay"]}),
                      ("listing the ClearPath link as reconnected by you", {"done.items": D["accept"][0] + ["cp"]}),
                      ("leaving the ended code out of what you fixed", {"done.items": [x for x in D["accept"][0] if x != "code"]}),
                      ("sending the ClearPath link to Sofia", {"wait.sofia": W["accept"][0] + ["cp"]}),
                      ("sending the scheduled autumn banner to Sofia", {"wait.sofia": W["accept"][0] + ["autumn"]}),
                      ("leaving your own over-broad access off Sofia's list", {"wait.sofia": [x for x in W["accept"][0] if x != "pay"]}),
                      ("'nothing for Maya'", {"wait.maya": "none"}), ("sending the healthy newsletter link to Maya", {"wait.maya": "news"})]:
        check("trap", "l3-b: %s fails" % why, not attempt_in(pg, P3, **over)[0])
    ctx.close()
    ctx, pg, _ = fresh(br)
    to_stage(pg, 2, "l3-a"); open_all(pg)
    for rid, call, why in [("f5", "fix", "removing temp-helper's access yourself"), ("f6", "fix", "taking Payments off your own account yourself"),
                           ("f3", "fix", "reconnecting the ClearPath link yourself"), ("f8", "fix", "publishing the unreviewed EF-102 update"),
                           ("f2", "fix", "taking down the scheduled autumn banner"), ("f1", "sofia", "sending a decided fix back to Sofia")]:
        goto(pg, M10 + "#task-3", 1); open_all(pg)
        for i, rw in enumerate(R3["rows"]):
            panel(pg).locator("select.desk-select").nth(i).select_option(call if rw["id"] == rid else rw["answer"])
        panel(pg).locator("button[type=submit]").first.click(); pg.wait_for_timeout(60)
        check("trap", "l3-a: %s fails" % why, not pg.is_enabled("#btnNext"))
    ctx.close()

    # ---------- opening a later lesson first gives no shortcut to an earlier one ----------
    l1 = learner_text(TASKS[0])
    check("later-first", "Lesson 1 never mentions Lesson 2's expired code", not re.search(r"SUMMERTIDY10|ended", l1, re.I))
    check("later-first", "Lessons 2 and 3 never print a Lesson 1 menu answer next to its job",
          not [acc_label(A1, f["id"]) for f in A1["fields"] if re.search(r"Where (to|it's) .{0,40}" + re.escape(acc_label(A1, f["id"])), learner_text(TASKS[1]) + learner_text(TASKS[2]))])
    check("later-first", "Lesson 3 never prints a Lesson 2 decision option", option_text(D2, correct_option(D2))[:50] not in learner_text(TASKS[2]))
    ctx, pg, errs = fresh(br)
    goto(pg, M10); pg.locator(".lesson-pill").nth(2).click(); pg.wait_for_timeout(100)
    pg.click("#btnNext"); pg.wait_for_timeout(60); open_all(pg)
    solve(pg, R3)
    check("later-first", "Lesson 3 stays usable when opened first", pg.is_enabled("#btnNext"))
    check("later-first", "no JS errors", not errs, errs)
    ctx.close()

    # ---------- cross-module: Module 10 prints no other module's graded answers ----------
    TEAM = set("%s, %s" % (p["name"], p["role"]) for p in DATA["team"].values())
    m10_all = EVERY + " " + " ".join(rec_text(r) for _, s in ALL for r in records_of(s))
    leaks = []
    for mod in ("module-2", "module-3", "module-4", "module-5", "module-6", "module-7", "module-8", "module-9", "module-13"):
        dm = decode(mod)
        for t in dm["tasks"]:
            for s in t["stages"]:
                for o in s.get("options", []):
                    if o.get("correct") and o["text"][:60] in m10_all: leaks.append((mod, s["id"], "option"))
                for f in s.get("findings", []):
                    if f.get("correct") and len(f["text"]) > 24 and f["text"] in m10_all: leaks.append((mod, s["id"], f["id"]))
                for f in s.get("fields", []):
                    if f["type"] == "number":
                        for a in f.get("accept", []):
                            if float(a) >= 10 and re.search(r"(?<![\w.#$/:-])(?<!Sep )(?<!Oct )%s(?![\d./:%%])" % re.escape(a), m10_all): leaks.append((mod, s["id"], f["id"], a))
                    if f["type"] in ("select", "multi"):
                        vals = [v for a in f.get("accept", []) for v in (a if isinstance(a, list) else [a])]
                        for v in vals:
                            lbl = next((o["label"] for o in f["options"] if o["value"] == v), "")
                            if len(lbl) > 24 and not re.match(r"^EF-\d{3} [A-Z][\w ]+$", lbl) and lbl not in TEAM and lbl in m10_all: leaks.append((mod, s["id"], f["id"], lbl[:40]))
    check("cross-module", "no correct option, finding, accepted label or typed figure (>= 10) from Modules 2-9 or 13 appears in Module 10", not leaks, leaks[:6])
    check("cross-module", "Module 10 writes no customer reply, listing copy or AI draft (M6, M3, M12 own those)", not re.search(r"\bAI\b|ChatGPT|Dear customer|Hi [A-Z][a-z]+,", EVERY))
    check("cross-module", "Module 10 retires the refund-as-routine-action legacy lesson (refund authority stays Module 7's)", "refund" not in json.dumps(SRC).lower())

    # ---------- shortcut attempts, derived completion, the summary ----------
    ctx, pg, _ = fresh(br); goto(pg, M10)
    pg.evaluate("""localStorage.setItem('%s', JSON.stringify({v:1,tasks:{'m10-l10':{completed:true,verified:true,views:1,
      stages:{'l3-a':{passed:true},'l3-b':{passed:true,answer:{values:{},confirms:[true,true]}}},drafts:{}}}}))""" % KEY)
    goto(pg, M10 + "#task-3")
    st3 = pg.evaluate("PVADesk.taskStatus(PVADesk.decode(window.PVA_DESK_MODULES.m10.payload).tasks[2])")
    check("integrity", "forged completed/verified/passed flags count for nothing", st3["passed"] == 0, st3)
    check("integrity", "forged state never reaches the legacy progress store", not (pg.evaluate("JSON.parse(localStorage.getItem('pva-ecom-ft-progress')||'{}')").get("lessons") or {}).get("m10-l10"))
    ctx.close()
    ctx, pg, _ = fresh(br)
    to_stage(pg, 2, "l3-b"); open_all(pg)
    GOOD = [("terse", "Summer code ended and banner down. EF-104 published; access and EF-102 wait for Sofia."),
            ("owners named", summary(0, 0, 0, 0)),
            ("'could not remove' is not a change claim", "I could not remove her access, so temp-helper is still active and waiting for Sofia. The ClearPath link shows an error and is with Maya."),
            ("ended and took down", "I ended the summer code and took the banner down. Everything else is waiting for Sofia or Maya."),
            ("a fix, then a waiting item in the same sentence", "I removed the summer banner; temp-helper is still active and with Sofia. The ClearPath sync is failing."),
            ("turned off the code; Payments is Sofia's", "I turned off the expired code and the banner; Payments access on my account is Sofia's call. EF-102 is still a draft."),
            ("fixed two things; ClearPath is Maya's", "I fixed the banner and the code; the ClearPath link still shows an error. That one is with Maya."),
            ("'per her note' is not a change to her access", "I removed the banner per her note from last week. The EF-104 update is now published."),
            ("published EF-104; EF-102 waits", "I published EF-104 as approved. EF-102 is still a draft waiting for Sofia's review."),
            ("store-health phrasing", "Two admins checked. The brand store had a live summer banner past its end date and a failing ClearPath link; the rest is in the table."),
            ("no internal codes", "The old summer promotion was still running, so I ended it and took its banner down. Access questions are with Sofia and the warehouse link is with Maya."),
            ("accepted by design (indirect directive; self-check and human review)", "The temp helper still has access and the ClearPath link is down. Time to lock down access before the weekend.")]
    for why, t in GOOD:
        okk, fbx = attempt_in(pg, P3, **{"sum.text": t})
        check("l3-summary", "passes -- %s" % why, okk, (t, fbx[:200]))
    BAD = [("is filler", "I spent the day looking around both of the admins today. It was a really useful and interesting exercise overall."),
           ("says what we should do", "temp-helper is still active after her contract ended. We should remove temp-helper's access today."),
           ("recommends", "The ClearPath link shows an error. I recommend reconnecting it before the weekend."),
           ("tells Sofia what to do", "My account can open Payments. Sofia should take that off my role."),
           ("says let's", "The ClearPath link is failing. Let's reconnect it this afternoon."),
           ("gives advice", "EF-102 is still a draft. My advice is to publish it today."),
           ("claims temp-helper's access was removed", "I removed temp-helper's access because her contract ended. The banner is down too."),
           ("claims Payments was revoked", "I revoked Payments access on my own account. The summer code is ended."),
           ("claims her account was deactivated", "Her contract ended on Fri, Sep 4, so I deactivated her account. The banner is down."),
           ("claims ClearPath was reconnected", "I reconnected the ClearPath link and it is syncing again. The banner is down."),
           ("claims the link was fixed", "I've fixed the ClearPath connection. Everything else is with Sofia."),
           ("claims EF-102 was published", "I published EF-104 and EF-102 today. The banner is down."),
           ("gives no finding", "The check is complete and the results are in the table. Everything is listed by area for review.")]
    for why, t in BAD:
        check("l3-summary", "rejected -- a summary that %s" % why, not attempt_in(pg, P3, **{"sum.text": t})[0], t)
    ctx.close()

    # ---------- answer encoding / leakage ----------
    ctx, pg, _ = fresh(br)
    shipped = "".join(pg.request.get(BASE + uu).text() for uu in ["/module-10/index.html", "/module-10/desk-data.js", "/shared/workdesk.js", "/shared/workdesk-ui.js", "/shared/workdesk-page.js", "/shared/everfield-data.js"])
    markers = ['"correct"', "correct: true", '"accept"', '"answer":', '"correctOrder"']
    check("leakage", "no plaintext answer markers in any shipped engine or content file", not any(m in shipped for m in markers), [m for m in markers if m in shipped])
    check("leakage", "no correct option text appears in shipped source", not any(option_text(s, correct_option(s)) in shipped for _, s in ALL if s["type"] == "decision"))
    check("leakage", "Sofia's promotion settings never appear in shipped source as plain text", "TIDYFALL15" not in shipped)
    vals_dom = []
    for ti in range(len(TASKS)):
        goto(pg, M10 + "#task-%d" % (ti + 1), 1); open_all(pg)
        check("leakage", "task %d: rendered DOM carries no correctness attributes before submission" % (ti + 1), not re.search(r'(class|data-[a-z-]+)="[^"]*(correct|answer|right)', pg.content()))
        vals_dom += pg.evaluate("Array.from(document.querySelectorAll('#stagePanel input,#stagePanel option')).map(e=>e.value)")
    badv = [x for x in vals_dom if re.match(r"^(correct|right|wrong|[fx]_)", x)]
    check("leakage", "no control value names the answer", not badv, badv)
    dec = pg.evaluate("JSON.stringify(PVADesk.decode(window.PVA_DESK_MODULES.m10.payload))")
    check("leakage", "decoded payload holds hashed keys only", '"correct"' not in dec and '"accept"' not in dec and '"answer"' not in dec)
    sel = [f for _, s in ALL if s["type"] == "compose" for f in s["fields"] if f["type"] == "select" and len(f["options"]) <= 6]
    strict = [f["id"] for f in sel if len(label_of(f, f["accept"][0])) > max(len(o["label"]) for o in f["options"] if o["value"] != f["accept"][0])]
    positions = [next(i for i, o in enumerate(f["options"]) if o["value"] == f["accept"][0]) for f in sel]
    check("leakage", "no short select's accepted option is strictly its longest, and accepted positions spread across the list",
          not strict and len(set(positions)) >= 3 and max(positions.count(i) for i in set(positions)) <= len(sel) // 2, (strict, positions))
    dl = [(s["id"], [len(o["text"]) for o in s["options"]], next(i for i, o in enumerate(s["options"]) if o.get("correct"))) for _, s in ALL if s["type"] == "decision"]
    check("leakage", "no decision's correct option is strictly its longest", not [x for x in dl if x[1][x[2]] > max(l for i, l in enumerate(x[1]) if i != x[2])], dl)
    ctx.close()

    # ---------- persistence ----------
    ctx, pg, _ = fresh(br)
    to_stage(pg, 2, "l3-a"); open_all(pg)
    panel(pg).locator("select.desk-select").first.select_option(R3["rows"][0]["answer"])
    pg.reload(); pg.wait_for_timeout(150); pg.click("#btnNext"); pg.wait_for_timeout(80)
    check("persistence", "an unsubmitted triage call survives refresh", panel(pg).locator("select.desk-select").first.input_value() == R3["rows"][0]["answer"])
    to_stage(pg, 2, "l3-b"); open_all(pg)
    panel(pg).get_by_label(field(P3, "sum.text")["label"], exact=True).fill("Draft summary")
    pg.reload(); pg.wait_for_timeout(150); pg.click("#btnNext"); pg.wait_for_timeout(80)
    if not panel(pg).get_by_label(field(P3, "sum.text")["label"], exact=True).count(): pg.click("#btnNext"); pg.wait_for_timeout(80)
    check("persistence", "an unsent summary survives refresh", panel(pg).get_by_label(field(P3, "sum.text")["label"], exact=True).input_value() == "Draft summary")
    ctx.close()

    # ---------- legacy progress compatibility (existing ids only) ----------
    ctx, pg, _ = fresh(br); goto(pg, BASE + "/index.html")
    pg.evaluate("v => localStorage.setItem('pva-ecom-ft-progress', JSON.stringify(v))", {"lessons": {"m10-l%d" % i: True for i in range(1, 11)}, "modules": {}})
    goto(pg, M10 + "#task-1")
    check("legacy", "all three lessons keep their earlier checkmarks", pg.locator(".lesson-pill.done").count() == 3)
    check("legacy", "the status line separates legacy completion from new work", "earlier version" in pg.inner_text("#taskStatus"))
    vw = pg.evaluate("PVADesk.verifiedWork()")
    check("legacy", "legacy completion is not verified work", not any(v["verified"] for v in vw.values()) and not any(v["samplesEarned"] for v in vw.values()))
    goto(pg, BASE + "/index.html")
    check("legacy", "someone who finished old Module 10 still sees it Completed on the course map", pg.locator(".module-status").nth(9).inner_text() == "Completed")
    pg.evaluate("v => localStorage.setItem('pva-ecom-ft-progress', JSON.stringify(v))", {"lessons": {"m10-l1": True, "m10-l10": True}, "modules": {}})
    goto(pg, BASE + "/index.html")
    check("legacy", "the course map counts Module 10 against its three lessons", "2 of 3" in pg.locator(".module-card").nth(9).inner_text(), pg.locator(".module-card").nth(9).inner_text())
    ctx.close()
    port = open(os.path.join(ROOT, "portfolio", "index.html"), encoding="utf-8").read()
    check("portfolio", "the portfolio points at Module 10, Lesson 3", "From Module 10, Lesson 3 -- Store Health Check" in port and "Why Platforms Differ" not in port)

    # ---------- isolation and shared authored state ----------
    ctx, pg, _ = fresh(br)
    goto(pg, M8 + "#task-1", 1); open_all(pg)
    answer_triage(pg, decode("module-8")["tasks"][0]["stages"][0])
    to_stage(pg, 2, "l3-a"); solve(pg, R3)
    keys = pg.evaluate("Object.keys(localStorage).sort()")
    check("isolation", "Module 10 and Module 8 keep separate desk keys, and nothing else is written", set(keys) - {"pva-ecom-ft-progress"} == {KEY, "pva-ecom-ft-m8-desk"}, keys)
    m8store = pg.evaluate("JSON.parse(localStorage.getItem('pva-ecom-ft-m8-desk'))")
    check("isolation", "Module 10 work writes nothing into Module 8's store", list(m8store["tasks"].keys()) == ["m8-l1"], list(m8store["tasks"].keys()))
    goto(pg, M10)
    mut = pg.evaluate("(()=>{try{EVERFIELD.calendar.m10.date='Y'; EVERFIELD.team.sofia.role='Z';}catch(e){} return [EVERFIELD.calendar.m10.date, EVERFIELD.team.sofia.role]})()")
    check("everfield", "shared Everfield reference cannot be mutated from Module 10", mut == [DATE, DATA["team"]["sofia"]["role"]], mut)
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
        goto(pg, M10 + "#task-%d" % n); check("deep-link", "#task-%d opens task %d" % (n, n), pg.inner_text("#lessonKicker") == "Task %d of 3" % n and pg.text_content("#deskDate") == DATE)
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
    goto(pg, M10 + "#task-1"); low += pg.evaluate(CONTRAST)
    pg.click("#btnNext"); pg.wait_for_timeout(60); open_all(pg); low += pg.evaluate(CONTRAST)
    fail_once(pg, A1); low += pg.evaluate(CONTRAST)
    to_stage(pg, 0, "l1-b"); fail_once(pg, B1); low += pg.evaluate(CONTRAST)
    panel(pg).get_by_role("button", name="Reconsider and try again").click(); fail_once(pg, B1); low += pg.evaluate(CONTRAST)
    to_stage(pg, 2, "l3-a"); fail_once(pg, R3); low += pg.evaluate(CONTRAST)
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
