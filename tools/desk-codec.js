#!/usr/bin/env node
/* PVA Free Training -- Work Desk content codec (any module)

   Module content is authored as a plaintext source (JSON) with readable answer
   markers, then encoded into <module>/desk-data.js. The plaintext source is never
   committed or deployed (*.src.json is git-ignored): it would publish the answers.
   Recover it any time from the shipped file.

     node tools/desk-codec.js decode module-4/desk-data.js > m4.src.json
     node tools/desk-codec.js check  m4.src.json            (lint; exit 1 on errors)
     node tools/desk-codec.js encode m4.src.json module-4/desk-data.js

   Source shape:
     { "config": { "moduleId": "m4", "salt": "...", "key": "...", ... },   <- shipped as plain JSON
       "version": 2, "module": "m4", "tasks": [ ... ] }                      <- shipped encoded

   Plaintext answer markers (removed and replaced by salted hashes on encode):
     findings[].correct: true            options[].correct: true
     triage rows[].answer: "<choiceId>"
     sequence correctOrder: ["id", ...]
     compose select fields[].accept: ["value", ...]
     compose multi  fields[].accept: [["a","b"], ["a"], ...]   (each an acceptable set)

   Hashing and encoding come from shared/workdesk.js, so the codec and the
   engine cannot drift apart. */

var fs = require("fs");
var path = require("path");
var Core = require(path.join(__dirname, "..", "shared", "workdesk.js"));

function codecFor(config){
  if(!config || !config.moduleId || !config.salt) throw new Error("source config needs moduleId and salt");
  return Core.createCodec({ salt: config.salt, key: config.key });
}

function lockStage(st, K){
  if(st.type === "decision"){
    (st.findings || []).forEach(function(f){ f.k = K.finding(st.id, f.id, !!f.correct); delete f.correct; });
    (st.options || []).forEach(function(o){ o.k = K.option(st.id, o.id, !!o.correct); delete o.correct; });
  }
  if(st.type === "triage"){
    st.rows.forEach(function(r){
      if(!r.answer) throw new Error("triage row without answer: " + st.id + "/" + r.id);
      r.k = K.row(st.id, r.id, r.answer); delete r.answer;
    });
  }
  if(st.type === "sequence"){
    st.items.forEach(function(it){ it.k = [K.seq(st.id, it.id, st.correctOrder.indexOf(it.id))]; });
    delete st.correctOrder;
  }
  if(st.type === "compose"){
    st.fields.forEach(function(f){
      if(f.type === "select" && f.accept){ f.acc = f.accept.map(function(v){ return K.field(st.id, f.id, v); }); delete f.accept; }
      if(f.type === "multi" && f.accept){ f.acc = f.accept.map(function(set){ return K.field(st.id, f.id, set.slice().sort().join(",")); }); delete f.accept; }
    });
  }
}
function unlockStage(st, K){
  if(st.type === "decision"){
    (st.findings || []).forEach(function(f){ f.correct = f.k === K.finding(st.id, f.id, true); delete f.k; });
    (st.options || []).forEach(function(o){ o.correct = o.k === K.option(st.id, o.id, true); delete o.k; });
  }
  if(st.type === "triage"){
    st.rows.forEach(function(r){
      r.answer = st.choices.map(function(c){ return c.id; }).filter(function(c){ return r.k === K.row(st.id, r.id, c); })[0];
      delete r.k;
    });
  }
  if(st.type === "sequence"){
    var order = [];
    st.items.forEach(function(it){
      for(var p = 0; p < st.items.length; p++){ if(it.k.indexOf(K.seq(st.id, it.id, p)) !== -1) order[p] = it.id; }
      delete it.k;
    });
    st.correctOrder = order;
  }
  if(st.type === "compose"){
    st.fields.forEach(function(f){
      if(f.type === "select" && f.acc){ f.accept = f.options.map(function(o){ return o.value; }).filter(function(v){ return f.acc.indexOf(K.field(st.id, f.id, v)) !== -1; }); delete f.acc; }
      if(f.type === "multi" && f.acc){
        var vals = f.options.map(function(o){ return o.value; }), sets = [];
        for(var m = 0; m < (1 << vals.length); m++){
          var set = vals.filter(function(_, i){ return m & (1 << i); });
          if(f.acc.indexOf(K.field(st.id, f.id, set.slice().sort().join(","))) !== -1) sets.push(set);
        }
        f.accept = sets; delete f.acc;
      }
    });
  }
}

