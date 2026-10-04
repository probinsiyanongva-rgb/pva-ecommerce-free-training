"""Module 4 Work Desk regression + adversarial suite (browser).

Run from the repo root with a static server on :8765 (see tests/README.md):
    python3 tests/e2e/test_module4.py
Answers come from decoding the shipped content at run time (desk_helpers.decode)."""
import json, os, sys, re
from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from desk_helpers import *  # noqa
from m4_answers import m4_text

SRC = decode("module-4")
M4 = BASE + "/module-4/index.html"
TASKS = SRC["tasks"]
ALL = [(ti, s) for ti, t in enumerate(TASKS) for s in t["stages"]]
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
        fill_compose(pg, st, compose_values(st, m4_text)); confirm_all(pg); submit(pg)


def fail_once(pg, st):
    """A plausible wrong attempt for any stage type."""
    open_all(pg)
    if st["type"] == "decision":
        cf = correct_findings(st)
        answer_decision(pg, st, findings=cf[1:] + distractors(st)[:1], option=(wrong_options(st) or [None])[0])
    elif st["type"] == "triage": answer_triage(pg, st, wrong=True)
    elif st["type"] == "sequence": answer_sequence(pg, st, wrong=True)
    else:
        vals = compose_values(st, m4_text)
        f = next(x for x in st["fields"] if x["type"] == "select")
        vals[f["id"]] = first_unaccepted(f)
        fill_compose(pg, st, vals); confirm_all(pg); submit(pg)


def to_stage(pg, ti, sid):
    goto(pg, M4 + "#task-%d" % (ti + 1), 1)
    for s in TASKS[ti]["stages"]:
        if s["id"] == sid: return
        if not pg.is_enabled("#btnNext"):      # already-verified stages are locked by design
            solve(pg, s)
        pg.click("#btnNext"); pg.wait_for_timeout(60)


def fresh(br, **kw):
    ctx = br.new_context(**kw); pg = ctx.new_page()
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    return ctx, pg, errs


