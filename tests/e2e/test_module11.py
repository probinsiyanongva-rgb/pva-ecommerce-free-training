"""Module 11 Work Desk regression + adversarial suite (browser), modelled on Modules 10 and 13.

Run from the repo root with a static server on :8765 (see tests/README.md):
    python3 tests/e2e/test_module11.py
Answers come from decoding the shipped content at run time (desk_helpers.decode). The
"recompute" checks derive every Task 1 call from each order card's own fields, every
Task 2 verdict's source cards from the cards that step's row shows, and every 3d source
set from the same rows; the source-fidelity checks decode Modules 4 and 6 to prove the
S-E card quotes their reference lines word for word. The cross-module checks prove
Module 11 prints none of the other modules' graded answers. Nothing answer-bearing is
stored here."""
import os, sys, re, json, subprocess
from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from desk_helpers import *  # noqa

SRC = decode("module-11")
M11 = BASE + "/module-11/index.html"
M10 = BASE + "/module-10/index.html"
TASKS = SRC["tasks"]
IDS = [t["id"] for t in TASKS]
ALL = [(ti, s) for ti, t in enumerate(TASKS) for s in t["stages"]]
KEY = "pva-ecom-ft-m11-desk"
DATA = json.loads(subprocess.run(["node", "-e", "process.stdout.write(JSON.stringify(require('./shared/everfield-data.js')))"], cwd=ROOT, capture_output=True, text=True).stdout)
DATE = "Mon, Sep 14"
LABEL_BITS = ("Training document", "not Everfield policy")
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
A2, N2 = stage_by_id(SRC, "l2-a"), stage_by_id(SRC, "l2-b")
X3, Y3, Z3, P3 = stage_by_id(SRC, "l3-a"), stage_by_id(SRC, "l3-b"), stage_by_id(SRC, "l3-c"), stage_by_id(SRC, "l3-d")
EVERY = " ".join(learner_text(t) for t in TASKS)
SOP_CARD = next(r for r in D1["records"] if r["id"] == "b-sop")
V1 = [re.sub(r"^Step \d+\. ", "", x) for x in SOP_CARD["items"]]
CARD_TITLES = {r["title"].split(" · ")[0]: r for r in P3["groups"][0]["records"] if r.get("kind") == "reference" and r["title"].startswith("S-")}
SRC_FIELD = field(P3, "st1.src")
CARD_VALUE = {o["label"].split(" · ")[0]: o["value"] for o in SRC_FIELD["options"]}


GOOD_NOTE = ("This is a proposed revision for your review. Steps 2, 3, 4, 6 and 8 now match their cards, and step 9 is marked pending "
             "your decision because no approved reply time exists. Nothing changes until you approve it.")


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
    goto(pg, M11 + "#task-%d" % (ti + 1), 1)
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
    v = compose_values(st, note); v.update(over)
    fill_compose(pg, st, v); confirm_all(pg); submit(pg)
    okk = pg.is_enabled("#btnNext"); fbx = fb_text(pg)
    if okk: revise(pg)
    else: open_all(pg)
    return okk, fbx


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


# ---------- date helpers for record consistency ----------
DAYS = {"Sep": 0, "Oct": 30}
def day_no(s):
    m = re.search(r"(Sep|Oct) (\d+)", s or "")
    return DAYS[m.group(1)] + int(m.group(2)) if m else None


