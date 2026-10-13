"""Certificate of Completion + Progress (Export / Restore / Clear) suite (browser).

Run from the repo root with a static server on :8765:
    python3 tests/e2e/test_certificate.py
Eligibility is tested against stand-in desk files (one small decision task per module, encoded
with the real codec into a temporary folder and served through Playwright routes), so every
combination can be set up exactly: all verified, one unverified, forged flags, legacy checkmarks,
Module 1 still legacy, Module 1 converted. One integration case runs the real Module 14 capstone.
Nothing is written to the repository."""
import os, sys, re, json, subprocess, tempfile
from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from desk_helpers import *  # noqa

CERT = BASE + "/certificate/index.html"
PROG = BASE + "/progress/index.html"
REAL_REQ = open(os.path.join(ROOT, "certificate", "requirements.js"), encoding="utf-8").read()
OPEN_REQ = REAL_REQ.replace("open: false,", "open: true,")
REMINDER = ["A Gentle Reminder Before You Save",
 "You've put time and effort into your learning journey. As you complete this course, take a moment to reflect on what you've learned and the skills you've practiced.",
 "Your certificate records your completion of the course requirements. The real value, however, comes from the knowledge and skills you can carry into your work.",
 "Please make sure that your completed activities reflect your own effort and that you've approached the exercises with honesty and a willingness to learn.",
 "Keep practicing, keep improving, and let your skills speak for themselves.",
 "Thank you for being part of PVA Academy!"]
ACK = "I've taken a moment to reflect on my learning and the work I've completed."
results = []


def check(area, name, cond, detail=""):
    results.append((area, name, bool(cond), str(detail)))
    print(("PASS " if cond else "FAIL ") + "[" + area + "] " + name + ((" -- " + str(detail)[:220]) if detail and not cond else ""))


# ---------- stand-in desks: one decision per module, real codec ----------
TMP = tempfile.mkdtemp(prefix="cert-fixtures-")
FIX = {}
for n in range(1, 15):
    mid = "m%d" % n
    src = {"config": {"moduleId": mid, "salt": "fixture-%s" % mid, "key": "FixtureKey", "legacyPill": "check"}, "version": 1, "module": mid,
           "tasks": [{"id": mid + "-fx1", "title": "Fixture task", "objective": "Fixture objective.", "brief": {"from": "maya", "subject": "Fixture", "body": ["Fixture."]},
                      "stages": [{"id": "fx-a", "label": "Fixture", "type": "decision", "cta": "Open", "records": [{"id": "r", "title": "R", "fields": [["A", "B"]]}],
                                  "findingsPrompt": "Tick.", "findings": [{"id": "a", "text": "Fixture true finding.", "miss": "Look.", "correct": True}, {"id": "b", "text": "Fixture false finding.", "wrong": "Check."}],
                                  "actionPrompt": "Do.", "options": [{"id": "o1", "text": "Right fixture action here.", "why": "Because.", "correct": True}, {"id": "o2", "text": "Wrong fixture action, longer text.", "why": "Re-check."}]}]}]}
    sp = os.path.join(TMP, mid + ".json"); out = os.path.join(TMP, mid + ".js")
    json.dump(src, open(sp, "w"))
    subprocess.run(["node", os.path.join(ROOT, "tools", "desk-codec.js"), "encode", sp, out], check=True, capture_output=True)
    FIX[n] = open(out, encoding="utf-8").read()
    os.remove(sp)


def store(n, good=True, forged=False):
    if forged:
        return {"v": 1, "tasks": {"m%d-fx1" % n: {"completed": True, "verified": True, "views": 1, "stages": {"fx-a": {"passed": True, "attempts": 1}}, "drafts": {}}}}
    return {"v": 1, "tasks": {"m%d-fx1" % n: {"views": 1, "stages": {"fx-a": {"attempts": 1, "answer": {"f": ["a"], "o": "o1" if good else "o2"}}}, "drafts": {}}}}


