"""Module 12 Work Desk regression + adversarial suite (browser), modelled on Module 11.

Run from the repo root with a static server on :8765 (see tests/README.md):
    python3 tests/e2e/test_module12.py
Answers come from decoding the shipped content at run time (desk_helpers.decode). The
"recompute" checks derive every Task 1 call from each request card's own fields, every
Task 2 verdict from the claim and the record on its card, and every Task 3 verdict, source
and corrected weight from the cards in its evidence and the shared product canon. The
EF-106 checks prove the count appears only inside the simulated AI draft; the label checks
prove Maya's note is a training instruction everywhere it appears; the portfolio checks prove
piece 12 is earned only when every graded field, the note, the self-check and the declared
human review are in place. Nothing answer-bearing is stored here."""
import os, sys, re, json, subprocess
from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from desk_helpers import *  # noqa

SRC = decode("module-12")
M12 = BASE + "/module-12/index.html"
M11 = BASE + "/module-11/index.html"
TASKS = SRC["tasks"]
IDS = [t["id"] for t in TASKS]
ALL = [(ti, s) for ti, t in enumerate(TASKS) for s in t["stages"]]
KEY = "pva-ecom-ft-m12-desk"
DATA = json.loads(subprocess.run(["node", "-e", "process.stdout.write(JSON.stringify(require('./shared/everfield-data.js')))"], cwd=ROOT, capture_output=True, text=True).stdout)
DATE = "Wed, Sep 16"
AI = "AI draft · simulated"
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
    parts = [r.get("title", "") or "", r.get("caption", ""), r.get("note", ""), r.get("logTitle", ""), r.get("label", "")]
    parts += [str(v) for kv in r.get("fields", []) for v in kv] + list(r.get("log", []))
    parts += [str(c) for row in r.get("rows", []) for c in row] + list(r.get("columns", []))
    parts += [str(v) for kv in r.get("meta", []) for v in kv] + list(r.get("body", [])) + list(r.get("paragraphs", [])) + list(r.get("items", []))
    return " ".join(parts)


def all_strings(o, loc=""):
    """Every string in the content with its location (ids, values and answer keys skipped)."""
    out = []
    if isinstance(o, str): out.append((loc, o))
    elif isinstance(o, list):
        for i, x in enumerate(o): out += all_strings(x, loc + "[%d]" % i)
    elif isinstance(o, dict):
        for k, v in o.items():
            if k in ("id", "value", "accept", "answer", "correct", "kind", "type", "k", "acc"): continue
            out += all_strings(v, loc + "." + k)
    return out


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


Q1, D1 = stage_by_id(SRC, "l1-a"), stage_by_id(SRC, "l1-b")
A2, B2 = stage_by_id(SRC, "l3-a"), stage_by_id(SRC, "l3-b")
P3 = stage_by_id(SRC, "l9-a")
EVERY = " ".join(learner_text(t) for t in TASKS)
EVREC = {r["id"]: r for r in records_of(P3)}
GRADED = [f for f in P3["fields"] if f["type"] != "text"]
SRCV = {o["label"].split(" · ")[0]: o["value"] for o in field(P3, "c1.src")["options"]}

GOOD_NOTE = ("I checked every claim against the cards. I corrected the weight to 2.2 lb from the record, took out the colors line, the "
             "material and the discount code, and the corrected draft is for your review; nothing is live yet.")


def note(st, g, f, labels): return GOOD_NOTE


def solve(pg, st):
    open_all(pg)
    if st["type"] == "decision": answer_decision(pg, st)
    elif st["type"] == "triage": answer_triage(pg, st)
    else:
        fill_compose(pg, st, compose_values(st, note)); confirm_all(pg); submit(pg)


def fail_once(pg, st):
    open_all(pg)
    if st["type"] == "decision":
        cf = correct_findings(st)
        answer_decision(pg, st, findings=cf[1:] + distractors(st)[:1], option=(wrong_options(st) or [None])[0])
    elif st["type"] == "triage": answer_triage(pg, st, wrong=True)
    else:
        vals = compose_values(st, note)
        sel = next(x for x in st["fields"] if x["type"] == "select")
        vals[sel["id"]] = first_unaccepted(sel)
        fill_compose(pg, st, vals); confirm_all(pg); submit(pg)


def to_stage(pg, ti, sid):
    goto(pg, M12 + "#task-%d" % (ti + 1), 1)
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


def earned(pg):
    vw = pg.evaluate("PVADesk.verifiedWork()")
    return vw["m12-l9"]["samplesEarned"]


def attempt_in(pg, st, confirms=True, **over):
    v = compose_values(st, note); v.update(over)
    fill_compose(pg, st, v)
    if confirms: confirm_all(pg)
    submit(pg)
    okk = pg.is_enabled("#btnNext"); fbx = fb_text(pg); got = earned(pg)
    if okk: revise(pg)
    else:
        b = panel(pg).get_by_role("button", name=re.compile("Reconsider|Revise", re.I))
        if b.count(): b.first.click(); pg.wait_for_timeout(30)
        open_all(pg)
    return okk, fbx, got


def triage_attempt(pg, st, override):
    root = panel(pg); open_all(pg)
    for i, r in enumerate(st["rows"]):
        root.locator("select.desk-select").nth(i).select_option(override.get(r["id"], r["answer"]))
    root.locator("button[type=submit]").first.click(); pg.wait_for_timeout(60)
    okk = pg.is_enabled("#btnNext")
    if not okk:
        b = root.get_by_role("button", name=re.compile("Reconsider|Try again|Revise", re.I))
        if b.count(): b.first.click(); pg.wait_for_timeout(40)
    return okk


DAYS = {"Sep": 0, "Oct": 30}
def day_no(s):
    m = re.search(r"(Sep|Oct) (\d+)", s or "")
    return DAYS[m.group(1)] + int(m.group(2)) if m else None


