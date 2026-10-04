/* PVA Free Training -- E-commerce VA Foundations
   Work Desk engine -- PAGE CONTROLLER. Requires workdesk.js and workdesk-ui.js.

   Mounts one module's desk into the standard module page markup:
     brief -> stages -> next task, contextual buttons, status line, task pills,
     #task-N deep links, and integration with the legacy course progress.

   Two progress concepts are kept apart on purpose:
     - legacy course completion (PVAEcom, key "pva-ecom-ft-progress"): historical,
       never erased, shown on the course map. Written ONLY when the new work for
       that lesson has been verified.
     - verified-work state (this module's desk key): derived from answers that
       re-validate on every load. A legacy checkmark never counts as verified work
       or as an earned work sample.

   Usage (in a module page, after loading the module's desk-data.js):
     PVADeskPage.mount({ module: "m4" });                                       */

(function(root){
  "use strict";
  var Core = root.PVADeskCore, UI = root.PVADeskUI;
  if(!Core || !UI) throw new Error("PVADeskPage: load workdesk.js and workdesk-ui.js first");
  var call = Core.call;

  var PAGE_COPY = {
    briefLabel: "Brief",
    referenceSummary: "Desk reference: what you need to know for this task",
    kicker: function(i, n){ return "Task " + i + " of " + n; },
    objective: function(o){ return "Objective: " + o; },
    stepLabel: function(label, i, n){ return label.toUpperCase() + "  ·  STEP " + i + " OF " + n; },
    notDone: { decision: "Make your decision above to move on.", triage: "Submit your review above to move on.",
               sequence: "Check your sequence above to move on.", compose: "Submit your work above to move on." },
    nextTask: "Continue to the next task",
    finish: "Close out the desk",
    fallbackCta: "Continue",
    statusEvidence: "<strong>Done</strong> -- work sample produced.",
    statusPracticed: function(n, parts){ return "<strong>Done</strong> -- all " + n + " " + parts + " completed."; },
    statusAttempted: function(p, n, parts){ return "In progress -- " + p + " of " + n + " " + parts + " done."; },
    statusNew: function(n, parts){ return "Not started -- " + n + " " + parts + "."; },
    statusLegacy: " You marked this lesson complete in the earlier version; that checkmark stays. The desk work here is new -- do it whenever you're ready.",
    pillDone: ", done", pillLegacy: ", complete (earlier version)", pillProgress: ", in progress",
    stillOpen: function(n, titles){ return "That was the last task on the list, but " + n + " task" + (n > 1 ? "s are" : " is") + " still open: " + titles + ". Use the task pills above to finish them."; },
    complete: "All tasks complete."
  };

  function mount(opts){
    opts = opts || {};
    var modules = root.PVA_DESK_MODULES || {};
    var mod = modules[opts.module];
    if(!mod) throw new Error("PVADeskPage: no desk data loaded for module '" + opts.module + "'");
    var config = Core.assign({}, mod.config);
    var team = (root.EVERFIELD && root.EVERFIELD.team) || {};
    if(!config.simDate && root.EVERFIELD && root.EVERFIELD.calendar && root.EVERFIELD.calendar[config.moduleId])
      config.simDate = root.EVERFIELD.calendar[config.moduleId].date;

    var desk = Core.createDesk(config);
    var DATA = desk.decode(mod.payload);
    var TASKS = DATA.tasks;
    var P = Core.assign({}, PAGE_COPY, config.copy && config.copy.page);
    var progress = root.PVAEcom || { isLessonDone: function(){ return false; }, markLessonDone: function(){} };
    /* How the task pills show legacy completion that has no verified desk work yet:
       "check"    -- same checkmark as verified work (the status line says which it is)
       "distinct" -- checkmark only for verified work; legacy-only pills get a separate marker */
    var legacyPill = config.legacyPill || "check";

    var $ = function(id){ return document.getElementById(id); };
    var navEl = $("lessonNav"), kickerEl = $("lessonKicker"), titleEl = $("lessonTitle"), objectiveEl = $("lessonObjective"),
        statusEl = $("taskStatus"), stepBarEl = $("stepBar"), stepLabelEl = $("stepLabel"), panel = $("stagePanel"),
        badgeSlot = $("portfolioBadgeSlot"), btnPrev = $("btnPrev"), btnNext = $("btnNext"), nextHint = $("nextHint"),
        doneBanner = $("doneBanner"), lessonCard = $("lessonCard");
    if($("deskDate") && config.simDate) $("deskDate").textContent = config.simDate;

    var cur = 0, stageIdx = 0;
    function stagesOf(t){ return [{ label: P.briefLabel, type: "brief" }].concat(t.stages); }
    function stageDone(t, i){ var s = stagesOf(t)[i]; return s.type === "brief" ? true : desk.stagePassed(t.id, s); }
    function ctaFor(s){ return (s && s.cta) || P.fallbackCta; }

    /* The only place legacy progress is written: after verified work. */
    function syncCompletion(t){
      var st = desk.taskStatus(t);
      if(st.passed === st.total && !progress.isLessonDone(t.id)) progress.markLessonDone(t.id);
      return st;
    }
    function statusText(t){
      var st = desk.taskStatus(t);
      var legacy = progress.isLessonDone(t.id) && st.passed < st.total;
      var parts = st.total === 1 ? "part" : "parts", s;
      if(st.level === "evidence") s = P.statusEvidence;
      else if(st.level === "practiced") s = call(P.statusPracticed, st.total, parts);
      else if(st.level === "attempted") s = call(P.statusAttempted, st.passed, st.total, parts);
      else s = call(P.statusNew, st.total, parts);
      if(legacy) s += P.statusLegacy;
      return s;
    }
    function buildNav(){
      navEl.innerHTML = "";
      TASKS.forEach(function(t, i){
        var pill = document.createElement("button");
        pill.type = "button"; pill.className = "lesson-pill";
        pill.textContent = (i + 1) + ". " + t.title;
        pill.addEventListener("click", function(){ loadTask(i, true); });
        navEl.appendChild(pill);
      });
      highlightNav();
    }
    function highlightNav(){
      Array.prototype.forEach.call(navEl.children, function(pill, i){
        var t = TASKS[i], st = desk.taskStatus(t);
        var verified = st.passed === st.total, legacyDone = progress.isLessonDone(t.id);
        var showDone = legacyPill === "distinct" ? verified : legacyDone;
        pill.setAttribute("aria-current", i === cur ? "true" : "false");
        pill.classList.toggle("done", showDone);
        pill.classList.toggle("legacy", legacyPill === "distinct" && legacyDone && !verified);
        pill.classList.toggle("started", !showDone && st.level === "attempted");
        pill.setAttribute("aria-label", (i + 1) + ". " + t.title + (verified ? P.pillDone : legacyDone ? P.pillLegacy : st.level === "attempted" ? P.pillProgress : ""));
      });
    }
    function loadTask(i, userAction){
      cur = i; stageIdx = 0;
      var t = TASKS[i];
      desk.store.touch(t.id);
      kickerEl.textContent = call(P.kicker, i + 1, TASKS.length);
      titleEl.textContent = t.title;
      objectiveEl.textContent = call(P.objective, t.objective);
      badgeSlot.innerHTML = t.portfolio ? '<span class="portfolio-badge">Portfolio</span>' : "";
      doneBanner.style.display = "none";
      try{ history.replaceState(null, "", "#task-" + (i + 1)); }catch(e){}
      renderStage(); highlightNav();
      if(userAction){
        window.scrollTo({ top: lessonCard.offsetTop - 20, behavior: "smooth" });
        titleEl.focus({ preventScroll: true });
      }
    }
    function renderStage(){
      var t = TASKS[cur], stages = stagesOf(t), s = stages[stageIdx];
      stepLabelEl.textContent = call(P.stepLabel, s.label, stageIdx + 1, stages.length);
      stepBarEl.innerHTML = "";
      stages.forEach(function(_, idx){
        var seg = document.createElement("div");
        seg.className = "seg" + (idx < stageIdx ? " past" : idx === stageIdx ? " active" : "");
        stepBarEl.appendChild(seg);
      });
      panel.innerHTML = "";
      if(s.type === "brief"){
        UI.renderBrief(panel, t.brief, team, desk.copy);
        var ref = document.createElement("details"); ref.className = "desk-reference";
        var sum = document.createElement("summary"); sum.textContent = P.referenceSummary; ref.appendChild(sum);
        (t.reference || []).forEach(function(p){ var e = document.createElement("p"); e.innerHTML = p; ref.appendChild(e); });
        panel.appendChild(ref);
      } else {
        UI.renderStage(panel, s, { desk: desk, taskId: t.id, onChange: onWork });
      }
      btnPrev.style.visibility = stageIdx === 0 ? "hidden" : "visible";
      statusEl.innerHTML = statusText(t);
      updateNext();
    }
    function onWork(){ var t = TASKS[cur]; syncCompletion(t); statusEl.innerHTML = statusText(t); highlightNav(); updateNext(); }
    function updateNext(){
      var t = TASKS[cur], stages = stagesOf(t), s = stages[stageIdx];
      var done = stageDone(t, stageIdx), isLast = stageIdx === stages.length - 1;
      if(!done){
        btnNext.disabled = true;
        nextHint.textContent = P.notDone[s.type] || "";
        btnNext.textContent = isLast ? P.nextTask : ctaFor(stages[stageIdx + 1]);
        return;
      }
      btnNext.disabled = false; nextHint.textContent = "";
      if(!isLast) btnNext.textContent = ctaFor(stages[stageIdx + 1]);
      else btnNext.textContent = cur < TASKS.length - 1 ? P.nextTask : P.finish;
    }
    btnPrev.addEventListener("click", function(){
      if(stageIdx > 0){ stageIdx--; renderStage(); stepLabelEl.scrollIntoView({ block: "nearest" }); titleEl.focus({ preventScroll: true }); }
    });
    btnNext.addEventListener("click", function(){
      var t = TASKS[cur], stages = stagesOf(t);
      if(!stageDone(t, stageIdx)) return;          /* disabled anyway; belt-and-braces */
      if(stageIdx < stages.length - 1){
        stageIdx++; renderStage();
        window.scrollTo({ top: lessonCard.offsetTop - 20, behavior: "smooth" });
        titleEl.focus({ preventScroll: true });
        return;
      }
      syncCompletion(t); highlightNav();
      if(cur < TASKS.length - 1){ loadTask(cur + 1, true); return; }
      var open = TASKS.filter(function(x){ var st = desk.taskStatus(x); return st.passed < st.total; });
      doneBanner.style.display = "block";
      doneBanner.textContent = open.length ? call(P.stillOpen, open.length, open.map(function(x){ return x.title; }).join(", ")) : P.complete;
      doneBanner.scrollIntoView({ behavior: "smooth" });
    });

    TASKS.forEach(syncCompletion);
    buildNav();
    (function(){
      var m = /^#task-(\d+)$/.exec(location.hash || "");
      var i = m ? Math.min(Math.max(parseInt(m[1], 10) - 1, 0), TASKS.length - 1) : -1;
      if(i < 0){ i = 0; for(var k = 0; k < TASKS.length; k++){ var st = desk.taskStatus(TASKS[k]); if(st.passed < st.total){ i = k; break; } } }
      loadTask(i, false);
    })();
    window.addEventListener("hashchange", function(){
      var m = /^#task-(\d+)$/.exec(location.hash || "");
      if(m){ var i = parseInt(m[1], 10) - 1; if(i >= 0 && i < TASKS.length && i !== cur) loadTask(i, true); }
    });

    var api = {
      desk: desk, tasks: TASKS,
      verifiedWork: function(){ return desk.verifiedWork(TASKS); },
      legacyCompletion: function(){ var o = {}; TASKS.forEach(function(t){ o[t.id] = progress.isLessonDone(t.id); }); return o; }
    };
    /* Read-only convenience handle for the mounted module (used by tests and the console). */
    root.PVADesk = {
      moduleId: desk.moduleId, storageKey: desk.storageKey, STORE_KEY: desk.storageKey,
      decode: desk.decode, evaluate: desk.evaluate, stagePassed: desk.stagePassed, taskStatus: desk.taskStatus,
      store: desk.store, verifiedWork: api.verifiedWork, legacyCompletion: api.legacyCompletion
    };
    return api;
  }

  root.PVADeskPage = { mount: mount, PAGE_COPY: PAGE_COPY };
})(typeof self !== "undefined" ? self : this);