/* ---------------- lint: the spec's content integrity rules ---------------- */
function lint(src){
  var errors = [], warnings = [], ids = {};
  function err(m){ errors.push(m); } function warn(m){ warnings.push(m); }
  var decisions = [];
  (src.tasks || []).forEach(function(t){
    if(!t.id || !t.title || !t.objective) err("task missing id/title/objective: " + (t.id || "?"));
    if(!t.brief || !t.brief.from || !t.brief.subject) err(t.id + ": task needs a work request (brief.from, brief.subject)");
    t.stages.forEach(function(st, si){
      if(ids[st.id]) err("duplicate stage id " + st.id); ids[st.id] = 1;
      if(!st.label) err(st.id + ": stage needs a label");
      if(si > 0 && !st.cta) warn(st.id + ": no cta -- the button into this stage will read 'Continue'");
      if(si === 0 && !st.cta) warn(st.id + ": no cta -- the button from the brief will read 'Continue'");
      if(st.type === "decision"){
        var correctF = st.findings.filter(function(f){ return f.correct; });
        if(!correctF.length) err(st.id + ": no correct finding");
        if(correctF.length === st.findings.length) err(st.id + ": every finding is correct -- ticking everything would pass");
        st.findings.forEach(function(f){
          if(f.correct && !(f.miss || f.principle)) err(st.id + "/" + f.id + ": correct finding needs a pointer (miss, or principle + look)");
          if(!f.correct && !f.wrong) err(st.id + "/" + f.id + ": distractor needs 'wrong' feedback");
          var pointer = [f.miss, f.principle, f.look, f.wrong].filter(Boolean).join(" ").toLowerCase();
          correctF.forEach(function(c){ if(c.text.length >= 12 && pointer.indexOf(c.text.toLowerCase().replace(/[.\s]+$/, "")) !== -1) err(st.id + "/" + f.id + ": feedback quotes a correct finding"); });
        });
        if(st.options && st.options.length){
          var co = st.options.filter(function(o){ return o.correct; });
          if(co.length !== 1) err(st.id + ": exactly one correct option required");
          st.options.forEach(function(o){
            if(!o.why) err(st.id + "/" + o.id + ": option needs 'why'");
            if(!o.correct && co[0] && o.why && o.why.toLowerCase().indexOf(co[0].text.toLowerCase().slice(0, 40)) !== -1) err(st.id + "/" + o.id + ": feedback quotes the correct option");
          });
          if(co.length === 1) decisions.push({ id: st.id, lens: st.options.map(function(o){ return o.text.length; }), ci: st.options.indexOf(co[0]) });
        }
      }
      if(st.type === "triage") st.rows.forEach(function(r){ if(!r.hint) err(st.id + "/" + r.id + ": row needs a hint"); if(!r.answer) err(st.id + "/" + r.id + ": row needs an answer"); });
      if(st.type === "sequence"){
        st.items.forEach(function(it){ if(!it.hint) err(st.id + "/" + it.id + ": item needs a hint"); });
        if(!st.correctOrder || st.correctOrder.length !== st.items.length) err(st.id + ": correctOrder must list every item");
        if(st.startOrder && JSON.stringify(st.startOrder) === JSON.stringify(st.correctOrder)) err(st.id + ": startOrder is already the answer");
      }
      if(st.type === "compose"){
        st.fields.forEach(function(f){
          if((f.type === "select" || f.type === "multi") && !f.accept && !(f.criteria && f.criteria.length)) warn(st.id + "/" + f.id + ": no accept and no criteria -- any choice passes");
        });
        if(st.evidence && !(st.confirm && st.confirm.length)) warn(st.id + ": produces a work sample without a self-check");
      }
    });
  });
  /* answer-pattern protection */
  if(decisions.length){
    var longest = decisions.filter(function(d){ return d.lens[d.ci] === Math.max.apply(null, d.lens); }).length;
    var allow = Math.max(2, Math.ceil(decisions.length / 4));
    if(longest > allow) err("correct option is the longest in " + longest + " of " + decisions.length + " decisions (limit " + allow + ")");
    var pos = {}; decisions.forEach(function(d){ pos[d.ci] = (pos[d.ci] || 0) + 1; });
    if(decisions.length >= 3 && Object.keys(pos).length === 1) err("correct option is always in position " + (decisions[0].ci + 1));
  }
  return { errors: errors, warnings: warnings, decisions: decisions.length };
}

