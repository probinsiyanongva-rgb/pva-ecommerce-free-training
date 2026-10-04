/* PVA Free Training -- E-commerce VA Foundations
   Work Desk engine -- CORE (no DOM). Runs in the browser and in Node (tests, codec).

   This file holds the learning mechanics that are the same for every module:
     - answer protection (encoding + salted hashes), parameterized per module
     - module-scoped learner storage (one key per module)
     - validators in five tiers (exact, consistency, criteria, self-review, human review)
       plus a junk filter for free text
     - stage evaluation, registered per stage type
     - feedback composition with a safety rule (never reveal the answer)
     - retry / reconsideration policy
     - verified-work state derived from stored answers (never a stored flag)

   Nothing in here may name a module, a record, a product, a person or a
   workflow. Wording a learner sees comes from module data or from the
   generic defaults in DEFAULT_COPY.

   Companion files:
     shared/workdesk-ui.js    DOM: evidence kinds, stage renderers, feedback, work samples
     shared/workdesk-page.js  page controller: brief -> stages -> next task, progress integration
     tools/desk-codec.js      encode / decode / lint module content (uses this file)
   See docs/workdesk-architecture.md. */

(function(root, factory){
  if(typeof module === "object" && module.exports) module.exports = factory();
  else root.PVADeskCore = factory();
})(typeof self !== "undefined" ? self : this, function(){
  "use strict";

  /* ---------------- defaults ---------------- */
  var DEFAULTS = {
    storagePrefix: "pva-ecom-ft-",
    storageSuffix: "-desk",
    key: "PVADeskEncoding",          /* XOR key used only to keep answers out of view-source */
    retry: { pauseAfterFails: 2 },   /* pause-and-re-check from the Nth failed attempt on a stage */
    text: {
      exampleSimilarity: 0.55,       /* word-overlap ratio above which text counts as a copy of the example */
      keywordListMinWords: 8,        /* only texts this long are checked for keyword lists */
      minFunctionWordRatio: 0.15,    /* below this share of connecting words, text reads as a keyword list */
      defaultMinWords: 6
    }
  };
  var RESERVED_IDS = ["progress"];   /* "pva-ecom-ft-progress" is the legacy course progress key */

  /* Generic learner-facing wording. Any entry can be overridden per module (config.copy). */
  var DEFAULT_COPY = {
    decisionPassTitle: "Good call -- that's the right read.",
    decisionFailTitle: "Not yet -- go back to the evidence.",
    missedLead: function(n){ return "Your read of the record leaves out " + n + " thing" + (n > 1 ? "s" : "") + " the evidence supports. Where to look:"; },
    reasoningLead: "Your chosen action may be reasonable, but your read of the evidence isn't complete. ",
    reasoningFallback: "A good action for the wrong reasons won't hold up on the next case.",
    reviewFallback: "Check your review against each part of the standard, one at a time.",
    triagePassTitle: "Reviewed -- every call holds up.",
    triageFailTitle: function(n, total, noun){ return n + " of " + total + " " + noun + " need another look."; },
    triageFailBody: function(nounOne){ return "Each flagged " + nounOne + " has a note pointing to the evidence to re-read. Calls that hold up are marked ✓."; },
    sequencePassTitle: "That's the real sequence.",
    sequenceFailTitle: function(step){ return "Not yet -- step " + step + " is out of place."; },
    sequenceGate: "Open the source record first -- the clues are in the details.",
    sequenceRecheck: "Re-open the record marked Re-check before checking again.",
    composePassTitle: "Submitted -- this would hold up with the team.",
    composeFailTitle: "Not ready to send yet -- fix these first.",
    rowNoun: "items",
    rowNounOne: "item",
    pauseTitle: "Pause and re-check",
    pauseBody: function(attempts){ return "You've tried this " + attempts + " times. Before trying again, re-open the evidence below and look at it with the feedback in mind:"; },
    retryLabel: "Reconsider and try again",
    msgChoose: "choose an option.",
    msgNumber: function(d){ return "enter a number using digits only" + (d ? " (up to " + d + " decimal place" + (d > 1 ? "s" : "") + ")" : " (a whole number)") + "."; },
    msgMinWords: function(n){ return "write at least " + n + " real words, in sentences, that a teammate could act on."; },
    msgNotBlank: "this can't be blank.",
    msgKeywordList: "this reads like a list of keywords. Write it as plain sentences a teammate could read aloud.",
    msgSentences: function(n){ return "write it as " + n + " or more complete sentences -- not a list of keywords."; },
    msgExampleCopy: "this reads very close to the example. Write it for this record, in your own words.",
    msgGroup: function(title, hint){ return title + ": something in this entry doesn't hold up against the record yet. " + hint; },
    msgSelfCheck: "Finish your self-check before submitting."
  };

  /* ---------------- small utilities ---------------- */
  function assign(target){
    for(var i = 1; i < arguments.length; i++){
      var src = arguments[i]; if(!src) continue;
      for(var k in src) if(Object.prototype.hasOwnProperty.call(src, k)) target[k] = src[k];
    }
    return target;
  }
  function deepFreeze(o){
    if(o && typeof o === "object" && !Object.isFrozen(o)){
      Object.freeze(o);
      Object.keys(o).forEach(function(k){ deepFreeze(o[k]); });
    }
    return o;
  }
  function call(v){ var args = Array.prototype.slice.call(arguments, 1); return typeof v === "function" ? v.apply(null, args) : v; }

  /* Typed numbers (compose field type "number"). One canonical form is used to
     lock (codec) and to check (engine): optional leading "$", thousands commas
     and spaces removed, then fixed to the field's declared decimals. Entries with
     more decimal places than declared are refused, never rounded into a pass. */
  function normalizeNumber(raw, field){
    var d = (field && field.decimals) || 0;
    var s = String(raw === undefined || raw === null ? "" : raw).trim().replace(/^\$\s*/, "").replace(/(\d)[,\s](?=\d{3}(\D|$))/g, "$1");
    if(!s) return { ok: false, blank: true };
    if(!/^-?\d+(\.\d+)?$/.test(s)) return { ok: false };
    var frac = (s.split(".")[1] || "").replace(/0+$/, "");
    if(frac.length > d) return { ok: false };
    return { ok: true, value: Number(s).toFixed(d) };
  }

  /* ---------------- answer protection ---------------- */
  function fnv(str){
    var x = 0x811c9dc5;
    for(var i = 0; i < str.length; i++){ x ^= str.charCodeAt(i); x = Math.imul(x, 0x01000193) >>> 0; }
    return ("0000000" + x.toString(16)).slice(-8);
  }
  function utf8Encode(s){
    if(typeof TextEncoder !== "undefined") return new TextEncoder().encode(s);
    return Uint8Array.from(Buffer.from(s, "utf8"));
  }
  function utf8Decode(bytes){
    if(typeof TextDecoder !== "undefined") return new TextDecoder("utf-8").decode(bytes);
    return Buffer.from(bytes).toString("utf8");
  }
  function b64ToBytes(b64){
    if(typeof atob === "function"){ var bin = atob(b64), out = new Uint8Array(bin.length); for(var i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i); return out; }
    return Uint8Array.from(Buffer.from(b64, "base64"));
  }
  function bytesToB64(bytes){
    if(typeof Buffer !== "undefined") return Buffer.from(bytes).toString("base64");
    var s = ""; for(var i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]); return btoa(s);
  }

  /* A codec is bound to one module's salt and key. Keys are hashes of
     "<salt>|<stage>|<kind>|<item>|<value>"; the data never says which answer is right. */
  function createCodec(opts){
    if(!opts || !opts.salt) throw new Error("PVADesk: a module salt is required");
    var salt = String(opts.salt), key = String(opts.key || DEFAULTS.key);
    function xor(bytes){ var out = new Uint8Array(bytes.length); for(var i = 0; i < bytes.length; i++) out[i] = bytes[i] ^ key.charCodeAt(i % key.length); return out; }
    var codec = {
      hash: function(str){ return fnv(salt + "|" + str); },
      encode: function(obj){ return bytesToB64(xor(utf8Encode(JSON.stringify(obj)))); },
      decode: function(b64){ return JSON.parse(utf8Decode(xor(b64ToBytes(b64)))); }
    };
    /* key builders: the same strings are used to lock (codec) and to check (engine) */
    codec.keys = {
      finding:  function(sid, id, right){ return codec.hash(sid + "|f|" + id + "|" + (right ? 1 : 0)); },
      option:   function(sid, id, right){ return codec.hash(sid + "|o|" + id + "|" + (right ? 1 : 0)); },
      row:      function(sid, id, choice){ return codec.hash(sid + "|row|" + id + "|" + choice); },
      seq:      function(sid, id, pos){ return codec.hash(sid + "|seq|" + id + "|" + pos); },
      field:    function(sid, id, value){ return codec.hash(sid + "|fld|" + id + "|" + value); }
    };
    return codec;
  }

  /* ---------------- module-scoped learner storage ---------------- */
  var openStores = {};
  function memoryStorage(){ var m = {}; return { getItem: function(k){ return k in m ? m[k] : null; }, setItem: function(k, v){ m[k] = String(v); }, removeItem: function(k){ delete m[k]; } }; }
  function defaultStorage(){ try{ return window.localStorage; }catch(e){ return memoryStorage(); } }

  function storageKeyFor(moduleId, cfg){
    cfg = cfg || {};
    return (cfg.storagePrefix || DEFAULTS.storagePrefix) + moduleId + (cfg.storageSuffix || DEFAULTS.storageSuffix);
  }

  function createStore(opts){
    var key = opts.key, storage = opts.storage || defaultStorage();
    function readAll(){
      try{
        var raw = storage.getItem(key), s = raw ? JSON.parse(raw) : null;
        if(!s || typeof s !== "object" || !s.tasks) s = { v: 1, tasks: {} };
        return s;
      }catch(e){ return { v: 1, tasks: {} }; }
    }
    function writeAll(s){ try{ storage.setItem(key, JSON.stringify(s)); }catch(e){} }
    function taskRec(s, taskId){
      if(!s.tasks[taskId]) s.tasks[taskId] = { views: 0, stages: {}, drafts: {} };
      var t = s.tasks[taskId]; t.stages = t.stages || {}; t.drafts = t.drafts || {};
      return t;
    }
    return {
      key: key,
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
      draft: function(taskId, k, value){
        var s = readAll(), t = taskRec(s, taskId);
        if(value === undefined) delete t.drafts[k]; else t.drafts[k] = value;
        writeAll(s);
      },
      getDraft: function(taskId, k){ return taskRec(readAll(), taskId).drafts[k]; },
      unpass: function(taskId, stageId){
        var s = readAll(), t = taskRec(s, taskId);
        if(t.stages[stageId]){ delete t.stages[stageId].answer; delete t.stages[stageId].passedAt; }
        writeAll(s);
      }
    };
  }

  /* ---------------- text helpers (junk filter, never a quality grade) ---------------- */
  var Text = (function(){
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
      return w.length >= 6 && Object.keys(uw).length / w.length < 0.5;
    }
    var FUNCTION_WORDS = " the a an is are was were has have had to of in on at by for with and or but not no since it its this that they them their we our be been will can so as from before after until about there it's isn't hasn't haven't we've they've ";
    function functionWordRatio(t){
      var w = words(t).map(function(x){ return x.toLowerCase().replace(/[^a-z']/g, ""); }).filter(Boolean);
      if(!w.length) return 0;
      return w.filter(function(x){ return FUNCTION_WORDS.indexOf(" " + x + " ") !== -1; }).length / w.length;
    }
    function sentenceCount(t){ return String(t || "").split(/[.!?](\s|$)/).filter(function(s){ return words(s).length >= 3; }).length; }
    return { normalize: normalize, hasAny: hasAny, words: words, similarity: similarity, looksMeaningless: looksMeaningless, functionWordRatio: functionWordRatio, sentenceCount: sentenceCount };
  })();

  /* ---------------- validators, by tier ----------------
     Each returns problems as { field?, group?, msg }. Module data supplies the
     rules; the engine supplies only the mechanics. */
  function makeValidators(codec, textCfg, copy){
    var K = codec.keys;
    var exact = {                                   /* Tier 1: one defensible answer, hashed */
      finding: function(sid, f){ return f.k === K.finding(sid, f.id, true); },
      option:  function(sid, o){ return o.k === K.option(sid, o.id, true); },
      row:     function(sid, r, choice){ return !!choice && r.k === K.row(sid, r.id, choice); },
      seqPos:  function(sid, it, pos){ return (it.k || []).indexOf(K.seq(sid, it.id, pos)) !== -1; },
      field:   function(sid, f, v){
        var key = f.type === "multi" ? (v || []).slice().sort().join(",") : String(v || "");
        return (f.acc || []).indexOf(K.field(sid, f.id, key)) !== -1;
      }
    };
    function label(f, msg){ return { group: f.group, field: f.id, msg: f.label + ": " + msg }; }

    /* Free-text junk filter: stops blank, filler, keyword lists and copied examples.
       It never judges whether writing is good. */
    function hygiene(stage, f, text){
      var minW = f.minWords || stage.minWords || textCfg.defaultMinWords;
      if(!String(text).trim() || Text.words(text).length < minW || (minW >= 4 && Text.looksMeaningless(text)))
        return [label(f, minW > 1 ? call(copy.msgMinWords, minW) : copy.msgNotBlank)];
      if(minW >= textCfg.keywordListMinWords && Text.functionWordRatio(text) < textCfg.minFunctionWordRatio)
        return [label(f, copy.msgKeywordList)];
      if(f.minSentences && Text.sentenceCount(text) < f.minSentences)
        return [label(f, call(copy.msgSentences, f.minSentences))];
      return null;
    }
    var consistency = function(stage, f, text, vals){   /* Tier 2: the learner's parts agree */
      var out = [];
      (f.rules || []).forEach(function(r){ if(!Text.hasAny(text, r.any)) out.push(label(f, r.msg)); });
      (f.when || []).forEach(function(r){
        var other = vals[r.field], applies = r.eq !== undefined ? other === r.eq : r.ne !== undefined ? (!!other && other !== r.ne) : false;
        if(!applies) return;
        if(r.any && !Text.hasAny(text, r.any)) out.push(label(f, r.msg));
        if(r.notAny && Text.hasAny(text, r.notAny)) out.push(label(f, r.msg));
      });
      (stage.banned || []).forEach(function(b){ if(Text.hasAny(text, b.any)) out.push(label(f, b.msg)); });
      if(stage.example && Text.similarity(text, stage.example.text) > textCfg.exampleSimilarity) out.push(label(f, copy.msgExampleCopy));
      return out;
    };
    /* Tier 3: several acceptable answers; rules are visible criteria, not secrets. */
    var criteriaKinds = {
      required: function(f, v){ return (Array.isArray(v) ? v.length : String(v || "").trim()) ? null : "this is required."; },
      oneOf: function(f, v, r){ return r.values.indexOf(v) !== -1 ? null : r.msg; },
      minItems: function(f, v, r){ return (v || []).length >= r.n ? null : r.msg; },
      matchesSource: function(f, v, r){ return Text.hasAny(v, r.sources) ? null : r.msg; },
      distinctFrom: function(f, v, r, vals){ return Text.similarity(v, vals[r.field]) <= (r.max === undefined ? 0.6 : r.max) ? null : r.msg; }
    };
    function criteria(stage, f, v, vals){
      var out = [];
      (f.criteria || []).forEach(function(r){
        var fn = criteriaKinds[r.kind];
        if(!fn) throw new Error("PVADesk: unknown criteria rule '" + r.kind + "' on " + f.id);
        var m = fn(f, v, r, vals); if(m) out.push(label(f, m));
      });
      return out;
    }
    /* Tier 4: the learner completed the review structure (confirmations), nothing more. */
    function selfReview(stage, answer){
      var c = (answer && answer.confirms) || [];
      return (stage.confirm || []).every(function(_, i){ return c[i] === true; });
    }
    /* Tier 5: human review is declared, never computed here. */
    function humanReview(stage){ return stage.humanReview ? { required: true, note: stage.humanReview.note || "" } : null; }
    return { exact: exact, hygiene: hygiene, consistency: consistency, criteria: criteria, criteriaKinds: criteriaKinds, selfReview: selfReview, humanReview: humanReview };
  }

  /* ---------------- stage evaluators (registry) ---------------- */
  var stageTypes = {};
  function registerStageType(type, def){ stageTypes[type] = assign({}, stageTypes[type] || {}, def); }

  registerStageType("decision", { evaluate: function(stage, answer, V){
    var sid = stage.id, picked = answer.f || [], missed = [], wrongPicked = [];
    (stage.findings || []).forEach(function(f){
      var right = V.exact.finding(sid, f), sel = picked.indexOf(f.id) !== -1;
      if(right && !sel) missed.push(f);
      if(!right && sel) wrongPicked.push(f);
    });
    var opt = null, optRight = true;
    if(stage.options && stage.options.length){
      opt = stage.options.filter(function(o){ return o.id === answer.o; })[0] || null;
      optRight = !!opt && V.exact.option(sid, opt);
    }
    return { pass: optRight && !missed.length && !wrongPicked.length, missed: missed, wrongPicked: wrongPicked, option: opt, optRight: optRight };
  }});
  registerStageType("triage", { evaluate: function(stage, answer, V){
    var wrongRows = stage.rows.filter(function(r){ return !V.exact.row(stage.id, r, answer[r.id]); });
    return { pass: !wrongRows.length, wrongRows: wrongRows };
  }});
  registerStageType("sequence", { evaluate: function(stage, answer, V){
    var order = answer.order || [], firstWrong = -1;
    if(order.length !== stage.items.length) firstWrong = 0;
    else for(var i = 0; i < order.length; i++){
      var it = stage.items.filter(function(x){ return x.id === order[i]; })[0];
      if(!it || !V.exact.seqPos(stage.id, it, i)){ firstWrong = i; break; }
    }
    return { pass: firstWrong === -1, firstWrong: firstWrong };
  }});
  registerStageType("compose", { evaluate: function(stage, answer, V, copy){
    var vals = answer.values || {}, problems = [], badGroups = {}, fieldMsgGroups = {};
    stage.fields.forEach(function(f){
      var v = vals[f.id];
      if(f.type === "number"){
        var n = normalizeNumber(v, f);
        if(!n.ok){ problems.push({ group: f.group, field: f.id, msg: f.label + ": " + call(copy.msgNumber, f.decimals || 0) }); return; }
        if(f.acc && !V.exact.field(stage.id, f, n.value)){
          badGroups[f.group] = true;
          if(f.msg){ problems.push({ group: f.group, field: f.id, msg: f.label + ": " + f.msg }); fieldMsgGroups[f.group] = true; }
          return;
        }
        problems.push.apply(problems, V.criteria(stage, f, n.value, vals));
        return;
      }
      if(f.type === "select" || f.type === "multi"){
        if(f.type === "select" && !v){ problems.push({ group: f.group, field: f.id, msg: f.label + ": " + copy.msgChoose }); return; }
        if(f.acc && !V.exact.field(stage.id, f, v)){
          badGroups[f.group] = true;
          if(f.msg){ problems.push({ group: f.group, field: f.id, msg: f.label + ": " + f.msg }); fieldMsgGroups[f.group] = true; }
          return;
        }
        problems.push.apply(problems, V.criteria(stage, f, v, vals));
        return;
      }
      var text = v || "";
      var junk = V.hygiene(stage, f, text);
      if(junk){ problems.push.apply(problems, junk); return; }
      problems.push.apply(problems, V.criteria(stage, f, text, vals));
      problems.push.apply(problems, V.consistency(stage, f, text, vals));
    });
    (stage.groups || []).forEach(function(g){
      if(badGroups[g.id] && !fieldMsgGroups[g.id]) problems.unshift({ group: g.id, msg: call(copy.msgGroup, g.title, g.hint) });
    });
    var confirmsDone = V.selfReview(stage, answer);
    return { pass: !problems.length && confirmsDone, problems: problems, badGroups: Object.keys(badGroups), confirmsDone: confirmsDone, humanReview: V.humanReview(stage) };
  }});

  /* ---------------- feedback composition ----------------
     Feedback may say what the learner chose, which principle failed and where to
     look. It must not reveal a correct finding, the correct option, or a value.
     The safety filter drops any line that contains answer text. */
  function findingPointer(f){
    if(f.miss) return f.miss;
    return [f.principle, f.look].filter(Boolean).join(" ");
  }
  function safetyFilter(lines, forbidden){
    var bad = forbidden.filter(function(s){ return s && s.length >= 12; }).map(function(s){ return Text.normalize(s.replace(/[.\s]+$/, "")).trim(); });
    return lines.filter(function(line){
      var n = Text.normalize(line);
      var leak = bad.some(function(b){ return n.indexOf(b) !== -1; });
      if(leak && typeof console !== "undefined") console.warn("PVADesk: feedback line withheld because it contains answer text:", line);
      return !leak;
    });
  }
  function composeDecisionFeedback(stage, res, copy, V){
    var correctFindings = (stage.findings || []).filter(function(f){ return V.exact.finding(stage.id, f); }).map(function(f){ return f.text; });
    var correctOption = (stage.options || []).filter(function(o){ return V.exact.option(stage.id, o); }).map(function(o){ return o.text; });
    var forbidden = correctFindings.concat(res.option && res.optRight ? [] : correctOption);
    var fb = { title: copy.decisionFailTitle, chosen: res.option ? res.option.text : null, missedLead: null, pointers: [], wrongPicks: [], why: null,
               categories: [] };
    if(res.missed.length){
      fb.missedLead = call(copy.missedLead, res.missed.length);
      fb.pointers = safetyFilter(res.missed.map(findingPointer), forbidden);
    }
    res.wrongPicked.forEach(function(f){
      var w = safetyFilter([f.wrong || ""], forbidden)[0];
      fb.wrongPicks.push({ text: f.text.replace(/[.\s]+$/, ""), why: w === undefined ? "" : w });
      if(f.category) fb.categories.push(f.category);
    });
    var why;
    if(res.option && !res.optRight){ why = res.option.why; if(res.option.category) fb.categories.push(res.option.category); }
    else if(res.option) why = copy.reasoningLead + (stage.findingsWhy || copy.reasoningFallback);
    else why = stage.findingsWhy || copy.reviewFallback;
    fb.why = why ? (safetyFilter([why], forbidden)[0] || null) : null;
    return fb;
  }

  /* ---------------- the desk: one module's engine instance ---------------- */
  function createDesk(config, opts){
    opts = opts || {};
    if(!config || !config.moduleId) throw new Error("PVADesk: config.moduleId is required");
    if(!/^[a-z0-9][a-z0-9-]*$/.test(config.moduleId)) throw new Error("PVADesk: invalid moduleId '" + config.moduleId + "'");
    if(RESERVED_IDS.indexOf(config.moduleId) !== -1) throw new Error("PVADesk: moduleId '" + config.moduleId + "' is reserved");
    var storageKey = config.storageKey || storageKeyFor(config.moduleId, config);
    var bucket = opts.storageScope || "default";
    openStores[bucket] = openStores[bucket] || {};
    if(openStores[bucket][storageKey] && openStores[bucket][storageKey] !== config.moduleId)
      throw new Error("PVADesk: storage key '" + storageKey + "' is already used by module " + openStores[bucket][storageKey]);
    openStores[bucket][storageKey] = config.moduleId;

    var copy = assign({}, DEFAULT_COPY, config.copy);
    var textCfg = assign({}, DEFAULTS.text, config.text);
    var retry = assign({}, DEFAULTS.retry, config.retry);
    var codec = createCodec({ salt: config.salt, key: config.key });
    var store = createStore({ key: storageKey, storage: opts.storage });
    var V = makeValidators(codec, textCfg, copy);

    function evaluate(stage, answer){
      if(!answer) return { pass: false };
      var def = stageTypes[stage.type];
      if(!def || !def.evaluate) return { pass: false };
      try{ return def.evaluate(stage, answer, V, copy); }catch(e){ return { pass: false }; }
    }
    function stagePassed(taskId, stage, rec){
      var t = rec || store.get(taskId), st = t.stages[stage.id];
      return !!(st && st.answer && evaluate(stage, st.answer).pass);
    }
    function taskStatus(task){
      var t = store.get(task.id);
      var passed = task.stages.filter(function(s){ return stagePassed(task.id, s, t); }).length;
      var attempted = task.stages.some(function(s){ return t.stages[s.id] && t.stages[s.id].attempts > 0; });
      var ev = task.stages.some(function(s){ return s.evidence; });
      var level = "new";
      if(t.views) level = "viewed";
      if(attempted) level = "attempted";
      if(passed === task.stages.length) level = ev ? "evidence" : "practiced";
      return { level: level, passed: passed, total: task.stages.length, hasEvidence: ev };
    }
    /* Verified-work state: derived only from answers that re-validate now.
       Distinct from legacy course completion, which this engine never reads or writes. */
    function verifiedWork(tasks){
      var out = {};
      tasks.forEach(function(task){
        var st = taskStatus(task), t = store.get(task.id);
        out[task.id] = {
          verified: st.passed === st.total,
          stagesVerified: st.passed, stagesTotal: st.total,
          samplesEarned: task.stages.filter(function(s){ return s.evidence && stagePassed(task.id, s, t); }).map(function(s){ return s.id; })
        };
      });
      return out;
    }
    function shouldPause(st){ return !!st && (st.fails || 0) >= retry.pauseAfterFails; }

    return {
      config: config, moduleId: config.moduleId, storageKey: storageKey,
      copy: copy, codec: codec, store: store, validators: V, retry: retry,
      decode: function(payload){ return codec.decode(payload); },
      evaluate: evaluate, stagePassed: stagePassed, taskStatus: taskStatus, verifiedWork: verifiedWork,
      shouldPause: shouldPause,
      decisionFeedback: function(stage, res){ return composeDecisionFeedback(stage, res, copy, V); }
    };
  }

  return {
    VERSION: "2.1.0",
    DEFAULTS: DEFAULTS, DEFAULT_COPY: DEFAULT_COPY,
    createCodec: createCodec, createStore: createStore, createDesk: createDesk, storageKeyFor: storageKeyFor,
    registerStageType: registerStageType, stageTypes: stageTypes,
    Text: Text, normalizeNumber: normalizeNumber, memoryStorage: memoryStorage, deepFreeze: deepFreeze, safetyFilter: safetyFilter, call: call, assign: assign,
    _resetStoreRegistry: function(){ openStores = {}; }
  };
});