def serve(body):
    def h(route): route.fulfill(status=200, content_type="application/javascript", body=body)
    return h


def setup(pg, req=OPEN_REQ, fixtures=range(1, 15), real=()):
    """Route requirements.js and each module's desk file. Modules in `fixtures` get stand-ins;
    `real` keep the shipped file; any other module returns 404 (a legacy module has no desk file)."""
    pg.route("**/certificate/requirements.js", lambda r: r.fulfill(status=200, content_type="application/javascript", body=req))
    for n in range(1, 15):
        if n in real: continue
        if n in fixtures: pg.route("**/module-%d/desk-data.js" % n, serve(FIX[n]))
        else: pg.route("**/module-%d/desk-data.js" % n, lambda r: r.fulfill(status=404, body="not found"))


def put(pg, state):
    goto(pg, BASE + "/index.html")
    pg.evaluate("s => { localStorage.clear(); for (const k in s) localStorage.setItem(k, typeof s[k] === 'string' ? s[k] : JSON.stringify(s[k])); }", state)


def all_good(skip=()):
    return dict(("pva-ecom-ft-m%d-desk" % n, store(n)) for n in range(1, 15) if n not in skip)


def open_cert(pg):
    pg.goto(CERT); pg.wait_for_function("document.getElementById('reqStatus').textContent.indexOf('verified') !== -1", timeout=15000); pg.wait_for_timeout(100)


def row_state(pg, n):
    return pg.locator("#reqList li").nth(n - 1).locator(".st").inner_text()


def fresh(br, **kw):
    ctx = br.new_context(accept_downloads=True, **kw); pg = ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    return ctx, pg, errs


LEGACY_M1 = {"pva-ecom-ft-progress": {"lessons": dict(("m1-l%d" % i, True) for i in range(1, 8)), "modules": {}}}

