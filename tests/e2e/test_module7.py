"""Module 7 Work Desk regression + adversarial suite (browser), modelled on Module 4's.

Run from the repo root with a static server on :8765 (see tests/README.md):
    python3 tests/e2e/test_module7.py
Answers come from decoding the shipped content at run time (desk_helpers.decode)."""
import os, sys, re
from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from desk_helpers import *  # noqa
from m7_answers import m7_text

SRC = decode("module-7")
M7 = BASE + "/module-7/index.html"
M4 = BASE + "/module-4/index.html"
TASKS = SRC["tasks"]
N = len(TASKS)
ALL = [(ti, s) for ti, t in enumerate(TASKS) for s in t["stages"]]
KEY = "pva-ecom-ft-m7-desk"
results = []


def check(area, name, cond, detail=""):
    results.append((area, name, bool(cond), str(detail)))
    print(("PASS " if cond else "FAIL ") + "[" + area + "] " + name + ((" -- " + str(detail)[:200]) if detail and not cond else ""))


def solve(pg, st):
    open_all(pg)
    if st["type"] == "decision": answer_decision(pg, st)
    elif st["type"] == "triage": answer_triage(pg, st)
    elif st["type"] == "sequence": answer_sequence(pg, st)
    else:
        fill_compose(pg, st, compose_values(st, m7_text)); confirm_all(pg); submit(pg)


def fail_once(pg, st):
    open_all(pg)
    if st["type"] == "decision":
        cf = correct_findings(st)
        answer_decision(pg, st, findings=cf[1:] + distractors(st)[:1], option=(wrong_options(st) or [None])[0])
    elif st["type"] == "triage": answer_triage(pg, st, wrong=True)
    else:
        vals = compose_values(st, m7_text)
        f = next(x for x in st["fields"] if x["type"] == "select")
        vals[f["id"]] = first_unaccepted(f)
        fill_compose(pg, st, vals); confirm_all(pg); submit(pg)


def to_stage(pg, ti, sid):
    goto(pg, M7 + "#task-%d" % (ti + 1), 1)
    for s in TASKS[ti]["stages"]:
        if s["id"] == sid: return
        if not pg.is_enabled("#btnNext"):
            solve(pg, s)
        pg.click("#btnNext"); pg.wait_for_timeout(60)


def fresh(br, **kw):
    ctx = br.new_context(**kw); pg = ctx.new_page()
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    return ctx, pg, errs


