/* PVA Free Training -- E-commerce VA Foundations
   Operations Desk engine (Module 4 pilot) -- v2 (repair cycle 1).

   Task types:
     decision  -- open the records, select what you noticed, choose an action
     triage    -- open each record in a batch, classify it from its evidence
     sequence  -- open the source record, put events in order (keyboard-operable)
     compose   -- structured operational documentation + a short written note,
                  self-checked, producing a work sample

   Learning-integrity mechanics
   - Evidence cards: records start closed. Opening one is recorded. Decisions,
     classifications and written entries are gated on the relevant evidence
     having been opened in this stage (lightweight -- "opened", not "read").
   - Self-check: evidence-review items are satisfied by opening the evidence,
     not by ticking. The remaining judgement confirmations can only be ticked
     once the evidence is open, and are cleared whenever the work changes.
   - Pause and re-check: from the second failed attempt on a stage, the
     evidence behind the mistake closes again and must be re-opened before
     another attempt. No scoring, no lives.
   - Feedback points to principles and where to look -- never the answer.
   - Task data ships encoded; answer keys are salted hashes; completion is
     re-derived from stored answers on every load (no "completed" flag).
   - Client-side code can still be reversed with dev tools. The aim is that
     the normal path requires the work.

   Storage: own key ("pva-ecom-ft-m4-desk"). The shared progress key is only
   written via the existing PVAEcom.markLessonDone(), from the page controller. */

