"""Shared helpers for Work Desk browser tests.

Answers are never stored in the repository: tests decode the shipped desk-data.js
with tools/desk-codec.js at run time and derive correct (and deliberately wrong)
answers from it. Text answers are generated from the accepted structured values,
so no prose answer is hard-coded either."""
import json, os, re, subprocess

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BASE = os.environ.get("DESK_TEST_BASE", "http://localhost:8765")


def decode(module_dir):
    out = subprocess.check_output(["node", os.path.join(ROOT, "tools", "desk-codec.js"), "decode",
                                   os.path.join(ROOT, module_dir, "desk-data.js")])
    return json.loads(out)


def stage_by_id(src, sid):
    for t in src["tasks"]:
        for s in t["stages"]:
            if s["id"] == sid:
                return s
    raise KeyError(sid)


def correct_findings(st): return [f["id"] for f in st["findings"] if f.get("correct")]
def distractors(st): return [f["id"] for f in st["findings"] if not f.get("correct")]
def correct_option(st): return next(o["id"] for o in st.get("options", []) if o.get("correct"))
def wrong_options(st): return [o["id"] for o in st.get("options", []) if not o.get("correct")]
def option_text(st, oid): return next(o["text"] for o in st["options"] if o["id"] == oid)
def finding_text(st, fid): return next(f["text"] for f in st["findings"] if f["id"] == fid)


def _label(field, value):
    return next(o["label"] for o in field["options"] if o["value"] == value)


def compose_values(st, text_for):
    """Correct structured values (first accepted option/set) + generated text.
    text_for(stage, group, field, labels_in_group) -> str"""
    vals = {}
    for f in st["fields"]:
        if f["type"] == "select":
            vals[f["id"]] = f["accept"][0]
        elif f["type"] == "multi":
            vals[f["id"]] = list(f["accept"][0])
    for g in st["groups"]:
        labels = []
        for f in st["fields"]:
            if f["group"] != g["id"]:
                continue
            if f["type"] == "select":
                labels.append(_label(f, vals[f["id"]]))
            elif f["type"] == "multi":
                labels.append("; ".join(_label(f, v) for v in vals[f["id"]]) or "none")
        for f in st["fields"]:
            if f["group"] == g["id"] and f["type"] == "text":
                vals[f["id"]] = text_for(st, g, f, labels)
    return vals


def first_unaccepted(field):
    return next(o["value"] for o in field["options"] if o["value"] not in field["accept"])


# ---------- page helpers ----------
def panel(pg): return pg.locator("#stagePanel")


def open_all(pg):
    for _ in range(40):
        b = panel(pg).locator(".desk-ev-head button[aria-expanded='false']")
        if b.count() == 0:
            return
        b.first.click()


def goto(pg, url, steps=0):
    pg.goto("about:blank")
    pg.goto(url)
    pg.wait_for_timeout(120)
    for _ in range(steps):
        pg.click("#btnNext")
        pg.wait_for_timeout(60)


def answer_decision(pg, st, findings=None, option=None, submit=True):
    root = panel(pg)
    want = correct_findings(st) if findings is None else findings
    for f in st["findings"]:
        cb = root.get_by_role("checkbox", name=f["text"], exact=True)
        if (f["id"] in want) != cb.is_checked():
            cb.click()
    if st.get("options"):
        oid = correct_option(st) if option is None else option
        root.get_by_role("radio", name=option_text(st, oid), exact=True).check()
    if submit:
        root.locator("button[type=submit]").first.click()
        pg.wait_for_timeout(60)


def answer_triage(pg, st, wrong=False):
    root = panel(pg)
    for i, r in enumerate(st["rows"]):
        v = r["answer"]
        if wrong:
            v = next(c["id"] for c in st["choices"] if c["id"] != r["answer"])
        root.locator("select.desk-select").nth(i).select_option(v)
    root.locator("button[type=submit]").first.click()
    pg.wait_for_timeout(60)


def answer_sequence(pg, st, wrong=False):
    root = panel(pg)
    if not wrong:
        labels = {it["id"]: it["label"] for it in st["items"]}
        for pos, iid in enumerate(st["correctOrder"]):
            for _ in range(10):
                if root.locator(".desk-seq-text").all_inner_texts().index(labels[iid]) == pos:
                    break
                root.get_by_role("button", name="Move “" + labels[iid] + "” up").click()
    root.locator(".desk-actions button").first.click()
    pg.wait_for_timeout(60)


def fill_compose(pg, st, vals):
    root = panel(pg)
    for f in st["fields"]:
        g = root.locator("section.desk-group").nth([x["id"] for x in st["groups"]].index(f["group"]))
        if f["type"] == "select":
            g.get_by_label(f["label"], exact=True).select_option(vals[f["id"]])
        elif f["type"] == "multi":
            fs = g.locator("fieldset.desk-multi").filter(has=pg.locator("legend", has_text=f["label"]))
            for cb in fs.locator("input").all():
                if (cb.evaluate("e => e.value") in vals[f["id"]]) != cb.is_checked():
                    cb.click()
        else:
            g.get_by_label(f["label"], exact=True).fill(vals[f["id"]])


def confirm_all(pg):
    for cb in panel(pg).locator(".desk-selfcheck input[type=checkbox]").all():
        if not cb.is_checked():
            cb.check()


def submit(pg):
    panel(pg).locator("button[type=submit]").first.click()
    pg.wait_for_timeout(80)


def order_ref(group):
    m = re.search(r"#\d+", group["title"])
    return m.group(0) if m else group["title"]
