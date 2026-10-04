"""Browser checks for the typed-number compose field (engine 2.1).

Renders a synthetic stage with the shipped engine on a real page (Module 4's,
which loads every engine script), so no module content is involved. The test
locks its own answers at run time; nothing answer-bearing is stored here.
    python3 tests/e2e/test_engine_number.py"""
import os, sys
from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from desk_helpers import BASE, goto

results = []
def check(area, name, cond, detail=""):
    results.append((area, name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + "[" + area + "] " + name + ((" -- " + str(detail)[:200]) if detail and not cond else ""))

MOUNT = """(() => {
  window.__mount = function(){
    var host = document.getElementById('numHost');
    if(!host){ host = document.createElement('div'); host.id = 'numHost'; document.body.prepend(host); }
    var d = window.__desk || (window.__desk = PVADeskCore.createDesk({moduleId:'m98', salt:'number-ui-test'}));
    var K = d.codec.keys;
    var st = {id:'nx', type:'compose', groups:[{id:'g', title:'Week figures', hint:'Re-read the rows.', records:[{id:'rec', title:'Order export', fields:[['Rows','14']]}]}],
      fields:[{id:'units', group:'g', type:'number', label:'Units shipped', unit:'units', max:500, msg:'count only the rows the question asks for.', sampleLabel:'Units shipped'},
              {id:'cost', group:'g', type:'number', label:'Cost of goods shipped', unit:'$', decimals:2, max:5000, sampleLabel:'Cost'}],
      confirm:['I counted only the rows the question asks for.'],
      evidence:{title:'Week in numbers', requestedBy:'Maya Collins (simulated)', badge:'Training work output', note:'test', filename:'t.txt'}};
    st.fields[0].acc = [K.field('nx','units','58')];
    st.fields[1].acc = [K.field('nx','cost','243.60')];
    host.innerHTML = '';
    PVADeskUI.renderStage(host, st, {desk:d, taskId:'t-num', onChange:function(){}});
  };
  localStorage.removeItem('pva-ecom-ft-m98-desk');
  window.__mount();
})()"""

with sync_playwright() as p:
    br = p.chromium.launch()
    ctx = br.new_context(); pg = ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    goto(pg, BASE + "/module-4/index.html")
    pg.evaluate(MOUNT); host = pg.locator("#numHost")
    units = host.get_by_label("Units shipped (units)", exact=True); cost = host.get_by_label("Cost of goods shipped ($)", exact=True)
    check("render", "number inputs render with the unit in their accessible name", units.count() == 1 and cost.count() == 1)
    check("render", "inputmode suits the declared decimals", units.get_attribute("inputmode") == "numeric" and cost.get_attribute("inputmode") == "decimal")
    check("render", "plain text input (no spinner) with autocomplete off", units.get_attribute("type") == "text" and units.get_attribute("autocomplete") == "off")
    check("gate", "inputs are disabled until the group's evidence is opened", units.is_disabled() and cost.is_disabled())
    host.locator(".desk-ev-head button[aria-expanded='false']").first.click()
    check("gate", "opening the evidence enables the inputs", units.is_enabled() and cost.is_enabled())
    dom = pg.content()
    check("leakage", "no answer value in the DOM before submission", "243.60" not in dom and 'value="58"' not in dom)

    units.fill("57"); cost.fill("$243.6"); host.locator(".desk-selfcheck input").first.check(); host.locator("button[type=submit]").click(); pg.wait_for_timeout(60)
    fb = host.locator(".desk-fb").inner_text()
    check("feedback", "a wrong number fails with the field's principle message", "count only the rows" in fb, fb[:200])
    check("feedback", "feedback never states the value or a direction", not any(w in fb.lower() for w in ["58", "higher", "lower", "too many", "too few"]), fb[:200])
    check("feedback", "the failing input is marked aria-invalid", units.get_attribute("aria-invalid") == "true")
    check("self-check", "a failed submission clears the self-check", not host.locator(".desk-selfcheck input").first.is_checked())

    units.fill("58 units"); host.locator(".desk-selfcheck input").first.check(); host.locator("button[type=submit]").click(); pg.wait_for_timeout(60)
    fb = host.locator(".desk-fb").inner_text()
    check("feedback", "text in a number field gets a format message", "enter a number" in fb, fb[:200])

    units.fill(" 58 "); pg.evaluate("window.__mount()")
    check("persistence", "a typed number survives a re-render (draft saved on input)", host.get_by_label("Units shipped (units)", exact=True).input_value() == " 58 ")
    host.locator(".desk-ev-head button[aria-expanded='false']").first.click() if host.locator(".desk-ev-head button[aria-expanded='false']").count() else None
    host.get_by_label("Cost of goods shipped ($)", exact=True).fill("243.6")
    host.locator(".desk-selfcheck input").first.check(); host.locator("button[type=submit]").click(); pg.wait_for_timeout(80)
    check("pass", "equivalent formats of the right numbers pass", host.locator(".desk-fb.is-pass").count() == 1)
    sample = host.locator(".ws-preview").inner_text() if host.locator(".ws-preview").count() else ""
    check("work-sample", "work sample prints canonical numbers with units", "Units shipped: 58 units" in sample and "Cost: $243.60" in sample, sample)
    pg.evaluate("window.__mount()")
    check("persistence", "a passing number answer re-verifies on load", host.locator(".desk-fb.is-pass").count() == 1)
    check("errors", "no page errors", not errs, errs)
    ctx.close()

    ctx = br.new_context(viewport={"width": 375, "height": 800}, is_mobile=True, has_touch=True); pg = ctx.new_page()
    goto(pg, BASE + "/module-4/index.html"); pg.evaluate(MOUNT)
    pg.locator("#numHost .desk-ev-head button").first.click()
    ov = pg.evaluate("document.documentElement.scrollWidth - window.innerWidth")
    check("mobile", "no horizontal overflow at 375px", ov <= 0, ov)
    ctx.close()
    br.close()

fails = [r for r in results if not r[2]]
print("\n%d checks, %d failed" % (len(results), len(fails)))
sys.exit(1 if fails else 0)
