/* PVA Free Training -- E-commerce VA Foundations
   Operations Desk engine (Module 4 pilot).

   A small, dependency-free engine for workplace-style tasks:
     decision  -- inspect records, select what you noticed, choose an action
     triage    -- classify each record in a batch using its evidence
     sequence  -- put events in order (keyboard-operable)
     compose   -- write real output, self-check it, produce a work sample

   Integrity notes
   - Task data ships encoded (see tools/desk-codec.js), so answers and
     feedback are not readable in page source or findable with Ctrl+F.
   - Answer keys are salted hashes rather than plain right/wrong flags; nothing
     in the DOM marks the right option before the learner submits.
   - Progress is NOT a stored "completed" flag. The learner's submitted
     answers are stored, and completion is re-derived on every load by
     re-checking those answers. Setting a flag in storage does nothing.
   - This is client-side code: a determined person with dev tools can still
     reverse it. The goal is that the normal path requires the work.

   Storage: its own key ("pva-ecom-ft-m4-desk"). The shared progress key
   used by the hub and every other module is only written through the
   existing PVAEcom.markLessonDone(), and only when a task is verifiably done. */

(function(){
  var SALT = "everfield-desk-v1";
  var STORE_KEY = "pva-ecom-ft-m4-desk";
  var XOR_KEY = "EverfieldOpsDesk";

  /* ---------------- encoding / hashing ---------------- */
  function decode(b64){
    var bin = atob(b64);
    var bytes = new Uint8Array(bin.length);
    for(var i = 0; i < bin.length; i++){
      bytes[i] = bin.charCodeAt(i) ^ XOR_KEY.charCodeAt(i % XOR_KEY.length);
    }
    var json = new TextDecoder("utf-8").decode(bytes);
    return JSON.parse(json);
  }

  function h(str){
    /* FNV-1a 32-bit over the salted string -> 8 hex chars */
    var s = SALT + "|" + str;
    var x = 0x811c9dc5;
    for(var i = 0; i < s.length; i++){
      x ^= s.charCodeAt(i);
      x = Math.imul(x, 0x01000193) >>> 0;
    }
    return ("0000000" + x.toString(16)).slice(-8);
  }

  function isFindingRight(stageId, f){ return f.k === h(stageId + "|f|" + f.id + "|1"); }
  function isOptionRight(stageId, o){ return o.k === h(stageId + "|o|" + o.id + "|1"); }
  function isRowRight(stageId, row, choiceId){ return !!choiceId && row.k === h(stageId + "|row|" + row.id + "|" + choiceId); }
  function seqPosKey(stageId, itemId, pos){ return h(stageId + "|seq|" + itemId + "|" + pos); }
  function isAccepted(stageId, field, value){
    if(!field.select) return true;
    return !!value && field.select.acc.indexOf(h(stageId + "|acc|" + field.id + "|" + value)) !== -1;
  }

  /* ---------------- storage ---------------- */
  function readAll(){
    try{
      var raw = window.localStorage.getItem(STORE_KEY);
      var s = raw ? JSON.parse(raw) : null;
      if(!s || typeof s !== "object" || !s.tasks) s = { v: 1, tasks: {} };
      return s;
    }catch(e){ return { v: 1, tasks: {} }; }
  }
  function writeAll(s){
    try{ window.localStorage.setItem(STORE_KEY, JSON.stringify(s)); }catch(e){}
  }
  function taskRec(s, taskId){
    if(!s.tasks[taskId]) s.tasks[taskId] = { views: 0, stages: {}, drafts: {} };
    var t = s.tasks[taskId];
    t.stages = t.stages || {}; t.drafts = t.drafts || {};
    return t;
  }
  var Store = {
    get: function(taskId){ return taskRec(readAll(), taskId); },
    touch: function(taskId){
      var s = readAll(); var t = taskRec(s, taskId);
      t.views = (t.views || 0) + 1;
      if(!t.firstViewed) t.firstViewed = new Date().toISOString();
      t.lastViewed = new Date().toISOString();
      writeAll(s);
    },
    attempt: function(taskId, stageId, answer, pass){
      var s = readAll(); var t = taskRec(s, taskId);
      var st = t.stages[stageId] || { attempts: 0 };
      st.attempts = (st.attempts || 0) + 1;
      st.last = answer;
      if(pass){
        st.answer = answer;
        if(st.firstTry === undefined) st.firstTry = (st.attempts === 1);
        st.passedAt = st.passedAt || new Date().toISOString();
      }
      t.stages[stageId] = st;
      writeAll(s);
      return st;
    },
    draft: function(taskId, key, value){
      var s = readAll(); var t = taskRec(s, taskId);
      t.drafts[key] = value;
      writeAll(s);
    },
    resetStage: function(taskId, stageId){
      var s = readAll(); var t = taskRec(s, taskId);
      delete t.stages[stageId];
      writeAll(s);
    }
  };

  /* ---------------- evaluation ---------------- */
  function normalize(t){ return (" " + String(t || "").toLowerCase().replace(/[‘’]/g, "'").replace(/\s+/g, " ") + " "); }
  function hasAny(text, tokens){
    var n = normalize(text);
    return tokens.some(function(tok){
      if(tok.indexOf("re:") === 0){ return new RegExp(tok.slice(3), "i").test(n); }
      return n.indexOf(tok.toLowerCase()) !== -1;
    });
  }
  function wordCount(t){ return String(t || "").trim().split(/\s+/).filter(function(w){ return /[a-z0-9]/i.test(w); }).length; }
  function wordSet(t){
    var o = {};
    normalize(t).replace(/[^a-z0-9#\- ]/g, " ").split(" ").forEach(function(w){ if(w.length > 2) o[w] = 1; });
    return o;
  }
  function similarity(a, b){
    var A = wordSet(a), B = wordSet(b), inter = 0, uni = 0, k;
    for(k in A){ uni++; if(B[k]) inter++; }
    for(k in B){ if(!A[k]) uni++; }
    return uni ? inter / uni : 0;
  }
  function looksMeaningless(t){
    var s = String(t || "").trim();
    if(!s) return true;
    if(/(.)\1{5,}/.test(s)) return true;                 /* "aaaaaa" */
    var letters = s.replace(/[^a-z]/gi, "");
    if(letters.length < 8) return true;
    var uniq = {}; letters.toLowerCase().split("").forEach(function(c){ uniq[c] = 1; });
    return Object.keys(uniq).length < 5;                  /* "asdf asdf asdf" */
  }

  /* Returns { pass, ... detail } */
  function evaluate(stage, answer){
    if(!answer) return { pass: false };
    if(stage.type === "decision"){
      var picked = answer.f || [];
      var missed = [], wrongPicked = [];
      (stage.findings || []).forEach(function(f){
        var right = isFindingRight(stage.id, f);
        var sel = picked.indexOf(f.id) !== -1;
        if(right && !sel) missed.push(f);
        if(!right && sel) wrongPicked.push(f);
      });
      var opt = null, optRight = true;
      if(stage.options && stage.options.length){
        opt = stage.options.filter(function(o){ return o.id === answer.o; })[0] || null;
        optRight = !!opt && isOptionRight(stage.id, opt);
      }
      return { pass: optRight && !missed.length && !wrongPicked.length,
               missed: missed, wrongPicked: wrongPicked, option: opt, optRight: optRight };
    }
    if(stage.type === "triage"){
      var wrongRows = [];
      stage.rows.forEach(function(r){ if(!isRowRight(stage.id, r, answer[r.id])) wrongRows.push(r); });
      return { pass: !wrongRows.length, wrongRows: wrongRows };
    }
    if(stage.type === "sequence"){
      var order = answer.order || [];
      var firstWrong = -1;
      if(order.length !== stage.items.length) firstWrong = 0;
      else {
        for(var i = 0; i < order.length; i++){
          var it = stage.items.filter(function(x){ return x.id === order[i]; })[0];
          if(!it || it.k.indexOf(seqPosKey(stage.id, it.id, i)) === -1){ firstWrong = i; break; }
        }
      }
      return { pass: firstWrong === -1, firstWrong: firstWrong };
    }
    if(stage.type === "compose"){
      var problems = [];
      var fields = answer.fields || {};
      var allText = "";
      stage.fields.forEach(function(f){
        var v = fields[f.id] || {};
        var text = v.text || "";
        allText += " " + text;
        if(f.select){
          if(!v.sel){ problems.push({ field: f.id, msg: f.label + ": choose which order this entry is about." }); return; }
          if(!isAccepted(stage.id, f, v.sel)){
            problems.push({ field: f.id, msg: f.label + ": " + (f.select.wrongMsg || "re-check which order fits this entry.") });
            return;
          }
        }
        var minW = f.minWords || stage.minWords || 6;
        if((minW >= 4 && looksMeaningless(text)) || !String(text).trim() || wordCount(text) < minW){
          problems.push({ field: f.id, msg: f.label + (minW > 1 ? ": write at least " + minW + " real words -- enough that a teammate could act on it." : ": this can't be blank.") });
          return;
        }
        var rules = (f.byChoice && v.sel && f.byChoice[v.sel]) || f.rules || [];
        rules.forEach(function(r){
          if(!hasAny(text, r.any)) problems.push({ field: f.id, msg: f.label + ": " + r.msg });
        });
        (stage.banned || []).forEach(function(b){
          if(hasAny(text, b.any)) problems.push({ field: f.id, msg: f.label + ": " + b.msg });
        });
        if(stage.example && similarity(text, stage.example.text) > 0.6){
          problems.push({ field: f.id, msg: f.label + ": this reads very close to the example. Write it for this order, from this record." });
        }
      });
      var checks = answer.checks || [];
      var checksDone = stage.selfCheck ? stage.selfCheck.every(function(_, i){ return checks[i] === true; }) : true;
      return { pass: !problems.length && checksDone, problems: problems, checksDone: checksDone };
    }
    return { pass: false };
  }

  /* Derived status -- never trusts a stored flag. */
  function stagePassed(taskId, stage, rec){
    var t = rec || Store.get(taskId);
    var st = t.stages[stage.id];
    return !!(st && st.answer && evaluate(stage, st.answer).pass);
  }
  function taskStatus(task){
    var t = Store.get(task.id);
    var passed = task.stages.filter(function(s){ return stagePassed(task.id, s, t); }).length;
    var attempted = task.stages.some(function(s){ return t.stages[s.id] && t.stages[s.id].attempts > 0; });
    var evStage = task.stages.filter(function(s){ return s.type === "compose" && s.evidence; })[0];
    var level = "new";
    if(t.views) level = "viewed";
    if(attempted) level = "attempted";
    if(passed === task.stages.length) level = "practiced";
    if(level === "practiced" && evStage) level = "evidence";
    return { level: level, passed: passed, total: task.stages.length, hasEvidence: !!evStage };
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
  function btn(label, cls){
    var b = el("button", "btn " + (cls || "btn-primary") + " btn-small", label);
    b.type = "button";
    return b;
  }

  function renderBrief(host, brief, team){
    var who = team[brief.from] || { name: brief.from, role: "" };
    var box = el("article", "desk-msg desk-brief");
    box.setAttribute("aria-label", "Work request from " + who.name);
    var head = el("div", "desk-msg-head");
    head.appendChild(el("span", "desk-tag", "Work request"));
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

  function renderRecord(rec){
    if(rec.kind === "message"){
      var m = el("article", "desk-msg desk-inbound");
      var hd = el("div", "desk-msg-head");
      hd.appendChild(el("span", "desk-tag desk-tag-soft", rec.label || "Message"));
      m.appendChild(hd);
      var meta = el("dl", "desk-msg-meta");
      (rec.meta || []).forEach(function(p){ meta.appendChild(el("dt", null, p[0])); meta.appendChild(el("dd", null, p[1])); });
      m.appendChild(meta);
      var b = el("div", "desk-msg-body");
      rec.body.forEach(function(p){ b.appendChild(el("p", null, p)); });
      m.appendChild(b);
      return m;
    }
    var card = el("section", "desk-record");
    var t = el("h4", "desk-record-title", rec.title);
    card.appendChild(t);
    var dl = el("dl", "desk-fields");
    rec.fields.forEach(function(f){
      var row = el("div", "desk-field");
      row.appendChild(el("dt", null, f[0]));
      var dd = el("dd", null, f[1]);
      if(f[1] === "—" || f[1] === "") dd.setAttribute("aria-label", f[0] + ": blank");
      row.appendChild(dd);
      dl.appendChild(row);
    });
    card.appendChild(dl);
    if(rec.log){
      var lg = el("div", "desk-log");
      lg.appendChild(el("div", "desk-log-title", rec.logTitle || "Activity"));
      var ol = el("ol", "desk-log-list");
      rec.log.forEach(function(line){ ol.appendChild(el("li", null, line)); });
      lg.appendChild(ol);
      card.appendChild(lg);
    }
    if(rec.note){ card.appendChild(el("p", "desk-record-note", rec.note)); }
    return card;
  }

  function renderRecords(host, records, now){
    if(now){
      var clock = el("p", "desk-clock");
      clock.appendChild(el("span", "desk-tag desk-tag-soft", "Now"));
      clock.appendChild(document.createTextNode(" " + now));
      host.appendChild(clock);
    }
    var grid = el("div", "desk-records");
    records.forEach(function(r){ grid.appendChild(renderRecord(r)); });
    host.appendChild(grid);
  }

  function fbBlock(pass, title){
    var fb = el("div", "desk-fb " + (pass ? "is-pass" : "is-retry"));
    var h = el("h4", "desk-fb-title", title);
    h.tabIndex = -1;
    fb.appendChild(h);
    return { box: fb, title: h };
  }
  function fbRow(dl, label, content){
    dl.appendChild(el("dt", null, label));
    var dd = el("dd");
    if(typeof content === "string") dd.textContent = content;
    else dd.appendChild(content);
    dl.appendChild(dd);
  }

  /* ---------------- DECISION ---------------- */
  function renderDecision(host, stage, ctx){
    if(stage.intro) host.appendChild(el("p", "desk-intro", stage.intro));
    renderRecords(host, stage.records || [], stage.now);

    var form = el("form", "desk-form");
    form.noValidate = true;
    form.addEventListener("submit", function(e){ e.preventDefault(); });

    var fsF = el("fieldset", "desk-fieldset");
    fsF.appendChild(el("legend", null, stage.findingsPrompt));
    fsF.appendChild(el("p", "desk-hint", "Select everything the evidence supports -- and nothing it doesn't."));
    var fInputs = [];
    stage.findings.forEach(function(f){
      var id = nid("f");
      var lab = el("label", "desk-choice");
      var inp = document.createElement("input");
      inp.type = "checkbox"; inp.id = id; inp.value = f.id;
      lab.htmlFor = id;
      lab.appendChild(inp);
      lab.appendChild(el("span", null, f.text));
      fsF.appendChild(lab);
      fInputs.push(inp);
    });
    form.appendChild(fsF);

    var oInputs = [];
    if(stage.options && stage.options.length){
      var fsO = el("fieldset", "desk-fieldset");
      fsO.appendChild(el("legend", null, stage.actionPrompt));
      var name = nid("opt");
      stage.options.forEach(function(o){
        var id = nid("o");
        var lab = el("label", "desk-choice");
        var inp = document.createElement("input");
        inp.type = "radio"; inp.name = name; inp.id = id; inp.value = o.id;
        lab.htmlFor = id;
        lab.appendChild(inp);
        lab.appendChild(el("span", null, o.text));
        fsO.appendChild(lab);
        oInputs.push(inp);
      });
      form.appendChild(fsO);
    }

    var actions = el("div", "desk-actions");
    var submit = btn(stage.submitLabel || (oInputs.length ? "Make your decision" : "Submit your review"));
    submit.type = "submit";
    var helpId = nid("help");
    var help = el("p", "desk-hint", oInputs.length ? "Select at least one finding and one action first." : "Select at least one item first.");
    help.id = helpId;
    submit.setAttribute("aria-describedby", helpId);
    var attemptsNote = el("span", "desk-attempts");
    actions.appendChild(submit); actions.appendChild(help); actions.appendChild(attemptsNote);
    form.appendChild(actions);

    var fbHost = el("div", "desk-fb-host");
    fbHost.setAttribute("aria-live", "polite");
    host.appendChild(form);
    host.appendChild(fbHost);

    function current(){
      var f = fInputs.filter(function(i){ return i.checked; }).map(function(i){ return i.value; });
      var o = oInputs.filter(function(i){ return i.checked; }).map(function(i){ return i.value; })[0];
      return { f: f.sort(), o: o };
    }
    function refreshSubmit(){
      var a = current();
      var ready = a.f.length > 0 && (!oInputs.length || !!a.o);
      submit.disabled = !ready;
      help.style.display = ready ? "none" : "block";
    }
    function setLocked(lock){
      fInputs.concat(oInputs).forEach(function(i){ i.disabled = lock; });
      submit.style.display = lock ? "none" : "";
      if(lock) help.style.display = "none";
    }
    function restore(ans){
      fInputs.forEach(function(i){ i.checked = (ans.f || []).indexOf(i.value) !== -1; });
      oInputs.forEach(function(i){ i.checked = i.value === ans.o; });
    }
    form.addEventListener("change", refreshSubmit);

    function showResult(ans, res, fromLoad, attempts){
      fbHost.innerHTML = "";
      var choice = res.option ? res.option.text : null;
      if(res.pass){
        var b = fbBlock(true, stage.passTitle || "Good call -- that's the right read.");
        var dl = el("dl", "desk-fb-dl");
        if(choice) fbRow(dl, "Your decision", choice);
        fbRow(dl, "Why it works", (res.option && res.option.why) || stage.passWhy || "");
        if(stage.takeaway) fbRow(dl, "Habit to keep", stage.takeaway);
        b.box.appendChild(dl);
        fbHost.appendChild(b.box);
        setLocked(true);
        if(!fromLoad) b.title.focus();
        return;
      }
      var b2 = fbBlock(false, "Not yet -- here's what to look at again.");
      var dl2 = el("dl", "desk-fb-dl");
      if(choice) fbRow(dl2, "Your decision", choice);
      if(res.missed.length || res.wrongPicked.length){
        var ul = el("ul", "desk-fb-list");
        /* Staged disclosure: on the first miss, say how much was missed and
           send the learner back to the record; reveal the specific facts only
           from the second failed attempt, so the answer can't be copied
           straight out of the first round of feedback. */
        if(res.missed.length){
          if((attempts || 1) < 2){
            ul.appendChild(el("li", null, "You left out " + res.missed.length + " thing" + (res.missed.length > 1 ? "s" : "") +
              " the evidence supports. Go back through the record field by field before you try again."));
          } else {
            res.missed.forEach(function(f){ ul.appendChild(el("li", null, f.miss)); });
          }
        }
        res.wrongPicked.forEach(function(f){
          var li = el("li");
          li.appendChild(el("strong", null, "You selected “" + f.text.replace(/[.\s]+$/, "") + "”. "));
          li.appendChild(document.createTextNode(f.wrong));
          ul.appendChild(li);
        });
        fbRow(dl2, "What you missed", ul);
      }
      var why;
      if(res.option && !res.optRight) why = res.option.why;
      else if(res.option) why = "Your action is the right one, but your read of the record isn't complete yet. " + (stage.findingsWhy || "A correct action for the wrong reasons won't hold up on the next order.");
      else why = stage.findingsWhy || stage.passWhy && "Compare the draft against each part of the format, one at a time.";
      if(why) fbRow(dl2, "Why this matters", why);
      b2.box.appendChild(dl2);
      var retry = btn("Reconsider and try again", "btn-ghost");
      retry.addEventListener("click", function(){
        fbHost.innerHTML = "";
        setLocked(false);
        refreshSubmit();
        (fInputs[0]).focus();
      });
      b2.box.appendChild(retry);
      fbHost.appendChild(b2.box);
      setLocked(true);
      if(!fromLoad) b2.title.focus();
    }

    submit.addEventListener("click", function(){
      var ans = current();
      if(submit.disabled) return;
      var res = evaluate(stage, ans);
      var st = Store.attempt(ctx.taskId, stage.id, ans, res.pass);
      attemptsNote.textContent = st.attempts > 1 ? "Attempt " + st.attempts : "";
      showResult(ans, res, false, st.attempts);
      ctx.onChange();
    });

    var saved = Store.get(ctx.taskId).stages[stage.id];
    if(saved && saved.answer && evaluate(stage, saved.answer).pass){
      restore(saved.answer);
      showResult(saved.answer, evaluate(stage, saved.answer), true);
    } else {
      if(saved && saved.last){ restore(saved.last); }
      refreshSubmit();
    }
  }

  /* ---------------- TRIAGE ---------------- */
  function renderTriage(host, stage, ctx){
    if(stage.intro) host.appendChild(el("p", "desk-intro", stage.intro));
    if(stage.now){
      var clock = el("p", "desk-clock");
      clock.appendChild(el("span", "desk-tag desk-tag-soft", "Now"));
      clock.appendChild(document.createTextNode(" " + stage.now));
      host.appendChild(clock);
    }
    var form = el("form", "desk-form");
    form.addEventListener("submit", function(e){ e.preventDefault(); });
    var list = el("div", "desk-records desk-triage");
    var selects = {}, notes = {}, cards = {};
    stage.rows.forEach(function(r){
      var card = renderRecord(r);
      card.classList.add("desk-triage-row");
      var wrap = el("div", "desk-triage-pick");
      var sid = nid("sel");
      var lab = el("label", "desk-select-label", stage.prompt);
      lab.htmlFor = sid;
      var sel = document.createElement("select");
      sel.id = sid; sel.className = "desk-select";
      var o0 = el("option", null, "Choose…"); o0.value = ""; sel.appendChild(o0);
      stage.choices.forEach(function(c){ var o = el("option", null, c.label); o.value = c.id; sel.appendChild(o); });
      wrap.appendChild(lab); wrap.appendChild(sel);
      var note = el("p", "desk-row-note");
      note.id = nid("note");
      note.hidden = true;
      sel.setAttribute("aria-describedby", note.id);
      wrap.appendChild(note);
      card.appendChild(wrap);
      list.appendChild(card);
      selects[r.id] = sel; notes[r.id] = note; cards[r.id] = card;
    });
    form.appendChild(list);

    var actions = el("div", "desk-actions");
    var submit = btn(stage.submitLabel || "Submit your review");
    submit.type = "submit";
    var help = el("p", "desk-hint", "Make a call on every order first.");
    help.id = nid("help");
    submit.setAttribute("aria-describedby", help.id);
    actions.appendChild(submit); actions.appendChild(help);
    var attemptsNote = el("span", "desk-attempts");
    actions.appendChild(attemptsNote);
    form.appendChild(actions);
    var fbHost = el("div", "desk-fb-host");
    fbHost.setAttribute("aria-live", "polite");
    host.appendChild(form); host.appendChild(fbHost);

    function current(){ var a = {}; Object.keys(selects).forEach(function(k){ a[k] = selects[k].value; }); return a; }
    function refreshSubmit(){
      var a = current(); var ready = Object.keys(a).every(function(k){ return !!a[k]; });
      submit.disabled = !ready; help.style.display = ready ? "none" : "block";
    }
    form.addEventListener("change", function(e){
      var t = e.target;
      Object.keys(selects).forEach(function(k){
        if(selects[k] === t){ notes[k].hidden = true; t.removeAttribute("aria-invalid"); cards[k].classList.remove("is-flag", "is-ok"); }
      });
      refreshSubmit();
    });

    function showResult(res, fromLoad){
      fbHost.innerHTML = "";
      stage.rows.forEach(function(r){
        var wrong = res.wrongRows.indexOf(r) !== -1;
        notes[r.id].hidden = !wrong;
        cards[r.id].classList.toggle("is-flag", wrong);
        cards[r.id].classList.toggle("is-ok", !wrong);
        if(wrong){
          notes[r.id].textContent = "Look again: " + r.hint;
          selects[r.id].setAttribute("aria-invalid", "true");
        } else {
          selects[r.id].removeAttribute("aria-invalid");
        }
        selects[r.id].disabled = res.pass;
      });
      if(res.pass){
        var b = fbBlock(true, "Batch reviewed -- every call holds up.");
        var dl = el("dl", "desk-fb-dl");
        if(stage.passWhy) fbRow(dl, "Why this matters", stage.passWhy);
        if(stage.takeaway) fbRow(dl, "Habit to keep", stage.takeaway);
        b.box.appendChild(dl);
        fbHost.appendChild(b.box);
        submit.style.display = "none"; help.style.display = "none";
        if(!fromLoad) b.title.focus();
      } else {
        var n = res.wrongRows.length;
        var b2 = fbBlock(false, n + " of " + stage.rows.length + " " + (stage.rowNoun || "orders") + " need another look.");
        var p = el("p", null, "Each flagged " + (stage.rowNounOne || "order") + " has a note under it pointing to the evidence you should re-read. The calls that hold up are marked ✓. Change what you need to, then submit again.");
        b2.box.appendChild(p);
        fbHost.appendChild(b2.box);
        if(!fromLoad) b2.title.focus();
      }
    }

    submit.addEventListener("click", function(){
      if(submit.disabled) return;
      var ans = current();
      var res = evaluate(stage, ans);
      var st = Store.attempt(ctx.taskId, stage.id, ans, res.pass);
      attemptsNote.textContent = st.attempts > 1 ? "Attempt " + st.attempts : "";
      showResult(res, false);
      ctx.onChange();
    });

    var saved = Store.get(ctx.taskId).stages[stage.id];
    var restoreAns = saved && (saved.answer && evaluate(stage, saved.answer).pass ? saved.answer : saved.last);
    if(restoreAns){ Object.keys(selects).forEach(function(k){ selects[k].value = restoreAns[k] || ""; }); }
    if(saved && saved.answer && evaluate(stage, saved.answer).pass) showResult(evaluate(stage, saved.answer), true);
    refreshSubmit();
    if(saved && saved.answer && evaluate(stage, saved.answer).pass){ submit.style.display = "none"; help.style.display = "none"; }
  }

  /* ---------------- SEQUENCE (keyboard-operable) ---------------- */
  function renderSequence(host, stage, ctx){
    if(stage.intro) host.appendChild(el("p", "desk-intro", stage.intro));
    var listLabel = nid("seq");
    host.appendChild(el("p", "desk-q", stage.prompt)).id = listLabel;
    var ol = el("ol", "desk-seq");
    ol.setAttribute("aria-labelledby", listLabel);
    host.appendChild(ol);
    var status = el("p", "desk-sr");
    status.setAttribute("aria-live", "polite");
    host.appendChild(status);
    var actions = el("div", "desk-actions");
    var submit = btn(stage.submitLabel || "Check the sequence");
    var attemptsNote = el("span", "desk-attempts");
    actions.appendChild(submit); actions.appendChild(attemptsNote);
    host.appendChild(actions);
    var fbHost = el("div", "desk-fb-host");
    fbHost.setAttribute("aria-live", "polite");
    host.appendChild(fbHost);

    var saved = Store.get(ctx.taskId).stages[stage.id];
    var order = (saved && (saved.answer || saved.last) && (saved.answer || saved.last).order) ||
                (stage.startOrder || stage.items.map(function(i){ return i.id; }));
    var locked = false;

    function item(id){ return stage.items.filter(function(x){ return x.id === id; })[0]; }
    function draw(focusId, dir){
      ol.innerHTML = "";
      order.forEach(function(id, i){
        var it = item(id);
        var li = el("li", "desk-seq-item");
        li.appendChild(el("span", "desk-seq-n", (i + 1) + "."));
        li.appendChild(el("span", "desk-seq-text", it.label));
        var ctr = el("span", "desk-seq-ctrls");
        var up = btn("↑", "btn-ghost"); up.setAttribute("aria-label", "Move “" + it.label + "” up");
        var dn = btn("↓", "btn-ghost"); dn.setAttribute("aria-label", "Move “" + it.label + "” down");
        up.disabled = locked || i === 0; dn.disabled = locked || i === order.length - 1;
        up.addEventListener("click", function(){ move(i, -1); });
        dn.addEventListener("click", function(){ move(i, 1); });
        up.dataset.id = id; dn.dataset.id = id; up.dataset.dir = "-1"; dn.dataset.dir = "1";
        ctr.appendChild(up); ctr.appendChild(dn);
        li.appendChild(ctr);
        ol.appendChild(li);
      });
      if(focusId){
        var target = ol.querySelector('button[data-id="' + focusId + '"][data-dir="' + dir + '"]:not([disabled])') ||
                     ol.querySelector('button[data-id="' + focusId + '"]:not([disabled])');
        if(target) target.focus();
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
    submit.addEventListener("click", function(){
      var ans = { order: order.slice() };
      var res = evaluate(stage, ans);
      var st = Store.attempt(ctx.taskId, stage.id, ans, res.pass);
      attemptsNote.textContent = st.attempts > 1 ? "Attempt " + st.attempts : "";
      show(res, false);
      ctx.onChange();
    });
    function show(res, fromLoad){
      fbHost.innerHTML = "";
      if(res.pass){
        locked = true; draw();
        submit.style.display = "none";
        var b = fbBlock(true, "That's the real sequence.");
        var dl = el("dl", "desk-fb-dl");
        fbRow(dl, "Why it works", stage.passWhy);
        b.box.appendChild(dl);
        fbHost.appendChild(b.box);
        if(!fromLoad) b.title.focus();
      } else {
        var it = item(order[res.firstWrong]);
        var b2 = fbBlock(false, "Not yet -- step " + (res.firstWrong + 1) + " is out of place.");
        var dl2 = el("dl", "desk-fb-dl");
        fbRow(dl2, "What to reconsider", "“" + it.label + "”: " + it.hint);
        fbRow(dl2, "Why this matters", stage.failWhy);
        b2.box.appendChild(dl2);
        fbHost.appendChild(b2.box);
        if(!fromLoad) b2.title.focus();
      }
    }
    var drafted = Store.get(ctx.taskId).drafts[stage.id + ":order"];
    if(!(saved && saved.answer) && drafted && drafted.length === stage.items.length) order = drafted.slice();
    if(saved && saved.answer && evaluate(stage, saved.answer).pass){ order = saved.answer.order.slice(); locked = true; draw(); show(evaluate(stage, saved.answer), true); }
    else draw();
  }

  /* ---------------- COMPOSE (+ self-check + evidence) ---------------- */
  function renderCompose(host, stage, ctx){
    if(stage.intro) host.appendChild(el("p", "desk-intro", stage.intro));
    if(stage.records) renderRecords(host, stage.records, stage.now);

    if(stage.example){
      var ex = el("details", "desk-example");
      ex.appendChild(el("summary", null, stage.example.label));
      ex.appendChild(el("pre", "desk-example-text", stage.example.text));
      if(stage.example.note) ex.appendChild(el("p", "desk-hint", stage.example.note));
      host.appendChild(ex);
    }

    var t = Store.get(ctx.taskId);
    var drafts = t.drafts || {};
    var form = el("form", "desk-form");
    form.addEventListener("submit", function(e){ e.preventDefault(); });
    var inputs = {};
    stage.fields.forEach(function(f){
      var wrap = el("div", "desk-compose-field");
      wrap.id = nid("cf");
      var head = el("div", "desk-compose-head");
      var taId = nid("ta");
      var lab = el("label", "ws-label", f.label);
      lab.htmlFor = taId;
      head.appendChild(lab);
      if(f.help) head.appendChild(el("p", "desk-hint", f.help));
      wrap.appendChild(head);
      var sel = null;
      if(f.select){
        var sid = nid("sel");
        var sl = el("label", "desk-select-label", f.select.label || "Which order?");
        sl.htmlFor = sid;
        sel = document.createElement("select");
        sel.id = sid; sel.className = "desk-select";
        var o0 = el("option", null, "Choose…"); o0.value = ""; sel.appendChild(o0);
        f.select.options.forEach(function(v){ var o = el("option", null, v); o.value = v; sel.appendChild(o); });
        sel.value = drafts[stage.id + ":" + f.id + ":sel"] || "";
        sel.addEventListener("change", function(){ Store.draft(ctx.taskId, stage.id + ":" + f.id + ":sel", sel.value); });
        var sw = el("div", "desk-inline-select");
        sw.appendChild(sl); sw.appendChild(sel);
        wrap.appendChild(sw);
      }
      var ta = document.createElement("textarea");
      ta.className = "ws-textarea"; ta.id = taId; ta.rows = f.rows || 3;
      ta.placeholder = f.placeholder || "";
      ta.value = drafts[stage.id + ":" + f.id] || "";
      var tmr = null;
      ta.addEventListener("input", function(){
        clearTimeout(tmr);
        tmr = setTimeout(function(){ Store.draft(ctx.taskId, stage.id + ":" + f.id, ta.value); }, 300);
      });
      var err = el("p", "desk-row-note"); err.id = nid("err"); err.hidden = true;
      ta.setAttribute("aria-describedby", err.id);
      wrap.appendChild(ta); wrap.appendChild(err);
      form.appendChild(wrap);
      inputs[f.id] = { ta: ta, sel: sel, err: err, wrap: wrap };
    });

    var nameInput = null;
    if(stage.evidence){
      var nw = el("div", "desk-compose-field");
      var nid2 = nid("name");
      var nl = el("label", "ws-label", "Your name for the work sample header (optional)");
      nl.htmlFor = nid2;
      nameInput = document.createElement("input");
      nameInput.type = "text"; nameInput.id = nid2; nameInput.className = "desk-input";
      nameInput.autocomplete = "name";
      nameInput.value = drafts[stage.id + ":name"] || "";
      nameInput.addEventListener("change", function(){ Store.draft(ctx.taskId, stage.id + ":name", nameInput.value); });
      nw.appendChild(nl); nw.appendChild(nameInput);
      form.appendChild(nw);
    }

    var checkBoxes = [];
    if(stage.selfCheck){
      var fs = el("fieldset", "desk-fieldset desk-selfcheck");
      fs.appendChild(el("legend", null, "Check your work before you submit it"));
      fs.appendChild(el("p", "desk-hint", "Re-read your entries against the records, then tick each check you've actually done."));
      var savedChecks = drafts[stage.id + ":checks"] || [];
      stage.selfCheck.forEach(function(c, i){
        var id = nid("chk");
        var lab = el("label", "desk-choice");
        var inp = document.createElement("input");
        inp.type = "checkbox"; inp.id = id;
        inp.checked = savedChecks[i] === true;
        lab.htmlFor = id;
        lab.appendChild(inp); lab.appendChild(el("span", null, c));
        fs.appendChild(lab);
        checkBoxes.push(inp);
      });
      fs.addEventListener("change", function(){
        Store.draft(ctx.taskId, stage.id + ":checks", checkBoxes.map(function(c){ return c.checked; }));
        refreshSubmit();
      });
      form.appendChild(fs);
    }

    var actions = el("div", "desk-actions");
    var submit = btn(stage.submitLabel || "Submit your work");
    submit.type = "submit";
    var help = el("p", "desk-hint", "Complete your self-check first.");
    help.id = nid("help");
    submit.setAttribute("aria-describedby", help.id);
    var attemptsNote = el("span", "desk-attempts");
    actions.appendChild(submit); actions.appendChild(help); actions.appendChild(attemptsNote);
    form.appendChild(actions);
    var fbHost = el("div", "desk-fb-host");
    fbHost.setAttribute("aria-live", "polite");
    var evHost = el("div", "desk-evidence-host");
    host.appendChild(form); host.appendChild(fbHost); host.appendChild(evHost);

    function refreshSubmit(){
      var ready = checkBoxes.every(function(c){ return c.checked; });
      submit.disabled = !ready;
      help.style.display = ready ? "none" : "block";
    }
    function current(){
      var a = { fields: {}, checks: checkBoxes.map(function(c){ return c.checked; }) };
      stage.fields.forEach(function(f){
        a.fields[f.id] = { text: inputs[f.id].ta.value, sel: inputs[f.id].sel ? inputs[f.id].sel.value : undefined };
      });
      if(nameInput) a.name = nameInput.value.trim();
      return a;
    }
    function setLocked(lock){
      Object.keys(inputs).forEach(function(k){ inputs[k].ta.readOnly = lock; if(inputs[k].sel) inputs[k].sel.disabled = lock; });
      checkBoxes.forEach(function(c){ c.disabled = lock; });
      if(nameInput) nameInput.readOnly = lock;
      submit.style.display = lock ? "none" : "";
      if(lock) help.style.display = "none";
    }

    function show(ans, res, fromLoad){
      fbHost.innerHTML = "";
      Object.keys(inputs).forEach(function(k){ inputs[k].err.hidden = true; inputs[k].ta.removeAttribute("aria-invalid"); });
      if(res.pass){
        var b = fbBlock(true, stage.passTitle || "Submitted -- this would hold up with the team.");
        if(stage.passWhy){ var dl = el("dl", "desk-fb-dl"); fbRow(dl, "Why it works", stage.passWhy); b.box.appendChild(dl); }
        fbHost.appendChild(b.box);
        setLocked(true);
        var edit = btn("Revise your work", "btn-ghost");
        edit.addEventListener("click", function(){
          Store.resetStage(ctx.taskId, stage.id);
          fbHost.innerHTML = ""; evHost.innerHTML = "";
          setLocked(false); refreshSubmit();
          ctx.onChange();
          inputs[stage.fields[0].id].ta.focus();
        });
        b.box.appendChild(edit);
        if(stage.evidence) renderEvidence(evHost, stage, ans);
        if(!fromLoad) b.title.focus();
        return;
      }
      var b2 = fbBlock(false, "Not ready to send yet -- fix these first.");
      var ul = el("ul", "desk-fb-list");
      var byField = {};
      res.problems.forEach(function(p){
        ul.appendChild(el("li", null, p.msg));
        (byField[p.field] = byField[p.field] || []).push(p.msg.replace(/^[^:]*:\s*/, ""));
      });
      if(!res.checksDone) ul.appendChild(el("li", null, "Finish your self-check before submitting."));
      b2.box.appendChild(ul);
      if(stage.failWhy){ var dl2 = el("dl", "desk-fb-dl"); fbRow(dl2, "Why this matters", stage.failWhy); b2.box.appendChild(dl2); }
      b2.box.appendChild(el("p", "desk-hint", "Your self-check has been cleared -- re-check after you edit."));
      fbHost.appendChild(b2.box);
      Object.keys(byField).forEach(function(k){
        inputs[k].err.hidden = false;
        inputs[k].err.textContent = byField[k].join(" ");
        inputs[k].ta.setAttribute("aria-invalid", "true");
      });
      /* A failed submission means the self-check wasn't real -- clear it. */
      checkBoxes.forEach(function(c){ c.checked = false; });
      Store.draft(ctx.taskId, stage.id + ":checks", []);
      refreshSubmit();
      if(!fromLoad) b2.title.focus();
    }

    submit.addEventListener("click", function(){
      if(submit.disabled) return;
      var ans = current();
      stage.fields.forEach(function(f){ Store.draft(ctx.taskId, stage.id + ":" + f.id, ans.fields[f.id].text); });
      var res = evaluate(stage, ans);
      var st = Store.attempt(ctx.taskId, stage.id, ans, res.pass);
      attemptsNote.textContent = st.attempts > 1 ? "Attempt " + st.attempts : "";
      show(ans, res, false);
      ctx.onChange();
    });

    var saved = Store.get(ctx.taskId).stages[stage.id];
    if(saved && saved.answer && evaluate(stage, saved.answer).pass){
      var a = saved.answer;
      stage.fields.forEach(function(f){
        inputs[f.id].ta.value = a.fields[f.id].text;
        if(inputs[f.id].sel) inputs[f.id].sel.value = a.fields[f.id].sel || "";
      });
      checkBoxes.forEach(function(c){ c.checked = true; });
      if(nameInput) nameInput.value = a.name || "";
      show(a, evaluate(stage, a), true);
    } else {
      refreshSubmit();
    }
  }

  function renderEvidence(host, stage, ans){
    host.innerHTML = "";
    var ev = stage.evidence;
    var lines = [];
    lines.push("TRAINING WORK SAMPLE");
    lines.push(ev.title);
    lines.push("Everfield Goods is a fictional company used in PVA Free Training. Orders and data are simulated.");
    lines.push("Prepared by: " + (ans.name || "E-commerce VA trainee") + "  |  Work date: " + (window.EVERFIELD ? EVERFIELD.simDate : "") + " (simulated)");
    lines.push("Requested by: " + ev.requestedBy);
    lines.push("");
    (ev.preface || []).forEach(function(l){ lines.push(l); });
    if(ev.preface && ev.preface.length) lines.push("");
    stage.fields.forEach(function(f){
      var v = ans.fields[f.id];
      lines.push((ev.fieldHeads && ev.fieldHeads[f.id]) || f.label);
      if(v.sel) lines.push("Order #" + v.sel);
      lines.push(v.text.trim());
      lines.push("");
    });
    lines.push("Self-check completed before submission: " + stage.selfCheck.length + " of " + stage.selfCheck.length + " items.");
    var text = lines.join("\n");

    var box = el("section", "desk-evidence");
    box.setAttribute("aria-label", "Your work sample");
    box.appendChild(el("div", "ws-preview-label", ev.badge || "Training work sample"));
    box.appendChild(el("p", "desk-hint", ev.note));
    var pre = el("pre", "ws-preview", text);
    pre.tabIndex = 0;
    pre.setAttribute("aria-label", "Work sample text");
    box.appendChild(pre);
    var row = el("div", "desk-actions");
    var copy = btn("Copy work sample", "btn-ghost");
    var dl = btn("Download as .txt", "btn-ghost");
    var msg = el("span", "desk-attempts"); msg.setAttribute("aria-live", "polite");
    copy.addEventListener("click", function(){
      var done = function(){ msg.textContent = "Copied."; };
      if(navigator.clipboard && navigator.clipboard.writeText){ navigator.clipboard.writeText(text).then(done, function(){ msg.textContent = "Copy failed -- select the text and copy it manually."; }); }
      else { msg.textContent = "Select the text above and copy it manually."; }
    });
    dl.addEventListener("click", function(){
      var blob = new Blob([text], { type: "text/plain" });
      var a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = ev.filename || "everfield-work-sample.txt";
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(function(){ URL.revokeObjectURL(a.href); }, 1000);
    });
    row.appendChild(copy); row.appendChild(dl); row.appendChild(msg);
    box.appendChild(row);
    host.appendChild(box);
  }

  function renderStage(host, stage, ctx){
    host.innerHTML = "";
    if(stage.type === "decision") return renderDecision(host, stage, ctx);
    if(stage.type === "triage") return renderTriage(host, stage, ctx);
    if(stage.type === "sequence") return renderSequence(host, stage, ctx);
    if(stage.type === "compose") return renderCompose(host, stage, ctx);
  }

  window.PVADesk = {
    decode: decode,
    store: Store,
    evaluate: evaluate,
    stagePassed: stagePassed,
    taskStatus: taskStatus,
    renderBrief: renderBrief,
    renderStage: renderStage,
    STORE_KEY: STORE_KEY,
    _hash: h   /* used by tools/desk-codec.js parity check only */
  };
})();