function readSource(file){ return JSON.parse(fs.readFileSync(file, "utf8")); }
function readShipped(file){
  var txt = fs.readFileSync(file, "utf8");
  var m = txt.match(/\.PVA_DESK_MODULES\[("[^"]+")\] = (\{[\s\S]*?\});\n/);
  if(!m) throw new Error("not a desk-data file: " + file);
  return JSON.parse(m[2]);
}

function encode(srcFile, out){
  var src = readSource(srcFile), config = src.config;
  var res = lint(src);
  if(res.errors.length){ console.error("lint errors:\n  " + res.errors.join("\n  ")); process.exit(1); }
  var codec = codecFor(config);
  var body = { version: src.version, module: src.module || config.moduleId, tasks: JSON.parse(JSON.stringify(src.tasks)) };
  body.tasks.forEach(function(t){ t.stages.forEach(function(st){ lockStage(st, codec.keys); }); });
  var shipped = { config: config, payload: codec.encode(body) };
  var id = JSON.stringify(config.moduleId);
  var js = "/* " + config.moduleId + " Work Desk content -- generated by tools/desk-codec.js. Do not edit by hand. */\n" +
           "window.PVA_DESK_MODULES = window.PVA_DESK_MODULES || {};\n" +
           "window.PVA_DESK_MODULES[" + id + "] = " + JSON.stringify(shipped) + ";\n";
  if(config.legacyGlobal) js += "/* Compatibility alias for pilot-era tests; safe to remove with them. */\nwindow." + config.legacyGlobal + " = window.PVA_DESK_MODULES[" + id + "].payload;\n";
  fs.writeFileSync(out, js);
  res.warnings.forEach(function(w){ console.error("warning: " + w); });
  console.error("encoded " + body.tasks.length + " tasks for " + config.moduleId + " -> " + out + " (" + js.length + " bytes)");
}
function decode(file){
  var shipped = readShipped(file), codec = codecFor(shipped.config);
  var body = codec.decode(shipped.payload);
  body.tasks.forEach(function(t){ t.stages.forEach(function(st){ unlockStage(st, codec.keys); }); });
  var src = { config: shipped.config, version: body.version, module: body.module, tasks: body.tasks };
  process.stdout.write(JSON.stringify(src, null, 2) + "\n");
}
function check(file){
  var src = /\.js$/.test(file) ? (function(){ var sh = readShipped(file), c = codecFor(sh.config), b = c.decode(sh.payload); b.tasks.forEach(function(t){ t.stages.forEach(function(st){ unlockStage(st, c.keys); }); }); return { config: sh.config, tasks: b.tasks }; })() : readSource(file);
  var res = lint(src);
  res.warnings.forEach(function(w){ console.log("warning: " + w); });
  res.errors.forEach(function(e){ console.log("ERROR: " + e); });
  console.log((res.errors.length ? "FAILED" : "OK") + " -- " + res.errors.length + " errors, " + res.warnings.length + " warnings, " + res.decisions + " decisions checked");
  process.exit(res.errors.length ? 1 : 0);
}

if(require.main === module){
  var cmd = process.argv[2];
  if(cmd === "encode") encode(process.argv[3], process.argv[4]);
  else if(cmd === "decode") decode(process.argv[3]);
  else if(cmd === "check") check(process.argv[3]);
  else { console.error("usage: desk-codec.js encode <src.json> <out.js> | decode <desk-data.js> | check <src.json|desk-data.js>"); process.exit(1); }
}
module.exports = { lint: lint, lockStage: lockStage, unlockStage: unlockStage, readShipped: readShipped };