(function(){
  var SALT = "everfield-desk-v1";
  var STORE_KEY = "pva-ecom-ft-m4-desk";
  var XOR_KEY = "EverfieldOpsDesk";

  /* ---------------- encoding / hashing ---------------- */
  function decode(b64){
    var bin = atob(b64);
    var bytes = new Uint8Array(bin.length);
    for(var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i) ^ XOR_KEY.charCodeAt(i % XOR_KEY.length);
    return JSON.parse(new TextDecoder("utf-8").decode(bytes));
  }
  function h(str){
    var s = SALT + "|" + str, x = 0x811c9dc5;
    for(var i = 0; i < s.length; i++){ x ^= s.charCodeAt(i); x = Math.imul(x, 0x01000193) >>> 0; }
    return ("0000000" + x.toString(16)).slice(-8);
  }
  function isFindingRight(sid, f){ return f.k === h(sid + "|f|" + f.id + "|1"); }
  function isOptionRight(sid, o){ return o.k === h(sid + "|o|" + o.id + "|1"); }
  function isRowRight(sid, row, c){ return !!c && row.k === h(sid + "|row|" + row.id + "|" + c); }
  function seqPosKey(sid, id, pos){ return h(sid + "|seq|" + id + "|" + pos); }
  function multiKey(v){ return (v || []).slice().sort().join(","); }
  function isFieldValueRight(sid, f, v){
    var key = f.type === "multi" ? multiKey(v) : String(v || "");
    return (f.acc || []).indexOf(h(sid + "|fld|" + f.id + "|" + key)) !== -1;
  }
  function rid(rec){ return rec.id || rec.title || rec.label; }

  /* ---------------- storage ---------------- */
  function readAll(){
    try{
      var raw = window.localStorage.getItem(STORE_KEY);
      var s = raw ? JSON.parse(raw) : null;
      if(!s || typeof s !== "object" || !s.tasks) s = { v: 1, tasks: {} };
      return s;
    }catch(e){ return { v: 1, tasks: {} }; }
  }
  function writeAll(s){ try{ window.localStorage.setItem(STORE_KEY, JSON.stringify(s)); }catch(e){} }
  function taskRec(s, taskId){
    if(!s.tasks[taskId]) s.tasks[taskId] = { views: 0, stages: {}, drafts: {} };
    var t = s.tasks[taskId]; t.stages = t.stages || {}; t.drafts = t.drafts || {};
    return t;
  }
  var Store = {
    get: function(taskId){ return taskRec(readAll(), taskId); },
    touch: function(taskId){
      var s = readAll(), t = taskRec(s, taskId);
      t.views = (t.views || 0) + 1;
      if(!t.firstViewed) t.firstViewed = new Date().toISOString();
      t.lastViewed = new Date().toISOString();
      writeAll(s);
    },
    attempt: function(taskId, stageId, answer, pass){
      var s = readAll(), t = taskRec(s, taskId);
      var st = t.stages[stageId] || { attempts: 0 };
      st.attempts = (st.attempts || 0) + 1;
      st.last = answer;
      if(pass){
        st.answer = answer;
        if(st.firstTry === undefined) st.firstTry = (st.attempts === 1);
        st.passedAt = st.passedAt || new Date().toISOString();
      } else {
        st.fails = (st.fails || 0) + 1;
      }
      t.stages[stageId] = st;
      writeAll(s);
      return st;
    },
    draft: function(taskId, key, value){
      var s = readAll(), t = taskRec(s, taskId);
      if(value === undefined) delete t.drafts[key]; else t.drafts[key] = value;
      writeAll(s);
    },
    getDraft: function(taskId, key){ return taskRec(readAll(), taskId).drafts[key]; },
    unpass: function(taskId, stageId){
      var s = readAll(), t = taskRec(s, taskId);
      if(t.stages[stageId]){ delete t.stages[stageId].answer; delete t.stages[stageId].passedAt; }
      writeAll(s);
    }
  };

  /* ---------------- text helpers ---------------- */
  function normalize(t){ return " " + String(t || "").toLowerCase().replace(/[‘’]/g, "'").replace(/\s+/g, " ") + " "; }
  function hasAny(text, tokens){
    var n = normalize(text);
    return (tokens || []).some(function(tok){
      if(tok.indexOf("re:") === 0) return new RegExp(tok.slice(3), "i").test(n);
      return n.indexOf(tok.toLowerCase()) !== -1;
    });
  }
  function words(t){ return String(t || "").trim().split(/\s+/).filter(function(w){ return /[a-z0-9]/i.test(w); }); }
  function wordSet(t){ var o = {}; normalize(t).replace(/[^a-z0-9#\- ]/g, " ").split(" ").forEach(function(w){ if(w.length > 2) o[w] = 1; }); return o; }
  function similarity(a, b){
    var A = wordSet(a), B = wordSet(b), inter = 0, uni = 0, k;
    for(k in A){ uni++; if(B[k]) inter++; }
    for(k in B){ if(!A[k]) uni++; }
    return uni ? inter / uni : 0;
  }
  function looksMeaningless(t){
    var s = String(t || "").trim();
    if(!s) return true;
    if(/(.)\1{5,}/.test(s)) return true;
    var letters = s.replace(/[^a-z]/gi, "");
    if(letters.length < 8) return true;
    var u = {}; letters.toLowerCase().split("").forEach(function(c){ u[c] = 1; });
    if(Object.keys(u).length < 6) return true;
    var w = words(s).map(function(x){ return x.toLowerCase(); });
    var uw = {}; w.forEach(function(x){ uw[x] = 1; });
    return w.length >= 6 && Object.keys(uw).length / w.length < 0.5;   /* repeated filler */
  }
  var FUNCTION_WORDS = " the a an is are was were has have had to of in on at by for with and or but not no since it its this that they them their we our be been will can so as from before after until about there it's isn't hasn't haven't we've they've ";
  function functionWordRatio(t){
    var w = words(t).map(function(x){ return x.toLowerCase().replace(/[^a-z']/g, ""); }).filter(Boolean);
    if(!w.length) return 0;
    return w.filter(function(x){ return FUNCTION_WORDS.indexOf(" " + x + " ") !== -1; }).length / w.length;
  }
  function sentenceCount(t){ return String(t || "").split(/[.!?](\s|$)/).filter(function(s){ return words(s).length >= 3; }).length; }

  /* ---------------- evaluation ---------------- */
  function evaluate(stage, answer){
    try{ return evaluateInner(stage, answer); }catch(e){ return { pass: false }; }
  }
  function evaluateInner(stage, answer){
    if(!answer) return { pass: false };
    var sid = stage.id;
    if(stage.type === "decision"){
      var picked = answer.f || [], missed = [], wrongPicked = [];
      (stage.findings || []).forEach(function(f){
        var right = isFindingRight(sid, f), sel = picked.indexOf(f.id) !== -1;
        if(right && !sel) missed.push(f);
        if(!right && sel) wrongPicked.push(f);
      });
      var opt = null, optRight = true;
      if(stage.options && stage.options.length){
        opt = stage.options.filter(function(o){ return o.id === answer.o; })[0] || null;
        optRight = !!opt && isOptionRight(sid, opt);
      }
      return { pass: optRight && !missed.length && !wrongPicked.length, missed: missed, wrongPicked: wrongPicked, option: opt, optRight: optRight };
    }
    if(stage.type === "triage"){
      var wrongRows = stage.rows.filter(function(r){ return !isRowRight(sid, r, answer[r.id]); });
      return { pass: !wrongRows.length, wrongRows: wrongRows };
    }
    if(stage.type === "sequence"){
      var order = answer.order || [], firstWrong = -1;
      if(order.length !== stage.items.length) firstWrong = 0;
      else for(var i = 0; i < order.length; i++){
        var it = stage.items.filter(function(x){ return x.id === order[i]; })[0];
        if(!it || it.k.indexOf(seqPosKey(sid, it.id, i)) === -1){ firstWrong = i; break; }
      }
      return { pass: firstWrong === -1, firstWrong: firstWrong };
    }
    if(stage.type === "compose"){
      var vals = answer.values || {}, problems = [], badGroups = {}, fieldMsgGroups = {};
      stage.fields.forEach(function(f){
        var v = vals[f.id];
        if(f.type === "select" || f.type === "multi"){
          if(f.type === "select" && !v){ problems.push({ group: f.group, field: f.id, msg: f.label + ": choose an option." }); return; }
          if(!isFieldValueRight(sid, f, v)){
            badGroups[f.group] = true;
            if(f.msg){ problems.push({ group: f.group, field: f.id, msg: f.label + ": " + f.msg }); fieldMsgGroups[f.group] = true; }
          }
          return;
        }
        /* text */
        var text = v || "", minW = f.minWords || 6;
        if(!String(text).trim() || words(text).length < minW || (minW >= 4 && looksMeaningless(text))){
          problems.push({ group: f.group, field: f.id, msg: f.label + ": write at least " + minW + " real words, in sentences, that a teammate could act on." }); return;
        }
        if(minW >= 8 && functionWordRatio(text) < 0.15){
          problems.push({ group: f.group, field: f.id, msg: f.label + ": this reads like a list of keywords. Write it as plain sentences a teammate could read aloud." }); return;
        }
        if(f.minSentences && sentenceCount(text) < f.minSentences){
          problems.push({ group: f.group, field: f.id, msg: f.label + ": write it as " + f.minSentences + " or more complete sentences -- not a list of keywords." }); return;
        }
        (f.rules || []).forEach(function(r){ if(!hasAny(text, r.any)) problems.push({ group: f.group, field: f.id, msg: f.label + ": " + r.msg }); });
        (f.when || []).forEach(function(r){
          var other = vals[r.field], applies = r.eq !== undefined ? other === r.eq : r.ne !== undefined ? (!!other && other !== r.ne) : false;
          if(!applies) return;
          if(r.any && !hasAny(text, r.any)) problems.push({ group: f.group, field: f.id, msg: f.label + ": " + r.msg });
          if(r.notAny && hasAny(text, r.notAny)) problems.push({ group: f.group, field: f.id, msg: f.label + ": " + r.msg });
        });
        (stage.banned || []).forEach(function(b){ if(hasAny(text, b.any)) problems.push({ group: f.group, field: f.id, msg: f.label + ": " + b.msg }); });
        if(stage.example && similarity(text, stage.example.text) > 0.55){
          problems.push({ group: f.group, field: f.id, msg: f.label + ": this reads very close to the example. Write it for this record, in your own words." });
        }
      });
      (stage.groups || []).forEach(function(g){
        if(badGroups[g.id] && !fieldMsgGroups[g.id]) problems.unshift({ group: g.id, msg: g.title + ": something in this entry doesn't hold up against the record yet. " + g.hint });
      });
      var confirms = answer.confirms || [];
      var confirmsDone = (stage.confirm || []).every(function(_, i){ return confirms[i] === true; });
      return { pass: !problems.length && confirmsDone, problems: problems, badGroups: Object.keys(badGroups), confirmsDone: confirmsDone };
    }
    return { pass: false };
  }

  function stagePassed(taskId, stage, rec){
    var t = rec || Store.get(taskId), st = t.stages[stage.id];
    return !!(st && st.answer && evaluate(stage, st.answer).pass);
  }
  function taskStatus(task){
    var t = Store.get(task.id);
    var passed = task.stages.filter(function(s){ return stagePassed(task.id, s, t); }).length;
    var attempted = task.stages.some(function(s){ return t.stages[s.id] && t.stages[s.id].attempts > 0; });
    var ev = task.stages.some(function(s){ return s.type === "compose" && s.evidence; });
    var level = "new";
    if(t.views) level = "viewed";
    if(attempted) level = "attempted";
    if(passed === task.stages.length) level = ev ? "evidence" : "practiced";
    return { level: level, passed: passed, total: task.stages.length, hasEvidence: ev };
  }

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
  function clock(host, now){
    if(!now) return;
    var c = el("p", "desk-clock");
    c.appendChild(el("span", "desk-tag desk-tag-soft", "Now"));
    c.appendChild(document.createTextNode(" " + now));
    host.appendChild(c);
  }

  function renderBrief(host, brief, team){
    var who = team[brief.from] || { name: brief.from, role: "" };
    var box = el("article", "desk-msg desk-brief");
    box.setAttribute("aria-label", "Work request from " + who.name);
    var head = el("div", "desk-msg-head"); head.appendChild(el("span", "desk-tag", "Work request"));
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

  function recordBody(rec){
    var frag = document.createDocumentFragment();
    if(rec.kind === "message"){
      var meta = el("dl", "desk-msg-meta");
      (rec.meta || []).forEach(function(p){ meta.appendChild(el("dt", null, p[0])); meta.appendChild(el("dd", null, p[1])); });
      frag.appendChild(meta);
      var b = el("div", "desk-msg-body");
      rec.body.forEach(function(p){ b.appendChild(el("p", null, p)); });
      frag.appendChild(b);
      return frag;
    }
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

  /* ---------------- evidence tracking (per stage) ---------------- */
  function Tracker(taskId, stageId){
    var self = this;
    this.taskId = taskId; this.stageId = stageId;
    this.opened = (Store.getDraft(taskId, stageId + ":opened") || []).slice();
    this.recheck = (Store.getDraft(taskId, stageId + ":recheck") || []).slice();
    this.cards = {}; this.listeners = [];
    this.save = function(){
      Store.draft(taskId, stageId + ":opened", self.opened);
      Store.draft(taskId, stageId + ":recheck", self.recheck.length ? self.recheck : undefined);
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

  /* An evidence card: title + Open/Hide toggle; the body stays closed until opened.
     `footer` (optional) is always visible -- used for triage selects. */
  function evidenceCard(rec, tracker, opts){
    opts = opts || {};
    var id = rid(rec);
    var card = el("section", "desk-record desk-evidence-card" + (rec.kind === "message" ? " desk-ev-message" : ""));
    var head = el("div", "desk-ev-head");
    var titleWrap = el("div", "desk-ev-titlewrap");
    if(rec.kind === "message") titleWrap.appendChild(el("span", "desk-tag desk-tag-soft", rec.label || "Message"));
    var title = el("h4", "desk-record-title", rec.kind === "message" ? (rec.meta && rec.meta[0] ? rec.meta[0][1] : "") : rec.title);
    titleWrap.appendChild(title);
    var chip = el("span", "desk-ev-chip");
    var toggle = btn("Open", "btn-ghost");
    var bodyId = nid("evb");
    toggle.setAttribute("aria-controls", bodyId);
    head.appendChild(titleWrap); head.appendChild(chip); head.appendChild(toggle);
    card.appendChild(head);
    var body = el("div", "desk-ev-body"); body.id = bodyId;
    body.appendChild(recordBody(rec));
    card.appendChild(body);
    if(opts.footer) card.appendChild(opts.footer);
    var label = rec.kind === "message" ? (rec.label || "message").toLowerCase() : (rec.title || "record");

    function sync(){
      var expanded = !body.hidden;
      toggle.textContent = expanded ? "Hide" : (tracker.recheck.indexOf(id) !== -1 ? "Re-open " : "Open ") + label;
      toggle.setAttribute("aria-expanded", expanded ? "true" : "false");
      var re = tracker.recheck.indexOf(id) !== -1;
      chip.textContent = re ? "Re-check" : tracker.isOpened(id) ? "✓ Reviewed" : "Not opened";
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

  function evidenceGrid(host, records, tracker){
    var grid = el("div", "desk-records");
    records.forEach(function(r){ grid.appendChild(evidenceCard(r, tracker, { startOpen: true })); });
    host.appendChild(grid);
  }

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

  /* Pause-and-re-check panel. Returns an updater. */
  function pausePanel(host, tracker, ids, nameOf, attempts){
    var box = el("div", "desk-pause");
    box.setAttribute("role", "note");
    box.appendChild(el("p", "desk-pause-title", "Pause and re-check"));
    box.appendChild(el("p", null, "You've tried this " + attempts + " times. Before trying again, re-open the evidence below and look at it with the feedback in mind:"));
    var ul = el("ul", "desk-pause-list");
    var items = ids.map(function(id){ var li = el("li", null, nameOf(id)); ul.appendChild(li); return { id: id, li: li }; });
    box.appendChild(ul);
    host.appendChild(box);
    function sync(){ items.forEach(function(it){ var ok = tracker.isOpened(it.id); it.li.classList.toggle("is-done", ok); it.li.textContent = (ok ? "✓ " : "") + nameOf(it.id); }); }
    tracker.onChange(sync); sync();
  }
  function recName(records){ var m = {}; records.forEach(function(r){ m[rid(r)] = r.kind === "message" ? (r.label + (r.meta && r.meta[0] ? " (" + r.meta[0][1] + ")" : "")) : r.title; }); return function(id){ return m[id] || id; }; }

  /* ---------------- DECISION ---------------- */
  function renderDecision(host, stage, ctx){
    var tracker = new Tracker(ctx.taskId, stage.id);
    var ids = (stage.records || []).map(rid);
    if(stage.intro) host.appendChild(el("p", "desk-intro", stage.intro));
    clock(host, stage.now);
    evidenceGrid(host, stage.records || [], tracker);

    var form = el("form", "desk-form"); form.noValidate = true;
    form.addEventListener("submit", function(e){ e.preventDefault(); });
    var fsF = el("fieldset", "desk-fieldset");
    fsF.appendChild(el("legend", null, stage.findingsPrompt));
    fsF.appendChild(el("p", "desk-hint", "Select everything the evidence supports -- and nothing it doesn't."));
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
    var submit = btn(stage.submitLabel || (oInputs.length ? "Make your decision" : "Submit your review")); submit.type = "submit";
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
      if(retryBtn){
        var ok = tracker.ready(ids);
        retryBtn.disabled = !ok;
      }
      if(locked) return;
      var a = current(), opened = tracker.ready(ids), picked = a.f.length > 0 && (!oInputs.length || !!a.o);
      submit.disabled = !(opened && picked);
      help.style.display = submit.disabled ? "block" : "none";
      help.textContent = !opened ? (tracker.recheck.length ? "Re-open the evidence marked Re-check first." : "Open each record before you decide (" + tracker.count(ids) + " of " + ids.length + " opened).")
                                 : (oInputs.length ? "Select at least one finding and one action." : "Select at least one item.");
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
    form.addEventListener("change", function(){ Store.draft(ctx.taskId, stage.id + ":sel", current()); refresh(); });
    tracker.onChange(refresh);

    function showPass(res, fromLoad){
      fbHost.innerHTML = ""; retryBtn = null;
      var b = fbBlock(true, stage.passTitle || "Good call -- that's the right read.");
      var dl = el("dl", "desk-fb-dl");
      if(res.option) fbRow(dl, "Your decision", res.option.text);
      fbRow(dl, "Why it works", (res.option && res.option.why) || stage.passWhy || "");
      if(stage.takeaway) fbRow(dl, "Habit to keep", stage.takeaway);
      b.box.appendChild(dl); fbHost.appendChild(b.box);
      setLocked(true);
      if(!fromLoad) b.title.focus();
    }
    function showFail(res, st){
      fbHost.innerHTML = "";
      var b = fbBlock(false, "Not yet -- go back to the evidence.");
      var dl = el("dl", "desk-fb-dl");
      if(res.option) fbRow(dl, "Your decision", res.option.text);
      if(res.missed.length || res.wrongPicked.length){
        var ul = el("ul", "desk-fb-list");
        if(res.missed.length){
          ul.appendChild(el("li", null, "Your read of the record leaves out " + res.missed.length + " thing" + (res.missed.length > 1 ? "s" : "") + " the evidence supports. Where to look:"));
          res.missed.forEach(function(f){ ul.appendChild(el("li", "desk-fb-sub", f.miss)); });
        }
        res.wrongPicked.forEach(function(f){
          var li = el("li");
          li.appendChild(el("strong", null, "You selected “" + f.text.replace(/[.\s]+$/, "") + "”. "));
          li.appendChild(document.createTextNode(f.wrong)); ul.appendChild(li);
        });
        fbRow(dl, "What you missed", ul);
      }
      var why;
      if(res.option && !res.optRight) why = res.option.why;
      else if(res.option) why = "Your chosen action may be reasonable, but your read of the evidence isn't complete. " + (stage.findingsWhy || "A good action for the wrong reasons won't hold up on the next order.");
      else why = stage.findingsWhy || "Check the draft against each part of the format, one at a time.";
      if(why) fbRow(dl, "Why this matters", why);
      b.box.appendChild(dl);
      if(st.fails >= 2){
        tracker.requireRecheck(ids);
        pausePanel(b.box, tracker, ids, recName(stage.records || []), st.attempts);
      }
      retryBtn = btn("Reconsider and try again", "btn-ghost");
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
      var ans = current(), res = evaluate(stage, ans);
      var st = Store.attempt(ctx.taskId, stage.id, ans, res.pass);
      attemptsNote.textContent = st.attempts > 1 ? "Attempt " + st.attempts : "";
      if(res.pass) showPass(res, false); else showFail(res, st);
      ctx.onChange();
    });

    var saved = Store.get(ctx.taskId).stages[stage.id];
    if(saved && saved.answer && evaluate(stage, saved.answer).pass){ restore(saved.answer); showPass(evaluate(stage, saved.answer), true); }
    else {
      var d = Store.getDraft(ctx.taskId, stage.id + ":sel") || (saved && saved.last);
      if(d) restore(d);
      if(saved && saved.attempts > 1) attemptsNote.textContent = "Attempt " + (saved.attempts + 1);
    }
    refresh();
  }

  /* ---------------- TRIAGE ---------------- */
  function renderTriage(host, stage, ctx){
    var tracker = new Tracker(ctx.taskId, stage.id);
    if(stage.intro) host.appendChild(el("p", "desk-intro", stage.intro));
    clock(host, stage.now);
    var form = el("form", "desk-form"); form.addEventListener("submit", function(e){ e.preventDefault(); });
    var list = el("div", "desk-records desk-triage");
    var selects = {}, notes = {}, cards = {}, locked = false;
    var draft = Store.getDraft(ctx.taskId, stage.id + ":sel") || {};
    stage.rows.forEach(function(r){
      var foot = el("div", "desk-triage-pick");
      var sid = nid("sel"), lab = el("label", "desk-select-label", stage.prompt + " — " + (r.title || r.id));
      lab.htmlFor = sid;
      var sel = document.createElement("select"); sel.id = sid; sel.className = "desk-select";
      var o0 = el("option", null, "Choose…"); o0.value = ""; sel.appendChild(o0);
      stage.choices.forEach(function(c){ var o = el("option", null, c.label); o.value = c.id; sel.appendChild(o); });
      var note = el("p", "desk-row-note"); note.id = nid("note"); note.hidden = true;
      var gate = el("p", "desk-hint desk-gate"); gate.id = nid("gate");
      sel.setAttribute("aria-describedby", note.id + " " + gate.id);
      foot.appendChild(lab); foot.appendChild(sel); foot.appendChild(gate); foot.appendChild(note);
      var card = evidenceCard(r, tracker, { footer: foot, startOpen: true });
      card.classList.add("desk-triage-row");
      list.appendChild(card);
      sel.value = draft[r.id] || "";
      selects[r.id] = sel; notes[r.id] = note; cards[r.id] = { card: card, gate: gate };
    });
    form.appendChild(list);
    var actions = el("div", "desk-actions");
    var submit = btn(stage.submitLabel || "Submit your review"); submit.type = "submit";
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
        cards[k].gate.textContent = open ? "" : (tracker.recheck.indexOf(k) !== -1 ? "Re-open this record to change your call." : "Open the record to make a call.");
        cards[k].gate.hidden = open || locked;
      });
      if(locked) return;
      var a = current(), allSet = Object.keys(a).every(function(k){ return !!a[k]; }), opened = tracker.ready(Object.keys(selects));
      submit.disabled = !(allSet && opened);
      help.style.display = submit.disabled ? "block" : "none";
      help.textContent = !opened ? "Open every record and make a call on each (" + tracker.count(Object.keys(selects)) + " of " + stage.rows.length + " opened)." : "Make a call on every " + (stage.rowNounOne || "order") + " first.";
    }
    form.addEventListener("change", function(e){
      Object.keys(selects).forEach(function(k){
        if(selects[k] === e.target){ notes[k].hidden = true; e.target.removeAttribute("aria-invalid"); cards[k].card.classList.remove("is-flag", "is-ok"); }
      });
      Store.draft(ctx.taskId, stage.id + ":sel", current());
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
        if(wrong){ notes[r.id].textContent = "Look again: " + r.hint; selects[r.id].setAttribute("aria-invalid", "true"); }
        else selects[r.id].removeAttribute("aria-invalid");
      });
      if(res.pass){
        locked = true;
        var b = fbBlock(true, "Reviewed -- every call holds up.");
        var dl = el("dl", "desk-fb-dl");
        if(stage.passWhy) fbRow(dl, "Why this matters", stage.passWhy);
        if(stage.takeaway) fbRow(dl, "Habit to keep", stage.takeaway);
        b.box.appendChild(dl); fbHost.appendChild(b.box);
        submit.style.display = "none"; help.style.display = "none";
        refresh();
        if(!fromLoad) b.title.focus();
        return;
      }
      var n = res.wrongRows.length;
      var b2 = fbBlock(false, n + " of " + stage.rows.length + " " + (stage.rowNoun || "orders") + " need another look.");
      b2.box.appendChild(el("p", null, "Each flagged " + (stage.rowNounOne || "order") + " has a note pointing to the evidence to re-read. Calls that hold up are marked ✓."));
      if(st && st.fails >= 2){
        var ids = res.wrongRows.map(function(r){ return r.id; });
        tracker.requireRecheck(ids);
        pausePanel(b2.box, tracker, ids, function(id){ var r = stage.rows.filter(function(x){ return x.id === id; })[0]; return r.title || id; }, st.attempts);
      }
      fbHost.appendChild(b2.box);
      refresh();
      if(!fromLoad) b2.title.focus();
    }
    submit.addEventListener("click", function(){
      if(submit.disabled || !tracker.ready(Object.keys(selects))) return;
      var ans = current(), res = evaluate(stage, ans);
      var st = Store.attempt(ctx.taskId, stage.id, ans, res.pass);
      attemptsNote.textContent = st.attempts > 1 ? "Attempt " + st.attempts : "";
      showResult(res, false, st);
      ctx.onChange();
    });
    var saved = Store.get(ctx.taskId).stages[stage.id];
    if(saved && saved.answer && evaluate(stage, saved.answer).pass){
      Object.keys(selects).forEach(function(k){ selects[k].value = saved.answer[k] || ""; });
      showResult(evaluate(stage, saved.answer), true);
    }
    refresh();
  }

  /* ---------------- SEQUENCE ---------------- */
  function renderSequence(host, stage, ctx){
    var tracker = new Tracker(ctx.taskId, stage.id);
    var ids = (stage.records || []).map(rid);
    if(stage.intro) host.appendChild(el("p", "desk-intro", stage.intro));
    evidenceGrid(host, stage.records || [], tracker);
    var qid = nid("seq");
    var q = el("p", "desk-q", stage.prompt); q.id = qid; host.appendChild(q);
    var ol = el("ol", "desk-seq"); ol.setAttribute("aria-labelledby", qid); host.appendChild(ol);
    var status = el("p", "desk-sr"); status.setAttribute("aria-live", "polite"); host.appendChild(status);
    var actions = el("div", "desk-actions");
    var submit = btn(stage.submitLabel || "Check the sequence");
    var help = el("p", "desk-hint"); help.id = nid("help"); submit.setAttribute("aria-describedby", help.id);
    var attemptsNote = el("span", "desk-attempts");
    actions.appendChild(submit); actions.appendChild(help); actions.appendChild(attemptsNote);
    host.appendChild(actions);
    var fbHost = el("div", "desk-fb-host"); fbHost.setAttribute("aria-live", "polite"); host.appendChild(fbHost);

    var saved = Store.get(ctx.taskId).stages[stage.id];
    var drafted = Store.getDraft(ctx.taskId, stage.id + ":order");
    var order = (drafted && drafted.length === stage.items.length) ? drafted.slice() : (stage.startOrder || stage.items.map(function(i){ return i.id; }));
    var locked = false;
    function item(id){ return stage.items.filter(function(x){ return x.id === id; })[0]; }
    function refresh(){
      if(locked){ help.style.display = "none"; return; }
      var ok = tracker.ready(ids);
      submit.disabled = !ok;
      help.style.display = ok ? "none" : "block";
      help.textContent = tracker.recheck.length ? "Re-open the export marked Re-check before checking again." : "Open ClearPath's export first -- the clues are in the details.";
    }
    tracker.onChange(refresh);
    function draw(focusId, dir){
      ol.innerHTML = "";
      order.forEach(function(id, i){
        var it = item(id), li = el("li", "desk-seq-item");
        li.appendChild(el("span", "desk-seq-n", (i + 1) + "."));
        li.appendChild(el("span", "desk-seq-text", it.label));
        var ctr = el("span", "desk-seq-ctrls");
        var up = btn("↑", "btn-ghost"); up.setAttribute("aria-label", "Move “" + it.label + "” up");
        var dn = btn("↓", "btn-ghost"); dn.setAttribute("aria-label", "Move “" + it.label + "” down");
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
      Store.draft(ctx.taskId, stage.id + ":order", order.slice());
      draw(id, String(d));
      status.textContent = "“" + item(id).label + "” moved to position " + (j + 1) + ".";
    }
    function show(res, fromLoad, st){
      fbHost.innerHTML = "";
      if(res.pass){
        locked = true; draw(); submit.style.display = "none"; refresh();
        var b = fbBlock(true, "That's the real sequence.");
        var dl = el("dl", "desk-fb-dl"); fbRow(dl, "Why it works", stage.passWhy);
        b.box.appendChild(dl); fbHost.appendChild(b.box);
        if(!fromLoad) b.title.focus();
        return;
      }
      var it = item(order[res.firstWrong]);
      var b2 = fbBlock(false, "Not yet -- step " + (res.firstWrong + 1) + " is out of place.");
      var dl2 = el("dl", "desk-fb-dl");
      fbRow(dl2, "What to reconsider", "“" + it.label + "”: " + it.hint);
      fbRow(dl2, "Why this matters", stage.failWhy);
      b2.box.appendChild(dl2);
      if(st && st.fails >= 2 && ids.length){
        tracker.requireRecheck(ids);
        pausePanel(b2.box, tracker, ids, recName(stage.records), st.attempts);
      }
      fbHost.appendChild(b2.box);
      refresh();
      if(!fromLoad) b2.title.focus();
    }
    submit.addEventListener("click", function(){
      if(submit.disabled || !tracker.ready(ids)) return;
      var ans = { order: order.slice() }, res = evaluate(stage, ans);
      var st = Store.attempt(ctx.taskId, stage.id, ans, res.pass);
      attemptsNote.textContent = st.attempts > 1 ? "Attempt " + st.attempts : "";
      show(res, false, st); ctx.onChange();
    });
    if(saved && saved.answer && evaluate(stage, saved.answer).pass){ order = saved.answer.order.slice(); locked = true; draw(); show(evaluate(stage, saved.answer), true); }
    else draw();
    refresh();
  }

  /* ---------------- COMPOSE (structured documentation) ---------------- */
  function renderCompose(host, stage, ctx){
    var tracker = new Tracker(ctx.taskId, stage.id);
    if(stage.intro) host.appendChild(el("p", "desk-intro", stage.intro));
    clock(host, stage.now);
    if(stage.example){
      var ex = el("details", "desk-example");
      ex.appendChild(el("summary", null, stage.example.label));
      ex.appendChild(el("pre", "desk-example-text", stage.example.text));
      if(stage.example.note) ex.appendChild(el("p", "desk-hint", stage.example.note));
      host.appendChild(ex);
    }
    var vals = Store.getDraft(ctx.taskId, stage.id + ":v") || {};
    var form = el("form", "desk-form"); form.addEventListener("submit", function(e){ e.preventDefault(); });
    var inputs = {}, groupEls = {}, allRecIds = [], locked = false;

    stage.groups.forEach(function(g){
      var box = el("section", "desk-group");
      box.setAttribute("aria-label", g.title);
      box.appendChild(el("h3", "desk-group-title", g.title));
      if(g.lead) box.appendChild(el("p", "desk-hint", g.lead));
      var recIds = g.records.map(rid);
      allRecIds = allRecIds.concat(recIds.filter(function(i){ return allRecIds.indexOf(i) === -1; }));
      var grid = el("div", "desk-records");
      g.records.forEach(function(r){ grid.appendChild(evidenceCard(r, tracker, { startOpen: true })); });
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
          var o0 = el("option", null, "Choose…"); o0.value = ""; ctrl.appendChild(o0);
          f.options.forEach(function(o){ var op = el("option", null, o.label); op.value = o.value; ctrl.appendChild(op); });
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

    /* self-check: evidence items are automatic; confirmations unlock only after */
    var sc = el("fieldset", "desk-fieldset desk-selfcheck");
    sc.appendChild(el("legend", null, "Check your work before you submit it"));
    var evList = el("ul", "desk-evlist");
    sc.appendChild(el("p", "desk-hint", "Evidence reviewed (ticks itself when you open each record):"));
    sc.appendChild(evList);
    var nameOf = recName([].concat.apply([], stage.groups.map(function(g){ return g.records; })));
    var evItems = allRecIds.map(function(id){ var li = el("li", null, ""); evList.appendChild(li); return { id: id, li: li }; });
    var confirmHint = el("p", "desk-hint"); sc.appendChild(confirmHint);
    var staleNote = el("p", "desk-row-note"); staleNote.hidden = true; sc.appendChild(staleNote);
    var confirmBoxes = [];
    var savedConfirms = Store.getDraft(ctx.taskId, stage.id + ":confirms") || [];
    (stage.confirm || []).forEach(function(c, i){
      var id = nid("chk"), lab = el("label", "desk-choice"), inp = document.createElement("input");
      inp.type = "checkbox"; inp.id = id; inp.checked = savedConfirms[i] === true; lab.htmlFor = id;
      lab.appendChild(inp); lab.appendChild(el("span", null, c)); sc.appendChild(lab); confirmBoxes.push(inp);
    });
    form.appendChild(sc);

    var actions = el("div", "desk-actions");
    var submit = btn(stage.submitLabel || "Submit your work"); submit.type = "submit";
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
    function setConfirms(arr){ confirmBoxes.forEach(function(c, i){ c.checked = arr[i] === true; }); Store.draft(ctx.taskId, stage.id + ":confirms", confirmBoxes.map(function(c){ return c.checked; })); }
    function refresh(){
      var allOpen = tracker.ready(allRecIds);
      evItems.forEach(function(it){
        var ok = tracker.isOpened(it.id);
        it.li.textContent = (ok ? "✓ " : "○ ") + "Opened " + nameOf(it.id) + (tracker.recheck.indexOf(it.id) !== -1 ? " (re-check needed)" : "");
        it.li.className = ok ? "is-done" : "";
      });
      Object.keys(groupEls).forEach(function(gid){
        var g = groupEls[gid], open = tracker.ready(g.recIds);
        g.gate.hidden = open || locked;
        g.gate.textContent = tracker.recheck.some(function(id){ return g.recIds.indexOf(id) !== -1; }) ? "Re-open the record above before you change this entry." : "Open the record above to start this entry.";
        stage.fields.filter(function(f){ return f.group === gid; }).forEach(function(f){
          var c = inputs[f.id].ctrl, dis = locked || !open;
          if(Array.isArray(c)) c.forEach(function(x){ x.disabled = dis; });
          else if(c.tagName === "TEXTAREA") c.readOnly = dis; else c.disabled = dis;
          if(c.tagName === "TEXTAREA") c.setAttribute("aria-disabled", dis ? "true" : "false");
        });
      });
      confirmBoxes.forEach(function(c){ c.disabled = locked || !allOpen; });
      confirmHint.textContent = allOpen ? "Then confirm these judgement checks:" : "The judgement checks below unlock once every record has been opened.";
      if(locked){ help.style.display = "none"; return; }
      var confirmed = confirmBoxes.every(function(c){ return c.checked; });
      submit.disabled = !(allOpen && confirmed);
      help.style.display = submit.disabled ? "block" : "none";
      help.textContent = !allOpen ? "Open every record first." : "Complete your self-check first.";
    }
    form.addEventListener("input", onEdit);
    form.addEventListener("change", function(e){
      if(confirmBoxes.indexOf(e.target) !== -1){ Store.draft(ctx.taskId, stage.id + ":confirms", confirmBoxes.map(function(c){ return c.checked; })); staleNote.hidden = true; refresh(); return; }
      onEdit(e);
    });
    function onEdit(e){
      if(confirmBoxes.indexOf(e.target) !== -1) return;
      Store.draft(ctx.taskId, stage.id + ":v", readValues());          /* saved on every keystroke */
      if(confirmBoxes.some(function(c){ return c.checked; })){
        setConfirms([]);
        staleNote.hidden = false;
        staleNote.textContent = "Your work changed after you checked it -- check it again before submitting.";
      }
      refresh();
    }
    window.addEventListener("pagehide", function(){ if(!locked) Store.draft(ctx.taskId, stage.id + ":v", readValues()); });
    tracker.onChange(refresh);

    function setLocked(lock){ locked = lock; submit.style.display = lock ? "none" : ""; refresh(); }
    function clearMarks(){
      Object.keys(inputs).forEach(function(k){ inputs[k].err.hidden = true; inputs[k].err.textContent = ""; var c = inputs[k].ctrl; if(!Array.isArray(c)) c.removeAttribute("aria-invalid"); });
      Object.keys(groupEls).forEach(function(g){ groupEls[g].note.hidden = true; groupEls[g].box.classList.remove("is-flag"); });
    }
    function show(ans, res, fromLoad, st){
      fbHost.innerHTML = ""; clearMarks();
      if(res.pass){
        var b = fbBlock(true, stage.passTitle || "Submitted -- this would hold up with the team.");
        if(stage.passWhy){ var dl = el("dl", "desk-fb-dl"); fbRow(dl, "Why it works", stage.passWhy); b.box.appendChild(dl); }
        var edit = btn("Revise your work", "btn-ghost");
        edit.addEventListener("click", function(){
          Store.unpass(ctx.taskId, stage.id);
          fbHost.innerHTML = ""; evHost.innerHTML = "";
          setConfirms([]); setLocked(false); ctx.onChange();
        });
        b.box.appendChild(edit);
        fbHost.appendChild(b.box);
        setLocked(true);
        if(stage.evidence) renderEvidence(evHost, stage, ans);
        if(!fromLoad) b.title.focus();
        return;
      }
      var b2 = fbBlock(false, "Not ready to send yet -- fix these first.");
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
      if(!res.confirmsDone) ul.appendChild(el("li", null, "Finish your self-check before submitting."));
      b2.box.appendChild(ul);
      if(stage.failWhy){ var dl2 = el("dl", "desk-fb-dl"); fbRow(dl2, "Why this matters", stage.failWhy); b2.box.appendChild(dl2); }
      if(st && st.fails >= 2 && res.badGroups.length){
        var ids = [];
        res.badGroups.forEach(function(gid){ groupEls[gid].recIds.forEach(function(i){ if(ids.indexOf(i) === -1) ids.push(i); }); });
        tracker.requireRecheck(ids);
        pausePanel(b2.box, tracker, ids, nameOf, st.attempts);
      }
      b2.box.appendChild(el("p", "desk-hint", "Your self-check has been cleared -- re-check after you edit."));
      fbHost.appendChild(b2.box);
      setConfirms([]); refresh();
      if(!fromLoad) b2.title.focus();
    }
    submit.addEventListener("click", function(){
      if(submit.disabled || !tracker.ready(allRecIds)) return;
      var ans = { values: readValues(), confirms: confirmBoxes.map(function(c){ return c.checked; }) };
      Store.draft(ctx.taskId, stage.id + ":v", ans.values);
      var res = evaluate(stage, ans);
      var st = Store.attempt(ctx.taskId, stage.id, ans, res.pass);
      attemptsNote.textContent = st.attempts > 1 ? "Attempt " + st.attempts : "";
      show(ans, res, false, st); ctx.onChange();
    });

    var saved = Store.get(ctx.taskId).stages[stage.id];
    if(saved && saved.answer && evaluate(stage, saved.answer).pass){
      var a = saved.answer;
      Object.keys(inputs).forEach(function(k){
        var it = inputs[k], v = a.values[k];
        if(Array.isArray(it.ctrl)) it.ctrl.forEach(function(c){ c.checked = (v || []).indexOf(c.value) !== -1; });
        else it.ctrl.value = v || "";
      });
      confirmBoxes.forEach(function(c){ c.checked = true; });
      show(a, evaluate(stage, a), true);
    }
    refresh();
  }

  function renderEvidence(host, stage, ans){
    host.innerHTML = "";
    var ev = stage.evidence, lines = [];
    lines.push("TRAINING WORK SAMPLE");
    lines.push(ev.title);
    lines.push("Everfield Goods is a fictional company used in PVA Free Training. Orders and data are simulated.");
    lines.push("Work date: " + (window.EVERFIELD ? EVERFIELD.simDate : "") + " (simulated)  |  Requested by: " + ev.requestedBy);
    lines.push("");
    stage.groups.forEach(function(g){
      lines.push(g.sampleHead || g.title);
      stage.fields.filter(function(f){ return f.group === g.id; }).forEach(function(f){
        var v = ans.values[f.id], out;
        if(f.type === "select") out = (f.options.filter(function(o){ return o.value === v; })[0] || {}).label || "";
        else if(f.type === "multi") out = (v || []).map(function(x){ return (f.options.filter(function(o){ return o.value === x; })[0] || {}).label; }).join("; ") || "None";
        else out = String(v || "").trim();
        lines.push("  " + (f.sampleLabel || f.label) + ": " + out);
      });
      lines.push("");
    });
    lines.push("Evidence opened before submitting; self-check completed.");
    var text = lines.join("\n");
    var box = el("section", "desk-evidence"); box.setAttribute("aria-label", "Your work sample");
    box.appendChild(el("div", "ws-preview-label", ev.badge || "Training work sample"));
    box.appendChild(el("p", "desk-hint", ev.note));
    var pre = el("pre", "ws-preview", text); pre.tabIndex = 0; pre.setAttribute("aria-label", "Work sample text");
    box.appendChild(pre);
    var row = el("div", "desk-actions");
    var copy = btn("Copy work sample", "btn-ghost"), dl = btn("Download as .txt", "btn-ghost");
    var msg = el("span", "desk-attempts"); msg.setAttribute("aria-live", "polite");
    copy.addEventListener("click", function(){
      if(navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(function(){ msg.textContent = "Copied."; }, function(){ msg.textContent = "Copy failed -- select the text and copy it manually."; });
      else msg.textContent = "Select the text above and copy it manually.";
    });
    dl.addEventListener("click", function(){
      var a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([text], { type: "text/plain" }));
      a.download = ev.filename || "everfield-work-sample.txt";
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(function(){ URL.revokeObjectURL(a.href); }, 1000);
    });
    row.appendChild(copy); row.appendChild(dl); row.appendChild(msg);
    box.appendChild(row); host.appendChild(box);
  }

  function renderStage(host, stage, ctx){
    host.innerHTML = "";
    if(stage.type === "decision") return renderDecision(host, stage, ctx);
    if(stage.type === "triage") return renderTriage(host, stage, ctx);
    if(stage.type === "sequence") return renderSequence(host, stage, ctx);
    if(stage.type === "compose") return renderCompose(host, stage, ctx);
  }

  window.PVADesk = {
    decode: decode, store: Store, evaluate: evaluate, stagePassed: stagePassed, taskStatus: taskStatus,
    renderBrief: renderBrief, renderStage: renderStage, STORE_KEY: STORE_KEY, _hash: h
  };
})();
