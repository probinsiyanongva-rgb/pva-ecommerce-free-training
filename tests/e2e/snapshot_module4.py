"""Behavioral snapshot of Module 4: everything a learner sees, in every state.

For each task and stage it records the panel text, step label, primary button
(label + disabled), hint, status line, task pills, chips, focus target and the
disabled-state of every control -- at: closed, evidence opened, first miss,
second miss (pause), evidence re-opened, pass. Plus the resulting storage shape,
the completion banner, and a legacy learner's view.

The committed baseline stores only a SHA-256 per state (raw text after a pass
would contain answers). It was generated from the pre-refactor pilot build
(195d16d); any learner-visible change in Module 4 makes this test fail.

  python3 tests/e2e/snapshot_module4.py                 compare with the baseline
  python3 tests/e2e/snapshot_module4.py --write          regenerate the baseline (only for an intended change)
  python3 tests/e2e/snapshot_module4.py --dump out.json  write raw snapshots locally (never commit: contains answers)
  DESK_TEST_BASE=http://localhost:8766 ...               point at another build"""
import hashlib, json, os, sys
from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from desk_helpers import *  # noqa
from m4_answers import m4_text

BASELINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "module4-behavior-baseline.json")
SRC = decode("module-4")
M4 = BASE + "/module-4/index.html"


def snap(pg, tag):
    return {"tag": tag, "panel": panel(pg).inner_text(),
            "step": pg.inner_text("#stepLabel"), "kicker": pg.inner_text("#lessonKicker"),
            "next": pg.inner_text("#btnNext"), "nextDisabled": pg.is_disabled("#btnNext"), "hint": pg.inner_text("#nextHint"),
            "status": pg.inner_text("#taskStatus"),
            "pills": [p.get_attribute("aria-label") for p in pg.locator(".lesson-pill").all()],
            "pillClasses": [p.get_attribute("class") for p in pg.locator(".lesson-pill").all()],
            "focus": pg.evaluate("(document.activeElement.className||'')+'|'+(document.activeElement.innerText||'').slice(0,60)"),
            "chips": panel(pg).locator(".desk-ev-chip").all_inner_texts(),
            "disabled": pg.evaluate("Array.from(document.querySelectorAll('#stagePanel input,#stagePanel select,#stagePanel button')).map(e=>e.disabled?1:0).join('')")}


def attempt(pg, st, wrong):
    if st["type"] == "decision":
        cf = correct_findings(st)
        answer_decision(pg, st, findings=(cf[:1] + distractors(st)[:1]) if wrong else cf,
                        option=(wrong_options(st)[0] if wrong else None) if st.get("options") else None)
    elif st["type"] == "triage": answer_triage(pg, st, wrong)
    elif st["type"] == "sequence": answer_sequence(pg, st, wrong)
    else:
        vals = compose_values(st, m4_text)
        if wrong:
            f = next(x for x in st["fields"] if x["type"] == "select"); vals[f["id"]] = first_unaccepted(f)
        fill_compose(pg, st, vals); confirm_all(pg); submit(pg)


def capture():
    out = []
    with sync_playwright() as p:
        br = p.chromium.launch(); ctx = br.new_context(); pg = ctx.new_page()
        errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        goto(pg, M4); out.append(snap(pg, "initial-load"))
        for ti, t in enumerate(SRC["tasks"]):
            goto(pg, M4 + "#task-%d" % (ti + 1)); out.append(snap(pg, "%s brief" % t["id"]))
            pg.click("#btnNext"); pg.wait_for_timeout(80)
            for st in t["stages"]:
                tag = "%s %s " % (t["id"], st["id"])
                out.append(snap(pg, tag + "closed"))
                open_all(pg); pg.wait_for_timeout(40); out.append(snap(pg, tag + "opened"))
                attempt(pg, st, True); out.append(snap(pg, tag + "miss1"))
                r = panel(pg).get_by_role("button", name="Reconsider and try again")
                if r.count(): r.click(); pg.wait_for_timeout(40)
                attempt(pg, st, True); out.append(snap(pg, tag + "miss2"))
                open_all(pg); pg.wait_for_timeout(40)
                r = panel(pg).get_by_role("button", name="Reconsider and try again")
                if r.count(): r.click(); pg.wait_for_timeout(40)
                out.append(snap(pg, tag + "reopened"))
                attempt(pg, st, False); out.append(snap(pg, tag + "pass"))
                pg.click("#btnNext"); pg.wait_for_timeout(80)
            out.append(snap(pg, "%s after" % t["id"]))
        out.append({"tag": "banner", "text": pg.inner_text("#doneBanner")})
        store = pg.evaluate("JSON.parse(localStorage.getItem('pva-ecom-ft-m4-desk'))")
        shape = {tid: {"stages": {k: {kk: (vv if kk in ("attempts", "fails", "firstTry", "answer", "last") else "<t>") for kk, vv in v.items()} for k, v in tk["stages"].items()},
                       "drafts": sorted(tk["drafts"].keys())} for tid, tk in store["tasks"].items()}
        out.append({"tag": "store", "shape": shape, "progress": pg.evaluate("localStorage.getItem('pva-ecom-ft-progress')"),
                    "keys": pg.evaluate("Object.keys(localStorage).sort()")})
        ctx2 = br.new_context(); pg2 = ctx2.new_page(); goto(pg2, M4)
        pg2.evaluate("localStorage.setItem('pva-ecom-ft-progress', JSON.stringify({lessons:{'m4-l1':true,'m4-l2':true,'m4-l3':true,'m4-l4':true,'m4-l5':true,'m4-l6':true,'m4-l7':true,'m4-l8':true},modules:{}}))")
        goto(pg2, M4); pg2.wait_for_timeout(100); out.append(snap(pg2, "legacy-learner"))
        out.append({"tag": "errors", "errs": errs})
        br.close()
    return out


def digest(s): return hashlib.sha256(json.dumps(s, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


if __name__ == "__main__":
    snaps = capture()
    hashes = {s["tag"]: digest(s) for s in snaps}
    if "--dump" in sys.argv:
        json.dump(snaps, open(sys.argv[sys.argv.index("--dump") + 1], "w"), indent=1, ensure_ascii=False)
    if "--write" in sys.argv:
        json.dump({"source": os.environ.get("BASELINE_SOURCE", "unspecified"), "states": hashes}, open(BASELINE, "w"), indent=1)
        print("wrote baseline: %d states" % len(hashes)); sys.exit(0)
    base = json.load(open(BASELINE))["states"]
    changed = [t for t in base if hashes.get(t) != base[t]]
    extra = [t for t in hashes if t not in base]
    for t in changed: print("CHANGED " + t)
    for t in extra: print("NEW     " + t)
    print("%d states compared with baseline, %d changed, %d new" % (len(base), len(changed), len(extra)))
    sys.exit(1 if changed or extra else 0)
