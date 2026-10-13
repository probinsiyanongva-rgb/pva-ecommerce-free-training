"""Module 1 Work Desk regression + adversarial suite (browser), modelled on Modules 11-14.

Run from the repo root with a static server on :8765 (see tests/README.md):
    python3 tests/e2e/test_module1.py
Answers come from decoding the shipped content at run time. The recompute checks derive every
channel, owner and journey-stage call from its record, #5575's findings from its records, and
every Task 3 structured answer from #5576's records. The written-answer checks run a set of
paraphrases that must pass and unsupported claims that must fail, field by field. The leakage
checks prove Module 1 prints no graded answer from Modules 2-14. Nothing answer-bearing is stored here."""
import os, sys, re, json, subprocess
from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from desk_helpers import *  # noqa

SRC = decode("module-1")
M1 = BASE + "/module-1/index.html"
TASKS = SRC["tasks"]
IDS = [t["id"] for t in TASKS]
ALL = [(ti, s) for ti, t in enumerate(TASKS) for s in t["stages"]]
KEY = "pva-ecom-ft-m1-desk"
DATA = json.loads(subprocess.run(["node", "-e", "process.stdout.write(JSON.stringify(require('./shared/everfield-data.js')))"], cwd=ROOT, capture_output=True, text=True).stdout)
HR = "This course checks required facts, decisions, and structure against defined criteria. Use your judgment to evaluate the quality of the work you produce."
results = []


def check(area, name, cond, detail=""):
    results.append((area, name, bool(cond), str(detail)))
    print(("PASS " if cond else "FAIL ") + "[" + area + "] " + name + ((" -- " + str(detail)[:220]) if detail and not cond else ""))


def field(st, fid): return next(f for f in st["fields"] if f["id"] == fid)
def label_of(f, v): return next(o["label"] for o in f["options"] if o["value"] == v)
def fields_of(rec): return dict((k, v) for k, v in rec.get("fields", []))
def strip(s): return re.sub(r"<[^>]+>", " ", s).replace("&amp;", "&")
def records_of(st):
    if st["type"] == "decision": return st["records"]
    if st["type"] == "triage": return st["rows"]
    return [r for g in st["groups"] for r in g["records"]]
def rec_text(r):
    parts = [r.get("title", "") or "", r.get("note", ""), r.get("label", "")]
    parts += [str(v) for kv in r.get("fields", []) for v in kv] + list(r.get("log", []))
    parts += [str(v) for kv in r.get("meta", []) for v in kv] + list(r.get("body", [])) + list(r.get("items", []))
    return " ".join(parts)
def learner_text(task):
    out = [task["title"], task["objective"], task["brief"]["subject"]] + task["brief"]["body"] + [strip(x) for x in task.get("reference", [])]
    for s in task["stages"]:
        out += [s.get("intro", ""), s.get("prompt", ""), s.get("findingsPrompt", ""), s.get("actionPrompt", ""), s.get("now", "")]
        out += [rec_text(r) for r in records_of(s)] + [c["label"] for c in s.get("choices", [])]
        out += [f["text"] for f in s.get("findings", [])] + [o["text"] for o in s.get("options", [])]
        for f in s.get("fields", []): out += [f["label"], f.get("placeholder", "")] + [o["label"] for o in f.get("options", [])]
    return " ‖ ".join(out)

C1, R1 = stage_by_id(SRC, "t1-a"), stage_by_id(SRC, "t1-b")
J2, O2 = stage_by_id(SRC, "t2-a"), stage_by_id(SRC, "t2-b")
M3 = stage_by_id(SRC, "t3-a")
EVERY = " ".join(learner_text(t) for t in TASKS)