EF106 = re.compile(r"(EF-106|Closet Divider)(?:(?!EF-\d{3})[^.]){0,80}\b(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)[- ]?(?:[a-z]+ ){0,2}(?:pack|pieces?|dividers)\b", re.I)
COUNT_WORD = re.compile(r"(?<!EF-)(?<!EF-\d)(?<!EF-\d\d)\b(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)[- ]?(?:[a-z]+ ){0,2}(?:pack|pieces?|dividers|count)\b", re.I)

with sync_playwright() as p:
    br = p.chromium.launch()

    # ---------- design ----------
    check("design", "three tasks with the approved ids, in order", IDS == ["m12-l1", "m12-l3", "m12-l9"], IDS)
    check("design", "stage types follow the approved map (triage+decision; decision+triage; compose)",
          [[s["type"] for s in t["stages"]] for t in TASKS] == [["triage", "decision"], ["decision", "triage"], ["compose"]])
    check("design", "only Task 3 carries a portfolio piece, and only its compose stage earns a work sample",
          [bool(t.get("portfolio")) for t in TASKS] == [False, False, True] and [s["id"] for _, s in ALL if s.get("evidence")] == ["l9-a"])
    check("design", "portfolio piece is 'AI-Assisted Task + QA Record'", "AI-Assisted Task + QA Record" in TASKS[2]["portfolio"])
    check("design", "every stage runs on Wed, Sep 16, in time order", all(s.get("now", "").startswith(DATE) for _, s in ALL) and
          [s["now"][-8:].strip() for _, s in ALL] == ["9:10 AM", "9:40 AM", "10:30 AM", "11:15 AM", "1:30 PM"])
    check("design", "Maya requests Task 1 (her AI use note); Sofia requests Tasks 2 and 3", [t["brief"]["from"] for t in TASKS] == ["maya", "sofia", "sofia"])
    check("design", "calendar.m12 is Wed, Sep 16", DATA["calendar"]["m12"]["date"] == DATE)
    check("design", "1a has eight requests over four calls, two each", len(Q1["rows"]) == 8 and sorted([r["answer"] for r in Q1["rows"]].count(c["id"]) for c in Q1["choices"]) == [2, 2, 2, 2])
    check("design", "2b has seven claims over four verdicts", len(B2["rows"]) == 7 and len({r["answer"] for r in B2["rows"]}) == 4)
    check("design", "Task 3 grades use, input, status, six claims (verdict + exact source) and the corrected weight, plus the note",
          [f["id"] for f in GRADED] == ["job.use", "job.input", "job.status"] + [x for n in range(1, 7) for x in ("c%d.verdict" % n, "c%d.src" % n) + (("c3.fix",) if n == 3 else ())] and
          [f["id"] for f in P3["fields"] if f["type"] == "text"] == ["note.text"])
    check("design", "every graded Task 3 field has an accepted answer", all(f.get("accept") for f in GRADED))
    check("design", "Task 3 has a three-line self-check and a declared human review", len(P3["confirm"]) == 3 and P3.get("humanReview", {}).get("note"))

    # ---------- Maya's note: a training instruction, never policy (A1, G2, G3) ----------
    note_cards = [r for _, s in ALL for r in records_of(s) if "N2 ·" in rec_text(r)]
    check("label", "Maya's note appears as a card in 1b, 2a and Task 3", len(note_cards) == 3, len(note_cards))
    check("label", "every note card is titled TRAINING INSTRUCTION and says it is not Everfield policy",
          all("TRAINING INSTRUCTION" in r["title"] and "not Everfield policy" in rec_text(r) for r in note_cards))
    check("label", "every task reference carries the label and the five note lines",
          all("not Everfield policy" in strip(" ".join(t["reference"])) and "training instruction" in strip(" ".join(t["reference"])).lower() and
              all(("N%d ·" % i) in " ".join(t["reference"]) for i in range(1, 6)) for t in TASKS))
    nl = [x for x in note_cards[0]["items"]]
    check("label", "the note has exactly N1-N5, identical on every card and in every reference",
          [x[:4] for x in nl] == ["N1 ·", "N2 ·", "N3 ·", "N4 ·", "N5 ·"] and all(r["items"] == nl for r in note_cards) and all(all(x in t["reference"] for x in nl) for t in TASKS))
    check("label", "no company-wide AI or privacy rule: nothing calls the note policy or Everfield's rule",
          not re.search(r"(?<!not )Everfield(?:'s)? (?:AI|privacy) (?:policy|rule)|company(?:-wide)? (?:AI|privacy) (?:policy|rule)|(?<!not )\bAI policy\b", EVERY, re.I))
    page = open(os.path.join(ROOT, "module-12", "index.html"), encoding="utf-8").read()
    check("label", "the page note under the title carries the label", 'id="trainingNote"' in page and "not Everfield policy" in page and "Training instruction" in page)
    ev = P3["evidence"]
    head = next(g["sampleHead"] for g in P3["groups"] if g["id"] == "ev")
    check("label", "the work-sample header and company line say training instruction, not Everfield policy, simulated drafts",
          "training instruction" in head and "not Everfield policy" in head and "simulated" in head and
          "not Everfield policy" in SRC["config"]["sample"]["companyLine"] and "For her review; not published." in ev["requestedBy"])
    # every graded privacy/AI-use call traces to a visible line
    privacy = [o for o in D1["options"] if o.get("correct")][0]["why"]
    check("authority", "1b's accepted action cites N2, and N2 names every detail the prompt must lose",
          "N2" in privacy and all(w in nl[1] for w in ("names", "email addresses", "phone numbers", "street addresses", "Order numbers, SKUs")))
    who = " ".join(strip(x) for x in TASKS[0]["reference"])
    check("authority", "each 'person decides' call has its owner on a canon line in the reference (P8, exceptions, promotions)",
          "P8 · A refund without the item coming back is Sofia's decision." in who and "Any policy exception" in who and "Whether to run a promotion is Sofia's decision." in who)

    # ---------- AI drafts: simulated, and the only home of false claims (G5) ----------
    ai_cards = [r for _, s in ALL for r in records_of(s) if (r.get("title") or "").startswith(AI)]
    check("ai", "every AI output card is titled 'AI draft · simulated'", len(ai_cards) >= 10 and
          all(any(AI in (r.get("title") or "") for r in records_of(s)) for _, s in ALL if s["id"] in ("l3-a", "l3-b", "l9-a")))
    FALSE = [r"\b2\.5 ?lb\b", r"\bthree colou?rs\b", r"\bBPA\b|\bplastic\b|\bbamboo\b", r"CP-7731-1240", r"\b8 of them\b", r"delivered by Friday", r"fits any closet shelf", r"code BIN10"]
    outside = []
    for ti, s in ALL:
        for r in records_of(s):
            if AI in (r.get("title") or ""): continue
            for f in FALSE:
                if re.search(f, rec_text(r), re.I): outside.append((r.get("id") or r.get("title"), f))
        for k in ("intro", "passWhy", "takeaway", "findingsWhy", "failWhy", "passTitle"):
            for f in FALSE:
                if re.search(f, s.get(k, ""), re.I): outside.append((s["id"] + "." + k, f))
        for x in [f["text"] for f in s.get("findings", [])] + [o["text"] for o in s.get("options", [])] + [o["label"] for fl in s.get("fields", []) for o in fl.get("options", [])]:
            for f in FALSE:
                if re.search(f, x, re.I) and not x.startswith("“"): outside.append((x[:40], f))
    check("ai", "no AI claim that is false or unsupported appears outside an AI-draft card", not outside, outside)

    # ---------- EF-106 count stays undefined (A2, G4) ----------
    hits = [(loc, t) for loc, t in all_strings(SRC["tasks"]) + all_strings(SRC["config"]) if EF106.search(t)]
    check("ef106", "an EF-106 count appears exactly once, inside 2a's AI-draft card",
          len(hits) == 1 and hits[0][0].startswith("[1].stages[0].records[2]") and A2["records"][2]["title"].startswith(AI), hits)
    rec106 = fields_of({"fields": A2["records"][3]["rows"]})
    check("ef106", "EF-106's approved record holds no pack count and no material (dash)", rec106.get("Pack count") == "—" and rec106.get("Material") == "—")
    others106 = [x for x in [f["text"] for f in A2["findings"]] + [o["text"] for o in A2["options"]] + [A2["findingsWhy"], A2["takeaway"], A2["intro"]] if re.search(r"\d", re.sub(r"EF-\d{3}", "", x))]
    check("ef106", "no 2a finding, option or feedback states any number", not others106, others106)
    acc = option_text(A2, correct_option(A2))
    check("ef106", "the accepted action removes the count and tells Sofia; it supplies no count", acc.startswith("Take out the count") and "Sofia" in acc and not COUNT_WORD.search(acc))
    check("ef106", "no work-sample, field label or option in Task 3 mentions EF-106", "EF-106" not in learner_text(TASKS[2]) and "EF-106" not in json.dumps(P3["evidence"]))
    check("ef106", "EF-106 has no product fact", "EF-106" not in DATA["productFacts"])
    m14 = open(os.path.join(ROOT, "module-14", "index.html"), encoding="utf-8").read()
    t9 = m14[m14.index('id: "m14-t9"'):m14.index('checkNote: "AI + QA Record skill: confirmed."')]
    main14 = subprocess.run(["git", "show", "main:module-14/index.html"], cwd=ROOT, capture_output=True, text=True).stdout
    check("ef106", "Module 14 t9 is unchanged from main and states no count", m14 == main14 and not COUNT_WORD.search(t9) and "EF-106 states a piece count" in t9)
    check("ef106", "the retired '8 to 6' placeholder is gone from Module 12", "from 8 to 6" not in page and "8 to 6" not in EVERY)

    # ---------- canon and ranges ----------
    canon = {}
    for line in open(os.path.join(ROOT, "docs", "everfield-continuity.md"), encoding="utf-8"):
        m = re.match(r"^\| (P\d+) \| (.+?) \| [^|]*\|\s*$", line)
        if m: canon[m.group(1)] = m.group(2)
    pl = re.findall(r"\b(P\d+) · ([^\n“”]+?)(?=$|\n)", "\n".join(strip(x) for _, x in all_strings(SRC["tasks"])), re.M)
    check("canon", "every policy line quotes the approved clause word for word", pl and all(canon.get(k) == v for k, v in pl), [k for k, v in pl if canon.get(k) != v])
    nums = [int(n) for n in re.findall(r"#(\d{4})", EVERY)]
    check("canon", "orders stay in #5521-#5535 and tracking in CP-7731-12xx", nums and all(5521 <= n <= 5535 for n in nums) and all(t.startswith("12") for t in re.findall(r"CP-7731-(\d{4})", EVERY)))
    check("canon", "no returns, stock figures, dollar amounts, marketplace IDs, EF-103 or EF-104 count",
          not re.search(r"Return #|\bAvailable\b|\bInbound\b|\$\s?\d|MKT-\d|EF-103\b", EVERY) and not re.search(r"(EF-104|Cable Management Set)[^.]{0,80}\b\d+[- ]?(piece|pieces|pack)\b", EVERY, re.I))
    pf = DATA["productFacts"]["EF-101"]
    r1 = fields_of({"fields": EVREC["e-r1"]["rows"]})
    check("canon", "R-1 states EF-101's canon name, category, dimensions and weight, and no material",
          r1["Product name"] == DATA["products"]["EF-101"] and r1["Category"] == pf["category"] and r1["Dimensions"] == pf["dimensions"] and r1["Weight"] == pf["weight"] and r1["Material"] == "—")
    check("canon", "R-2 states the catalog's no-variants canon", "No size or color variants on any SKU" in rec_text(EVREC["e-r2"]) and "no size/color variants" in DATA["productFacts"]["catalog"]["variants"])
    dated = []
    for loc, t in all_strings(SRC["tasks"]):
        d = day_no(t)
        if d is not None and not (10 <= d <= 16): dated.append((loc, t[:40]))
    check("canon", "every dated record falls Thu Sep 10 - Wed Sep 16", not dated, dated)
    check("canon", "only fictional contact details (example.com, 555-01xx)",
          all(e.endswith("@example.com") for e in re.findall(r"[\w.]+@[\w.]+", EVERY)) and all(re.match(r"555-01\d\d$", ph) for ph in re.findall(r"555-\d{4}", EVERY)))
    others = {m: decode("module-%d" % m) for m in (2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 13)}
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
    leaks = [x[:50] for x in acc_texts if len(x) > 24 and x in EVERY and x not in TEAM]
    check("cross-module", "no graded answer from Modules 2-11 or 13 appears in Module 12", not leaks, leaks[:6])

    # ---------- recompute every call from its own evidence ----------
    def call1(r):
        f = fields_of(r); t = rec_text(r)
        if re.search(r"Email|Street address|\(\d{3}\) 555-\d{4}|Columns:.*(?:Email|address)", t): return "strip"
        if re.search(r"promotion|refund", t, re.I): return "person"
        if "Platform status" in f or "Shared inbox log" in f: return "record"
        return "draft"
    got = {r["id"]: call1(r) for r in Q1["rows"]}
    check("recompute", "Task 1: every call follows from the request card's own fields", all(got[r["id"]] == r["answer"] for r in Q1["rows"]), got)
    pr = fields_of(D1["records"][0])
    check("recompute", "1b: exactly the four N2 details are in the prompt beside an order number, SKU and question",
          all(pr.get(k) and pr[k] != "—" for k in ("Customer", "Email", "Phone", "Street address", "Order", "Her question")) and "EF-105" in pr["Order"])
    def call2(r):
        f = fields_of(r); claim = f.get("Claim · AI reply draft") or f.get("Claim · AI summary for Maya")
        if "refund" in claim: return "person"
        m = re.search(r"CP-7731-\d{4}", claim)
        if m: return "keep" if m.group(0) == f["Tracking"] else "fix"
        if "delivered by" in claim: return "keep" if f.get("Estimated delivery") not in ("—", None) else "remove"
        if "shipped on Tuesday" in claim: return "keep" if f["ClearPath"].startswith("Shipped Tue") else "fix"
        if "last week" in claim: return "remove" if "No earlier" in rec_text(r) else "keep"
        n = int(re.search(r"\d+", claim).group(0)); log = r["log"]
        cnt = len(log) if "came in" in claim else len([x for x in log if x.endswith("Shipped")])
        return "keep" if n == cnt else "fix"
    got = {r["id"]: call2(r) for r in B2["rows"]}
    check("recompute", "Task 2b: every verdict follows from the claim beside its record", all(got[r["id"]] == r["answer"] for r in B2["rows"]), got)
    draft3 = fields_of(EVREC["e-r6"])["Draft"]
    claims = {f["id"].split(".")[0]: fields_of(next(r for r in records_of(P3) if r["id"] == "d-" + f["id"].split(".")[0]))["Claim"] for f in P3["fields"] if f["id"].endswith(".verdict")}
    check("recompute", "Task 3: each claim card quotes the AI draft", all(c.strip("“”").lower() in draft3.lower() for c in claims.values()), claims)
    def call3(c):
        c = c.strip("“”")
        dims = re.search(r"(\d+) x (\d+) x (\d+)", c)
        if dims: return ("keep" if "%sin x %sin x %sin" % dims.groups() == r1["Dimensions"] else "fix"), ["r1"]
        w = re.search(r"([\d.]+) lb", c)
        if w: return ("keep" if w.group(1) + " lb" == r1["Weight"] else "fix"), ["r1"]
        if c == r1["Product name"]: return "keep", ["r1"]
        if re.search(r"colou?rs?", c): return "fix", ["r2"]
        if re.search(r"made from", c, re.I): return ("remove", ["none"]) if r1["Material"] == "—" else ("keep", ["r1"])
        if re.search(r"code|% off", c): return "person", ["r7"]
    wrong = [(k, call3(c), field(P3, k + ".verdict")["accept"], field(P3, k + ".src")["accept"]) for k, c in claims.items()
             if [call3(c)[0]] != field(P3, k + ".verdict")["accept"] or [sorted(call3(c)[1])] != field(P3, k + ".src")["accept"]]
    check("recompute", "Task 3: every verdict and exact source set follows from R-1, R-2 and R-7", not wrong, wrong)
    check("recompute", "Task 3: the corrected weight is R-1's weight", field(P3, "c3.fix")["accept"] == [r1["Weight"].split()[0]])
    check("recompute", "Task 3: the prompt card shows only Sofia's request and the record (no customer details)",
          "Nothing else" in rec_text(EVREC["e-r5"]) and not re.search(r"@|555-|Street|Customer", rec_text(EVREC["e-r5"])) and label_of(field(P3, "job.input"), "rec").endswith("no customer details"))

    # ---------- normal flow, completion, work sample ----------
    ctx, pg, errs = fresh(br); goto(pg, M12)
    check("page", "desk bar shows Wed, Sep 16, three tasks, and the training note",
          pg.text_content("#deskDate") == DATE and "AI-assisted work" in pg.text_content(".desk-bar") and pg.inner_text("#lessonKicker") == "Task 1 of 3" and pg.locator("#trainingNote").is_visible())
    for ti, t in enumerate(TASKS):
        goto(pg, M12 + "#task-%d" % (ti + 1), 1); ok = True
        for st in t["stages"]:
            solve(pg, st)
            if not pg.is_enabled("#btnNext"): ok = False; break
            pg.click("#btnNext"); pg.wait_for_timeout(60)
        check("flow", "task %d completes through the UI" % (ti + 1), ok, fb_text(pg)[:200])
    check("flow", "completion banner", "Module 12 complete" in pg.inner_text("#doneBanner"), pg.inner_text("#doneBanner"))
    prog = pg.evaluate("JSON.parse(localStorage.getItem('pva-ecom-ft-progress'))")
    check("progress", "verified work marks all three lessons in the legacy progress store", all(prog["lessons"].get(i) for i in IDS))
    keys = pg.evaluate("Object.keys(localStorage).sort()")
    check("isolation", "only the Module 12 desk key and the legacy progress key are written", keys == [KEY, "pva-ecom-ft-progress"], keys)
    vw = pg.evaluate("PVADesk.verifiedWork()")
    check("verified-work", "all three tasks verified, one earned sample (l9-a)",
          all(v["verified"] for v in vw.values()) and vw["m12-l9"]["samplesEarned"] == ["l9-a"] and not any(v["samplesEarned"] for k, v in vw.items() if k != "m12-l9"), vw)
    goto(pg, BASE + "/index.html")
    card = pg.locator(".module-card").nth(11).inner_text()
    check("progress", "course map shows Module 12 Completed", "AI-Assisted E-commerce VA Work" in card and "Completed" in card, card)
    goto(pg, M12 + "#task-3", 1)
    sample = pg.locator(".ws-preview").inner_text() if pg.locator(".ws-preview").count() else ""
    check("work-sample", "the sample header is honest: training work sample, AI + QA Record, not Everfield policy, simulated, for Sofia's review",
          sample.startswith("TRAINING WORK SAMPLE\nEverfield Goods — AI + QA Record (training work sample)") and "Work date: Wed, Sep 16 (simulated)" in sample and
          "For her review; not published." in sample and "not Everfield policy" in sample, sample[:600])
    check("work-sample", "the sample lists all six claims with verdicts and sources, the corrected weight, the status and the note",
          all(("Claim %d" % n) in sample for n in range(1, 7)) and "2.2" in sample and "nothing is published yet" in sample and GOOD_NOTE in sample and "human review" in sample, sample[-900:])
    check("flow", "no JS errors", not errs, errs)
    ctx.close()

    # ---------- Task 3 opened first (G7) ----------
    ctx, pg, errs = fresh(br)
    goto(pg, M12 + "#task-3", 1); solve(pg, P3)
    store = pg.evaluate("JSON.parse(localStorage.getItem('%s'))" % KEY)
    vw = pg.evaluate("PVADesk.verifiedWork()")
    check("task3-first", "in fresh storage, Task 3 completes and earns the sample with Tasks 1 and 2 untouched",
          pg.is_enabled("#btnNext") and vw["m12-l9"]["samplesEarned"] == ["l9-a"] and not vw["m12-l1"]["verified"] and not vw["m12-l3"]["verified"] and set(store["tasks"].keys()) == {"m12-l9"},
          (vw, list(store["tasks"].keys())))
    t12 = learner_text(TASKS[0]) + learner_text(TASKS[1])
    check("task3-first", "Task 3 uses a different product, request and cards: no EF-101 claim, R-card or BIN10 code in Tasks 1-2",
          not re.search(r"R-\d ·|BIN10|2\.5 lb|Stackable Storage Bin\. Measures", t12) and "EF-106" not in learner_text(TASKS[2]))
    check("task3-first", "no JS errors", not errs, errs)
    ctx.close()

    # ---------- portfolio piece 12 is earned only by validated work (G8) ----------
    ctx, pg, _ = fresh(br)
    to_stage(pg, 2, "l9-a"); open_all(pg)
    okk, fbx, got = attempt_in(pg, P3)
    check("portfolio", "the accepted QA record passes and earns the sample", okk and got == ["l9-a"], fbx[:200])
    ctx.close()
    ctx, pg, _ = fresh(br)
    to_stage(pg, 2, "l9-a"); open_all(pg)
    for f in GRADED:
        if f["type"] == "select": bad = first_unaccepted(f)
        elif f["type"] == "multi": bad = sorted(set(f["accept"][0]) ^ {f["options"][0]["value"] if f["options"][0]["value"] not in f["accept"][0] else f["options"][1]["value"]})
        else: bad = "2.5"
        okk, fbx, got = attempt_in(pg, P3, **{f["id"]: bad})
        check("portfolio", "a wrong %s alone blocks the piece" % f["id"], not okk and not got, fbx[:120])
    for why, txt in (("blank", ""), ("one word", "Checked."), ("non-empty filler", "ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok"), ("keyword list", "weight colors material code review draft Sofia")):
        okk, fbx, got = attempt_in(pg, P3, **{"note.text": txt})
        check("portfolio", "a %s note blocks the piece" % why, not okk and not got, fbx[:120])
    fill_compose(pg, P3, compose_values(P3, note)); confirm_all(pg)
    boxes = panel(pg).locator(".desk-selfcheck input[type=checkbox]")
    blocked = []
    for i in range(boxes.count()):
        boxes.nth(i).uncheck(); pg.wait_for_timeout(30)
        blocked.append(panel(pg).locator("button[type=submit]").first.is_disabled())
        boxes.nth(i).check(); pg.wait_for_timeout(30)
    check("portfolio", "each unticked self-check line alone blocks submission (and so the piece)", blocked and all(blocked) and not earned(pg), blocked)
    check("portfolio", "human review is declared on the stage and named in the sample", P3["humanReview"]["note"].startswith("Quality of this QA record is judged by human review"))
    for why, val in (("2.20 (trailing zero)", "2.20"), ("2.2", "2.2")):
        okk, fbx, got = attempt_in(pg, P3, **{"c3.fix": val})
        check("portfolio", "corrected weight %s passes" % why, okk, fbx[:120])
    for why, val in (("2.5 (the draft's)", "2.5"), ("2.2 lb (unit typed)", "2.2 lb"), ("22", "22"), ("blank", "")):
        okk, fbx, got = attempt_in(pg, P3, **{"c3.fix": val})
        check("portfolio", "corrected weight %s fails" % why, not okk)
    SRC_TRAPS = [("c1", ["r1", "r6"], "the AI draft cited as a source"), ("c5", ["none", "r1"], "'no card' plus a card"), ("c5", ["r6"], "the AI draft as the material's source"),
                 ("c6", ["r3"], "Maya's note as a source"), ("c6", ["r4"], "Sofia's request instead of who decides promotions"), ("c4", ["r1"], "the product record for the variants claim"),
                 ("c3", ["r1", "r5"], "the prompt as an extra source")]
    for c, val, why in SRC_TRAPS:
        okk, _, got = attempt_in(pg, P3, **{c + ".src": sorted(val)})
        check("portfolio", "%s source fails: %s" % (c, why), not okk and not got)
    VERD_TRAPS = [("c5", "fix", "correcting a material no record holds"), ("c6", "remove", "dropping the code without asking Sofia"), ("c6", "keep", "keeping the discount"),
                  ("c4", "remove", "treating the variants claim as unrecorded"), ("c3", "keep", "keeping the draft's weight")]
    for c, v, why in VERD_TRAPS:
        okk, _, got = attempt_in(pg, P3, **{c + ".verdict": v})
        check("portfolio", "%s verdict fails: %s" % (c, why), not okk and not got)
    for v in ("publish", "asis", "selffix"):
        okk, _, got = attempt_in(pg, P3, **{"job.status": v})
        check("portfolio", "status '%s' fails" % label_of(field(P3, "job.status"), v)[:45], not okk and not got)
    okk, _, got = attempt_in(pg, P3, **{"job.input": "review"})
    check("portfolio", "a prompt with a customer's name fails the input field", not okk and not got)

    # ---------- the QA note ----------
    GOOD = [("terse", "Corrected the weight to 2.2 lb and removed the color claim. Draft for your review."),
            ("first person", "I fixed the weight from the record and took the BPA-free plastic line out because no record holds a material. Please review it before anything goes live."),
            ("negation", "Nothing is published yet. I removed the discount code because promotions are your call, and the colors line, since the catalog has no variants."),
            ("quotes the claim", "The draft said it is made from BPA-free plastic, so I removed that line and corrected the weight. The corrected draft is for your review."),
            ("mentions the assistant", "I used the assistant for a first draft and checked each claim myself. Weight corrected to 2.2 lb; it's for your review."),
            ("not live", "Weight fixed and the BIN10 code taken out for you to decide. The description is not live yet.")]
    for why, t in GOOD:
        okk, fbx, _ = attempt_in(pg, P3, **{"note.text": t})
        check("note", "passes -- %s" % why, okk, (t, fbx[:200]))
    AIV, LIVE, FACT, CHG, REV = "the assistant checks nothing", "nothing is live", "no record holds a material", "name at least one change", "for sofia's review"
    BAD = [("says the assistant checked it", "The assistant checked the facts already, so the draft is accurate. I removed the colors line anyway, and it is for your review.", AIV),
           ("says it was verified by AI", "Every claim was verified by the AI, and I corrected the weight. For your review.", AIV),
           ("claims it is published", "I've published the corrected description and removed the discount code from it. It is ready for customers to read now.", LIVE),
           ("claims it is now live", "The corrected description is now live with the weight fixed. Draft notes for your review.", LIVE),
           ("states a material as fact", "It's made of bamboo, so I changed that, and the weight is fixed. For your review.", FACT),
           ("states a shipping time", "I corrected the weight from the record. It ships in two days, which I added to the text. It is for your review.", FACT),
           ("names no change", "I checked the draft carefully against every card on the desk. It is ready for your review.", CHG),
           ("has no review statement", "I corrected the weight to 2.2 lb and removed the colors line. The rest matches the record.", REV)]
    for why, t, want in BAD:
        okk, fbx, got = attempt_in(pg, P3, **{"note.text": t})
        check("note", "rejected with the matching reason -- a note that %s" % why, not okk and not got and want in fbx.lower(), (t, fbx[:200]))
    ctx.close()

    # ---------- evidence gate (every stage) ----------
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
    ctx, pg, _ = fresh(br)
    to_stage(pg, 2, "l9-a"); r = panel(pg)
    groups = r.locator("section.desk-group")
    check("evidence-gate", "l9-a: every group with fields has its own gated card", all(len([x for x in g["records"] if x.get("kind") != "reference"]) for g in P3["groups"] if any(f["group"] == g["id"] for f in P3["fields"])))
    ctx.close()

    # ---------- wrong answer, feedback safety, pause, re-open (every stage) ----------
    ctx, pg, _ = fresh(br)
    for ti, st in ALL:
        to_stage(pg, ti, st["id"])
        fail_once(pg, st); fb = fb_text(pg)
        check("feedback", "%s: wrong attempt gets explanatory feedback, next stays locked" % st["id"], fb and not pg.is_enabled("#btnNext"), fb[:120])
        leak = []
        if st["type"] == "decision": leak = [option_text(st, correct_option(st))] + [finding_text(st, f) for f in correct_findings(st)]
        if st["type"] == "triage": leak = [next(c["label"] for c in st["choices"] if c["id"] == r["answer"]) + " -- " for r in st["rows"]]
        check("feedback", "%s: feedback never quotes a correct option or finding" % st["id"], not any(x in fb for x in leak if len(x) > 20))
        b = panel(pg).get_by_role("button", name=re.compile("Reconsider|Revise", re.I))
        if b.count(): b.first.click(); pg.wait_for_timeout(40)
        fail_once(pg, st); pg.wait_for_timeout(40)
        r = panel(pg)
        paused = r.locator(".desk-pause").count() == 1 and r.locator(".desk-evidence-card.is-recheck").count() >= 1
        check("pause", "%s: second miss pauses and closes the evidence behind it until re-opened" % st["id"], paused)
        open_all(pg); pg.wait_for_timeout(30)
        retry = r.get_by_role("button", name="Reconsider and try again")
        if retry.count(): retry.click(); pg.wait_for_timeout(30)
        rv = r.get_by_role("button", name="Revise your work")
        if rv.count(): rv.click(); pg.wait_for_timeout(30)
        solve(pg, st)
        check("pause", "%s: after re-opening, the right answer passes" % st["id"], pg.is_enabled("#btnNext"), fb_text(pg)[:120])
    ctx.close()

    # ---------- authority and AI traps ----------
    ctx, pg, _ = fresh(br)
    T1 = [("the promotion drafted with AI", {"r7": "draft"}), ("the early refund drafted with AI", {"r8": "draft"}), ("Maya's export sent in with customer details", {"r3": "draft"}),
          ("the signed reply sent in with her address", {"r4": "draft"}), ("asking AI whether #5521 shipped", {"r5": "draft"}), ("the inbox count drafted with AI", {"r6": "draft"}),
          ("the EF-104 draft refused as a person's decision", {"r1": "person"}), ("handoff notes stripped though they hold no customer details", {"r2": "strip"})]
    for why, ov in T1:
        to_stage(pg, 0, "l1-a")
        check("traps", "l1-a fails when %s" % why, not triage_attempt(pg, Q1, ov))
    T2 = [("the swapped tracking number kept", {"b": "keep"}), ("the delivery promise kept", {"c": "keep"}), ("the shipping refund kept", {"d": "keep"}),
          ("the shipping refund just deleted", {"d": "remove"}), ("the shipped count kept", {"f": "keep"}), ("the last-week comparison kept", {"g": "keep"}),
          ("the true ship day 'corrected'", {"a": "fix"})]
    for why, ov in T2:
        to_stage(pg, 1, "l3-b")
        check("traps", "l3-b fails when %s" % why, not triage_attempt(pg, B2, ov))
    ctx.close()
    for st in (D1, A2):
        for wo in wrong_options(st):
            ctx, pg, _ = fresh(br)
            to_stage(pg, 0 if st is D1 else 1, st["id"]); open_all(pg)
            answer_decision(pg, st, option=wo)
            check("traps", "%s: '%s' fails" % (st["id"], option_text(st, wo)[:50]), not pg.is_enabled("#btnNext"))
            ctx.close()

    # ---------- integrity, leakage ----------
    ctx, pg, _ = fresh(br); goto(pg, M12)
    pg.evaluate("""localStorage.setItem('%s', JSON.stringify({v:1,tasks:{'m12-l9':{completed:true,verified:true,views:1,
      stages:{'l9-a':{passed:true,answer:{values:{},confirms:[true,true,true]}}},drafts:{}}}}))""" % KEY)
    goto(pg, M12 + "#task-3")
    st3 = pg.evaluate("PVADesk.taskStatus(PVADesk.decode(window.PVA_DESK_MODULES.m12.payload).tasks[2])")
    check("integrity", "forged completed/verified/passed flags count for nothing", st3["passed"] == 0, st3)
    check("integrity", "forged state earns no sample and never reaches the legacy progress store",
          not earned(pg) and not (pg.evaluate("JSON.parse(localStorage.getItem('pva-ecom-ft-progress')||'{}')").get("lessons") or {}).get("m12-l9"))
    shipped = "".join(pg.request.get(BASE + uu).text() for uu in ["/module-12/index.html", "/module-12/desk-data.js"])
    markers = ['"correct"', "correct: true", '"accept"', '"answer":', '"correctOrder"']
    check("leakage", "no plaintext answer markers in shipped Module 12 files", not any(m in shipped for m in markers))
    check("leakage", "no correct decision option text appears in shipped source", not any(option_text(s, correct_option(s)) in shipped for _, s in ALL if s["type"] == "decision"))
    check("leakage", "no plaintext source file is in the repository", not any(f.endswith(".src.json") for _, _, fs in os.walk(ROOT) for f in fs))
    sel = [f for f in P3["fields"] if f["type"] == "select" and not f["id"].endswith(".verdict")]
    strict = [f["id"] for f in sel if len(label_of(f, f["accept"][0])) > max(len(o["label"]) for o in f["options"] if o["value"] != f["accept"][0])]
    check("leakage", "no job select's accepted option is strictly its longest", not strict, strict)
    vpos = [field(P3, "c%d.verdict" % n)["accept"][0] for n in range(1, 7)]
    check("leakage", "claim verdicts use all four options", len(set(vpos)) == 4, vpos)
    dl = [(s["id"], [len(o["text"]) for o in s["options"]], next(i for i, o in enumerate(s["options"]) if o.get("correct"))) for _, s in ALL if s["type"] == "decision"]
    check("leakage", "no decision's correct option is strictly its longest, and the positions differ",
          not [x for x in dl if x[1][x[2]] > max(l for i, l in enumerate(x[1]) if i != x[2])] and len({x[2] for x in dl}) == 2, dl)
    vals_dom = []
    for ti in range(3):
        goto(pg, M12 + "#task-%d" % (ti + 1), 1); open_all(pg)
        check("leakage", "task %d: rendered DOM carries no correctness attributes" % (ti + 1), not re.search(r'(class|data-[a-z-]+)="[^"]*(correct|answer|right)', pg.content()))
        vals_dom += pg.evaluate("Array.from(document.querySelectorAll('#stagePanel input,#stagePanel option')).map(e=>e.value)")
    check("leakage", "no control value names the answer", not [x for x in vals_dom if re.match(r"^(correct|right|wrong)", x)])
    ctx.close()

    # ---------- persistence, legacy, hub, portfolio ----------
    ctx, pg, _ = fresh(br)
    to_stage(pg, 0, "l1-a"); open_all(pg)
    panel(pg).locator("select.desk-select").first.select_option(Q1["rows"][0]["answer"])
    pg.reload(); pg.wait_for_timeout(150); pg.click("#btnNext"); pg.wait_for_timeout(80)
    check("persistence", "an unsubmitted triage call survives refresh", panel(pg).locator("select.desk-select").first.input_value() == Q1["rows"][0]["answer"])
    ctx.close()
    ctx, pg, _ = fresh(br); goto(pg, BASE + "/index.html")
    pg.evaluate("v => localStorage.setItem('pva-ecom-ft-progress', JSON.stringify(v))", {"lessons": {"m12-l%d" % i: True for i in range(1, 11)}, "modules": {}})
    goto(pg, M12 + "#task-1")
    check("legacy", "all three lessons keep their earlier checkmarks", pg.locator(".lesson-pill.done").count() == 3)
    check("legacy", "the status line separates legacy completion from new work", "earlier version" in pg.inner_text("#taskStatus"))
    vw = pg.evaluate("PVADesk.verifiedWork()")
    check("legacy", "legacy completion is not verified work and earns no sample", not any(v["verified"] for v in vw.values()) and not any(v["samplesEarned"] for v in vw.values()))
    goto(pg, BASE + "/index.html")
    check("legacy", "someone who finished old Module 12 still sees it Completed", pg.locator(".module-status").nth(11).inner_text() == "Completed")
    pg.evaluate("v => localStorage.setItem('pva-ecom-ft-progress', JSON.stringify(v))", {"lessons": {"m12-l1": True, "m12-l9": True, "m12-l10": True}, "modules": {}})
    goto(pg, BASE + "/index.html")
    check("legacy", "the course map counts Module 12 against its three lessons (retired ids ignored)", "2 of 3" in pg.locator(".module-card").nth(11).inner_text())
    ctx.close()
    hub = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
    check("hub", "the course map lists m12-l1, m12-l3, m12-l9 with the new description", 'lessonIds: ["m12-l1","m12-l3","m12-l9"]' in hub and "keep customer details out" in hub)
    port = open(os.path.join(ROOT, "portfolio", "index.html"), encoding="utf-8").read()
    check("portfolio", "piece 12 keeps its title and points at Module 12, Lesson 3", "AI-Assisted Task + QA Record" in port and "From Module 12, Lesson 3 -- The AI + QA Record" in port and "Lesson 9 -- Human Review" not in port)
    check("portfolio", "the portfolio still lists 14 pieces", len(re.findall(r'class="portfolio-num"', port)) == 14)

    # ---------- isolation, accessibility, deep links ----------
    ctx, pg, _ = fresh(br)
    goto(pg, M11 + "#task-1", 1); open_all(pg)
    to_stage(pg, 0, "l1-a"); solve(pg, Q1)
    keys = pg.evaluate("Object.keys(localStorage).sort()")
    check("isolation", "Module 12 writes only its own desk key", set(keys) - {"pva-ecom-ft-progress", "pva-ecom-ft-m11-desk"} == {KEY}, keys)
    mut = pg.evaluate("(()=>{try{EVERFIELD.calendar.m12.date='Y';}catch(e){} return EVERFIELD.calendar.m12.date})()")
    check("everfield", "shared Everfield reference cannot be mutated from Module 12", mut == DATE, mut)
    for ti, st in ALL:
        to_stage(pg, ti, st["id"]); open_all(pg)
        unnamed = pg.evaluate("""Array.from(document.querySelectorAll('#stagePanel select,#stagePanel input,#stagePanel textarea,#stagePanel button')).filter(e=>{var n=(e.labels&&e.labels.length)||e.getAttribute('aria-label')||e.getAttribute('aria-labelledby')||(e.tagName==='BUTTON'&&e.innerText.trim());return !n}).length""")
        check("a11y", "%s: every control has an accessible name" % st["id"], not unnamed, unnamed)
    for n in (1, 2, 3):
        goto(pg, M12 + "#task-%d" % n); check("deep-link", "#task-%d opens task %d" % (n, n), pg.inner_text("#lessonKicker") == "Task %d of 3" % n and pg.text_content("#deskDate") == DATE)
    ctx.close()

    # ---------- contrast and five widths ----------
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
    goto(pg, M12 + "#task-1"); low += pg.evaluate(CONTRAST)
    to_stage(pg, 0, "l1-a"); open_all(pg); fail_once(pg, Q1); low += pg.evaluate(CONTRAST)
    to_stage(pg, 2, "l9-a"); open_all(pg); solve(pg, P3); low += pg.evaluate(CONTRAST)
    check("contrast", "all enabled text meets WCAG AA in brief, triage feedback and work-sample states", not low, sorted(set(low))[:8])
    ctx.close()
    RESP = """(()=>{
     var ov=document.documentElement.scrollWidth-innerWidth;
     var cells=Array.from(document.querySelectorAll('#stagePanel .desk-table tbody td, #stagePanel .desk-table tbody th')).filter(c=>c.scrollWidth>c.clientWidth+1).length;
     function hit(a,b){var x=a.getBoundingClientRect(),y=b.getBoundingClientRect();return x.width&&y.width&&x.left<y.right-1&&y.left<x.right-1&&x.top<y.bottom-1&&y.top<x.bottom-1;}
     var heads=Array.from(document.querySelectorAll('#stagePanel .desk-ev-head')).filter(h=>{var t=h.querySelector('.desk-record-title');return t&&Array.from(h.children).filter(c=>!c.contains(t)).some(c=>hit(t,c));}).length;
     var bar=document.querySelector('.desk-bar'); var barov=bar?bar.scrollWidth-bar.clientWidth>1:false;
     return [ov>1?ov:0,cells,heads,barov?1:0];})()"""
    for w in (320, 375, 390, 768, 1100):
        ctx, pg, _ = fresh(br, viewport={"width": w, "height": 812}, device_scale_factor=2 if w < 700 else 1, is_mobile=w < 700, has_touch=w < 700)
        for ti, st in ALL:
            to_stage(pg, ti, st["id"]); open_all(pg); pg.wait_for_timeout(60)
            r = pg.evaluate(RESP)
            check("responsive", "%s at %dpx: no sideways scroll, no clipped cell, no overlapping card header" % (st["id"], w), not any(r), r)
        ctx.close()
    br.close()

fails = [r for r in results if not r[2]]
print("\n%d checks, %d failed" % (len(results), len(fails)))
sys.exit(1 if fails else 0)