with sync_playwright() as p:
    br = p.chromium.launch()

    # ---------- structure: the approved design ----------
    check("design", "10 tasks with the original lesson ids", [t["id"] for t in TASKS] == ["m7-l%d" % i for i in range(1, 11)])
    kinds = {t["id"]: [s["type"] for s in t["stages"]] for t in TASKS}
    check("design", "stage types match the conversion map", kinds == {
        "m7-l1": ["triage"], "m7-l2": ["decision", "decision"], "m7-l3": ["triage"], "m7-l4": ["decision", "decision"],
        "m7-l5": ["triage"], "m7-l6": ["decision", "decision"], "m7-l7": ["decision", "decision"], "m7-l8": ["decision", "decision"],
        "m7-l9": ["triage", "decision"], "m7-l10": ["compose"]}, kinds)
    check("design", "only l10 is a portfolio task", [t["id"] for t in TASKS if t.get("portfolio")] == ["m7-l10"])
    every = " ".join(str(v) for v in [SRC])
    check("design", "no colour or size variant is implied anywhere (EF-105 resolution)", not re.search(r"colou?r|size variant", every, re.I))
    pol = [r for _, s in ALL for r in s.get("records", []) if r.get("kind") == "reference"]
    check("design", "decision stages carry an open policy card", len(pol) >= 10 and all(r["id"] == "policy" for r in pol), len(pol))

    # ---------- normal flow, completion, work sample ----------
    ctx, pg, errs = fresh(br); goto(pg, M7)
    for ti, t in enumerate(TASKS):
        goto(pg, M7 + "#task-%d" % (ti + 1), 1); ok = True
        for st in t["stages"]:
            solve(pg, st)
            if not pg.is_enabled("#btnNext"): ok = False; break
            pg.click("#btnNext"); pg.wait_for_timeout(60)
        check("flow", "task %d completes through the UI" % (ti + 1), ok)
    prog = pg.evaluate("JSON.parse(localStorage.getItem('pva-ecom-ft-progress'))")
    check("progress", "verified work marks all 10 lessons in the legacy progress store", all(prog["lessons"].get("m7-l%d" % i) for i in range(1, 11)))
    check("flow", "completion banner", "Module 7 complete" in pg.inner_text("#doneBanner"))
    keys = pg.evaluate("Object.keys(localStorage).sort()")
    check("isolation", "only the Module 7 desk key and the legacy progress key are written", keys == [KEY, "pva-ecom-ft-progress"], keys)
    vw = pg.evaluate("PVADesk.verifiedWork()")
    check("verified-work", "verifiedWork() reports all 10 tasks verified and the one earned sample",
          all(v["verified"] for v in vw.values()) and vw["m7-l10"]["samplesEarned"] == ["l10-log"] and
          not any(v["samplesEarned"] for k, v in vw.items() if k != "m7-l10"), vw)
    goto(pg, BASE + "/index.html")
    check("progress", "course map shows Module 7 Completed", "Completed" in pg.locator(".module-card").nth(6).inner_text())
    goto(pg, M7 + "#task-10", 1)
    ev = pg.locator(".ws-preview").inner_text() if pg.locator(".ws-preview").count() else ""
    check("work-sample", "Exception Resolution Log survives reload with an honest training header",
          ev.startswith("TRAINING WORK SAMPLE\nException Resolution Log") and "fictional company" in ev and
          "Work date: Thu, Sep 17 (simulated)" in ev and "Maya Collins" in ev and "human review" in ev, ev[:300])
    check("work-sample", "the sample covers both investigated cases", "#5437" in ev and "#5440" in ev)
    check("flow", "no JS errors", not errs, errs)
    ctx.close()

    # ---------- evidence gate (every stage) ----------
    ctx, pg, _ = fresh(br)
    for ti, st in ALL:
        to_stage(pg, ti, st["id"]); r = panel(pg)
        if st["type"] == "triage":
            gated = all(s.is_disabled() for s in r.locator("select.desk-select").all())
        elif st["type"] == "compose":
            gated = r.locator("section.desk-group select").first.is_disabled() and all(c.is_disabled() for c in r.locator(".desk-selfcheck input").all())
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
        fb = r.locator(".desk-fb").last.inner_text() if r.locator(".desk-fb").count() else ""
        check("feedback", "%s: wrong attempt gets explanatory feedback, next stays locked" % st["id"],
              len(fb) > 60 and not pg.is_enabled("#btnNext") and r.locator(".desk-pause").count() == 0, fb[:120])
        if st["type"] == "decision":
            leaks = [finding_text(st, f) for f in correct_findings(st) if finding_text(st, f) in fb]
            co = option_text(st, correct_option(st))
            if co in fb: leaks.append(co)
            check("feedback-safety", "%s: feedback reveals no correct finding or option" % st["id"], not leaks, leaks)
        retry = r.get_by_role("button", name="Reconsider and try again")
        if retry.count(): retry.click(); pg.wait_for_timeout(30)
        fail_once(pg, st)
        paused = r.locator(".desk-pause").count() == 1 and r.locator(".desk-evidence-card.is-recheck").count() >= 1
        blocked = (r.get_by_role("button", name="Reconsider and try again").is_disabled() if st["type"] == "decision"
                   else (r.locator(".desk-actions button").first.is_disabled() if st["type"] == "compose" else
                         any(s.is_disabled() for s in r.locator("select.desk-select").all())))
        check("retry", "%s: second miss pauses and blocks the next attempt until evidence is re-opened" % st["id"], paused and blocked)
        open_all(pg); pg.wait_for_timeout(30)
        retry = r.get_by_role("button", name="Reconsider and try again")
        if retry.count():
            check("retry", "%s: re-opening evidence re-enables retry" % st["id"], retry.is_enabled())
            retry.click(); pg.wait_for_timeout(30)
        solve(pg, st)
        check("retry", "%s: corrected attempt passes with no attempt limit" % st["id"], pg.is_enabled("#btnNext"))
    ctx.close()

    # ---------- transfer and anti-shortcut ----------
    ctx, pg, _ = fresh(br)
    for ti, st in ALL:
        if st["type"] != "decision": continue
        to_stage(pg, ti, st["id"]); open_all(pg)
        answer_decision(pg, st, findings=correct_findings(st)[:-1])
        check("transfer", "%s: right action without the full reading of the evidence fails" % st["id"], not pg.is_enabled("#btnNext"))
    for ti, st in ALL:
        if st["type"] != "decision" or "copy" not in [o["id"] for o in st["options"]]: continue
        to_stage(pg, ti, st["id"]); open_all(pg)
        answer_decision(pg, st, option="copy")
        fb = panel(pg).locator(".desk-fb").last.inner_text()
        check("transfer", "%s: reusing the first case's answer fails and says so" % st["id"], not pg.is_enabled("#btnNext") and "different" in fb, fb[:120])
    ctx.close()

    # ---------- shortcut attempts, derived completion, work samples ----------
    ctx, pg, _ = fresh(br); goto(pg, M7)
    pg.evaluate("""localStorage.setItem('%s', JSON.stringify({v:1,tasks:{'m7-l10':{completed:true,verified:true,views:1,
      stages:{'l10-log':{passed:true,answer:{values:{},confirms:[true,true]}}},drafts:{'l10-log:v':{'c1.note':'x'}}}}}))""" % KEY)
    goto(pg, M7 + "#task-10")
    st10 = pg.evaluate("PVADesk.taskStatus(PVADesk.decode(window.PVA_DESK_MODULES.m7.payload).tasks[9])")
    check("integrity", "forged completed/verified/passed flags count for nothing", st10["passed"] == 0, st10)
    check("integrity", "forged state never reaches the legacy progress store", not (pg.evaluate("JSON.parse(localStorage.getItem('pva-ecom-ft-progress')||'{}')").get("lessons") or {}).get("m7-l10"))
    goto(pg, M7 + "#task-10", 1)
    check("work-sample", "no work sample exists before the work verifies", panel(pg).locator(".ws-preview").count() == 0)
    open_all(pg); st = stage_by_id(SRC, "l10-log"); vals = compose_values(st, m7_text)
    fill_compose(pg, st, vals); confirm_all(pg)
    panel(pg).locator("section.desk-group").first.locator("select").first.select_option(first_unaccepted(st["fields"][0]))
    check("self-check", "changing work after confirming clears the confirmations", not any(c.is_checked() for c in panel(pg).locator(".desk-selfcheck input").all()))
    # consistency: a note that contradicts the chosen action fails even with every structured field right
    vals = compose_values(st, m7_text); vals["c1.note"] = "Order #5437: two EF-106 sets arrived damaged. I refunded both and closed the case for Maya by Friday."
    fill_compose(pg, st, vals); confirm_all(pg); submit(pg)
    check("consistency", "a note that contradicts the chosen action is rejected", not pg.is_enabled("#btnNext"))
    vals = compose_values(st, m7_text); vals["c2.note"] = "Order #5440 probably got stolen from the side door, so Maya should decide on a claim today."
    fill_compose(pg, st, vals); confirm_all(pg); submit(pg)
    check("consistency", "a note that guesses a cause is rejected", not pg.is_enabled("#btnNext"))
    ctx.close()

    # ---------- answer encoding / leakage ----------
    ctx, pg, _ = fresh(br)
    shipped = "".join(pg.request.get(BASE + u).text() for u in ["/module-7/index.html", "/module-7/desk-data.js", "/shared/workdesk.js", "/shared/workdesk-ui.js", "/shared/workdesk-page.js", "/shared/everfield-data.js"])
    markers = ['"correct"', "correct: true", '"accept"', '"answer":', '"correctOrder"']
    check("leakage", "no plaintext answer markers in any shipped engine or content file", not any(m in shipped for m in markers), [m for m in markers if m in shipped])
    texts = [option_text(st, correct_option(st)) for _, st in ALL if st["type"] == "decision"]
    check("leakage", "no correct option text appears in shipped source", not any(t in shipped for t in texts))
    goto(pg, M7 + "#task-2", 1); open_all(pg)
    dom = pg.content()
    check("leakage", "rendered DOM carries no correctness attributes before submission", not re.search(r'(class|data-[a-z-]+)="[^"]*(correct|answer|right)', dom))
    vals_dom = pg.evaluate("Array.from(document.querySelectorAll('#stagePanel input,#stagePanel option')).map(e=>e.value)")
    check("leakage", "no control value names the answer (correct/right/wrong, fact/distractor prefixes)",
          not [v for v in vals_dom if re.match(r"^(correct|right|wrong|[fx]_)", v)], vals_dom)
    dec = pg.evaluate("JSON.stringify(PVADesk.decode(window.PVA_DESK_MODULES.m7.payload))")
    check("leakage", "no option, finding or value id names the answer",
          not re.search(r'"(id|value)":"(correct|right|wrong|[fx]_[a-z]+)"', dec), re.findall(r'"(?:id|value)":"(?:correct|right|wrong|[fx]_[a-z]+)"', dec)[:5])
    check("leakage", "decoded payload holds hashed keys only", '"correct"' not in dec and '"accept"' not in dec and '"answer"' not in dec)
    m4src = pg.request.get(BASE + "/module-4/desk-data.js").text()
    check("leakage", "Module 4 content is untouched by Module 7 (no Module 7 orders in it)", not re.search(r"#54[2-4]\d", m4src))
    ctx.close()

    # ---------- persistence ----------
    ctx, pg, _ = fresh(br)
    to_stage(pg, 9, "l10-log"); open_all(pg)
    panel(pg).locator("textarea").first.fill("Draft text that must survive an instant refresh")
    pg.reload(); pg.wait_for_timeout(150); pg.click("#btnNext"); pg.wait_for_timeout(80)
    check("persistence", "typed text survives an immediate refresh", "must survive" in panel(pg).locator("textarea").first.input_value())
    check("persistence", "opened evidence survives refresh", panel(pg).locator(".desk-ev-head button[aria-expanded='false']").count() == 0)
    to_stage(pg, 5, "l6-a"); st = stage_by_id(SRC, "l6-a"); open_all(pg)
    answer_decision(pg, st, findings=correct_findings(st)[:2], submit=False)
    pg.reload(); pg.wait_for_timeout(150); pg.click("#btnNext"); pg.wait_for_timeout(60)
    check("persistence", "unsubmitted decision selections survive refresh",
          panel(pg).get_by_role("checkbox", name=finding_text(st, correct_findings(st)[1]), exact=True).is_checked())
    fail_once(pg, st); panel(pg).get_by_role("button", name="Reconsider and try again").click(); fail_once(pg, st)
    pg.reload(); pg.wait_for_timeout(150); pg.click("#btnNext"); pg.wait_for_timeout(60)
    check("persistence", "the re-check requirement survives refresh", panel(pg).locator(".desk-evidence-card.is-recheck").count() == 3)
    ctx.close()

    # ---------- legacy progress compatibility, verified vs legacy ----------
    ctx, pg, _ = fresh(br); goto(pg, BASE + "/index.html")
    legacy = {"lessons": {**{"m4-l%d" % i: True for i in range(1, 9)}, **{"m7-l%d" % i: True for i in range(1, 11)}}, "modules": {}}
    pg.evaluate("v => localStorage.setItem('pva-ecom-ft-progress', JSON.stringify(v))", legacy)
    goto(pg, M7 + "#task-1")
    check("legacy", "legacy checkmarks still display in Module 7 (legacyPill 'check')", pg.locator(".lesson-pill.done").count() == 10)
    check("legacy", "the status line separates legacy completion from new work", "earlier version" in pg.inner_text("#taskStatus"))
    vw = pg.evaluate("PVADesk.verifiedWork()"); lc = pg.evaluate("PVADesk.legacyCompletion()")
    check("legacy", "legacy completion is not verified work", all(lc.values()) and not any(v["verified"] for v in vw.values()) and not any(v["samplesEarned"] for v in vw.values()))
    pg.click("#btnNext"); solve(pg, stage_by_id(SRC, "l1-a"))
    check("legacy", "desk work never rewrites legacy progress", pg.evaluate("JSON.parse(localStorage.getItem('pva-ecom-ft-progress'))") == legacy)
    goto(pg, BASE + "/index.html")
    s = pg.locator(".module-status").all_inner_texts()
    check("legacy", "course map unchanged", s[3] == "Completed" and s[6] == "Completed", s[:7])
    goto(pg, M4 + "#task-1")
    check("legacy", "Module 4 still shows its own legacy checkmarks", pg.locator(".lesson-pill.done").count() == 8)
    ctx.close()

    # ---------- module isolation and shared authored state ----------
    ctx, pg, _ = fresh(br)
    goto(pg, M4 + "#task-1", 1); m4st = decode("module-4")["tasks"][0]["stages"][0]; solve(pg, m4st)
    to_stage(pg, 0, "l1-a"); solve(pg, stage_by_id(SRC, "l1-a"))
    keys = pg.evaluate("Object.keys(localStorage).sort()")
    check("isolation", "Module 4 and Module 7 keep separate desk keys", keys == ["pva-ecom-ft-m4-desk", KEY, "pva-ecom-ft-progress"], keys)
    m4store = pg.evaluate("JSON.parse(localStorage.getItem('pva-ecom-ft-m4-desk'))")
    check("isolation", "Module 7 work writes nothing into Module 4's store", list(m4store["tasks"].keys()) == ["m4-l1"], list(m4store["tasks"].keys()))
    goto(pg, M7)
    mut = pg.evaluate("(()=>{try{EVERFIELD.calendar.m7.date='Y'; EVERFIELD.team.maya.role='X';}catch(e){} return [EVERFIELD.calendar.m7.date, EVERFIELD.team.maya.role]})()")
    check("everfield", "shared Everfield reference cannot be mutated from Module 7", mut == ["Thu, Sep 17", "Operations Manager"], mut)
    check("everfield", "the desk bar shows Module 7's calendar date", pg.text_content("#deskDate") == "Thu, Sep 17")
    clash = pg.evaluate("(()=>{try{PVADeskCore.createDesk({moduleId:'m9',salt:'x',storageKey:'%s'});return 'created'}catch(e){return e.message}})()" % KEY)
    check("isolation", "another module cannot take Module 7's storage key", "already used" in clash, clash)
    ctx.close()

    # ---------- keyboard + accessibility basics ----------
    ctx, pg, _ = fresh(br); goto(pg, M7 + "#task-2")
    def tab_until(js, limit=150):
        for _ in range(limit):
            pg.keyboard.press("Tab")
            if pg.evaluate(js): return True
        return False
    tab_until("document.activeElement.id==='btnNext'"); pg.keyboard.press("Enter"); pg.wait_for_timeout(80)
    pg.evaluate("document.activeElement.blur()")
    st = stage_by_id(SRC, "l2-a"); want = [finding_text(st, f) for f in correct_findings(st)]; wo = option_text(st, correct_option(st))
    opened = 0
    for _ in range(2):
        if tab_until("document.activeElement.getAttribute('aria-expanded')==='false'"): pg.keyboard.press("Enter"); opened += 1
    picked = 0
    for _ in range(120):
        pg.keyboard.press("Tab")
        info = pg.evaluate("(()=>{var a=document.activeElement,l=a.closest&&a.closest('label');return {type:a.type,tag:a.tagName,label:l?l.innerText:'',text:a.innerText}})()")
        if info["type"] == "checkbox" and info["label"] in want: pg.keyboard.press("Space"); picked += 1
        if info["type"] == "radio":
            for _ in range(6):
                if pg.evaluate("document.activeElement.closest('label').innerText") == wo: break
                pg.keyboard.press("ArrowDown")
            pg.keyboard.press("Space")
        if info["tag"] == "BUTTON" and "decision" in info["text"]: pg.keyboard.press("Enter"); break
    pg.wait_for_timeout(80)
    check("keyboard", "open evidence and decide using only the keyboard", opened == 2 and picked == len(want) and pg.is_enabled("#btnNext"), (opened, picked))
    for ti, st in ALL:
        to_stage(pg, ti, st["id"]); open_all(pg)
        unnamed = pg.evaluate("""Array.from(document.querySelectorAll('#stagePanel select,#stagePanel input,#stagePanel textarea,#stagePanel button')).filter(e=>{var n=(e.labels&&e.labels.length)||e.getAttribute('aria-label')||e.getAttribute('aria-labelledby')||(e.tagName==='BUTTON'&&e.innerText.trim());return !n}).length""")
        if unnamed: check("a11y", "%s: every control has an accessible name" % st["id"], False, unnamed)
    check("a11y", "every control in every stage has an accessible name", not any(r for r in results if r[0] == "a11y" and not r[2]))
    check("a11y", "evidence toggles expose aria-expanded and aria-controls",
          pg.evaluate("Array.from(document.querySelectorAll('.desk-ev-head button')).every(b=>b.hasAttribute('aria-expanded')&&b.hasAttribute('aria-controls'))"))
    for n in (1, 5, 10):
        goto(pg, M7 + "#task-%d" % n); check("deep-link", "#task-%d opens task %d" % (n, n), pg.inner_text("#lessonKicker") == "Task %d of 10" % n)
    ctx.close()

    # ---------- mobile ----------
    ctx, pg, _ = fresh(br, viewport={"width": 375, "height": 812}, device_scale_factor=2, is_mobile=True, has_touch=True)
    for ti, sid in [(0, "l1-a"), (3, "l4-a"), (5, "l6-a"), (8, "l9-a"), (9, "l10-log")]:
        to_stage(pg, ti, sid); open_all(pg); pg.wait_for_timeout(60)
        ov = pg.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        check("mobile", "%s: no horizontal overflow at 375px" % sid, ov <= 0, ov)
    ctx.close()
    br.close()

fails = [r for r in results if not r[2]]
print("\n%d checks, %d failed" % (len(results), len(fails)))
sys.exit(1 if fails else 0)