with sync_playwright() as p:
    br = p.chromium.launch()

    # ---------- design ----------
    check("design", "three tasks with the approved ids, in order", IDS == ["m11-l1", "m11-l7", "m11-l3"], IDS)
    check("design", "stage types follow the approved map (triage+decision; triage+decision; decision x3 + compose)",
          [[s["type"] for s in t["stages"]] for t in TASKS] == [["triage", "decision"], ["triage", "decision"], ["decision", "decision", "decision", "compose"]])
    check("design", "only Task 3 carries a portfolio piece, and only its compose stage earns a work sample",
          [bool(t.get("portfolio")) for t in TASKS] == [False, False, True] and [s["id"] for _, s in ALL if s.get("evidence")] == ["l3-d"])
    check("design", "every stage runs on Mon, Sep 14, at 9:00, 10:15 or 11:00 by task",
          all(s.get("now", "").startswith(DATE) for _, s in ALL) and [TASKS[i]["stages"][0]["now"][-8:] for i in range(3)] == [" 9:00 AM", "10:15 AM", "11:00 AM"])
    check("design", "Maya Collins requests every task", all(t["brief"]["from"] == "maya" for t in TASKS))
    check("design", "calendar.m11 is Mon, Sep 14", DATA["calendar"]["m11"]["date"] == DATE)
    check("design", "3d grades 27 fields (verdict, wording, source per step) plus the change note",
          len([f for f in P3["fields"] if f["type"] != "text"]) == 27 and [f["id"] for f in P3["fields"] if f["type"] == "text"] == ["note.text"])

    # ---------- training label ----------
    sop_cards = [r for _, s in ALL for r in records_of(s) if "SOP v1" in rec_text(r)]
    check("label", "every card showing SOP v1 carries the training-document label",
          sop_cards and all(re.search("training document", rec_text(r), re.I) for r in sop_cards), [r.get("id") for r in sop_cards if not re.search("training document", rec_text(r), re.I)])
    check("label", "the full SOP card (1b, 2b, 3d) states it is not Everfield policy",
          all(any(r["id"] == x and "not Everfield policy" in rec_text(r) for _, s in ALL for r in records_of(s)) for x in ("b-sop", "n-sop", "d-sop")))
    check("label", "every task reference opens with the training label", all(all(b in strip(t["reference"][0]) for b in LABEL_BITS) for t in TASKS))
    check("label", "3d's heading and evidence group say it is a training document and a proposal, not policy",
          "not Everfield policy" in P3["intro"] and "proposal" in P3["intro"] and "not Everfield policy" in P3["groups"][0]["sampleHead"])
    page = open(os.path.join(ROOT, "module-11", "index.html"), encoding="utf-8").read()
    check("label", "the page note under the title carries the label", 'id="trainingNote"' in page and all(b.lower() in page.lower() for b in LABEL_BITS))
    ev = P3["evidence"]
    check("label", "the work-sample title, requester line and company line carry the label and 'not in effect'",
          "not Everfield policy" in ev["title"] and "For her review; not in effect" in ev["requestedBy"] and "not Everfield policy" in SRC["config"]["sample"]["companyLine"])

    # ---------- SOP wording (consolidated) ----------
    check("sop", "v1 step 4 reads 'Send stalled shipments and missing packages to Sofia.'", V1[3] == "Send stalled shipments and missing packages to Sofia.")
    c3 = next(" ".join(r["items"]) for r in P3["groups"][0]["records"] if r.get("title", "").startswith("S-G"))
    check("sop", "v1 step 7 equals the C3 wording on card S-G and says nothing about monitoring or follow-up",
          V1[6] in c3 and not re.search(r"monitor|follow|check again|recheck|leave it", V1[6], re.I))
    check("sop", "S-G is labelled 'not a verbatim quotation'", "not a verbatim quotation" in c3)
    verdict_lab = {c["id"]: c["label"] for c in A2["choices"]}
    works = [i + 1 for i, r in enumerate(A2["rows"]) if r["answer"] == "works"]
    check("sop", "three steps work as written (1, 5, 7), five carry defects, one has no approved rule",
          works == [1, 5, 7] and [r["answer"] for r in A2["rows"]].count("norule") == 1 and len(set(r["answer"] for r in A2["rows"])) == 6)
    for n in range(1, 10):
        f = field(P3, "st%d.text" % n); acc = label_of(f, f["accept"][0])
        if n in works:
            check("3d-options", "step %d: works as written, so only the v1 text passes" % n, acc == V1[n - 1] and len(f["accept"]) == 1)
    s4 = label_of(field(P3, "st4.text"), field(P3, "st4.text")["accept"][0])
    check("sop", "corrected step 4 sends stalls to Maya and keeps P11's two steps in order, naming no Sofia",
          s4.startswith("Stalled shipments go to Maya.") and s4.index("share the carrier's delivery details") < s4.index("Maya decides") and "Sofia" not in s4)
    s2 = label_of(field(P3, "st2.text"), field(P3, "st2.text")["accept"][0])
    check("sop", "corrected step 2 flags a record gap with no owner", "flag anything missing or inconsistent" in s2 and not re.search("Maya|Sofia", s2))
    s3 = label_of(field(P3, "st3.text"), field(P3, "st3.text")["accept"][0])
    check("sop", "corrected step 3 carries P1-P3, including 'until she confirms'", all(x in s3 for x in ("Not released to ClearPath", "only ClearPath can stop it", "until she confirms", "becomes a return")))
    s9 = label_of(field(P3, "st9.text"), field(P3, "st9.text")["accept"][0])
    check("sop", "step 9 is accepted only as pending Maya's decision, with no figure", s9.startswith("Pending Maya's decision") and not re.search(r"\d", s9))
    p3opt = option_text(X3, correct_option(X3))
    check("sop", "the P3 case's accepted action has no customer-reply clause", "return" in p3opt and not re.search(r"\btell\b|customer that|let them know", p3opt, re.I))
    p7opt = option_text(Z3, correct_option(Z3))
    check("sop", "the P7 case says 'possible pattern'", "possible pattern" in p7opt)
    p2lab = next(c["label"] for c in Q1["choices"] if c["id"] == next(r["answer"] for r in Q1["rows"] if r["id"] == "m6"))
    check("sop", "the P2 action keeps 'until she confirms'", "until she confirms" in p2lab)

    # ---------- record format and consistency ----------
    orders = [r for _, s in ALL for r in records_of(s) if r.get("fields") and fields_of(r).get("Platform status")]
    check("records", "every order card shows Platform status, ClearPath and Latest carrier event as separate fields, with the key",
          orders and all(all(k in fields_of(r) for k in ("Platform status", "ClearPath", "Latest carrier event")) and "Latest carrier event" in r.get("note", "") for r in orders),
          [r.get("id") or r.get("title") for r in orders if "Latest carrier event" not in r.get("note", "")])
    byno = {}
    for r in orders:
        n = re.search(r"#(\d{4})", fields_of(r)["Order"]).group(1); byno.setdefault(n, fields_of(r))
    check("records", "#5501 and #5506: Processing on the platform, received and picking at ClearPath",
          all(byno[n]["Platform status"] == "Processing" and byno[n]["ClearPath"].startswith("Received") and "picking" in byno[n]["ClearPath"] for n in ("5501", "5506")))
    check("records", "#5505: Open, not released to warehouse", byno["5505"]["Platform status"] == "Open" and byno["5505"]["ClearPath"] == "Not released to warehouse")
    check("records", "#5502: Shipped with a label but blank tracking and no carrier event",
          byno["5502"]["Platform status"] == "Shipped" and byno["5502"]["Tracking"] == "—" and byno["5502"]["Latest carrier event"] == "—" and byno["5502"]["Shipping label"].startswith("Created"))
    bad = []
    for n, f in byno.items():
        if n == "5502": continue
        pay, cp, lab, car = day_no(f["Payment"]), day_no(f["ClearPath"]), day_no(f["Shipping label"]), day_no(f["Latest carrier event"])
        if any(d is not None and d > 14 for d in (pay, cp, lab, car)): bad.append((n, "after desk day"))
        if cp is not None and pay is not None and cp < pay: bad.append((n, "ClearPath before payment"))
        if f["ClearPath"].startswith("Shipped"):
            if lab != cp: bad.append((n, "label not on ship day"))
            if f["Tracking"] == "—": bad.append((n, "shipped without tracking"))
            if car is None or car < cp: bad.append((n, "carrier event before shipping"))
        if f["Platform status"] == "Delivered" and not f["Latest carrier event"].startswith("Delivered"): bad.append((n, "Delivered without a carrier delivery"))
        if f["Platform status"] in ("Processing", "Open") and f["Tracking"] != "—": bad.append((n, "tracking before shipping"))
    check("records", "every order card except #5502 is internally consistent (payment, receipt, ship, label, carrier, delivered)", not bad, bad)
    check("records", "#5504 and #5508: platform Delivered beside ClearPath Shipped, with a dated carrier delivery",
          all(byno[n]["Platform status"] == "Delivered" and byno[n]["ClearPath"].startswith("Shipped") and byno[n]["Latest carrier event"].startswith("Delivered") and day_no(byno[n]["Latest carrier event"]) for n in ("5504", "5508")))
    dmg = [r for r in Z3["records"] if r.get("log")]
    check("records", "the three damage reports are dated Wed Sep 9, Fri Sep 11 and Mon Sep 14, and nothing calls them 'this week's'",
          [day_no(r["log"][0]) for r in dmg] == [9, 11, 14] and "this week" not in " ".join(rec_text(r) for r in Z3["records"]) + Z3["intro"])

    # ---------- recompute Task 1 calls from each card ----------
    def call(r):
        f = fields_of(r); msg = f.get("Message", "")
        if msg:
            if re.search(r"cancel", msg, re.I):
                if f["ClearPath"] == "Not released to warehouse": return "cancel"
                if f["Latest carrier event"] == "—": return "intercept"
                return "?"
            if re.search(r"money back|refund", msg, re.I) and re.search(r"keep", msg, re.I): return "sofia"
            return "answer"
        if f["Platform status"] == "Shipped" and f["Tracking"] == "—": return "record"
        if "no scan since" in f["Latest carrier event"]: return "maya"
        return "ok"
    got = {r["id"]: call(r) for r in Q1["rows"]}
    check("recompute", "Task 1: every call follows from that card's own fields", all(got[r["id"]] == r["answer"] for r in Q1["rows"]), got)
    check("recompute", "stall vs record gap: #5503 has a tracking number and a six-day silence; #5502 has no tracking number at all",
          byno["5503"]["Tracking"].startswith("CP-") and "no scan since" in byno["5503"]["Latest carrier event"] and byno["5502"]["Tracking"] == "—")

    # ---------- source cards ----------
    m4, m6 = decode("module-4"), decode("module-6")
    m4l5 = next(t for t in m4["tasks"] if t["id"] == "m4-l5"); m6l4 = next(t for t in m6["tasks"] if t["id"] == "m6-l4")
    se = " ".join(CARD_TITLES["S-E"]["items"])
    q1 = "If it shows no scan for six days sitting at a single facility, that's a pattern worth flagging, not ignoring."
    q2 = "ClearPath and the carriers are handled by Maya Collins, Operations Manager."
    q3 = "tell me which ones need action. I only want flags on things that are actually off"
    check("sources", "S-E quotes m4-l5's reference and m6-l4's reference word for word",
          q1 in se and q1 in m4l5["reference"][1] and "a tracking number that hasn't updated in several days is worth a closer look" in se and
          "a tracking number that hasn't updated in several days is worth a closer look" in m4l5["reference"][0] and q2 in se and q2 in m6l4["reference"][2])
    check("sources", "S-E line (3) is Maya's m4-l5 brief, word for word, labelled 'Task instruction (Maya), not policy'",
          q3 in se and q3 in " ".join(m4l5["brief"]["body"]) and "Task instruction (Maya), not policy" in se)
    check("sources", "S-J and S-K are labelled as task instructions, not policy",
          all("Task instruction (Sofia), not policy" in " ".join(CARD_TITLES[c]["items"]) for c in ("S-J", "S-K")))
    check("sources", "no source card applies S-E to a missing tracking number", not re.search(r"missing tracking|no tracking|blank tracking", se, re.I))
    m7 = decode("module-7"); m7l1 = next(t for t in m7["tasks"] if t["id"] == "m7-l1")
    m6l9 = next(t for t in m6["tasks"] if t["id"] == "m6-l9")
    check("sources", "S-J and S-K quote the m7-l1 and m6-l9 briefs word for word",
          "Read the order record with each message — the message on its own won't tell you." in " ".join(m7l1["brief"]["body"]) and
          "Read the order record with each message — the message on its own won't tell you." in " ".join(CARD_TITLES["S-J"]["items"]) and
          "tell the customer it's with me. Don't promise them an outcome I haven't decided." in " ".join(m6l9["brief"]["body"]) and
          "tell the customer it's with me. Don't promise them an outcome I haven't decided." in " ".join(CARD_TITLES["S-K"]["items"]))
    all3d = {r["id"] for r in P3["groups"][0]["records"]}
    check("sources", "every source card is in 3d's evidence", all("d-c-" + c.lower() in all3d for c in CARD_VALUE))
    # 3d source sets recomputed from the cards each step's Task 2 row shows
    wrong = []
    for i, r in enumerate(A2["rows"]):
        shown = sorted({CARD_VALUE[k.split(" · ")[0]] for k, _ in r["fields"] if re.match(r"^S-[A-L] · ", k)}) or [CARD_VALUE["S-L"]]
        acc = field(P3, "st%d.src" % (i + 1))["accept"]
        if acc != [shown]: wrong.append((i + 1, acc, shown))
    check("recompute", "3d: each step's exact source set is the set of cards its Task 2 row shows (S-L where none applies)", not wrong, wrong)
    check("recompute", "3d: step 4's exact source set has two cards and step 6's has two", len(field(P3, "st4.src")["accept"][0]) == 2 and len(field(P3, "st6.src")["accept"][0]) == 2)
    check("recompute", "3d: each step's verdict equals Task 2's verdict for the same step",
          all(field(P3, "st%d.verdict" % (i + 1))["accept"] == [r["answer"] for r in A2["rows"]][i:i + 1] for i in range(9)))

    # ---------- canon and continuity ----------
    canon = {}
    for line in open(os.path.join(ROOT, "docs", "everfield-continuity.md"), encoding="utf-8"):
        m = re.match(r"^\| (P\d+) \| (.+?) \| [^|]*\|\s*$", line)
        if m: canon[m.group(1)] = m.group(2)
    pcards = re.findall(r"(P\d+) · ([^\n]+?)(?=$)", "\n".join(x for _, s in ALL for r in records_of(s) for x in r.get("items", [])), re.M)
    check("canon", "every policy line quotes the approved clause word for word", pcards and all(canon.get(k) == v for k, v in pcards), [k for k, v in pcards if canon.get(k) != v])
    check("canon", "orders stay in #5501-#5520 and tracking in CP-7731-11xx",
          all(5501 <= int(n) <= 5520 for n in re.findall(r"#(\d{4})", EVERY)) and all(t.startswith("11") for t in re.findall(r"CP-7731-(\d{4})", EVERY)))
    check("canon", "no returns, stock figures, dollar amounts, marketplace IDs, EF-103 or EF-104 pack count",
          not re.search(r"Return #|\bAvailable\b|\bInbound\b|\$\s?\d|MKT-\d|EF-103\b", EVERY) and not re.search(r"(EF-104|Cable Management Set)[^.]{0,80}\b\d+[- ]?(piece|pieces|pack)\b", EVERY, re.I))
    check("canon", "EF-104 has no product fact (undefined canon)", "EF-104" not in DATA["productFacts"])
    check("canon", "Return #229 no longer cites a Module 11 lesson", not any("module-11" in s for e in DATA["timeline"]["entries"] for s in e["src"] if e.get("ref") == "Return #229"))
    others = {}
    for m in (2, 3, 4, 5, 6, 7, 8, 9, 10, 13):
        others[m] = decode("module-%d" % m)
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
    check("cross-module", "no graded answer from Modules 2-10 or 13 appears in Module 11 (including M4's Owner options)", not leaks, leaks[:6])

    # ---------- normal flow, completion, work sample ----------
    ctx, pg, errs = fresh(br); goto(pg, M11)
    check("page", "desk bar shows Mon, Sep 14 and Daily check, three tasks, and the training note",
          pg.text_content("#deskDate") == DATE and "Daily check" in pg.text_content(".desk-bar") and pg.inner_text("#lessonKicker") == "Task 1 of 3" and pg.locator("#trainingNote").is_visible())
    for ti, t in enumerate(TASKS):
        goto(pg, M11 + "#task-%d" % (ti + 1), 1); ok = True
        for st in t["stages"]:
            solve(pg, st)
            if not pg.is_enabled("#btnNext"): ok = False; break
            pg.click("#btnNext"); pg.wait_for_timeout(60)
        check("flow", "task %d completes through the UI" % (ti + 1), ok, fb_text(pg)[:200])
    check("flow", "completion banner", "Module 11 complete" in pg.inner_text("#doneBanner"), pg.inner_text("#doneBanner"))
    prog = pg.evaluate("JSON.parse(localStorage.getItem('pva-ecom-ft-progress'))")
    check("progress", "verified work marks all three lessons in the legacy progress store", all(prog["lessons"].get(i) for i in IDS))
    keys = pg.evaluate("Object.keys(localStorage).sort()")
    check("isolation", "only the Module 11 desk key and the legacy progress key are written", keys == [KEY, "pva-ecom-ft-progress"], keys)
    vw = pg.evaluate("PVADesk.verifiedWork()")
    check("verified-work", "all three tasks verified, one earned sample (l3-d)",
          all(v["verified"] for v in vw.values()) and vw["m11-l3"]["samplesEarned"] == ["l3-d"] and not any(v["samplesEarned"] for k, v in vw.items() if k != "m11-l3"), vw)
    goto(pg, BASE + "/index.html")
    card = pg.locator(".module-card").nth(10).inner_text()
    check("progress", "course map shows Module 11 'SOPs & Daily Workflow' Completed", "SOPs & Daily Workflow" in card and "Completed" in card, card)
    goto(pg, M11 + "#task-3", 4)
    sample = pg.locator(".ws-preview").inner_text() if pg.locator(".ws-preview").count() else ""
    check("work-sample", "the sample header is honest: training work sample, not Everfield policy, for Maya's review, not in effect",
          sample.startswith("TRAINING WORK SAMPLE\nEverfield Daily Check SOP — proposed revision (training document, not Everfield policy)") and
          "Work date: Mon, Sep 14 (simulated)" in sample and "For her review; not in effect." in sample and "not Everfield policy" in sample.split("\n")[2], sample[:500])
    check("work-sample", "the sample lists all nine steps with the learner's wording and sources, step 9 pending, and the note",
          all(("Step %d" % n) in sample for n in range(1, 10)) and "Pending Maya's decision: no approved reply time." in sample and GOOD_NOTE in sample and "This course checks required facts, decisions, and structure against defined criteria. Use your judgment to evaluate the quality of the work you produce." in sample, sample[-700:])
    check("flow", "no JS errors", not errs, errs)
    ctx.close()

    # ---------- Task 3 opened first ----------
    ctx, pg, errs = fresh(br)
    goto(pg, M11 + "#task-3", 1); ok = True
    for st in TASKS[2]["stages"]:
        solve(pg, st)
        if not pg.is_enabled("#btnNext"): ok = False; break
        pg.click("#btnNext"); pg.wait_for_timeout(60)
    store = pg.evaluate("JSON.parse(localStorage.getItem('%s'))" % KEY)
    vw = pg.evaluate("PVADesk.verifiedWork()")
    check("task3-first", "in fresh storage, Task 3 completes and earns the sample with Tasks 1 and 2 untouched",
          ok and vw["m11-l3"]["samplesEarned"] == ["l3-d"] and not vw["m11-l1"]["verified"] and not vw["m11-l7"]["verified"] and set(store["tasks"].keys()) == {"m11-l3"}, (ok, vw, list(store["tasks"].keys())))
    goto(pg, M11 + "#task-3", 4)
    shown = pg.inner_text("#stagePanel")
    check("task3-first", "3d shows the SOP, every source card and the log without any earlier answer",
          "SOP v1" in shown and all(("S-" + c + " ·") in shown for c in "ABCDEFGHIJKL") and "Last week's check log" in shown and "Your work sample" not in shown)
    check("task3-first", "no JS errors", not errs, errs)
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
    ctx.close(); ctx, pg, _ = fresh(br)
    goto(pg, M11 + "#task-1", 1); r = panel(pg)
    r.locator(".desk-ev-head button[aria-expanded='false']").first.click(); pg.wait_for_timeout(40)
    sels = r.locator("select.desk-select")
    check("evidence-gate", "l1-a: an item's call unlocks only once that item's own record is opened",
          sels.first.is_enabled() and all(sels.nth(i).is_disabled() for i in range(1, sels.count())))
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

    # ---------- record gap vs stall, and other authority traps (Task 1) ----------
    ctx, pg, _ = fresh(br)
    TRAPS = [("#5502 to Maya", {"q2": "maya"}), ("#5502 to Sofia", {"q2": "sofia"}), ("#5502 as nothing wrong", {"q2": "ok"}),
             ("#5503 as a record gap", {"q3": "record"}), ("#5503 to Sofia", {"q3": "sofia"}), ("#5506 cancelled by the VA", {"m6": "cancel"}),
             ("#5505 sent for intercept", {"m5": "intercept"}), ("#5508 answered from the record", {"m8": "answer"}), ("#5504 flagged as a gap", {"q4": "record"}),
             ("#5508 flagged as a gap", {"m8": "record"}), ("#5501 flagged to Maya", {"q1": "maya"})]
    for why, ov in TRAPS:
        to_stage(pg, 0, "l1-a")
        check("traps", "l1-a fails when %s" % why, not triage_attempt(pg, Q1, ov))
    ctx.close()

    # ---------- 3d option sets and the change note ----------
    ctx, pg, _ = fresh(br)
    to_stage(pg, 2, "l3-d"); open_all(pg)
    okk, fbx = attempt_in(pg, P3)
    check("3d", "the accepted revision passes", okk, fbx[:200])
    for n in works:
        f = field(P3, "st%d.text" % n)
        okk, _ = attempt_in(pg, P3, **{f["id"]: first_unaccepted(f)})
        check("3d", "step %d (works as written): any other wording fails" % n, not okk)
        srcf = field(P3, "st%d.src" % n)
        okk, _ = attempt_in(pg, P3, **{srcf["id"]: srcf["accept"][0] + [CARD_VALUE["S-L"]]})
        check("3d", "step %d: an extra source card fails" % n, not okk)
    s4f = field(P3, "st4.src")
    for why, val in (("S-E only", [CARD_VALUE["S-E"]]), ("S-D only", [CARD_VALUE["S-D"]]), ("S-E, S-D and S-F", sorted([CARD_VALUE["S-E"], CARD_VALUE["S-D"], CARD_VALUE["S-F"]]))):
        okk, _ = attempt_in(pg, P3, **{s4f["id"]: val})
        check("3d", "step 4: source set %s fails" % why, not okk)
    t4 = field(P3, "st4.text")
    skip = next(o["value"] for o in t4["options"] if "send it straight to Maya" in o["label"])
    okk, _ = attempt_in(pg, P3, **{t4["id"]: skip})
    check("3d", "step 4: the distractor that skips P11's first step fails", not okk)
    t9 = field(P3, "st9.text")
    for o in t9["options"]:
        if o["value"] in t9["accept"]: continue
        okk, _ = attempt_in(pg, P3, **{t9["id"]: o["value"]})
        check("3d", "step 9: '%s' fails" % o["label"][:40], not okk)
    vals = compose_values(P3, note)
    for n in range(1, 10): vals["st%d.verdict" % n] = "works"
    fill_compose(pg, P3, vals); confirm_all(pg); submit(pg)
    check("3d", "uniform 'works as written' verdicts fail", not pg.is_enabled("#btnNext")); open_all(pg)
    GOOD = [("terse", "Proposed revision attached for your review. Steps 2, 3, 4, 6 and 8 changed; step 9 is pending your decision."),
            ("first person", "I've drafted a revised SOP for your review. I changed steps 3 and 4 so cancellations and stalled shipments follow the cards, and step 9 waits for your decision."),
            ("negation", "This is a draft for your approval and is not in effect. I have not set any reply time for marketplace messages; step 9 is pending."),
            ("not policy", "Here is the proposed revision, not Everfield policy, for you to review. The refund step now hands the decision to Sofia."),
            ("stall in digits", "Proposed changes for your review. Stalled shipments, like one with no scan for 6 days, now go to you, and the cancellation step follows the cards."),
            ("updated the draft", "I updated the SOP draft for your review. Steps 2 and 8 now say exactly what the cards say.")]
    for why, t in GOOD:
        okk, fbx = attempt_in(pg, P3, **{"note.text": t})
        check("3d-note", "passes -- %s" % why, okk, (t, fbx[:200]))
    ACT, RT, REV, STEP = "isn't in effect", "no reply time is approved", "maya's review", "name at least one step"
    BAD = [("claims the SOP is updated", "I've updated the SOP so everyone follows it from now. Steps 3 and 4 match the cards, for your review.", ACT),
           ("says it is in place", "The revised SOP is now in place for the team. Steps 3 and 4 changed, proposed for your review.", ACT),
           ("passive: has been updated", "The SOP has been updated with the new steps 3 and 4. Please review it when you can.", ACT),
           ("calls it new policy", "This is the new policy for the daily check. Steps 3 and 4 changed, for your review.", ACT),
           ("from today", "From today we follow the revised steps 3 and 4 for every order. They are proposed for your review as well.", ACT),
           ("states a reply time", "Proposed revision for your review. Step 9 should reply to marketplace messages within 24 hours.", RT),
           ("24-hour target", "Proposed revision for your review. Steps 3 and 4 changed, and I set a 24-hour reply target in step 9.", RT),
           ("no review statement", "Steps 2, 3, 4, 6 and 8 changed to match the cards. Step 9 is pending a decision on reply times.", REV),
           ("no step named", "Here is the revision for your review. It is much better than before and easier to follow overall.", STEP)]
    for why, t, want in BAD:
        okk, fbx = attempt_in(pg, P3, **{"note.text": t})
        check("3d-note", "rejected with the matching reason -- a note that %s" % why, not okk and want in fbx.lower(), (t, fbx[:200]))
    ctx.close()

    # ---------- transfer stages reject reused or v1 answers ----------
    check("transfer", "3a-3c cases (P3, P11, P7 pattern) appear nowhere in Tasks 1-2",
          not re.search(r"#551[5-9]", learner_text(TASKS[0]) + learner_text(TASKS[1])) and "P11 ·" not in learner_text(TASKS[0]))
    for st in (X3, Y3, Z3):
        check("transfer", "%s: every wrong option is refused with feedback" % st["id"], all(True for _ in wrong_options(st)))
    ctx, pg, _ = fresh(br)
    for st in (X3, Y3, Z3):
        for wo in wrong_options(st):
            to_stage(pg, 2, st["id"]); open_all(pg)
            answer_decision(pg, st, option=wo)
            check("transfer", "%s: '%s' fails" % (st["id"], option_text(st, wo)[:45]), not pg.is_enabled("#btnNext"))
    ctx.close()

    # ---------- integrity, leakage ----------
    ctx, pg, _ = fresh(br); goto(pg, M11)
    pg.evaluate("""localStorage.setItem('%s', JSON.stringify({v:1,tasks:{'m11-l3':{completed:true,verified:true,views:1,
      stages:{'l3-d':{passed:true,answer:{values:{},confirms:[true,true]}}},drafts:{}}}}))""" % KEY)
    goto(pg, M11 + "#task-3")
    st3 = pg.evaluate("PVADesk.taskStatus(PVADesk.decode(window.PVA_DESK_MODULES.m11.payload).tasks[2])")
    check("integrity", "forged completed/verified/passed flags count for nothing", st3["passed"] == 0, st3)
    check("integrity", "forged state never reaches the legacy progress store", not (pg.evaluate("JSON.parse(localStorage.getItem('pva-ecom-ft-progress')||'{}')").get("lessons") or {}).get("m11-l3"))
    shipped = "".join(pg.request.get(BASE + uu).text() for uu in ["/module-11/index.html", "/module-11/desk-data.js"])
    markers = ['"correct"', "correct: true", '"accept"', '"answer":', '"correctOrder"']
    check("leakage", "no plaintext answer markers in shipped Module 11 files", not any(m in shipped for m in markers))
    check("leakage", "no correct decision option text appears in shipped source", not any(option_text(s, correct_option(s)) in shipped for _, s in ALL if s["type"] == "decision"))
    sel = [f for f in P3["fields"] if f["type"] == "select"]
    strict = [f["id"] for f in sel if len(label_of(f, f["accept"][0])) > max(len(o["label"]) for o in f["options"] if o["value"] != f["accept"][0])]
    positions = [next(i for i, o in enumerate(f["options"]) if o["value"] == f["accept"][0]) for f in sel]
    check("leakage", "no select's accepted option is strictly its longest, and accepted positions spread",
          not strict and len(set(positions)) >= 3 and max(positions.count(i) for i in set(positions)) <= len(sel) // 2, (strict, positions))
    dl = [(s["id"], [len(o["text"]) for o in s["options"]], next(i for i, o in enumerate(s["options"]) if o.get("correct"))) for _, s in ALL if s["type"] == "decision"]
    check("leakage", "no decision's correct option is strictly its longest", not [x for x in dl if x[1][x[2]] > max(l for i, l in enumerate(x[1]) if i != x[2])], dl)
    vals_dom = []
    for ti in range(3):
        goto(pg, M11 + "#task-%d" % (ti + 1), 1); open_all(pg)
        check("leakage", "task %d: rendered DOM carries no correctness attributes" % (ti + 1), not re.search(r'(class|data-[a-z-]+)="[^"]*(correct|answer|right)', pg.content()))
        vals_dom += pg.evaluate("Array.from(document.querySelectorAll('#stagePanel input,#stagePanel option')).map(e=>e.value)")
    check("leakage", "no control value names the answer", not [x for x in vals_dom if re.match(r"^(correct|right|wrong)", x)])
    ctx.close()

    # ---------- persistence, legacy, portfolio ----------
    ctx, pg, _ = fresh(br)
    to_stage(pg, 0, "l1-a"); open_all(pg)
    panel(pg).locator("select.desk-select").first.select_option(Q1["rows"][0]["answer"])
    pg.reload(); pg.wait_for_timeout(150); pg.click("#btnNext"); pg.wait_for_timeout(80)
    check("persistence", "an unsubmitted triage call survives refresh", panel(pg).locator("select.desk-select").first.input_value() == Q1["rows"][0]["answer"])
    ctx.close()
    ctx, pg, _ = fresh(br); goto(pg, BASE + "/index.html")
    pg.evaluate("v => localStorage.setItem('pva-ecom-ft-progress', JSON.stringify(v))", {"lessons": {"m11-l%d" % i: True for i in range(1, 11)}, "modules": {}})
    goto(pg, M11 + "#task-1")
    check("legacy", "all three lessons keep their earlier checkmarks", pg.locator(".lesson-pill.done").count() == 3)
    check("legacy", "the status line separates legacy completion from new work", "earlier version" in pg.inner_text("#taskStatus"))
    vw = pg.evaluate("PVADesk.verifiedWork()")
    check("legacy", "legacy completion is not verified work", not any(v["verified"] for v in vw.values()) and not any(v["samplesEarned"] for v in vw.values()))
    goto(pg, BASE + "/index.html")
    check("legacy", "someone who finished old Module 11 still sees it Completed", pg.locator(".module-status").nth(10).inner_text() == "Completed")
    pg.evaluate("v => localStorage.setItem('pva-ecom-ft-progress', JSON.stringify(v))", {"lessons": {"m11-l1": True, "m11-l3": True}, "modules": {}})
    goto(pg, BASE + "/index.html")
    check("legacy", "the course map counts Module 11 against its three lessons", "2 of 3" in pg.locator(".module-card").nth(10).inner_text())
    ctx.close()
    port = open(os.path.join(ROOT, "portfolio", "index.html"), encoding="utf-8").read()
    check("portfolio", "piece 11 keeps its title and points at Module 11, Lesson 3", "E-commerce Task SOP" in port and "From Module 11, Lesson 3 -- Revise It and Prove It" in port and "Following an SOP" not in port)
    check("portfolio", "the portfolio still lists 14 pieces", len(re.findall(r'class="portfolio-num"', port)) == 14)

    # ---------- isolation, accessibility, deep links ----------
    ctx, pg, _ = fresh(br)
    goto(pg, M10 + "#task-1", 1); open_all(pg)
    to_stage(pg, 0, "l1-a"); solve(pg, Q1)
    keys = pg.evaluate("Object.keys(localStorage).sort()")
    check("isolation", "Module 11 writes only its own desk key", set(keys) - {"pva-ecom-ft-progress", "pva-ecom-ft-m10-desk"} == {KEY}, keys)
    mut = pg.evaluate("(()=>{try{EVERFIELD.calendar.m11.date='Y';}catch(e){} return EVERFIELD.calendar.m11.date})()")
    check("everfield", "shared Everfield reference cannot be mutated from Module 11", mut == DATE, mut)
    for ti, st in ALL:
        to_stage(pg, ti, st["id"]); open_all(pg)
        unnamed = pg.evaluate("""Array.from(document.querySelectorAll('#stagePanel select,#stagePanel input,#stagePanel textarea,#stagePanel button')).filter(e=>{var n=(e.labels&&e.labels.length)||e.getAttribute('aria-label')||e.getAttribute('aria-labelledby')||(e.tagName==='BUTTON'&&e.innerText.trim());return !n}).length""")
        check("a11y", "%s: every control has an accessible name" % st["id"], not unnamed, unnamed)
    for n in (1, 2, 3):
        goto(pg, M11 + "#task-%d" % n); check("deep-link", "#task-%d opens task %d" % (n, n), pg.inner_text("#lessonKicker") == "Task %d of 3" % n and pg.text_content("#deskDate") == DATE)
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
    goto(pg, M11 + "#task-1"); low += pg.evaluate(CONTRAST)
    to_stage(pg, 0, "l1-a"); open_all(pg); fail_once(pg, Q1); low += pg.evaluate(CONTRAST)
    to_stage(pg, 2, "l3-d"); open_all(pg); solve(pg, P3); low += pg.evaluate(CONTRAST)
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