with sync_playwright() as p:
    br = p.chromium.launch()

    # ---------- requirements file ----------
    check("requirements", "the shipped certificate is closed (open: false) until Module 1 is released", "open: false," in REAL_REQ and "open: true" not in REAL_REQ)
    req = json.loads(subprocess.run(["node", "-e", "global.window={};require('./certificate/requirements.js');process.stdout.write(JSON.stringify(window.PVA_ECOM_CERT))"], cwd=ROOT, capture_output=True, text=True).stdout)
    check("requirements", "every module 1-14 is required, Module 1 included", [m["n"] for m in req["modules"]] == list(range(1, 15)) and req["modules"][0]["id"] == "m1")
    check("requirements", "issuer signature is Kuya Lito, Probinsiyanong VA", req["signatureCaption"] == "Kuya Lito, Probinsiyanong VA")

    # ---------- closed: nothing can be issued, whatever the work ----------
    ctx, pg, errs = fresh(br); setup(pg, req=REAL_REQ); put(pg, all_good()); open_cert(pg)
    check("closed", "with every module verified but the certificate closed, there is no name field or Save button",
          pg.locator("#certNotOpen").count() == 1 and pg.locator("#certSave").count() == 0 and pg.locator("#certName").count() == 0)
    check("closed", "the closed notice says certificates open with the updated Module 1", "Module 1" in pg.inner_text("#certNotOpen"))
    check("closed", "no JS errors", not errs, errs); ctx.close()

    # ---------- Module 1 transition ----------
    ctx, pg, _ = fresh(br); setup(pg, fixtures=range(2, 15)); s = all_good(skip=(1,)); s.update(LEGACY_M1); put(pg, s); open_cert(pg)
    check("m1-transition", "open, Modules 2-14 verified, Module 1 still legacy (no desk file) with old checkmarks: locked",
          pg.locator("#certLocked").count() == 1 and pg.locator("#certSave").count() == 0 and row_state(pg, 1) == "Not available yet", pg.inner_text("#reqList")[:200])
    check("m1-transition", "Module 1's row says it will be required", "will be required" in pg.locator("#reqList li").nth(0).inner_text())
    ctx.close()
    ctx, pg, _ = fresh(br); setup(pg); s = all_good(skip=(1,)); s.update(LEGACY_M1); put(pg, s); open_cert(pg)
    check("m1-transition", "Module 1 converted but its desk work not done (old checkmarks only): locked, row 'Not yet'",
          pg.locator("#certLocked").count() == 1 and row_state(pg, 1) == "Not yet" and "earlier version" in pg.locator("#reqList li").nth(0).inner_text())
    put(pg, dict(list(s.items()) + [("pva-ecom-ft-m1-desk", store(1))])); open_cert(pg)
    check("m1-transition", "Module 1's desk work done: every row Verified and the form appears", pg.locator("#certSave").count() == 1 and all(row_state(pg, n) == "Verified" for n in range(1, 15)))
    ctx.close()

    # ---------- what never qualifies ----------
    for why, state in (("legacy checkmarks only", {"pva-ecom-ft-progress": {"lessons": dict(("m%d-l%d" % (m, i), True) for m in range(1, 15) for i in range(1, 11)), "modules": {}}}),
                       ("forged completed/verified/passed flags", dict(("pva-ecom-ft-m%d-desk" % n, store(n, forged=True)) for n in range(1, 15))),
                       ("one module with a wrong answer", dict(list(all_good().items()) + [("pva-ecom-ft-m7-desk", store(7, good=False))])),
                       ("one module missing", all_good(skip=(13,))),
                       ("nothing at all", {})):
        ctx, pg, _ = fresh(br); setup(pg); put(pg, state); open_cert(pg)
        check("eligibility", "locked with %s" % why, pg.locator("#certLocked").count() == 1 and pg.locator("#certSave").count() == 0)
        ctx.close()

    # ---------- the save flow ----------
    ctx, pg, errs = fresh(br); setup(pg); put(pg, all_good()); open_cert(pg)
    form = pg.locator("#certForm")
    order = pg.evaluate("""(()=>{const f=document.getElementById('certForm'); const kids=[...f.querySelectorAll('#certName,#certReminder,#certAck,#certSave')]; return kids.map(k=>k.id);})()""")
    check("save", "order: name, then the reminder, then the acknowledgment, then Save Certificate", order == ["certName", "certReminder", "certAck", "certSave"], order)
    rem = [x.strip() for x in pg.locator("#certReminder").inner_text().split("\n") if x.strip()]
    check("save", "the reminder is the approved text, word for word", rem == REMINDER, rem)
    ack = pg.locator("label.ack").inner_text().strip()
    check("save", "the acknowledgment is the approved line, word for word", ack == ACK, ack)
    nxt = pg.evaluate("document.getElementById('certAck').closest('label').nextElementSibling.id")
    check("save", "Save Certificate sits immediately after the acknowledgment", nxt == "certSave", nxt)
    check("save", "Save is disabled with no name and no acknowledgment", pg.is_disabled("#certSave"))
    pg.fill("#certName", "Ana Reyes"); check("save", "Save stays disabled with a name but no acknowledgment", pg.is_disabled("#certSave"))
    pg.fill("#certName", ""); pg.check("#certAck"); check("save", "Save stays disabled with the acknowledgment but no name", pg.is_disabled("#certSave"))
    pg.fill("#certName", "A"); check("save", "a one-letter name doesn't enable Save", pg.is_disabled("#certSave"))
    pg.fill("#certName", "   ");
    check("save", "a blank name doesn't enable Save", pg.is_disabled("#certSave"))
    pg.fill("#certName", "<b>Ana</b> & Reyes \"Jr\""); check("save", "name + acknowledgment enables Save", pg.is_enabled("#certSave"))
    pg.click("#certSave"); pg.wait_for_timeout(200)
    svg = pg.locator("#certificate svg")
    txt = " ".join(pg.locator("#certificate svg text").all_text_contents()) if svg.count() else ""
    check("certificate", "the certificate renders", svg.count() == 1)
    check("certificate", "it carries the name as typed (escaped, not markup), the course, issuer and date",
          "<b>Ana</b> & Reyes \"Jr\"" in txt and pg.locator("#certificate svg b").count() == 0 and "E-commerce VA — Beginner Foundations" in txt and "PVA Free Training" in txt and "Date completed" in txt, txt[:300])
    check("certificate", "signature 'Kuya Lito' and caption 'Kuya Lito, Probinsiyanong VA'", "Kuya Lito, Probinsiyanong VA" in txt and re.search(r"\bKuya Lito\b", txt))
    check("certificate", "states completion of lessons and practical requirements, with the 'not a credential' footer",
          "has completed the lessons and practical requirements of" in txt and "Not a professional license, a credential, or evidence of paid client work." in txt)
    check("certificate", "no certificate ID, QR code, verification link or accreditation claim",
          not re.search(r"\b(ID|No\.|Number|Code)\b|verif|QR|accredit|licensed|certified (professional|expert)", txt) and pg.locator("#certificate a, #certificate image, #certificate canvas").count() == 0)
    saved = pg.evaluate("JSON.parse(localStorage.getItem('pva-ecom-ft-certificate'))")
    check("certificate", "saved: name, date, acknowledgment, in this course's own key", saved and saved["acknowledged"] is True and saved["name"].startswith("<b>Ana") and saved.get("date"))
    with pg.expect_download() as dl: pg.click("text=Download (SVG)")
    path = dl.value.path(); svgtxt = open(path, encoding="utf-8").read()
    check("certificate", "Download (SVG) gives a standalone SVG with the escaped name", svgtxt.startswith("<svg") and "&lt;b&gt;Ana&lt;/b&gt; &amp; Reyes" in svgtxt and dl.value.suggested_filename.endswith(".svg"))
    check("certificate", "Print / Save as PDF is offered", pg.locator("text=Print / Save as PDF").count() == 1)
    open_cert(pg)
    check("certificate", "after a reload the saved certificate shows again", pg.locator("#certificate svg").count() == 1 and pg.locator("#certSave").count() == 0)
    pg.evaluate("localStorage.setItem('pva-ecom-ft-m9-desk', JSON.stringify(%s))" % json.dumps(store(9, good=False))); open_cert(pg)
    check("certificate", "if a module's stored answer no longer checks out, the certificate disappears and the page locks",
          pg.locator("#certificate svg").count() == 0 and pg.locator("#certLocked").count() == 1)
    check("certificate", "no JS errors", not errs, errs)
    ctx.close()
    ctx, pg, _ = fresh(br, viewport={"width": 360, "height": 800}); setup(pg); put(pg, all_good()); open_cert(pg)
    check("certificate", "at 360px: no sideways scroll on the certificate page", pg.evaluate("document.documentElement.scrollWidth - innerWidth") <= 1)
    pg.fill("#certName", "Ana Reyes"); pg.check("#certAck"); pg.click("#certSave"); pg.wait_for_timeout(150)
    check("certificate", "at 360px: the certificate fits the screen", pg.evaluate("document.documentElement.scrollWidth - innerWidth") <= 1 and pg.locator("#certificate svg").bounding_box()["width"] <= 360)
    ctx.close()

    # ---------- integration: the real capstone counts, only once it is done ----------
    ctx, pg, _ = fresh(br); setup(pg, fixtures=[n for n in range(1, 15) if n != 14], real=(14,)); put(pg, all_good(skip=(14,))); open_cert(pg)
    check("integration", "real Module 14 not done: locked, its row 'Not yet'", pg.locator("#certLocked").count() == 1 and row_state(pg, 14) == "Not yet")
    src14 = decode("module-14")
    TXT = {"note.text": "Order #5557's EF-102 labels arrived creased and torn, with photos. A refund or replacement is your decision, and the customer has been told it's with you. I gave Maya the three damage reports as a possible pattern.",
           "sum.text": "We shipped 9 orders and received 4 returns this week. #5567 still hasn't shipped and is with Maya, EF-104 is below its alert level, and a bulk buyer's price request is waiting for you.",
           "ov.text": "This portfolio shows my training work on Everfield Goods, a simulated company used in PVA Free Training. It covers product data, listings, orders, inventory, customer support and reporting. These are training work samples, not paid client work."}
    for ti, t in enumerate(src14["tasks"]):
        goto(pg, BASE + "/module-14/index.html#task-%d" % (ti + 1), 1)
        for st in t["stages"]:
            open_all(pg)
            if st["type"] == "decision": answer_decision(pg, st)
            elif st["type"] == "triage": answer_triage(pg, st)
            else:
                v = {}
                for f in st["fields"]:
                    if f["type"] == "text": v[f["id"]] = TXT[f["id"]]
                    elif "accept" in f: v[f["id"]] = list(f["accept"][0]) if f["type"] == "multi" else f["accept"][0]
                    elif f["type"] == "multi": v[f["id"]] = [o["value"] for o in f["options"][:3]]
                    else: v[f["id"]] = f["options"][0]["value"]
                fill_compose(pg, st, v); confirm_all(pg); submit(pg)
            pg.click("#btnNext"); pg.wait_for_timeout(60)
    open_cert(pg)
    check("integration", "real Module 14 done through the UI: its row Verified and the form appears", row_state(pg, 14) == "Verified" and pg.locator("#certSave").count() == 1)
    real14 = pg.evaluate("localStorage.getItem('pva-ecom-ft-m14-desk')")
    ctx.close()

    # ---------- progress: export / restore / clear ----------
    ctx, pg, _ = fresh(br); setup(pg); s = all_good(); s["pva-ecom-ft-progress"] = {"lessons": {"m2-l1": True}, "modules": {}}; s["pva-smm-ft-progress"] = {"keep": "me"}; s["pva-ecom-ft-certificate"] = {"name": "Ana", "date": "x", "acknowledged": True}
    put(pg, s); pg.goto(PROG); pg.wait_for_timeout(600)
    with pg.expect_download() as dl: pg.click("#btnExport")
    backup = json.load(open(dl.value.path(), encoding="utf-8"))
    check("progress", "export file name, format and version", re.match(r"E-commerce-VA-progress-backup-\d{4}-\d{2}-\d{2}\.json$", dl.value.suggested_filename) and backup["format"] == "pva-ecom-ft-progress-backup" and backup["version"] == 1)
    check("progress", "export holds only this course's keys (the other course's key is left out)",
          sorted(backup["keys"]) == sorted([k for k in s if k.startswith("pva-ecom-ft-")]) and "pva-smm-ft-progress" not in backup["keys"])
    check("progress", "warnings about devices, clearing data, private browsing and keeping a backup are shown",
          all(w in pg.inner_text(".warn") for w in ("devices", "Clearing", "Private", "backup")))
    ctx.close()

    def restore(pg, obj, confirm=True):
        f = os.path.join(TMP, "backup.json"); open(f, "w").write(obj if isinstance(obj, str) else json.dumps(obj))
        pg.set_input_files("#fileRestore", f); pg.wait_for_timeout(250)
        if confirm and pg.locator("#btnRestore").is_visible(): pg.click("#btnRestore"); pg.wait_for_timeout(300)
        return pg.inner_text("#restoreMsg")

    ctx, pg, _ = fresh(br); setup(pg); put(pg, {"pva-smm-ft-progress": {"keep": "me"}}); pg.goto(PROG); pg.wait_for_timeout(400)
    msg = restore(pg, backup)
    check("restore", "a valid backup restores in a fresh browser", "Restored" in msg and pg.evaluate("localStorage.getItem('pva-ecom-ft-m5-desk')") is not None, msg)
    check("restore", "restoring leaves other courses' keys alone", json.loads(pg.evaluate("localStorage.getItem('pva-smm-ft-progress')")) == {"keep": "me"})
    open_cert(pg)
    check("restore", "restored work is re-checked and counts: the certificate form appears", pg.locator("#certificate svg").count() == 1 or pg.locator("#certSave").count() == 1)
    ctx.close()

    tampered = json.loads(json.dumps(backup)); tampered["keys"]["pva-ecom-ft-m4-desk"] = json.dumps(store(4, good=False))
    forgedb = json.loads(json.dumps(backup)); forgedb["keys"] = dict(("pva-ecom-ft-m%d-desk" % n, json.dumps(store(n, forged=True))) for n in range(1, 15))
    for why, b in (("an edited answer", tampered), ("forged verified flags", forgedb)):
        ctx, pg, _ = fresh(br); setup(pg); put(pg, {}); pg.goto(PROG); pg.wait_for_timeout(400)
        msg = restore(pg, b); open_cert(pg)
        check("restore", "a backup with %s restores as text but earns nothing (locked)" % why, "Restored" in msg and pg.locator("#certLocked").count() == 1, msg)
        ctx.close()

    other = dict(backup, format="pva-smm-ft-progress-backup"); newer = dict(backup, version=2)
    unknown = json.loads(json.dumps(backup)); unknown["keys"]["pva-smm-ft-progress"] = "{}"
    for why, b, want in (("another PVA course's backup", other, "other PVA courses"), ("a non-JSON file", "not json at all", "isn't valid JSON"),
                         ("a newer version", newer, "newer version"), ("keys from outside this course", unknown, "don't belong"), ("a random JSON file", {"hello": 1}, "isn't a progress backup")):
        ctx, pg, _ = fresh(br); setup(pg); put(pg, {"pva-ecom-ft-m2-desk": store(2)}); pg.goto(PROG); pg.wait_for_timeout(400)
        before = pg.evaluate("JSON.stringify(Object.assign({}, localStorage))")
        msg = restore(pg, b)
        after = pg.evaluate("JSON.stringify(Object.assign({}, localStorage))")
        check("restore", "rejects %s and changes nothing" % why, want in msg and not pg.locator("#btnRestore").is_visible() and after == before, (msg, pg.locator("#btnRestore").is_visible(), before[:120], after[:120]))
        ctx.close()
    ctx, pg, _ = fresh(br); setup(pg); put(pg, {"pva-ecom-ft-m2-desk": store(2)}); pg.goto(PROG); pg.wait_for_timeout(400)
    restore(pg, backup, confirm=False); pg.click("#btnCancel"); pg.wait_for_timeout(100)
    check("restore", "Cancel leaves the browser's progress as it was", pg.evaluate("localStorage.getItem('pva-ecom-ft-m5-desk')") is None and "cancelled" in pg.inner_text("#restoreMsg"))
    ctx.close()

    if real14:
        ctx, pg, _ = fresh(br); setup(pg, fixtures=[n for n in range(1, 15) if n != 14], real=(14,)); put(pg, {}); pg.goto(PROG); pg.wait_for_timeout(400)
        b = json.loads(json.dumps(backup)); b["keys"]["pva-ecom-ft-m14-desk"] = real14
        restore(pg, b); open_cert(pg)
        check("restore", "the real capstone's work survives a backup and restore, and re-checks as Verified", row_state(pg, 14) == "Verified")
        ctx.close()

    ctx, pg, _ = fresh(br); setup(pg); s = all_good(); s["pva-smm-ft-progress"] = {"keep": "me"}; put(pg, s); pg.goto(PROG); pg.wait_for_timeout(400)
    pg.on("dialog", lambda d: d.accept()); pg.click("#btnClear"); pg.wait_for_timeout(200)
    left = pg.evaluate("Object.keys(localStorage)")
    check("clear", "Clear removes only this course's keys", left == ["pva-smm-ft-progress"], left)
    ctx.close()
    br.close()

fails = [r for r in results if not r[2]]
print("\n%d checks, %d failed" % (len(results), len(fails)))
sys.exit(1 if fails else 0)
