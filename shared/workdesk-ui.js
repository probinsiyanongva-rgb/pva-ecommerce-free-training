/* PVA Free Training -- E-commerce VA Foundations
   Work Desk engine -- UI (DOM). Requires shared/workdesk.js (PVADeskCore).

   Renders the reusable mechanics for any module:
     - evidence cards, by registered kind: record | message | table | reference
     - the evidence gate and pause-and-re-check (via a per-stage Tracker)
     - stage renderers, by registered type: decision | triage | sequence | compose
     - diagnostic feedback, self-check, and earned work samples

   Every renderer receives ctx = { desk, taskId, onChange }. `desk` is the
   module's engine instance (PVADeskCore.createDesk); nothing here knows which
   module it is serving. */

(function(root){
  "use strict";
  var Core = root.PVADeskCore;
  if(!Core) throw new Error("PVADeskUI: load shared/workdesk.js first");
  var call = Core.call;

  /* Generic UI wording; overridable per module through config.copy. */
  var UI_COPY = {
    workRequest: "Work request",
    findingsHint: "Select everything the evidence supports -- and nothing it doesn't.",
    decisionSubmit: "Make your decision",
    reviewSubmit: "Submit your review",
    decisionGate: function(n, total){ return "Open each record before you decide (" + n + " of " + total + " opened)."; },
    decisionRecheck: "Re-open the evidence marked Re-check first.",
    decisionPick: "Select at least one finding and one action.",
    reviewPick: "Select at least one item.",
    yourDecision: "Your decision", whyItWorks: "Why it works", habit: "Habit to keep",
    whatYouMissed: "What you missed", whyMatters: "Why this matters", whatToReconsider: "What to reconsider",
    youSelected: function(text){ return "You selected “" + text + "”. "; },
    triageGateOpen: "Open the record to make a call.",
    triageGateRecheck: "Re-open this record to change your call.",
    triageHelpOpen: function(n, total){ return "Open every record and make a call on each (" + n + " of " + total + " opened)."; },
    triageHelpPick: function(nounOne){ return "Make a call on every " + nounOne + " first."; },
    lookAgain: "Look again: ",
    choose: "Choose…",
    sequenceSubmit: "Check the sequence",
    moveUp: function(l){ return "Move “" + l + "” up"; },
    moveDown: function(l){ return "Move “" + l + "” down"; },
    moved: function(l, pos){ return "“" + l + "” moved to position " + pos + "."; },
    composeSubmit: "Submit your work",
    selfCheckLegend: "Check your work before you submit it",
    selfCheckEvidence: "Evidence reviewed (ticks itself when you open each record):",
    selfCheckOpened: function(name, recheck){ return "Opened " + name + (recheck ? " (re-check needed)" : ""); },
    confirmReady: "Then confirm these judgement checks:",
    confirmLocked: "The judgement checks below unlock once every record has been opened.",
    composeGateOpen: "Open every record first.",
    composeGateConfirm: "Complete your self-check first.",
    groupGateOpen: "Open the record above to start this entry.",
    groupGateRecheck: "Re-open the record above before you change this entry.",
    staleConfirm: "Your work changed after you checked it -- check it again before submitting.",
    confirmCleared: "Your self-check has been cleared -- re-check after you edit.",
    revise: "Revise your work",
    nameField: "Your name for the work sample header (optional)",
    evOpen: "Open ", evReopen: "Re-open ", evHide: "Hide",
    chipRecheck: "Re-check", chipReviewed: "✓ Reviewed", chipNotOpened: "Not opened",
    now: "Now",
    sampleHeader: "TRAINING WORK SAMPLE",
    sampleCompanyLine: "This is a fictional company used in PVA Free Training. Data is simulated.",
    sampleDateLine: function(date, requestedBy){ return "Work date: " + date + " (simulated)  |  Requested by: " + requestedBy; },
    sampleFooter: "Evidence opened before submitting; self-check completed.",
    sampleHumanReview: "Quality of this work is judged by human review at certification, not by this course.",
    sampleBadge: "Training work sample",
    sampleAria: "Your work sample", sampleTextAria: "Work sample text",
    copySample: "Copy work sample", downloadSample: "Download as .txt",
    copied: "Copied.", copyFailed: "Copy failed -- select the text and copy it manually.", copyManual: "Select the text above and copy it manually.",
    sampleFilename: "work-sample.txt"
  };
  function copyOf(ctx){ return Core.assign({}, UI_COPY, ctx.desk.copy); }

  /* ---------------- DOM helpers ---------------- */
  var uid = 0;
  function nid(p){ uid++; return (p || "d") + "-" + uid; }
  function el(tag, cls, text){
    var e = document.createElement(tag);
    if(cls) e.className = cls;
    if(text !== undefined && text !== null) e.textContent = text;
    return e;
  }
  function btn(label, cls){ var b = el("button", "btn " + (cls || "btn-primary") + " btn-small", label); b.type = "button"; return b; }
  function clock(host, now, C){
    if(!now) return;
    var c = el("p", "desk-clock");
    c.appendChild(el("span", "desk-tag desk-tag-soft", C.now));
    c.appendChild(document.createTextNode(" " + now));
    host.appendChild(c);
  }
  function rid(rec){ return rec.id || rec.title || rec.label; }

  /* ---------------- work request ---------------- */
  function renderBrief(host, brief, team, copy){
    var C = Core.assign({}, UI_COPY, copy);
    var who = (team && team[brief.from]) || { name: brief.from, role: "" };
    var box = el("article", "desk-msg desk-brief");
    box.setAttribute("aria-label", "Work request from " + who.name);
    var head = el("div", "desk-msg-head"); head.appendChild(el("span", "desk-tag", C.workRequest));
    var meta = el("dl", "desk-msg-meta");
    [["From", who.name + (who.role ? ", " + who.role : "")], ["Subject", brief.subject]].forEach(function(p){
      meta.appendChild(el("dt", null, p[0])); meta.appendChild(el("dd", null, p[1]));
    });
    box.appendChild(head); box.appendChild(meta);
    var body = el("div", "desk-msg-body");
    brief.body.forEach(function(p){ body.appendChild(el("p", null, p)); });
    box.appendChild(body);
    host.appendChild(box);
  }

  /* ---------------- evidence kinds (registry) ----------------
     A kind supplies: body(rec) -> Node, and optionally title(rec), tag(rec),
     toggleLabel(rec), cardClass, gated (default true), startsOpen. */
  var evidenceKinds = {};
  function registerEvidenceKind(name, def){ evidenceKinds[name] = def; }
  function kindOf(rec){ return evidenceKinds[rec.kind || "record"] || evidenceKinds.record; }
  function isGated(rec){ var k = kindOf(rec); return rec.gate !== undefined ? rec.gate !== false : k.gated !== false; }
  function gatedIds(records){ return (records || []).filter(isGated).map(rid); }

  registerEvidenceKind("record", {
    title: function(rec){ return rec.title; },
    toggleLabel: function(rec){ return rec.title || "record"; },
    body: function(rec){
      var frag = document.createDocumentFragment();
      var dl = el("dl", "desk-fields");
      (rec.fields || []).forEach(function(f){
        var row = el("div", "desk-field");
        row.appendChild(el("dt", null, f[0]));
        var dd = el("dd", null, f[1]);
        if(f[1] === "—" || f[1] === "") dd.setAttribute("aria-label", f[0] + ": blank");
        row.appendChild(dd); dl.appendChild(row);
      });
      frag.appendChild(dl);
      if(rec.log){
        var lg = el("div", "desk-log");
        lg.appendChild(el("div", "desk-log-title", rec.logTitle || "Activity"));
        var ol = el("ol", "desk-log-list");
        rec.log.forEach(function(line){ ol.appendChild(el("li", null, line)); });
        lg.appendChild(ol); frag.appendChild(lg);
      }
      if(rec.note) frag.appendChild(el("p", "desk-record-note", rec.note));
      return frag;
    }
  });
  registerEvidenceKind("message", {
    cardClass: "desk-ev-message",
    tag: function(rec){ return rec.label || "Message"; },
    title: function(rec){ return rec.meta && rec.meta[0] ? rec.meta[0][1] : ""; },
    toggleLabel: function(rec){ return (rec.label || "message").toLowerCase(); },
    name: function(rec){ return rec.label + (rec.meta && rec.meta[0] ? " (" + rec.meta[0][1] + ")" : ""); },
    body: function(rec){
      var frag = document.createDocumentFragment();
      var meta = el("dl", "desk-msg-meta");
      (rec.meta || []).forEach(function(p){ meta.appendChild(el("dt", null, p[0])); meta.appendChild(el("dd", null, p[1])); });
      frag.appendChild(meta);
      var b = el("div", "desk-msg-body");
      rec.body.forEach(function(p){ b.appendChild(el("p", null, p)); });
      frag.appendChild(b);
      return frag;
    }
  });
  /* Rows of data (spreadsheet-like evidence). Scrolls inside its own region on small screens. */
  registerEvidenceKind("table", {
    cardClass: "desk-ev-table",
    title: function(rec){ return rec.title; },
    toggleLabel: function(rec){ return rec.title || "table"; },
    body: function(rec){
      var wrap = el("div", "desk-table-wrap");
      wrap.setAttribute("role", "region"); wrap.tabIndex = 0;
      wrap.setAttribute("aria-label", (rec.title || "Table") + " (scrolls sideways on small screens)");
      var table = el("table", "desk-table");
      if(rec.caption) table.appendChild(el("caption", null, rec.caption));
      var thead = el("thead"), tr = el("tr");
      (rec.columns || []).forEach(function(c){ var th = el("th", null, c); th.scope = "col"; tr.appendChild(th); });
      thead.appendChild(tr); table.appendChild(thead);
      var tbody = el("tbody");
      (rec.rows || []).forEach(function(r){
        var row = el("tr");
        r.forEach(function(cell, i){ var td = el(i === 0 && rec.rowHeaders ? "th" : "td", null, cell); if(i === 0 && rec.rowHeaders) td.scope = "row"; row.appendChild(td); });
        tbody.appendChild(row);
      });
      table.appendChild(tbody); wrap.appendChild(table);
      var frag = document.createDocumentFragment(); frag.appendChild(wrap);
      if(rec.note) frag.appendChild(el("p", "desk-record-note", rec.note));
      return frag;
    }
  });
  /* Long reference material (an SOP, a policy): shown open, never gated --
     there is no honest way to check it was read. */
  registerEvidenceKind("reference", {
    cardClass: "desk-ev-reference", gated: false, startsOpen: true,
    title: function(rec){ return rec.title; },
    body: function(rec){
      var frag = document.createDocumentFragment();
      (rec.paragraphs || []).forEach(function(p){ frag.appendChild(el("p", null, p)); });
      if(rec.items){ var ul = el("ul", "desk-log-list"); rec.items.forEach(function(i){ ul.appendChild(el("li", null, i)); }); frag.appendChild(ul); }
      return frag;
    }
  });
  function evidenceName(rec){ var k = kindOf(rec); return k.name ? k.name(rec) : (k.title ? k.title(rec) : rid(rec)); }

  /* ---------------- evidence tracking (per stage) ---------------- */
  function Tracker(store, taskId, stageId){
    var self = this;
    this.store = store; this.taskId = taskId; this.stageId = stageId;
    this.opened = (store.getDraft(taskId, stageId + ":opened") || []).slice();
    this.recheck = (store.getDraft(taskId, stageId + ":recheck") || []).slice();
    this.cards = {}; this.listeners = [];
    this.save = function(){
      store.draft(taskId, stageId + ":opened", self.opened);
      store.draft(taskId, stageId + ":recheck", self.recheck.length ? self.recheck : undefined);
    };
  }
  Tracker.prototype.isOpened = function(id){ return this.opened.indexOf(id) !== -1; };
  Tracker.prototype.open = function(id){
    var changed = false;
    if(this.opened.indexOf(id) === -1){ this.opened.push(id); changed = true; }
    var i = this.recheck.indexOf(id); if(i !== -1){ this.recheck.splice(i, 1); changed = true; }
    if(changed){ this.save(); this.listeners.forEach(function(fn){ fn(); }); }
  };
  Tracker.prototype.ready = function(ids){ var s = this; return ids.every(function(id){ return s.isOpened(id); }); };
  Tracker.prototype.count = function(ids){ var s = this; return ids.filter(function(id){ return s.isOpened(id); }).length; };
  Tracker.prototype.requireRecheck = function(ids){
    var s = this;
    ids.forEach(function(id){
      var i = s.opened.indexOf(id); if(i !== -1) s.opened.splice(i, 1);
      if(s.recheck.indexOf(id) === -1) s.recheck.push(id);
      if(s.cards[id]) s.cards[id].forEach(function(c){ c.close(); });
    });
    this.save();
    this.listeners.forEach(function(fn){ fn(); });
  };
  Tracker.prototype.onChange = function(fn){ this.listeners.push(fn); };

  /* An evidence card. Gated kinds: title + Open/Hide toggle, body closed until
     opened, opening recorded. Ungated kinds (reference): shown open, untracked.
     `footer` (optional) is always visible -- used for triage selects. */
  function evidenceCard(rec, tracker, C, opts){
    opts = opts || {};
    var id = rid(rec), kind = kindOf(rec), gated = isGated(rec);
    var card = el("section", "desk-record desk-evidence-card" + (kind.cardClass ? " " + kind.cardClass : ""));
    var head = el("div", "desk-ev-head");
    var titleWrap = el("div", "desk-ev-titlewrap");
    if(kind.tag) titleWrap.appendChild(el("span", "desk-tag desk-tag-soft", kind.tag(rec)));
    titleWrap.appendChild(el("h4", "desk-record-title", kind.title ? kind.title(rec) : ""));
    head.appendChild(titleWrap);
    card.appendChild(head);
    var body = el("div", "desk-ev-body"); body.id = nid("evb");
    body.appendChild(kind.body(rec));
    card.appendChild(body);
    if(opts.footer) card.appendChild(opts.footer);
    if(!gated){ body.hidden = false; return card; }

    var chip = el("span", "desk-ev-chip");
    var toggle = btn(C.evOpen, "btn-ghost");
    toggle.setAttribute("aria-controls", body.id);
    head.appendChild(chip); head.appendChild(toggle);
    var label = kind.toggleLabel ? kind.toggleLabel(rec) : "record";
    function sync(){
      var expanded = !body.hidden, re = tracker.recheck.indexOf(id) !== -1;
      toggle.textContent = expanded ? C.evHide : (re ? C.evReopen : C.evOpen) + label;
      toggle.setAttribute("aria-expanded", expanded ? "true" : "false");
      chip.textContent = re ? C.chipRecheck : tracker.isOpened(id) ? C.chipReviewed : C.chipNotOpened;
      chip.className = "desk-ev-chip " + (re ? "is-recheck" : tracker.isOpened(id) ? "is-done" : "");
      card.classList.toggle("is-recheck", re);
    }
    toggle.addEventListener("click", function(){
      if(body.hidden){ body.hidden = false; tracker.open(id); }
      else body.hidden = true;
      sync();
    });
    body.hidden = !(opts.startOpen && tracker.isOpened(id));
    (tracker.cards[id] = tracker.cards[id] || []).push({ close: function(){ body.hidden = true; sync(); } });
    tracker.onChange(sync);
    sync();
    return card;
  }
  function evidenceGrid(host, records, tracker, C){
    var grid = el("div", "desk-records");
    records.forEach(function(r){ grid.appendChild(evidenceCard(r, tracker, C, { startOpen: true })); });
    host.appendChild(grid);
  }

  /* ---------------- feedback blocks ---------------- */
  function fbBlock(pass, title){
    var fb = el("div", "desk-fb " + (pass ? "is-pass" : "is-retry"));
    var hd = el("h4", "desk-fb-title", title); hd.tabIndex = -1;
    fb.appendChild(hd);
    return { box: fb, title: hd };
  }
  function fbRow(dl, label, content){
    dl.appendChild(el("dt", null, label));
    var dd = el("dd");
    if(typeof content === "string") dd.textContent = content; else dd.appendChild(content);
    dl.appendChild(dd);
  }
  /* Pause and re-check: listed evidence must be re-opened before the next attempt. */
  function pausePanel(host, tracker, ids, nameOf, attempts, C){
    var box = el("div", "desk-pause");
    box.setAttribute("role", "note");
    box.appendChild(el("p", "desk-pause-title", C.pauseTitle));
    box.appendChild(el("p", null, call(C.pauseBody, attempts)));
    var ul = el("ul", "desk-pause-list");
    var items = ids.map(function(id){ var li = el("li", null, nameOf(id)); ul.appendChild(li); return { id: id, li: li }; });
    box.appendChild(ul);
    host.appendChild(box);
    function sync(){ items.forEach(function(it){ var ok = tracker.isOpened(it.id); it.li.classList.toggle("is-done", ok); it.li.textContent = (ok ? "✓ " : "") + nameOf(it.id); }); }
    tracker.onChange(sync); sync();
  }
  function recName(records){ var m = {}; records.forEach(function(r){ m[rid(r)] = evidenceName(r); }); return function(id){ return m[id] || id; }; }

  /* ---------------- stage renderers (registry) ---------------- */
  var renderers = {};
  function registerRenderer(type, fn){ renderers[type] = fn; }

  /* DECISION: findings + action, gated on evidence */
  registerRenderer("decision", function(host, stage, ctx){
    var desk = ctx.desk, store = desk.store, C = copyOf(ctx);
    var tracker = new Tracker(store, ctx.taskId, stage.id);
    var ids = gatedIds(stage.records);
    if(stage.intro) host.appendChild(el("p", "desk-intro", stage.intro));
    clock(host, stage.now, C);
    evidenceGrid(host, stage.records || [], tracker, C);

    var form = el("form", "desk-form"); form.noValidate = true;
    form.addEventListener("submit", function(e){ e.preventDefault(); });
    var fsF = el("fieldset", "desk-fieldset");
    fsF.appendChild(el("legend", null, stage.findingsPrompt));
    fsF.appendChild(el("p", "desk-hint", C.findingsHint));
    var fInputs = [];
    stage.findings.forEach(function(f){
      var id = nid("f"), lab = el("label", "desk-choice"), inp = document.createElement("input");
      inp.type = "checkbox"; inp.id = id; inp.value = f.id; lab.htmlFor = id;
      lab.appendChild(inp); lab.appendChild(el("span", null, f.text)); fsF.appendChild(lab); fInputs.push(inp);
    });
    form.appendChild(fsF);
    var oInputs = [];
    if(stage.options && stage.options.length){
      var fsO = el("fieldset", "desk-fieldset"), name = nid("opt");
      fsO.appendChild(el("legend", null, stage.actionPrompt));
      stage.options.forEach(function(o){
        var id = nid("o"), lab = el("label", "desk-choice"), inp = document.createElement("input");
        inp.type = "radio"; inp.name = name; inp.id = id; inp.value = o.id; lab.htmlFor = id;
        lab.appendChild(inp); lab.appendChild(el("span", null, o.text)); fsO.appendChild(lab); oInputs.push(inp);
      });
      form.appendChild(fsO);
    }
    var actions = el("div", "desk-actions");
    var submit = btn(stage.submitLabel || (oInputs.length ? C.decisionSubmit : C.reviewSubmit)); submit.type = "submit";
    var help = el("p", "desk-hint"); help.id = nid("help"); submit.setAttribute("aria-describedby", help.id);
    var attemptsNote = el("span", "desk-attempts");
    actions.appendChild(submit); actions.appendChild(help); actions.appendChild(attemptsNote);
    form.appendChild(actions);
    var fbHost = el("div", "desk-fb-host"); fbHost.setAttribute("aria-live", "polite");
    host.appendChild(form); host.appendChild(fbHost);

    var locked = false, retryBtn = null;
    function current(){
      return { f: fInputs.filter(function(i){ return i.checked; }).map(function(i){ return i.value; }).sort(),
               o: oInputs.filter(function(i){ return i.checked; }).map(function(i){ return i.value; })[0] };
    }
    function refresh(){
      if(retryBtn) retryBtn.disabled = !tracker.ready(ids);
      if(locked) return;
      var a = current(), opened = tracker.ready(ids), picked = a.f.length > 0 && (!oInputs.length || !!a.o);
      submit.disabled = !(opened && picked);
      help.style.display = submit.disabled ? "block" : "none";
      help.textContent = !opened ? (tracker.recheck.length ? C.decisionRecheck : call(C.decisionGate, tracker.count(ids), ids.length))
                                 : (oInputs.length ? C.decisionPick : C.reviewPick);
    }
    function setLocked(lock){
      locked = lock;
      fInputs.concat(oInputs).forEach(function(i){ i.disabled = lock; });
      submit.style.display = lock ? "none" : ""; if(lock) help.style.display = "none";
    }
    function restore(a){
      fInputs.forEach(function(i){ i.checked = (a.f || []).indexOf(i.value) !== -1; });
      oInputs.forEach(function(i){ i.checked = i.value === a.o; });
    }
    form.addEventListener("change", function(){ store.draft(ctx.taskId, stage.id + ":sel", current()); refresh(); });
    tracker.onChange(refresh);

    function showPass(res, fromLoad){
      fbHost.innerHTML = ""; retryBtn = null;
      var b = fbBlock(true, stage.passTitle || C.decisionPassTitle);
      var dl = el("dl", "desk-fb-dl");
      if(res.option) fbRow(dl, C.yourDecision, res.option.text);
      fbRow(dl, C.whyItWorks, (res.option && res.option.why) || stage.passWhy || "");
      if(stage.takeaway) fbRow(dl, C.habit, stage.takeaway);
      b.box.appendChild(dl); fbHost.appendChild(b.box);
      setLocked(true);
      if(!fromLoad) b.title.focus();
    }
    function showFail(res, st){
      fbHost.innerHTML = "";
      var fb = desk.decisionFeedback(stage, res);
      var b = fbBlock(false, fb.title);
      var dl = el("dl", "desk-fb-dl");
      if(fb.chosen) fbRow(dl, C.yourDecision, fb.chosen);
      if(fb.missedLead || fb.wrongPicks.length){
        var ul = el("ul", "desk-fb-list");
        if(fb.missedLead){
          ul.appendChild(el("li", null, fb.missedLead));
          fb.pointers.forEach(function(p){ ul.appendChild(el("li", "desk-fb-sub", p)); });
        }
        fb.wrongPicks.forEach(function(w){
          var li = el("li");
          li.appendChild(el("strong", null, call(C.youSelected, w.text)));
          li.appendChild(document.createTextNode(w.why)); ul.appendChild(li);
        });
        fbRow(dl, C.whatYouMissed, ul);
      }
      if(fb.why) fbRow(dl, C.whyMatters, fb.why);
      b.box.appendChild(dl);
      if(desk.shouldPause(st)){
        tracker.requireRecheck(ids);
        pausePanel(b.box, tracker, ids, recName(stage.records || []), st.attempts, C);
      }
      retryBtn = btn(C.retryLabel, "btn-ghost");
      retryBtn.addEventListener("click", function(){
        if(!tracker.ready(ids)) return;
        fbHost.innerHTML = ""; retryBtn = null; setLocked(false); refresh(); fInputs[0].focus();
      });
      b.box.appendChild(retryBtn);
      fbHost.appendChild(b.box);
      setLocked(true); refresh();
      b.title.focus();
    }
    submit.addEventListener("click", function(){
      if(submit.disabled || !tracker.ready(ids)) return;
      var ans = current(), res = desk.evaluate(stage, ans);
      var st = store.attempt(ctx.taskId, stage.id, ans, res.pass);
      attemptsNote.textContent = st.attempts > 1 ? "Attempt " + st.attempts : "";
      if(res.pass) showPass(res, false); else showFail(res, st);
      ctx.onChange();
    });

    var saved = store.get(ctx.taskId).stages[stage.id];
    if(saved && saved.answer && desk.evaluate(stage, saved.answer).pass){ restore(saved.answer); showPass(desk.evaluate(stage, saved.answer), true); }
    else {
      var d = store.getDraft(ctx.taskId, stage.id + ":sel") || (saved && saved.last);
      if(d) restore(d);
      if(saved && saved.attempts > 1) attemptsNote.textContent = "Attempt " + (saved.attempts + 1);
    }
    refresh();
  });

  /* TRIAGE: one call per record, each gated on its own evidence */
  registerRenderer("triage", function(host, stage, ctx){
    var desk = ctx.desk, store = desk.store, C = copyOf(ctx);
    var nounOne = stage.rowNounOne || C.rowNounOne, noun = stage.rowNoun || C.rowNoun;
    var tracker = new Tracker(store, ctx.taskId, stage.id);
    if(stage.intro) host.appendChild(el("p", "desk-intro", stage.intro));
    clock(host, stage.now, C);
    var form = el("form", "desk-form"); form.addEventListener("submit", function(e){ e.preventDefault(); });
    var list = el("div", "desk-records desk-triage");
    var selects = {}, notes = {}, cards = {}, locked = false;
    var draft = store.getDraft(ctx.taskId, stage.id + ":sel") || {};
    stage.rows.forEach(function(r){
      var foot = el("div", "desk-triage-pick");
      var sid = nid("sel"), lab = el("label", "desk-select-label", stage.prompt + " — " + (r.title || r.id));
      lab.htmlFor = sid;
      var sel = document.createElement("select"); sel.id = sid; sel.className = "desk-select";
      var o0 = el("option", null, C.choose); o0.value = ""; sel.appendChild(o0);
      stage.choices.forEach(function(c){ var o = el("option", null, c.label); o.value = c.id; sel.appendChild(o); });
      var note = el("p", "desk-row-note"); note.id = nid("note"); note.hidden = true;
      var gate = el("p", "desk-hint desk-gate"); gate.id = nid("gate");
      sel.setAttribute("aria-describedby", note.id + " " + gate.id);
      foot.appendChild(lab); foot.appendChild(sel); foot.appendChild(gate); foot.appendChild(note);
      var card = evidenceCard(r, tracker, C, { footer: foot, startOpen: true });
      card.classList.add("desk-triage-row");
      list.appendChild(card);
      sel.value = draft[r.id] || "";
      selects[r.id] = sel; notes[r.id] = note; cards[r.id] = { card: card, gate: gate };
    });
    form.appendChild(list);
    var actions = el("div", "desk-actions");
    var submit = btn(stage.submitLabel || C.reviewSubmit); submit.type = "submit";
    var help = el("p", "desk-hint"); help.id = nid("help"); submit.setAttribute("aria-describedby", help.id);
    var attemptsNote = el("span", "desk-attempts");
    actions.appendChild(submit); actions.appendChild(help); actions.appendChild(attemptsNote);
    form.appendChild(actions);
    var fbHost = el("div", "desk-fb-host"); fbHost.setAttribute("aria-live", "polite");
    host.appendChild(form); host.appendChild(fbHost);

    function current(){ var a = {}; Object.keys(selects).forEach(function(k){ a[k] = selects[k].value; }); return a; }
    function refresh(){
      Object.keys(selects).forEach(function(k){
        var open = tracker.isOpened(k);
        selects[k].disabled = locked || !open;
        cards[k].gate.textContent = open ? "" : (tracker.recheck.indexOf(k) !== -1 ? C.triageGateRecheck : C.triageGateOpen);
        cards[k].gate.hidden = open || locked;
      });
      if(locked) return;
      var a = current(), allSet = Object.keys(a).every(function(k){ return !!a[k]; }), opened = tracker.ready(Object.keys(selects));
      submit.disabled = !(allSet && opened);
      help.style.display = submit.disabled ? "block" : "none";
      help.textContent = !opened ? call(C.triageHelpOpen, tracker.count(Object.keys(selects)), stage.rows.length) : call(C.triageHelpPick, nounOne);
    }
    form.addEventListener("change", function(e){
      Object.keys(selects).forEach(function(k){
        if(selects[k] === e.target){ notes[k].hidden = true; e.target.removeAttribute("aria-invalid"); cards[k].card.classList.remove("is-flag", "is-ok"); }
      });
      store.draft(ctx.taskId, stage.id + ":sel", current());
      refresh();
    });
    tracker.onChange(refresh);

    function showResult(res, fromLoad, st){
      fbHost.innerHTML = "";
      stage.rows.forEach(function(r){
        var wrong = res.wrongRows.indexOf(r) !== -1;
        notes[r.id].hidden = !wrong;
        cards[r.id].card.classList.toggle("is-flag", wrong);
        cards[r.id].card.classList.toggle("is-ok", !wrong);
        if(wrong){ notes[r.id].textContent = C.lookAgain + r.hint; selects[r.id].setAttribute("aria-invalid", "true"); }
        else selects[r.id].removeAttribute("aria-invalid");
      });
      if(res.pass){
        locked = true;
        var b = fbBlock(true, stage.passTitle || C.triagePassTitle);
        var dl = el("dl", "desk-fb-dl");
        if(stage.passWhy) fbRow(dl, C.whyMatters, stage.passWhy);
        if(stage.takeaway) fbRow(dl, C.habit, stage.takeaway);
        b.box.appendChild(dl); fbHost.appendChild(b.box);
        submit.style.display = "none"; help.style.display = "none";
        refresh();
        if(!fromLoad) b.title.focus();
        return;
      }
      var n = res.wrongRows.length;
      var b2 = fbBlock(false, call(C.triageFailTitle, n, stage.rows.length, noun));
      b2.box.appendChild(el("p", null, call(C.triageFailBody, nounOne)));
      if(desk.shouldPause(st)){
        var ids = res.wrongRows.map(function(r){ return r.id; });
        tracker.requireRecheck(ids);
        pausePanel(b2.box, tracker, ids, function(id){ var r = stage.rows.filter(function(x){ return x.id === id; })[0]; return r.title || id; }, st.attempts, C);
      }
      fbHost.appendChild(b2.box);
      refresh();
      if(!fromLoad) b2.title.focus();
    }
    submit.addEventListener("click", function(){
      if(submit.disabled || !tracker.ready(Object.keys(selects))) return;
      var ans = current(), res = desk.evaluate(stage, ans);
      var st = store.attempt(ctx.taskId, stage.id, ans, res.pass);
      attemptsNote.textContent = st.attempts > 1 ? "Attempt " + st.attempts : "";
      showResult(res, false, st);
      ctx.onChange();
    });
    var saved = store.get(ctx.taskId).stages[stage.id];
    if(saved && saved.answer && desk.evaluate(stage, saved.answer).pass){
      Object.keys(selects).forEach(function(k){ selects[k].value = saved.answer[k] || ""; });
      showResult(desk.evaluate(stage, saved.answer), true);
    }
    refresh();
  });

  /* SEQUENCE: keyboard-operable ordering; clues live in the evidence */
  registerRenderer("sequence", function(host, stage, ctx){
    var desk = ctx.desk, store = desk.store, C = copyOf(ctx);
    var tracker = new Tracker(store, ctx.taskId, stage.id);
    var ids = gatedIds(stage.records);
    if(stage.intro) host.appendChild(el("p", "desk-intro", stage.intro));
    evidenceGrid(host, stage.records || [], tracker, C);
    var qid = nid("seq");
    var q = el("p", "desk-q", stage.prompt); q.id = qid; host.appendChild(q);
    var ol = el("ol", "desk-seq"); ol.setAttribute("aria-labelledby", qid); host.appendChild(ol);
    var status = el("p", "desk-sr"); status.setAttribute("aria-live", "polite"); host.appendChild(status);
    var actions = el("div", "desk-actions");
    var submit = btn(stage.submitLabel || C.sequenceSubmit);
    var help = el("p", "desk-hint"); help.id = nid("help"); submit.setAttribute("aria-describedby", help.id);
    var attemptsNote = el("span", "desk-attempts");
    actions.appendChild(submit); actions.appendChild(help); actions.appendChild(attemptsNote);
    host.appendChild(actions);
    var fbHost = el("div", "desk-fb-host"); fbHost.setAttribute("aria-live", "polite"); host.appendChild(fbHost);

    var saved = store.get(ctx.taskId).stages[stage.id];
    var drafted = store.getDraft(ctx.taskId, stage.id + ":order");
    var order = (drafted && drafted.length === stage.items.length) ? drafted.slice() : (stage.startOrder || stage.items.map(function(i){ return i.id; }));
    var locked = false;
    function item(id){ return stage.items.filter(function(x){ return x.id === id; })[0]; }
    function refresh(){
      if(locked){ help.style.display = "none"; return; }
      var ok = tracker.ready(ids);
      submit.disabled = !ok;
      help.style.display = ok ? "none" : "block";
      help.textContent = tracker.recheck.length ? (stage.recheckText || C.sequenceRecheck) : (stage.gateText || C.sequenceGate);
    }
    tracker.onChange(refresh);
    function draw(focusId, dir){
      ol.innerHTML = "";
      order.forEach(function(id, i){
        var it = item(id), li = el("li", "desk-seq-item");
        li.appendChild(el("span", "desk-seq-n", (i + 1) + "."));
        li.appendChild(el("span", "desk-seq-text", it.label));
        var ctr = el("span", "desk-seq-ctrls");
        var up = btn("↑", "btn-ghost"); up.setAttribute("aria-label", call(C.moveUp, it.label));
        var dn = btn("↓", "btn-ghost"); dn.setAttribute("aria-label", call(C.moveDown, it.label));
        up.disabled = locked || i === 0; dn.disabled = locked || i === order.length - 1;
        up.addEventListener("click", function(){ move(i, -1); });
        dn.addEventListener("click", function(){ move(i, 1); });
        up.dataset.id = id; dn.dataset.id = id; up.dataset.dir = "-1"; dn.dataset.dir = "1";
        ctr.appendChild(up); ctr.appendChild(dn); li.appendChild(ctr); ol.appendChild(li);
      });
      if(focusId){
        var t = ol.querySelector('button[data-id="' + focusId + '"][data-dir="' + dir + '"]:not([disabled])') || ol.querySelector('button[data-id="' + focusId + '"]:not([disabled])');
        if(t) t.focus();
      }
    }
    function move(i, d){
      var j = i + d; if(j < 0 || j >= order.length) return;
      var id = order[i]; order[i] = order[j]; order[j] = id;
      fbHost.innerHTML = "";
      store.draft(ctx.taskId, stage.id + ":order", order.slice());
      draw(id, String(d));
      status.textContent = call(C.moved, item(id).label, j + 1);
    }
    function show(res, fromLoad, st){
      fbHost.innerHTML = "";
      if(res.pass){
        locked = true; draw(); submit.style.display = "none"; refresh();
        var b = fbBlock(true, stage.passTitle || C.sequencePassTitle);
        var dl = el("dl", "desk-fb-dl"); fbRow(dl, C.whyItWorks, stage.passWhy);
        b.box.appendChild(dl); fbHost.appendChild(b.box);
        if(!fromLoad) b.title.focus();
        return;
      }
      var it = item(order[res.firstWrong]);
      var b2 = fbBlock(false, call(C.sequenceFailTitle, res.firstWrong + 1));
      var dl2 = el("dl", "desk-fb-dl");
      fbRow(dl2, C.whatToReconsider, "“" + it.label + "”: " + it.hint);
      fbRow(dl2, C.whyMatters, stage.failWhy);
      b2.box.appendChild(dl2);
      if(desk.shouldPause(st) && ids.length){
        tracker.requireRecheck(ids);
        pausePanel(b2.box, tracker, ids, recName(stage.records), st.attempts, C);
      }
      fbHost.appendChild(b2.box);
      refresh();
      if(!fromLoad) b2.title.focus();
    }
    submit.addEventListener("click", function(){
      if(submit.disabled || !tracker.ready(ids)) return;
      var ans = { order: order.slice() }, res = desk.evaluate(stage, ans);
      var st = store.attempt(ctx.taskId, stage.id, ans, res.pass);
      attemptsNote.textContent = st.attempts > 1 ? "Attempt " + st.attempts : "";
      show(res, false, st); ctx.onChange();
    });
    if(saved && saved.answer && desk.evaluate(stage, saved.answer).pass){ order = saved.answer.order.slice(); locked = true; draw(); show(desk.evaluate(stage, saved.answer), true); }
    else draw();
    refresh();
  });

  /* COMPOSE: structured production, self-check, earned work sample */
  registerRenderer("compose", function(host, stage, ctx){
    var desk = ctx.desk, store = desk.store, C = copyOf(ctx);
    var tracker = new Tracker(store, ctx.taskId, stage.id);
    if(stage.intro) host.appendChild(el("p", "desk-intro", stage.intro));
    clock(host, stage.now, C);
    if(stage.example){
      var ex = el("details", "desk-example");
      ex.appendChild(el("summary", null, stage.example.label));
      ex.appendChild(el("pre", "desk-example-text", stage.example.text));
      if(stage.example.note) ex.appendChild(el("p", "desk-hint", stage.example.note));
      host.appendChild(ex);
    }
    var vals = store.getDraft(ctx.taskId, stage.id + ":v") || {};
    var form = el("form", "desk-form"); form.addEventListener("submit", function(e){ e.preventDefault(); });
    var inputs = {}, groupEls = {}, allRecIds = [], locked = false;

    stage.groups.forEach(function(g){
      var box = el("section", "desk-group");
      box.setAttribute("aria-label", g.title);
      box.appendChild(el("h3", "desk-group-title", g.title));
      if(g.lead) box.appendChild(el("p", "desk-hint", g.lead));
      var recIds = gatedIds(g.records);
      allRecIds = allRecIds.concat(recIds.filter(function(i){ return allRecIds.indexOf(i) === -1; }));
      var grid = el("div", "desk-records");
      g.records.forEach(function(r){ grid.appendChild(evidenceCard(r, tracker, C, { startOpen: true })); });
      box.appendChild(grid);
      var gate = el("p", "desk-hint desk-gate"); box.appendChild(gate);
      var gNote = el("p", "desk-row-note"); gNote.hidden = true; box.appendChild(gNote);
      stage.fields.filter(function(f){ return f.group === g.id; }).forEach(function(f){
        var wrap = el("div", "desk-compose-field");
        var err = el("p", "desk-row-note"); err.id = nid("err"); err.hidden = true;
        var ctrl;
        if(f.type === "select"){
          var id = nid("sel");
          var lab = el("label", "ws-label", f.label); lab.htmlFor = id; wrap.appendChild(lab);
          if(f.help) wrap.appendChild(el("p", "desk-hint", f.help));
          ctrl = document.createElement("select"); ctrl.id = id; ctrl.className = "desk-select";
          var o0 = el("option", null, C.choose); o0.value = ""; ctrl.appendChild(o0);
          f.options.forEach(function(o){ var op = el("option", null, o.label); op.value = o.value; ctrl.appendChild(op); });
          ctrl.value = vals[f.id] || "";
          ctrl.setAttribute("aria-describedby", err.id);
          wrap.appendChild(ctrl);
        } else if(f.type === "number"){
          /* Typed number: a plain text input (no spinner, no locale surprises);
             the unit is part of the visible label. */
          var nid2 = nid("num");
          var nl = el("label", "ws-label", f.label + (f.unit ? " (" + f.unit + ")" : "")); nl.htmlFor = nid2; wrap.appendChild(nl);
          if(f.help) wrap.appendChild(el("p", "desk-hint", f.help));
          ctrl = document.createElement("input"); ctrl.type = "text"; ctrl.id = nid2; ctrl.className = "desk-input desk-number";
          ctrl.setAttribute("inputmode", f.decimals ? "decimal" : "numeric"); ctrl.setAttribute("autocomplete", "off"); ctrl.setAttribute("spellcheck", "false");
          if(f.placeholder) ctrl.placeholder = f.placeholder;
          ctrl.value = vals[f.id] || "";
          ctrl.setAttribute("aria-describedby", err.id);
          wrap.appendChild(ctrl);
        } else if(f.type === "multi"){
          var fs = el("fieldset", "desk-fieldset desk-multi");
          fs.appendChild(el("legend", null, f.label));
          if(f.help) fs.appendChild(el("p", "desk-hint", f.help));
          ctrl = [];
          f.options.forEach(function(o){
            var cid = nid("m"), lb = el("label", "desk-choice"), inp = document.createElement("input");
            inp.type = "checkbox"; inp.id = cid; inp.value = o.value; lb.htmlFor = cid;
            inp.checked = (vals[f.id] || []).indexOf(o.value) !== -1;
            lb.appendChild(inp); lb.appendChild(el("span", null, o.label)); fs.appendChild(lb); ctrl.push(inp);
          });
          fs.setAttribute("aria-describedby", err.id);
          wrap.appendChild(fs);
        } else {
          var tid = nid("ta");
          var tl = el("label", "ws-label", f.label); tl.htmlFor = tid; wrap.appendChild(tl);
          if(f.help) wrap.appendChild(el("p", "desk-hint", f.help));
          ctrl = document.createElement("textarea"); ctrl.id = tid; ctrl.className = "ws-textarea";
          ctrl.rows = f.rows || 3; ctrl.placeholder = f.placeholder || ""; ctrl.value = vals[f.id] || "";
          ctrl.setAttribute("aria-describedby", err.id);
          wrap.appendChild(ctrl);
        }
        wrap.appendChild(err);
        box.appendChild(wrap);
        inputs[f.id] = { f: f, ctrl: ctrl, err: err };
      });
      groupEls[g.id] = { box: box, gate: gate, note: gNote, recIds: recIds };
      form.appendChild(box);
    });

    var sc = el("fieldset", "desk-fieldset desk-selfcheck");
    sc.appendChild(el("legend", null, C.selfCheckLegend));
    var evList = el("ul", "desk-evlist");
    sc.appendChild(el("p", "desk-hint", C.selfCheckEvidence));
    sc.appendChild(evList);
    var nameOf = recName([].concat.apply([], stage.groups.map(function(g){ return g.records; })));
    var evItems = allRecIds.map(function(id){ var li = el("li", null, ""); evList.appendChild(li); return { id: id, li: li }; });
    var confirmHint = el("p", "desk-hint"); sc.appendChild(confirmHint);
    var staleNote = el("p", "desk-row-note"); staleNote.hidden = true; sc.appendChild(staleNote);
    var confirmBoxes = [];
    var savedConfirms = store.getDraft(ctx.taskId, stage.id + ":confirms") || [];
    (stage.confirm || []).forEach(function(c, i){
      var id = nid("chk"), lab = el("label", "desk-choice"), inp = document.createElement("input");
      inp.type = "checkbox"; inp.id = id; inp.checked = savedConfirms[i] === true; lab.htmlFor = id;
      lab.appendChild(inp); lab.appendChild(el("span", null, c)); sc.appendChild(lab); confirmBoxes.push(inp);
    });
    form.appendChild(sc);

    var actions = el("div", "desk-actions");
    var submit = btn(stage.submitLabel || C.composeSubmit); submit.type = "submit";
    var help = el("p", "desk-hint"); help.id = nid("help"); submit.setAttribute("aria-describedby", help.id);
    var attemptsNote = el("span", "desk-attempts");
    actions.appendChild(submit); actions.appendChild(help); actions.appendChild(attemptsNote);
    form.appendChild(actions);
    var fbHost = el("div", "desk-fb-host"); fbHost.setAttribute("aria-live", "polite");
    var evHost = el("div", "desk-evidence-host");
    host.appendChild(form); host.appendChild(fbHost); host.appendChild(evHost);

    function readValues(){
      var v = {};
      Object.keys(inputs).forEach(function(k){
        var it = inputs[k];
        if(it.f.type === "multi") v[k] = it.ctrl.filter(function(c){ return c.checked; }).map(function(c){ return c.value; }).sort();
        else v[k] = it.ctrl.value;
      });
      return v;
    }
    function setConfirms(arr){ confirmBoxes.forEach(function(c, i){ c.checked = arr[i] === true; }); store.draft(ctx.taskId, stage.id + ":confirms", confirmBoxes.map(function(c){ return c.checked; })); }
    function refresh(){
      var allOpen = tracker.ready(allRecIds);
      evItems.forEach(function(it){
        var ok = tracker.isOpened(it.id);
        it.li.textContent = (ok ? "✓ " : "○ ") + call(C.selfCheckOpened, nameOf(it.id), tracker.recheck.indexOf(it.id) !== -1);
        it.li.className = ok ? "is-done" : "";
      });
      Object.keys(groupEls).forEach(function(gid){
        var g = groupEls[gid], open = tracker.ready(g.recIds);
        g.gate.hidden = open || locked;
        g.gate.textContent = tracker.recheck.some(function(id){ return g.recIds.indexOf(id) !== -1; }) ? C.groupGateRecheck : C.groupGateOpen;
        stage.fields.filter(function(f){ return f.group === gid; }).forEach(function(f){
          var c = inputs[f.id].ctrl, dis = locked || !open;
          if(Array.isArray(c)) c.forEach(function(x){ x.disabled = dis; });
          else if(c.tagName === "TEXTAREA") c.readOnly = dis; else c.disabled = dis;
          if(c.tagName === "TEXTAREA") c.setAttribute("aria-disabled", dis ? "true" : "false");
        });
      });
      confirmBoxes.forEach(function(c){ c.disabled = locked || !allOpen; });
      confirmHint.textContent = allOpen ? C.confirmReady : C.confirmLocked;
      if(locked){ help.style.display = "none"; return; }
      var confirmed = confirmBoxes.every(function(c){ return c.checked; });
      submit.disabled = !(allOpen && confirmed);
      help.style.display = submit.disabled ? "block" : "none";
      help.textContent = !allOpen ? C.composeGateOpen : C.composeGateConfirm;
    }
    form.addEventListener("input", onEdit);
    form.addEventListener("change", function(e){
      if(confirmBoxes.indexOf(e.target) !== -1){ store.draft(ctx.taskId, stage.id + ":confirms", confirmBoxes.map(function(c){ return c.checked; })); staleNote.hidden = true; refresh(); return; }
      onEdit(e);
    });
    function onEdit(e){
      if(confirmBoxes.indexOf(e.target) !== -1) return;
      store.draft(ctx.taskId, stage.id + ":v", readValues());          /* saved on every keystroke */
      if(confirmBoxes.some(function(c){ return c.checked; })){
        setConfirms([]);
        staleNote.hidden = false;
        staleNote.textContent = C.staleConfirm;
      }
      refresh();
    }
    window.addEventListener("pagehide", function(){ if(!locked) store.draft(ctx.taskId, stage.id + ":v", readValues()); });
    tracker.onChange(refresh);

    function setLocked(lock){ locked = lock; submit.style.display = lock ? "none" : ""; refresh(); }
    function clearMarks(){
      Object.keys(inputs).forEach(function(k){ inputs[k].err.hidden = true; inputs[k].err.textContent = ""; var c = inputs[k].ctrl; if(!Array.isArray(c)) c.removeAttribute("aria-invalid"); });
      Object.keys(groupEls).forEach(function(g){ groupEls[g].note.hidden = true; groupEls[g].box.classList.remove("is-flag"); });
    }
    function show(ans, res, fromLoad, st){
      fbHost.innerHTML = ""; clearMarks();
      if(res.pass){
        var b = fbBlock(true, stage.passTitle || C.composePassTitle);
        if(stage.passWhy){ var dl = el("dl", "desk-fb-dl"); fbRow(dl, C.whyItWorks, stage.passWhy); b.box.appendChild(dl); }
        var edit = btn(C.revise, "btn-ghost");
        edit.addEventListener("click", function(){
          store.unpass(ctx.taskId, stage.id);
          fbHost.innerHTML = ""; evHost.innerHTML = "";
          setConfirms([]); setLocked(false); ctx.onChange();
        });
        b.box.appendChild(edit);
        fbHost.appendChild(b.box);
        setLocked(true);
        if(stage.evidence) renderWorkSample(evHost, stage, ans, res, ctx);
        if(!fromLoad) b.title.focus();
        return;
      }
      var b2 = fbBlock(false, C.composeFailTitle);
      var ul = el("ul", "desk-fb-list");
      res.problems.forEach(function(p){
        ul.appendChild(el("li", null, p.msg));
        if(p.field && inputs[p.field]){
          var it = inputs[p.field];
          it.err.textContent = (it.err.textContent ? it.err.textContent + " " : "") + p.msg.replace(/^[^:]*:\s*/, "");
          it.err.hidden = false;
          if(!Array.isArray(it.ctrl)) it.ctrl.setAttribute("aria-invalid", "true");
        } else if(p.group && groupEls[p.group]){
          groupEls[p.group].note.hidden = false; groupEls[p.group].note.textContent = p.msg; groupEls[p.group].box.classList.add("is-flag");
        }
      });
      if(!res.confirmsDone) ul.appendChild(el("li", null, C.msgSelfCheck));
      b2.box.appendChild(ul);
      if(stage.failWhy){ var dl2 = el("dl", "desk-fb-dl"); fbRow(dl2, C.whyMatters, stage.failWhy); b2.box.appendChild(dl2); }
      if(desk.shouldPause(st) && res.badGroups.length){
        var ids = [];
        res.badGroups.forEach(function(gid){ groupEls[gid].recIds.forEach(function(i){ if(ids.indexOf(i) === -1) ids.push(i); }); });
        tracker.requireRecheck(ids);
        pausePanel(b2.box, tracker, ids, nameOf, st.attempts, C);
      }
      b2.box.appendChild(el("p", "desk-hint", C.confirmCleared));
      fbHost.appendChild(b2.box);
      setConfirms([]); refresh();
      if(!fromLoad) b2.title.focus();
    }
    submit.addEventListener("click", function(){
      if(submit.disabled || !tracker.ready(allRecIds)) return;
      var ans = { values: readValues(), confirms: confirmBoxes.map(function(c){ return c.checked; }) };
      store.draft(ctx.taskId, stage.id + ":v", ans.values);
      var res = desk.evaluate(stage, ans);
      var st = store.attempt(ctx.taskId, stage.id, ans, res.pass);
      attemptsNote.textContent = st.attempts > 1 ? "Attempt " + st.attempts : "";
      show(ans, res, false, st); ctx.onChange();
    });

    var saved = store.get(ctx.taskId).stages[stage.id];
    if(saved && saved.answer && desk.evaluate(stage, saved.answer).pass){
      var a = saved.answer;
      Object.keys(inputs).forEach(function(k){
        var it = inputs[k], v = a.values[k];
        if(Array.isArray(it.ctrl)) it.ctrl.forEach(function(c){ c.checked = (v || []).indexOf(c.value) !== -1; });
        else it.ctrl.value = v || "";
      });
      confirmBoxes.forEach(function(c){ c.checked = true; });
      show(a, desk.evaluate(stage, a), true);
    }
    refresh();
  });

  /* ---------------- earned work sample ----------------
     Built only from a passing answer: validated learner state -> generator -> sample.
     Title, requester and field headings come from the stage's `evidence` block;
     the company line and simulated date come from module config. */
  function workSampleText(stage, ans, res, desk){
    var C = Core.assign({}, UI_COPY, desk.copy), ev = stage.evidence, cfg = desk.config, sample = cfg.sample || {}, lines = [];
    lines.push(C.sampleHeader);
    lines.push(ev.title);
    lines.push(sample.companyLine || C.sampleCompanyLine);
    lines.push(call(C.sampleDateLine, cfg.simDate || "", ev.requestedBy));
    lines.push("");
    stage.groups.forEach(function(g){
      lines.push(g.sampleHead || g.title);
      stage.fields.filter(function(f){ return f.group === g.id; }).forEach(function(f){
        var v = ans.values[f.id], out;
        if(f.type === "number"){ var nv = Core.normalizeNumber(v, f); out = nv.ok ? (f.unit === "$" ? "$" + nv.value : nv.value + (f.unit ? " " + f.unit : "")) : String(v || "").trim(); }
        else if(f.type === "select") out = (f.options.filter(function(o){ return o.value === v; })[0] || {}).label || "";
        else if(f.type === "multi") out = (v || []).map(function(x){ return (f.options.filter(function(o){ return o.value === x; })[0] || {}).label; }).join("; ") || "None";
        else out = String(v || "").trim();
        lines.push("  " + (f.sampleLabel || f.label) + ": " + out);
      });
      lines.push("");
    });
    lines.push(C.sampleFooter);
    if(res && res.humanReview) lines.push(C.sampleHumanReview);
    return lines.join("\n");
  }
  function renderWorkSample(host, stage, ans, res, ctx){
    host.innerHTML = "";
    var C = copyOf(ctx), ev = stage.evidence, text = workSampleText(stage, ans, res, ctx.desk);
    var box = el("section", "desk-evidence"); box.setAttribute("aria-label", C.sampleAria);
    box.appendChild(el("div", "ws-preview-label", ev.badge || C.sampleBadge));
    box.appendChild(el("p", "desk-hint", ev.note));
    var pre = el("pre", "ws-preview", text); pre.tabIndex = 0; pre.setAttribute("aria-label", C.sampleTextAria);
    box.appendChild(pre);
    var row = el("div", "desk-actions");
    var copyBtn = btn(C.copySample, "btn-ghost"), dl = btn(C.downloadSample, "btn-ghost");
    var msg = el("span", "desk-attempts"); msg.setAttribute("aria-live", "polite");
    copyBtn.addEventListener("click", function(){
      if(navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(function(){ msg.textContent = C.copied; }, function(){ msg.textContent = C.copyFailed; });
      else msg.textContent = C.copyManual;
    });
    dl.addEventListener("click", function(){
      var a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([text], { type: "text/plain" }));
      a.download = ev.filename || C.sampleFilename;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(function(){ URL.revokeObjectURL(a.href); }, 1000);
    });
    row.appendChild(copyBtn); row.appendChild(dl); row.appendChild(msg);
    box.appendChild(row); host.appendChild(box);
  }

  function renderStage(host, stage, ctx){
    host.innerHTML = "";
    var r = renderers[stage.type];
    if(!r) throw new Error("PVADeskUI: no renderer for stage type '" + stage.type + "'");
    return r(host, stage, ctx);
  }

  root.PVADeskUI = {
    UI_COPY: UI_COPY,
    renderBrief: renderBrief, renderStage: renderStage,
    registerRenderer: registerRenderer, registerEvidenceKind: registerEvidenceKind, evidenceKinds: evidenceKinds,
    evidenceCard: evidenceCard, gatedIds: gatedIds, Tracker: Tracker, workSampleText: workSampleText
  };
})(typeof self !== "undefined" ? self : this);