# ---------- written answers: paraphrases that must pass, unsupported claims that must fail ----------
GOOD = {
 "disc.text": ["The customer found the bag set through a search on the marketplace.",
               "They typed “storage bags” into the marketplace search and Everfield's listing came up.",
               "A marketplace search for storage bags is how this shopper first came across the set.",
               "This buyer discovered EF-107 by searching the marketplace, not through a social post."],
 "res.text": ["Before buying, the shopper asked how many bags come in the set and was told it's a 3-piece set.",
              "They messaged to check the number of bags, and Everfield answered from the product record: three.",
              "The customer wanted to know how many bags were included; the answer was 3 bags."],
 "buy.text": ["They placed the order on the marketplace and the payment was confirmed.",
              "The customer bought one EF-107 set through the marketplace checkout and paid for it.",
              "The purchase went through on the online marketplace, not the brand store, and payment was confirmed."],
 "conf.text": ["They got an order confirmation, then tracking updates after ClearPath shipped it, and it was delivered on Saturday.",
               "They got a tracking link once ClearPath sent it out, and the parcel arrived on Saturday.",
               "Everfield's fulfillment partner packed and shipped it, the buyer followed the updates, and it was delivered.",
               "After the confirmation, ClearPath shipped the order and the customer could follow it until delivery."],
 "after.text": ["The customer left a 5-star review and asked how to order another set.",
                "After it arrived they rated it five stars and wanted to buy again.",
                "They were happy: a review saying it was exactly as described, and a question about reordering.",
                "No return or complaint; the buyer reviewed the set and asked about getting another one."],
 "va.text": ["A VA can answer questions like the bag count straight from the product record, so the shopper buys with confidence.",
             "Keeping the EF-107 listing accurate to the approved record helps at the research stage.",
             "The VA can follow the order through to delivery and answer the buyer if they ask where it is.",
             "I'd help by answering the reorder question from the records and keeping the listing accurate, not by negotiating with the supplier."],
}
BAD = {
 "disc.text": [("adds a delivery promise", "Found it through a marketplace search, and I promised it would arrive Friday.", "promise"),
               ("says it came from a social post", "The customer came from Everfield's social post and then searched the marketplace.", "not another route"),
               ("names a real marketplace", "The customer found the bags by searching on Amazon for storage bags.", "real marketplace")],
 "res.text": [("gives the wrong count", "The shopper asked how many bags there were and was told it is a 4-piece set, not 3.", "piece count"),
              ("invents a material", "They asked how many bags come in the set; it's 3 silicone bags.", "piece count"),
              ("leaves out the answer", "The shopper sent a question to Everfield before deciding to buy the set.", "what they were told")],
 "buy.text": [("says the brand store", "They bought the set on Everfield's own website and paid at checkout.", "which channel"),
              ("adds a price", "They ordered on the marketplace and paid $12.99 at checkout.", "no price")],
 "conf.text": [("has tracking before shipping", "ClearPath sent tracking before it shipped, and the parcel was delivered on Saturday.", "order of events"),
               ("names a carrier", "ClearPath shipped it with UPS and tracking updates followed until delivery.", "carrier"),
               ("adds a delivery time", "ClearPath shipped it and the tracking said it would arrive within two days, guaranteed.", "delivery time"),
               ("invents a refund", "ClearPath shipped it with tracking, and the customer was sent a refund after delivery.", "actually received"),
               ("has the keywords but the wrong shipper", "The marketplace shipped it and the customer got tracking updates until delivery.", "who packed and shipped")],
 "after.text": [("invents a return", "The customer left a review, then returned it because the bags were damaged.", "don't show a problem"),
                ("adds a return window", "They left a review and have a 30-day return window if they change their mind.", "return window")],
 "va.text": [("is out of role", "The VA should negotiate a better supplier price so the set sells for less on the marketplace.", "outside this beginner va role"),
             ("decides refunds", "The VA can decide a refund for buyers who keep the item, which helps after delivery.", "outside this beginner va role"),
             ("names no store-side task", "A VA is a helpful person to have around during this journey for the company.", "store-side task")],
}
TEXTS = dict((k, v[0]) for k, v in GOOD.items())


def vals_for(st, **over):
    v = {}
    for f in st["fields"]:
        if f["type"] == "text": v[f["id"]] = TEXTS[f["id"]]
        else: v[f["id"]] = list(f["accept"][0]) if f["type"] == "multi" else f["accept"][0]
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
        cf = correct_findings(st); answer_decision(pg, st, findings=cf[1:] + distractors(st)[:1], option=wrong_options(st)[0])
    elif st["type"] == "triage": answer_triage(pg, st, wrong=True)
    else:
        sel = next(x for x in st["fields"] if x["type"] == "select")
        fill_compose(pg, st, vals_for(st, **{sel["id"]: first_unaccepted(sel)})); confirm_all(pg); submit(pg)


def to_stage(pg, ti, sid):
    goto(pg, M1 + "#task-%d" % (ti + 1), 1)
    for s in TASKS[ti]["stages"]:
        if s["id"] == sid: return
        if not pg.is_enabled("#btnNext"): solve(pg, s)
        pg.click("#btnNext"); pg.wait_for_timeout(60)


def fresh(br, **kw):
    ctx = br.new_context(**kw); pg = ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    return ctx, pg, errs
def fb_text(pg):
    r = panel(pg).locator(".desk-fb"); return r.last.inner_text() if r.count() else ""
def earned(pg): return pg.evaluate("PVADesk.verifiedWork()")["m1-t3"]["samplesEarned"]


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


EVAL = """([vals, conf]) => { const d = PVADesk.decode(PVA_DESK_MODULES.m1.payload); const st = d.tasks[2].stages[0];
  const r = PVADesk.evaluate(st, {values: vals, confirms: conf}); return {pass: r.pass, problems: (r.problems || []).map(p => p.msg)}; }"""