with sync_playwright() as p:
    br = p.chromium.launch()

    # ---------- normal flow, completion, work sample ----------
    ctx, pg, errs = fresh(br); goto(pg, M4)
    for ti, t in enumerate(TASKS):
        goto(pg, M4 + "#task-%d" % (ti + 1), 1); ok = True
        for st in t["stages"]:
            solve(pg, st)
            if not pg.is_enabled("#btnNext"): ok = False; break
            pg.click("#btnNext"); pg.wait_for_timeout(60)
        check("flow", "task %d completes through the UI" % (ti + 1), ok)
    prog = pg.evaluate("JSON.parse(localStorage.getItem('pva-ecom-ft-progress'))")
    check("progress", "verified work marks all 8 lessons in the legacy progress store", all(prog["lessons"].get("m4-l%d" % i) for i in range(1, 9)))
    check("flow", "completion banner", "Module 4 complete" in pg.inner_text("#doneBanner"))
    keys = pg.evaluate("Object.keys(localStorage).sort()")
    check("isolation", "only the Module 4 desk key and the legacy progress key are written", keys == ["pva-ecom-ft-m4-desk", "pva-ecom-ft-progress"], keys)
    vw = pg.evaluate("PVADesk.verifiedWork()")
    check("verified-work", "verifiedWork() reports all 8 tasks verified and the two earned samples",
          all(v["verified"] for v in vw.values()) and vw["m4-l6"]["samplesEarned"] == ["l6-log"] and vw["m4-l8"]["samplesEarned"] == ["l8-update"], vw)
    goto(pg, BASE + "/index.html")
    check("progress", "course map shows Module 4 Completed", "Completed" in pg.locator(".module-card").nth(3).inner_text())
    goto(pg, M4 + "#task-6", 2)
    ev = pg.locator(".ws-preview").inner_text() if pg.locator(".ws-preview").count() else ""
    check("work-sample", "Order Log sample survives reload with honest training header",
          ev.startswith("TRAINING WORK SAMPLE\nOrder Log") and "fictional company" in ev and "Work date: Tue, Sep 15 (simulated)" in ev, ev[:200])
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
        att = pg.evaluate("((JSON.parse(localStorage.getItem('pva-ecom-ft-m4-desk'))||{tasks:{}}).tasks['%s']||{stages:{}}).stages['%s']" % (TASKS[ti]["id"], st["id"]))
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
            co = option_text(st, correct_option(st)) if st.get("options") else None
            if co and co in fb: leaks.append(co)
            check("feedback-safety", "%s: feedback reveals no correct finding or option" % st["id"], not leaks, leaks)
        retry = r.get_by_role("button", name="Reconsider and try again")
        if retry.count(): retry.click(); pg.wait_for_timeout(30)
        fail_once(pg, st)
        paused = r.locator(".desk-pause").count() == 1 and r.locator(".desk-evidence-card.is-recheck").count() >= 1
        blocked = (r.get_by_role("button", name="Reconsider and try again").is_disabled() if st["type"] == "decision"
                   else (r.locator(".desk-actions button").first.is_disabled() if st["type"] in ("sequence", "compose") else
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

    # ---------- transfer: a right action with an incomplete read never passes ----------
    ctx, pg, _ = fresh(br)
    for ti, st in ALL:
        if st["type"] != "decision" or not st.get("options"): continue
        to_stage(pg, ti, st["id"]); open_all(pg)
        cf = correct_findings(st)
        answer_decision(pg, st, findings=cf[:-1])
        check("transfer", "%s: right action without combining all the evidence fails" % st["id"], not pg.is_enabled("#btnNext"))
    to_stage(pg, 6, "l7-c")
    check("transfer", "fits-no-rule case asks the learner to open 3 separate sources", panel(pg).locator(".desk-evidence-card").count() == 3)
    ctx.close()

    # ---------- shortcut attempts, derived completion, work samples ----------
    ctx, pg, _ = fresh(br); goto(pg, M4)
    pg.evaluate("""localStorage.setItem('pva-ecom-ft-m4-desk', JSON.stringify({v:1,tasks:{'m4-l6':{completed:true,verified:true,views:1,
      stages:{'l6-a':{passed:true,answer:{}},'l6-log':{passed:true,answer:{values:{},confirms:[true,true]}}},drafts:{'l6-log:v':{'5414.note':'x'}}}}}))""")
    goto(pg, M4 + "#task-6")
    st6 = pg.evaluate("PVADesk.taskStatus(PVADesk.decode(window.PVA_DESK_MODULES.m4.payload).tasks[5])")
    check("integrity", "forged completed/verified/passed flags and drafts count for nothing", st6["passed"] == 0, st6)
    check("integrity", "forged state never reaches the legacy progress store", not (pg.evaluate("JSON.parse(localStorage.getItem('pva-ecom-ft-progress')||'{}')").get("lessons") or {}).get("m4-l6"))
    goto(pg, M4 + "#task-6", 1); solve(pg, stage_by_id(SRC, "l6-a")); pg.click("#btnNext"); pg.wait_for_timeout(60)
    check("work-sample", "no work sample exists before the work verifies", panel(pg).locator(".ws-preview").count() == 0)
    open_all(pg); st = stage_by_id(SRC, "l6-log"); vals = compose_values(st, m4_text)
    fill_compose(pg, st, vals); confirm_all(pg)
    panel(pg).locator("section.desk-group").first.locator("select").first.select_option(first_unaccepted(st["fields"][0]))
    check("self-check", "changing work after confirming clears the confirmations", not any(c.is_checked() for c in panel(pg).locator(".desk-selfcheck input").all()))
    ctx.close()

    # ---------- answer encoding / leakage ----------
    ctx, pg, _ = fresh(br)
    shipped = "".join(pg.request.get(BASE + u).text() for u in ["/module-4/index.html", "/module-4/desk-data.js", "/shared/workdesk.js", "/shared/workdesk-ui.js", "/shared/workdesk-page.js"])
    markers = ['"correct"', "correct: true", '"accept"', '"answer":', '"correctOrder"']
    check("leakage", "no plaintext answer markers in any shipped engine or content file", not any(m in shipped for m in markers), [m for m in markers if m in shipped])
    texts = [option_text(st, correct_option(st)) for _, st in ALL if st["type"] == "decision" and st.get("options")]
    check("leakage", "no correct option text appears in shipped source", not any(t in shipped for t in texts))
    goto(pg, M4 + "#task-1", 1); open_all(pg)
    dom = pg.content()
    check("leakage", "rendered DOM carries no correctness attributes before submission", not re.search(r'(class|data-[a-z-]+)="[^"]*(correct|answer|right)', dom))
    dec = pg.evaluate("JSON.stringify(PVADesk.decode(window.PVA_DESK_MODULES.m4.payload))")
    check("leakage", "decoded payload holds hashed keys only", '"correct"' not in dec and '"accept"' not in dec and '"answer"' not in dec)
    ctx.close()

    # ---------- persistence ----------
    ctx, pg, _ = fresh(br)
    to_stage(pg, 7, "l8-update"); open_all(pg)
    panel(pg).locator("textarea").fill("Draft text that must survive an instant refresh")
    pg.reload(); pg.wait_for_timeout(150); pg.click("#btnNext"); pg.click("#btnNext"); pg.wait_for_timeout(80)
    check("persistence", "typed text survives an immediate refresh", "must survive" in panel(pg).locator("textarea").input_value())
    check("persistence", "incomplete work stays incomplete", not pg.is_enabled("#btnNext") and "1 of 2" in pg.inner_text("#taskStatus"))
    check("persistence", "opened evidence survives refresh", panel(pg).locator(".desk-ev-head button[aria-expanded='false']").count() == 0)
    to_stage(pg, 2, "l3-a"); st = stage_by_id(SRC, "l3-a"); open_all(pg)
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
    legacy = {"lessons": {**{"m1-l%d" % i: True for i in range(1, 8)}, **{"m4-l%d" % i: True for i in range(1, 9)}}, "modules": {}}
    pg.evaluate("v => localStorage.setItem('pva-ecom-ft-progress', JSON.stringify(v))", legacy)
    goto(pg, M4 + "#task-1")
    check("legacy", "legacy checkmarks still display in Module 4", pg.locator(".lesson-pill.done").count() == 8)
    check("legacy", "the status line separates legacy completion from new work", "earlier version" in pg.inner_text("#taskStatus"))
    vw = pg.evaluate("PVADesk.verifiedWork()"); lc = pg.evaluate("PVADesk.legacyCompletion()")
    check("legacy", "legacy completion is not verified work", all(lc.values()) and not any(v["verified"] for v in vw.values()) and not any(v["samplesEarned"] for v in vw.values()))
    ctx2 = br.new_context(); pg2 = ctx2.new_page()
    pg2.route("**/module-4/desk-data.js", lambda route: route.fulfill(status=200, content_type="application/javascript",
              body=route.fetch().text().replace('"legacyPill":"check"', '"legacyPill":"distinct"')))
    goto(pg2, BASE + "/index.html"); pg2.evaluate("v => localStorage.setItem('pva-ecom-ft-progress', JSON.stringify(v))", legacy)
    goto(pg2, M4 + "#task-1")
    check("legacy", "legacyPill 'distinct': legacy-only tasks get their own marker, not the verified checkmark",
          pg2.locator(".lesson-pill.done").count() == 0 and pg2.locator(".lesson-pill.legacy").count() == 8)
    ctx2.close()
    pg.click("#btnNext"); solve(pg, stage_by_id(SRC, "l1-a"))
    check("legacy", "desk work never rewrites legacy progress", pg.evaluate("JSON.parse(localStorage.getItem('pva-ecom-ft-progress'))") == legacy)
    goto(pg, BASE + "/index.html")
    s = pg.locator(".module-status").all_inner_texts()
    check("legacy", "course map unchanged", s[0] == "Completed" and s[3] == "Completed", s[:4])
    goto(pg, BASE + "/module-1/index.html")
    check("legacy", "an unconverted module still reads progress", pg.locator(".lesson-pill.done").count() == 7)
    ctx.close()

    # ---------- shared authored state, engine boundaries, extensibility ----------
    ctx, pg, _ = fresh(br); goto(pg, M4)
    mut = pg.evaluate("(()=>{try{EVERFIELD.team.sofia.name='X'; EVERFIELD.calendar.m4.date='Y';}catch(e){} return [EVERFIELD.team.sofia.name, EVERFIELD.calendar.m4.date]})()")
    check("everfield", "shared Everfield reference cannot be mutated from a page", mut == ["Sofia Ramirez", "Tue, Sep 15"], mut)
    clash = pg.evaluate("(()=>{try{PVADeskCore.createDesk({moduleId:'m7',salt:'x',storageKey:'pva-ecom-ft-m4-desk'});return 'created'}catch(e){return e.message}})()")
    check("isolation", "a second module cannot take Module 4's storage key", "already used" in clash, clash)
    ext = pg.evaluate("""(()=>{
      var d = PVADeskCore.createDesk({moduleId:'m99', salt:'ext-test'}), K = d.codec.keys;
      var st = {id:'x1', type:'decision', findingsPrompt:'What does it show?', actionPrompt:'Next?',
        records:[{kind:'table', id:'tbl', title:'Stock sheet', columns:['SKU','On hand'], rows:[['EF-101','4'],['EF-102','0']], rowHeaders:true},
                 {kind:'reference', id:'sop', title:'Low-stock SOP', paragraphs:['Flag any SKU under 5 units.']}],
        findings:[{id:'a', text:'EF-102 is out of stock.', k:K.finding('x1','a',true), miss:'Read the On hand column.'},
                  {id:'b', text:'Everything is fine.', k:K.finding('x1','b',false), wrong:'Check each row.'}],
        options:[{id:'o1', text:'Flag EF-102.', k:K.option('x1','o1',true), why:'ok'},{id:'o2', text:'Do nothing.', k:K.option('x1','o2',false), why:'no'}]};
      var host = document.createElement('div'); document.body.appendChild(host);
      PVADeskUI.renderStage(host, st, {desk:d, taskId:'t', onChange:function(){}});
      var hint = host.querySelector('.desk-actions .desk-hint').textContent;
      var ref = host.querySelectorAll('.desk-ev-reference');
      var refOpen = ref.length === 1 && !ref[0].querySelector('.desk-ev-body').hidden && !ref[0].querySelector('button');
      var th = host.querySelectorAll('.desk-table th[scope=col]').length, rowh = host.querySelectorAll('.desk-table th[scope=row]').length;
      var region = host.querySelector('.desk-table-wrap[role=region][tabindex="0"]') !== null;
      host.querySelector('.desk-ev-table button').click();
      var hint2 = host.querySelector('.desk-actions .desk-hint').textContent;
      host.remove(); localStorage.removeItem(d.storageKey);
      return {hint:hint, hint2:hint2, refOpen:refOpen, th:th, rowh:rowh, region:region};
    })()""")
    check("extensibility", "table evidence renders an accessible, scrollable table", ext["th"] == 2 and ext["rowh"] == 2 and ext["region"], ext)
    check("extensibility", "reference evidence is shown open and never gates the decision", ext["refOpen"] and "0 of 1 opened" in ext["hint"], ext)
    check("extensibility", "opening the one gated card satisfies the gate", "Select at least one finding" in ext["hint2"], ext)
    ctx.close()

    # ---------- keyboard + accessibility basics ----------
    ctx, pg, _ = fresh(br); goto(pg, M4 + "#task-1")
    def tab_until(js, limit=150):
        for _ in range(limit):
            pg.keyboard.press("Tab")
            if pg.evaluate(js): return True
        return False
    tab_until("document.activeElement.id==='btnNext'"); pg.keyboard.press("Enter"); pg.wait_for_timeout(80)
    pg.evaluate("document.activeElement.blur()")
    st = stage_by_id(SRC, "l1-a"); want = [finding_text(st, f) for f in correct_findings(st)]; wo = option_text(st, correct_option(st))
    opened = tab_until("document.activeElement.getAttribute('aria-expanded')==='false'"); pg.keyboard.press("Enter")
    picked = 0
    for _ in range(90):
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
    check("keyboard", "open evidence and decide using only the keyboard", opened and picked == len(want) and pg.is_enabled("#btnNext"), picked)
    to_stage(pg, 3, "l4-a"); open_all(pg); seq = stage_by_id(SRC, "l4-a"); labels = {i["id"]: i["label"] for i in seq["items"]}
    for pos, iid in enumerate(seq["correctOrder"]):
        for _ in range(6):
            if panel(pg).locator(".desk-seq-text").all_inner_texts().index(labels[iid]) == pos: break
            panel(pg).get_by_role("button", name="Move “" + labels[iid] + "” up").focus(); pg.keyboard.press("Enter")
    panel(pg).get_by_role("button", name="Check the sequence").focus(); pg.keyboard.press("Enter"); pg.wait_for_timeout(60)
    check("keyboard", "sequence reorderable with the keyboard", pg.is_enabled("#btnNext"))
    for ti, st in ALL:
        to_stage(pg, ti, st["id"]); open_all(pg)
        unnamed = pg.evaluate("""Array.from(document.querySelectorAll('#stagePanel select,#stagePanel input,#stagePanel textarea,#stagePanel button')).filter(e=>{var n=(e.labels&&e.labels.length)||e.getAttribute('aria-label')||e.getAttribute('aria-labelledby')||(e.tagName==='BUTTON'&&e.innerText.trim());return !n}).length""")
        if unnamed: check("a11y", "%s: every control has an accessible name" % st["id"], False, unnamed)
    check("a11y", "every control in every stage has an accessible name", not any(r for r in results if r[0] == "a11y" and not r[2]))
    check("a11y", "evidence toggles expose aria-expanded and aria-controls",
          pg.evaluate("Array.from(document.querySelectorAll('.desk-ev-head button')).every(b=>b.hasAttribute('aria-expanded')&&b.hasAttribute('aria-controls'))"))
    pg.keyboard.press("Tab")   # :focus-visible applies to keyboard users; put the page in keyboard modality first
    focus_style = pg.evaluate("(()=>{var e=document.createElement('button');e.className='btn';document.body.appendChild(e);e.focus();var s=getComputedStyle(e);return s.outlineStyle+' '+s.outlineWidth})()")
    check("a11y", "visible focus outline", "solid" in focus_style and "3px" in focus_style, focus_style)
    for n in (1, 6, 8):
        goto(pg, M4 + "#task-%d" % n); check("deep-link", "#task-%d opens task %d" % (n, n), pg.inner_text("#lessonKicker") == "Task %d of 8" % n)
    ctx.close()

    # ---------- mobile ----------
    ctx, pg, _ = fresh(br, viewport={"width": 375, "height": 812}, device_scale_factor=2, is_mobile=True, has_touch=True)
    for ti, sid in [(0, "l1-a"), (5, "l6-log"), (6, "l7-c"), (7, "l8-update")]:
        to_stage(pg, ti, sid); open_all(pg); pg.wait_for_timeout(60)
        ov = pg.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        check("mobile", "%s: no horizontal overflow at 375px" % sid, ov <= 0, ov)
    ctx.close()
    br.close()

fails = [r for r in results if not r[2]]
print("\n%d checks, %d failed" % (len(results), len(fails)))
sys.exit(1 if fails else 0)