with sync_playwright() as p:
    br = p.chromium.launch()

    # ---------- design ----------
    check("design", "three tasks with the new ids m1-t1, m1-t2, m1-t3 (D2)", IDS == ["m1-t1", "m1-t2", "m1-t3"], IDS)
    check("design", "titles: Meet the Business, Follow an Order, Build the Customer Journey Map",
          [t["title"] for t in TASKS] == ["Meet the Business", "Follow an Order", "Build the Customer Journey Map"])
    check("design", "stage types: two triages; a triage and a decision; one compose", [[s["type"] for s in t["stages"]] for t in TASKS] == [["triage", "triage"], ["triage", "decision"], ["compose"]])
    cfg = json.loads(re.search(r"= (\{.*\});\n", open(os.path.join(ROOT, "module-1", "desk-data.js"), encoding="utf-8").read()).group(1))["config"]
    check("design", "config: module m1, its own salt, legacyPill 'distinct'", cfg["moduleId"] == "m1" and cfg["salt"] == "everfield-desk-m1-v1" and cfg["legacyPill"] == "distinct")
    check("design", "only Task 3 earns a portfolio piece, titled 'Customer Journey Map'",
          [t.get("portfolio") for t in TASKS] == [None, None, "Portfolio piece: Customer Journey Map"] and M3["evidence"]["badge"].endswith("Customer Journey Map"))
    check("design", "every brief comes from Sofia, the closest contact", all(t["brief"]["from"] == "sofia" for t in TASKS))
    check("design", "the retired lessons' recall activities are gone (no quiz, match or sequence)", not any(s["type"] == "sequence" for _, s in ALL) and "quiz" not in json.dumps(SRC).lower())
    page = open(os.path.join(ROOT, "module-1", "index.html"), encoding="utf-8").read()
    check("design", "the page uses the shared engine only (no legacy LESSONS or activities.js)", "var LESSONS" not in page and "activities.js" not in page and 'PVADeskPage.mount({ module: "m1" })' in page)
    check("design", "the page explains the Work Desk and that old checkmarks don't carry over",
          "How the Work Desk works" in page and "Checkmarks from the earlier lessons don't carry over" in page)
    check("design", "the shared statement is declared on the piece, and no copy implies a person reviews submissions",
          "humanReview" in M3 and not re.search(r"human review|reviewed by|a reviewer|our team will (check|review)|graded by", EVERY + strip(page), re.I))

    # ---------- canon ----------
    T = DATA["team"]
    for k in ("sofia", "maya"):
        check("canon", "%s's role matches the hub and shared data" % T[k]["name"], (T[k]["name"] + ", " + T[k]["role"]) in strip(EVERY))
    check("canon", "the three channels match the hub: brand store, online marketplace, B2B / bulk", all(c["label"].split(" (")[0] in ["Brand store", "Online marketplace", "B2B / bulk"] for c in C1["choices"]) and len(C1["choices"]) == 3)
    ref1 = strip(" ".join(TASKS[0]["reference"]))
    check("canon", "the role boundary (m1-t1) states the out-of-scope work, as cited in continuity §6",
          "Deeper supplier coordination, purchase orders and warehouse-level logistics belong to a separate, more advanced specialization" in ref1 and "closest contact" in ref1)
    check("canon", "Sofia decides promotions and refunds without a return (m10-l6, P8); Maya owns ClearPath and patterns",
          "Whether to run a promotion is her decision, and so is a refund when the item isn't coming back" in ref1 and "patterns across cases" in ref1)
    names = re.findall(r"(EF-\d{3}) ([A-Z][a-z]+(?: [A-Z][a-z]+)*)", EVERY)
    bad_names = sorted({(sku, n) for sku, n in names if not DATA["products"].get(sku, "").startswith(n.split(" ")[0]) and n not in ("Drawer Label Sets", "Stackable Storage Bins", "Home Organization Starter Kits")})
    check("canon", "every product named with its SKU uses its catalog name", not bad_names and all(sku in DATA["products"] for sku, _ in names), bad_names)
    check("canon", "product facts used agree with the catalog (EF-101 16in x 11in x 9in, EF-102 40 Pieces, EF-107 3-piece set)",
          DATA["productFacts"]["EF-101"]["dimensions"] in EVERY and "40 Pieces" in EVERY and "3-piece set" in EVERY and DATA["productFacts"]["EF-107"]["pack"] == "3-piece set")
    learner = EVERY
    check("canon", "nothing undefined is stated: no return window, carrier, price, EF-104/EF-106 count or material",
          not re.search(r"\b\d+[- ]day|\breturn window\b|\$\s?\d|\b(UPS|FedEx|USPS|DHL)\b|EF-10[46]|silicone|plastic|cotton|nylon", learner), re.findall(r"\b\d+[- ]day|\$\s?\d|EF-10[46]", learner)[:5])
    check("canon", "no real marketplace is named in learner text", not re.search(r"\b(amazon|walmart|ebay|etsy|shopify|tiktok|temu|shein|lazada|shopee)\b", learner, re.I))
    check("canon", "Module 1 ranges: orders #5570-#5579 only, tracking CP-7731-01xx only, no return numbers",
          all(5570 <= int(n) <= 5579 for n in re.findall(r"#(\d{4})\b", learner)) and all(x.startswith("CP-7731-01") for x in re.findall(r"CP-\d{4}-\d{4}", learner)) and not re.search(r"#\d{3}\b", learner))
    dates = re.findall(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2}\b", learner)
    check("canon", "the only numeric date is the desk day, Tue, Sep 1; calendar.m1 agrees", set(dates) == {"Sep 1"} and DATA["calendar"]["m1"]["date"] == "Tue, Sep 1", sorted(set(dates)))
    out = subprocess.run(["node", "tools/everfield-check.js"], cwd=ROOT, capture_output=True, text=True)
    check("continuity", "the continuity checker passes, with the Module 1 range check (6o)", out.returncode == 0 and "ok   Module 1 day stays in its ranges" in out.stdout, out.stdout[-400:])
    cont = open(os.path.join(ROOT, "docs", "everfield-continuity.md"), encoding="utf-8").read()
    check("continuity", "the canon cites m1-t1 for the team and the out-of-scope line, and no live m1-l6 citation remains",
          "(m1-t1, m6-l9;" in cont and "warehouse logistics (m1-t1, M5 page note)" in cont and not re.search(r"\(m1-l6[,)]", cont))

    # ---------- recompute from evidence ----------
    def channel(r):
        t = rec_text(r)
        if re.search(r"invoice", t, re.I) and re.search(r"\b\d{2}\b", t): return "b2b"
        if re.search(r"platform", t, re.I): return "mkt"
        if re.search(r"Everfield's (own|store|homepage)|I've picked", t): return "dtc"
    check("recompute", "t1-a: every channel follows from the record's details", all(channel(r) == r["answer"] for r in C1["rows"]), [(r["id"], channel(r)) for r in C1["rows"]])
    def owner(r):
        t = rec_text(r); f = fields_of(r)
        if "Approved product record" in f or re.search(r"Shipped · tracking", t): return "va"
        if re.search(r"manufactur|warehouse", t, re.I) and not re.search(r"Packed by", t): return "out"
        if re.search(r"discount|refund", t, re.I): return "sofia"
        if re.search(r"ClearPath", t): return "maya"
    check("recompute", "t1-b: every owner follows from the item and the role card", all(owner(r) == r["answer"] for r in R1["rows"]), [(r["id"], owner(r)) for r in R1["rows"]])
    def stage(r):
        t = rec_text(r)
        if "Arrived from" in t: return "disc"
        if "Asked" in t and "product record" in t: return "res"
        if "Placed" in t and "Payment" in t: return "pur"
        if re.search(r"order two more|order another", t): return "after"
        if re.search(r"confirmation|Shipped|Delivered", t): return "conf"
    check("recompute", "t2-a: every journey stage follows from what the record shows", all(stage(r) == r["answer"] for r in J2["rows"]), [(r["id"], stage(r)) for r in J2["rows"]])
    check("recompute", "t2-a: records are shown out of journey order, and every stage is used",
          [r["answer"] for r in J2["rows"]] != sorted([r["answer"] for r in J2["rows"]], key=["disc", "res", "pur", "conf", "after"].index) and {r["answer"] for r in J2["rows"]} == {c["id"] for c in J2["choices"]})
    check("recompute", "t1-a: each channel is right for exactly two records", sorted([r["answer"] for r in C1["rows"]].count(c["id"]) for c in C1["choices"]) == [2, 2, 2])
    rec = dict((r["id"], r) for r in O2["records"]); order_f = fields_of(rec["o-order"]); cp = fields_of(rec["o-cp"]); trk = fields_of(rec["o-trk"])
    truth = {"paid": order_f["Payment"].startswith("Confirmed"), "queue": "not yet picked" in cp["#5575"], "notrack": trk["Tracking number"] == "None yet",
             "shipped": trk["Carrier events"] != "None", "failed": not order_f["Payment"].startswith("Confirmed")}
    check("recompute", "t2-b: the correct findings are exactly those the records support", sorted(k for k, v in truth.items() if v) == sorted(correct_findings(O2)), truth)
    copt = option_text(O2, correct_option(O2))
    check("recompute", "t2-b: the accepted reply claims no shipment, no other order's tracking, no date and no cancellation",
          "not shipped" in copt and not re.search(r"arrive|Wednesday|cancel|another", copt) and all(re.search(r"shipped last night|another|[Cc]ancel", o["text"]) for o in O2["options"] if not o.get("correct")))
    G = dict((g["id"], g) for g in M3["groups"])
    src_f = fields_of(G["disc"]["records"][0]); ord_f = fields_of(G["buy"]["records"][0]); ship_f = fields_of(G["conf"]["records"][0]); role_f = fields_of(G["va"]["records"][0])
    q_body = " ".join(G["res"]["records"][0]["body"]); after_body = " ".join(G["after"]["records"][0]["body"])
    derived = {"disc.how": "search" if "search" in src_f["Found via"] else None,
               "res.what": "count" if re.search(r"How many", q_body) else None,
               "buy.channel": {"Online marketplace": "mkt", "Brand store": "dtc"}.get(ord_f["Channel"]),
               "buy.item": re.search(r"EF-(\d{3})", ord_f["Item"]).group(1),
               "conf.got": sorted(x for x, cond in (("conf", "confirmation" in ship_f["Order confirmation"].lower() or ship_f["Order confirmation"].startswith("Sent")),
                                                     ("track", "Sent" in ship_f["Tracking updates"]), ("deliv", "Delivered" in ship_f["Carrier status"]),
                                                     ("refund", "refund" in str(ship_f).lower()), ("repl", "replacement" in str(ship_f).lower())) if cond),
               "after.what": sorted(x for x, cond in (("review", "★★★★★" in after_body), ("reorder", "order another" in after_body), ("return", "return" in after_body.lower()), ("damage", "damage" in after_body.lower())) if cond)}
    acc = dict((f["id"], (sorted(f["accept"][0]) if f["type"] == "multi" else f["accept"][0])) for f in M3["fields"] if f["type"] != "text")
    check("recompute", "t3-a: every structured answer follows from #5576's records", all(derived[k] == acc[k] for k in derived), [(k, derived[k], acc[k]) for k in derived if derived[k] != acc[k]])
    va = field(M3, "va.pick")
    check("recompute", "t3-a: the accepted VA support points are exactly the role card's store-side work",
          all(re.search(label_of(va, v).split(" ")[0].lower(), role_f["Store-side work"].lower()) for v in va["accept"]) and "supplier" not in va["accept"] and "refund" not in va["accept"])
    check("recompute", "Task 3 uses its own customer file (no Task 1-2 order or tracking)", not re.search(r"#557[0-5]|CP-7731-017[34]", learner_text(TASKS[2])))

    # ---------- leakage across modules (G3) ----------
    others = {m: decode("module-%d" % m) for m in range(2, 15)}
    acc_texts = []
    for m, srcm in others.items():
        for t in srcm["tasks"]:
            for s in t["stages"]:
                acc_texts += [o["text"] for o in s.get("options", []) if o.get("correct")] + [f["text"] for f in s.get("findings", []) if f.get("correct")]
                acc_texts += [it["label"] for it in s.get("items", [])]
                for r in s.get("rows", []): acc_texts.append(rec_text(r))
                for f in s.get("fields", []):
                    if f["type"] in ("select", "multi"):
                        for a in f.get("accept", []):
                            for v in (a if isinstance(a, list) else [a]):
                                lbl = next((o["label"] for o in f["options"] if o["value"] == v), "")
                                if len(lbl) > 24 and not re.match(r"^EF-\d{3} [A-Z][\w ]+$", lbl): acc_texts.append(lbl)
    TEAMS = [m["name"] + ", " + m["role"] for m in DATA["team"].values()]
    leaks = [x[:60] for x in acc_texts if len(x) > 24 and x in EVERY and x not in TEAMS]
    check("leakage", "no graded answer, finding, sequence item or triage row from Modules 2-14 appears in Module 1", not leaks, leaks[:6])
    m4seq = [it["label"] for t in others[4]["tasks"] for s in t["stages"] if s["type"] == "sequence" for it in s["items"]]
    check("leakage", "Module 4's pick/pack/label/handoff sequence is not reused", m4seq and not any(x in EVERY for x in m4seq))
    other_nums = set(re.findall(r"#\d{3,4}\b|CP-7731-\d{4}", " ".join(json.dumps(s) for s in others.values())))
    mine = set(re.findall(r"#\d{3,4}\b|CP-7731-\d{4}", EVERY))
    check("leakage", "every Module 1 order and tracking number is new", mine and not (mine & other_nums), sorted(mine & other_nums))

    # ---------- written answers (G6): paraphrases pass, unsupported claims fail ----------
    ctx, pg, errs = fresh(br); goto(pg, M1)
    base = vals_for(M3)
    r = pg.evaluate(EVAL, [base, [True, True]])
    check("text", "the reference answer passes", r["pass"], r["problems"])
    for fid, lst in GOOD.items():
        for t in lst:
            v = dict(base); v[fid] = t; r = pg.evaluate(EVAL, [v, [True, True]])
            check("text", "%s paraphrase passes: %s" % (fid, t[:60]), r["pass"], r["problems"])
    for fid, lst in BAD.items():
        for why, t, want in lst:
            v = dict(base); v[fid] = t; r = pg.evaluate(EVAL, [v, [True, True]])
            check("text", "%s rejected when it %s" % (fid, why), not r["pass"] and any(want in m.lower() for m in r["problems"]), r["problems"])
    for fid in GOOD:
        v = dict(base); v[fid] = "marketplace tracking review listing search three ClearPath"
        r = pg.evaluate(EVAL, [v, [True, True]])
        check("text", "%s: a bare keyword list fails" % fid, not r["pass"], r["problems"])
    ctx.close()

    # ---------- flow, completion, sample ----------
    ctx, pg, errs = fresh(br); goto(pg, M1)
    check("page", "desk bar, three tasks and the training note", pg.text_content("#deskDate") == "Tue, Sep 1" and pg.inner_text("#lessonKicker") == "Task 1 of 3" and pg.locator("#trainingNote").is_visible())
    for ti, t in enumerate(TASKS):
        goto(pg, M1 + "#task-%d" % (ti + 1), 1); ok = True
        for st in t["stages"]:
            solve(pg, st)
            if not pg.is_enabled("#btnNext"): ok = False; break
            pg.click("#btnNext"); pg.wait_for_timeout(60)
        check("flow", "task %d completes through the UI" % (ti + 1), ok, fb_text(pg)[:200])
    banner = pg.inner_text("#doneBanner")
    check("flow", "completion banner names Module 2 as next (the stale 'continues the story soon' is gone)", "Module 1 complete" in banner and "Module 2 is next" in banner and "soon" not in banner, banner)
    prog = pg.evaluate("JSON.parse(localStorage.getItem('pva-ecom-ft-progress'))")
    check("progress", "verified work marks all three tasks", all(prog["lessons"].get(i) for i in IDS))
    vw = pg.evaluate("PVADesk.verifiedWork()")
    check("verified-work", "all three tasks verified, one earned sample (t3-a)", all(v["verified"] for v in vw.values()) and vw["m1-t3"]["samplesEarned"] == ["t3-a"], vw)
    keys = pg.evaluate("Object.keys(localStorage).sort()")
    check("isolation", "only the Module 1 desk key and the legacy progress key are written", keys == [KEY, "pva-ecom-ft-progress"], keys)
    goto(pg, M1 + "#task-3", 1)
    sample = pg.locator(".ws-preview").inner_text() if pg.locator(".ws-preview").count() else ""
    check("work-sample", "piece 01: titled Customer Journey Map, labelled training work, every section, the learner's words, and the approved shared statement",
          "Customer Journey Map (training work sample)" in sample and all(g["sampleHead"] in sample for g in M3["groups"]) and TEXTS["conf.text"] in sample and HR in sample and "fictional" in sample.lower(), sample[-600:])
    goto(pg, BASE + "/index.html")
    check("progress", "course map shows Module 1 Completed", "How E-commerce Works" in pg.locator(".module-card").nth(0).inner_text() and pg.locator(".module-status").nth(0).inner_text() == "Completed")
    check("flow", "no JS errors", not errs, errs)
    ctx.close()

    for n in (3, 2):
        ctx, pg, errs = fresh(br)
        goto(pg, M1 + "#task-%d" % n, 1); ok = True
        for st in TASKS[n - 1]["stages"]:
            solve(pg, st)
            if not pg.is_enabled("#btnNext"): ok = False; break
            pg.click("#btnNext"); pg.wait_for_timeout(60)
        vw = pg.evaluate("PVADesk.verifiedWork()")
        check("independence", "task %d completes first in fresh storage, other tasks untouched" % n, ok and vw[IDS[n - 1]]["verified"] and sum(v["verified"] for v in vw.values()) == 1, vw)
        ctx.close()

    # ---------- piece 01 earned only by validated work (G8) ----------
    ctx, pg, _ = fresh(br)
    to_stage(pg, 2, "t3-a"); open_all(pg)
    FILLER = {"disc.text": "This part of the journey happened and it was fine for the customer overall.",
              "res.text": "This part of the journey happened and it was fine for the customer overall.",
              "buy.text": "Something happened at this point and it went along as it normally would.",
              "conf.text": "Then the next things happened in the usual way, as they always do here.",
              "after.text": "Afterwards things carried on and that was the end of this part of it.",
              "va.text": "A virtual assistant can be useful here in many different ways for everyone involved."}
    okk, fbx, got = attempt_in(pg, M3, **FILLER)
    check("portfolio", "five-plus non-empty filler fields with every choice right: rejected, nothing earned", not okk and not got, fbx[:160])
    for f in [x for x in M3["fields"] if x["type"] in ("select", "multi")]:
        wrong = first_unaccepted(f) if f["type"] == "select" else sorted(set(f["accept"][0]) ^ {f["options"][-1]["value"]})
        okk, fbx, got = attempt_in(pg, M3, **{f["id"]: wrong})
        check("portfolio", "one wrong %s (%s), every text right: rejected, nothing earned" % (f["type"], f["id"]), not okk and not got, fbx[:160])
    okk, fbx, got = attempt_in(pg, M3, **{"after.text": ""})
    check("portfolio", "a blank section: rejected", not okk and not got, fbx[:120])
    fill_compose(pg, M3, vals_for(M3)); confirm_all(pg)
    boxes = panel(pg).locator(".desk-selfcheck input[type=checkbox]"); blocked = []
    for i in range(boxes.count()):
        boxes.nth(i).uncheck(); pg.wait_for_timeout(30); blocked.append(panel(pg).locator("button[type=submit]").first.is_disabled()); boxes.nth(i).check(); pg.wait_for_timeout(30)
    check("portfolio", "each unticked self-check line blocks submission", blocked and all(blocked) and not earned(pg))
    okk, fbx, got = attempt_in(pg, M3, **{"conf.text": "They got a tracking link once ClearPath sent it out, and the parcel arrived on Saturday."})
    check("portfolio", "through the UI: a natural paraphrase passes and earns piece 01", okk and got == ["t3-a"], fbx[:160])
    ctx.close(); ctx, pg, _ = fresh(br); to_stage(pg, 2, "t3-a"); open_all(pg)
    okk, fbx, got = attempt_in(pg, M3, **{"conf.text": "ClearPath sent tracking before it shipped, and the parcel was delivered on Saturday."})
    check("portfolio", "through the UI: an unsupported claim is rejected with a pointer to the record", not okk and not got and "order of events" in fbx, fbx[:200])
    ctx.close()

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
    check("evidence-gate", "every Task 3 group has its own gated record card",
          all(any(x.get("kind") != "reference" for x in g["records"]) for g in M3["groups"]) and len(M3["groups"]) == 6)
    ctx.close(); ctx, pg, _ = fresh(br)
    for ti, st in ALL:
        to_stage(pg, ti, st["id"]); fail_once(pg, st); fb = fb_text(pg)
        check("feedback", "%s: wrong attempt gets feedback, next stays locked" % st["id"], fb and not pg.is_enabled("#btnNext"), fb[:120])
        leak = []
        if st["type"] == "decision": leak = [option_text(st, correct_option(st))] + [finding_text(st, f) for f in correct_findings(st)]
        if st["type"] == "triage": leak = [r["id"] + ": " + next(c["label"] for c in st["choices"] if c["id"] == r["answer"]) for r in st["rows"]]
        check("feedback", "%s: feedback never quotes a correct option or finding" % st["id"], not any(x in fb for x in leak if len(x) > 12))
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

    # ---------- integrity, legacy (G9), isolation ----------
    ctx, pg, _ = fresh(br); goto(pg, M1)
    pg.evaluate("""localStorage.setItem('%s', JSON.stringify({v:1,tasks:{'m1-t3':{completed:true,verified:true,views:1,stages:{'t3-a':{passed:true,answer:{values:{},confirms:[true,true]}}},drafts:{}}}}))""" % KEY)
    goto(pg, M1 + "#task-3")
    check("integrity", "forged flags count for nothing", pg.evaluate("PVADesk.verifiedWork()")["m1-t3"]["stagesVerified"] == 0 and not earned(pg))
    shipped_src = "".join(pg.request.get(BASE + u).text() for u in ["/module-1/index.html", "/module-1/desk-data.js"])
    check("leakage", "no plaintext answer markers in shipped files", not any(m in shipped_src for m in ['"correct"', "correct: true", '"accept"', '"answer":']))
    check("leakage", "no plaintext source file in the repository", not any(f.endswith(".src.json") for _, _, fs in os.walk(ROOT) for f in fs))
    sel = [f for f in M3["fields"] if f["type"] == "select" and len(f["accept"]) == 1]
    strict = [f["id"] for f in sel if len(label_of(f, f["accept"][0])) > max(len(o["label"]) for o in f["options"] if o["value"] != f["accept"][0])]
    check("leakage", "no single-answer select's accepted option is strictly its longest", not strict, strict)
    lens = [len(o["text"]) for o in O2["options"]]; ci = [i for i, o in enumerate(O2["options"]) if o.get("correct")][0]
    check("leakage", "t2-b's correct option is not strictly the longest", lens[ci] <= max(l for i, l in enumerate(lens) if i != ci), lens)
    vals_dom = []
    for ti in range(3):
        goto(pg, M1 + "#task-%d" % (ti + 1), 1); open_all(pg)
        vals_dom += pg.evaluate("Array.from(document.querySelectorAll('#stagePanel input,#stagePanel option')).map(e=>e.value)")
    check("leakage", "no control value names the answer", not [x for x in vals_dom if re.match(r"^(correct|right|wrong)", x)])
    ctx.close()
    LEG = {"lessons": dict(("m1-l%d" % i, True) for i in range(1, 8)), "modules": {}}
    ctx, pg, _ = fresh(br); goto(pg, BASE + "/index.html")
    pg.evaluate("v => localStorage.setItem('pva-ecom-ft-progress', JSON.stringify(v))", LEG)
    goto(pg, M1 + "#task-1")
    check("legacy", "old m1-l1 - m1-l7 checkmarks give no done pill and no legacy marker on the new tasks",
          pg.locator(".lesson-pill.done").count() == 0 and pg.locator(".lesson-pill.legacy").count() == 0)
    check("legacy", "old checkmarks are not verified work", not any(v["verified"] for v in pg.evaluate("PVADesk.verifiedWork()").values()))
    goto(pg, BASE + "/index.html")
    check("legacy", "the course map does not show Module 1 Completed from old checkmarks", pg.locator(".module-status").nth(0).inner_text() == "Start module")
    to_stage(pg, 0, "t1-a"); solve(pg, C1)
    after = pg.evaluate("JSON.parse(localStorage.getItem('pva-ecom-ft-progress'))")
    check("legacy", "desk work never rewrites or removes the old entries", all(after["lessons"].get(k) for k in LEG["lessons"]))
    mut = pg.evaluate("(()=>{try{EVERFIELD.team.sofia.name='X'; EVERFIELD.calendar.m1.date='Y';}catch(e){} return [EVERFIELD.team.sofia.name, EVERFIELD.calendar.m1.date]})()")
    check("everfield", "shared Everfield reference cannot be mutated from Module 1", mut == ["Sofia Ramirez", "Tue, Sep 1"], mut)
    ctx.close()

    # ---------- hub, portfolio, certificate links, locked files ----------
    hub = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read(); port = open(os.path.join(ROOT, "portfolio", "index.html"), encoding="utf-8").read()
    check("hub", "the course map lists m1-t1, m1-t2, m1-t3 with the new description", 'lessonIds: ["m1-t1","m1-t2","m1-t3"]' in hub and "Meet Everfield Goods, follow an order, and map a customer's journey." in hub)
    check("hub", "hero says 14 portfolio deliverables; the map says all 14 modules are open",
          '<div class="num">14</div><div class="label">portfolio deliverables</div>' in hub and "All 14 modules are open. Start with Module 1." in hub and "Module 1 is ready now" not in hub and ">13<" not in hub)
    check("hub", "the hub links the certificate as 'Certificate of Completion'", re.search(r'href="certificate/index.html">Certificate of Completion', hub))
    check("portfolio", "piece 01 keeps its title and points at Module 1, Lesson 3; 14 pieces; the certificate is linked",
          "<h3>Customer Journey Map</h3>" in port and "From Module 1, Lesson 3 -- Build the Customer Journey Map" in port and len(re.findall(r'class="portfolio-num"', port)) == 14
          and re.search(r'href="../certificate/index.html">Certificate of Completion', port))
    diff = subprocess.run(["git", "diff", "--name-only", "main", "--", "module-14", "shared/workdesk.js", "shared/workdesk-ui.js", "shared/workdesk-page.js", "shared/activities.js", "shared/progress.js",
                           "certificate/verify.js", "certificate/certificate.js", "progress"] + ["module-%d" % m for m in range(2, 14)], cwd=ROOT, capture_output=True, text=True)
    check("locked", "no locked module page or content, engine file, activities.js, verifier or progress page differs from main", diff.returncode == 0 and not diff.stdout.strip(), diff.stdout)
    ctx, pg, _ = fresh(br)
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
    goto(pg, M1 + "#task-1"); low += pg.evaluate(CONTRAST)
    to_stage(pg, 0, "t1-a"); open_all(pg); fail_once(pg, C1); low += pg.evaluate(CONTRAST)
    to_stage(pg, 2, "t3-a"); open_all(pg); solve(pg, M3); low += pg.evaluate(CONTRAST)
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
