#!/usr/bin/env node
/* Everfield continuity check.

   Reads the shared Everfield files and every module's learner-facing text, and
   fails when they disagree. Prints locations and IDs only -- never Module 4
   desk text, which is decoded here and contains answer-bearing content.

     node tools/everfield-check.js            run all checks (exit 1 on failure)

   Checks: shared data is frozen and answer/learner-state free; record IDs are
   unique and every record used by two modules is a shared record with complete
   `src`; shared record facts match the module text; product IDs and names;
   product facts; people and roles; policy cards vs the
   approved canon; dates (weekday/date agreement, numeric dates
   on the timeline, the desk date matches the calendar; month-aware across
   September and October); Module 9's week stays
   in its own order, tracking and SKU ranges; no reference to a missing record
   or lesson. A productFacts source may be an approved canon document
   ("docs everfield-continuity.md"). Known, deliberately deferred conflicts are listed
   in DEFERRED and reported as warnings. */
var fs = require("fs"), path = require("path"), vm = require("vm");
var ROOT = process.env.EVERFIELD_ROOT || path.resolve(__dirname, "..");
process.chdir(ROOT);
var EVERFIELD = require(path.join(ROOT, "shared/everfield-data.js"));
var RECORDS = require(path.join(ROOT, "shared/everfield-records.js"));

/* Conflicts the audit found but that sit in a module this pass may not edit.
   Each entry is matched by check name + location; remove it when fixed. */
var DEFERRED = [];

// ---------- corpus ----------
var rows = [];
function walk(o, loc){
  if(typeof o === "string"){ rows.push({ loc: loc, text: o.replace(/<[^>]+>/g, " ").replace(/&amp;/g, "&").replace(/&mdash;/g, "--") }); return; }
  if(Array.isArray(o)) o.forEach(function(x, i){ walk(x, loc + "[" + i + "]"); });
  else if(o && typeof o === "object") Object.keys(o).forEach(function(k){
    if(["k", "acc", "id", "kind", "type", "value", "correct"].indexOf(k) !== -1 && typeof o[k] !== "object") return;
    walk(o[k], loc + "." + k); });
}
function loadDesk(dir){ // decoded in memory only; never written or printed
  return JSON.parse(require("child_process").execFileSync(process.execPath, [path.join(ROOT, "tools/desk-codec.js"), "decode", path.join(dir, "desk-data.js")], { maxBuffer: 1 << 26 }).toString());
}
var lessonIds = {};
for(var m = 1; m <= 14; m++){
  var dir = "module-" + m;
  if(fs.existsSync(path.join(dir, "desk-data.js"))){
    var src = loadDesk(dir);
    src.tasks.forEach(function(t){ lessonIds[t.id] = 1; walk(t, "M" + m + " " + t.id); });
    lessonIds["desk-data@" + m] = 1;
    continue;
  }
  var html = fs.readFileSync(path.join(dir, "index.html"), "utf8");
  var L = vm.runInNewContext("(" + html.match(/var LESSONS = (\[[\s\S]*?\n\]);/)[1] + ")");
  L.forEach(function(l){ lessonIds[l.id] = 1; walk(l, "M" + m + " " + l.id); });
}
var hub = fs.readFileSync("index.html", "utf8").replace(/<script[\s\S]*?<\/script>/g, " ").replace(/<style[\s\S]*?<\/style>/g, " ")
  .replace(/<[^>]+>/g, " ").replace(/&amp;/g, "&").replace(/&mdash;/g, "--").replace(/\s+/g, " ");
rows.push({ loc: "hub", text: hub });

function modOf(loc){ var x = /^M(\d+) /.exec(loc); return x ? +x[1] : null; }
function lessonOf(loc){ var x = /^M\d+ ([\w-]+)/.exec(loc); return x ? x[1] : loc; }
function textAt(ref){ // "module-5 m5-l7" -> concatenated text of that lesson; "docs <file>" -> approved canon document
  var p = ref.split(" ");
  if(p[0] === "docs") return fs.readFileSync(path.join("docs", p[1]), "utf8");
  var m = +p[0].replace("module-", "");
  return rows.filter(function(r){ return modOf(r.loc) === m && (p[1] === "desk-data" || lessonOf(r.loc) === p[1]); })
             .map(function(r){ return r.text; }).join(" ‖ ");
}
function refExists(ref){
  var p = ref.split(" ");
  if(p[0] === "docs") return /^[\w-]+\.md$/.test(p[1] || "") && fs.existsSync(path.join("docs", p[1]));
  if(!/^module-\d+$/.test(p[0])) return false;
  return p[1] === "desk-data" ? !!lessonIds["desk-data@" + p[0].slice(7)] : !!lessonIds[p[1]];
}

// ---------- reporting ----------
var failures = 0, warnings = 0;
function check(name, problems){
  var real = [], deferred = [];
  problems.forEach(function(p){
    var d = DEFERRED.filter(function(x){ return x.check === name && p.loc && p.loc.indexOf(x.loc) === 0; })[0];
    (d ? deferred : real).push(d ? p.msg + "  [deferred: " + d.why + "]" : p.msg);
  });
  console.log((real.length ? "FAIL " : "ok   ") + name + (real.length ? " (" + real.length + ")" : ""));
  real.forEach(function(x){ console.log("       - " + x); });
  deferred.forEach(function(x){ console.log("  warn - " + x); });
  failures += real.length; warnings += deferred.length;
}
function each(obj, fn, pfx){ Object.keys(obj).forEach(function(k){ var v = obj[k], p = (pfx ? pfx + "." : "") + k; fn(k, v, p); if(v && typeof v === "object") each(v, fn, p); }); }

// 1. shared data: frozen, no learner state, no answer keys
(function(){
  var probs = [];
  [["EVERFIELD", EVERFIELD], ["EVERFIELD_RECORDS", RECORDS]].forEach(function(pair){
    each(pair[1], function(k, v, p){ if(v && typeof v === "object" && !Object.isFrozen(v)) probs.push({ msg: pair[0] + "." + p + " is not frozen" }); });
    if(!Object.isFrozen(pair[1])) probs.push({ msg: pair[0] + " is not frozen" });
  });
  check("shared data is deep-frozen", probs);

  var LEARNER = /^(answers?|attempts?|fails?|drafts?|done|completed?|progress|learner\w*|user\w*|last|passing|confirm\w*|opened|recheck|views?|score|submitted|status_by_learner)$/i;
  var ANSWER = /^(correct\w*|accept\w*|answerKey|hash(es)?|salt|feedback|why|hint|miss|wrong|rules|when|findings|options|choices|explanation|solution)$/i;
  var l = [], a = [];
  [["EVERFIELD", EVERFIELD], ["EVERFIELD_RECORDS", RECORDS]].forEach(function(pair){
    each(pair[1], function(k, v, p){
      if(LEARNER.test(k)) l.push({ msg: pair[0] + "." + p });
      if(ANSWER.test(k)) a.push({ msg: pair[0] + "." + p });
    });
  });
  ["shared/everfield-data.js", "shared/everfield-records.js"].forEach(function(f){
    if(/localStorage|sessionStorage|indexedDB/.test(fs.readFileSync(f, "utf8").replace(/\/\*[\s\S]*?\*\//g, ""))) l.push({ msg: f + " touches browser storage" });
  });
  check("no learner-state fields in shared data", l);
  // No desk prompt/option/finding text may appear in a shared file (would leak answers).
  var shared = fs.readFileSync("shared/everfield-data.js", "utf8") + fs.readFileSync("shared/everfield-records.js", "utf8");
  rows.forEach(function(r){
    if(/\.(options|findings|choices|items|fields)\[\d+\]\.(text|label)$/.test(r.loc) && r.text.length > 24 && shared.indexOf(r.text) !== -1)
      a.push({ msg: "shared file quotes exercise text from " + r.loc.split(".")[0] });
  });
  check("no answer keys or exercise text in shared data", a);
})();

// 2. record IDs
var ID_RX = [
  { kind: "order",    rx: /(?:Order #|order #|#)(\d{4})\b/g, fmt: function(x){ return "#" + x; } },
  { kind: "return",   rx: /Return #(\d+)/g, fmt: function(x){ return "Return #" + x; } },
  { kind: "po",       rx: /\b(EG-\d{3,})\b/g, fmt: function(x){ return x; } },
  { kind: "tracking", rx: /\b(CP-\d{4}-\d{4})\b/g, fmt: function(x){ return x; } }
];
var seen = {};
rows.forEach(function(r){
  if(r.loc === "hub") return;
  ID_RX.forEach(function(d){ var mm; d.rx.lastIndex = 0;
    while((mm = d.rx.exec(r.text))){ var id = d.fmt(mm[1]); (seen[id] = seen[id] || { kind: d.kind, locs: {} }).locs[r.loc] = 1; } });
});
(function(){
  var probs = [], sharedIds = {};
  [["orders", RECORDS.orders], ["stock.snapshots", RECORDS.stock.snapshots], ["stock.movements", RECORDS.stock.movements],
   ["stock.inbound", RECORDS.stock.inbound], ["returns", RECORDS.returns], ["customers", RECORDS.customers], ["cases", RECORDS.cases]].forEach(function(pair){
    Object.keys(pair[1]).forEach(function(id){ if(sharedIds[id]) probs.push({ msg: id + " defined in " + sharedIds[id] + " and " + pair[0] }); sharedIds[id] = pair[0]; });
  });
  check("shared record IDs are unique", probs);

  probs = [];
  Object.keys(seen).forEach(function(id){
    var mods = {}; Object.keys(seen[id].locs).forEach(function(l){ mods[modOf(l)] = 1; });
    var n = Object.keys(mods).length, rec = RECORDS.orders[id] || RECORDS.returns[id];
    if(n > 1 && !rec) probs.push({ msg: id + " appears in modules " + Object.keys(mods).join(", ") + " but is not a shared record" });
    if(rec){
      var listed = rec.src.map(function(s){ return s.split(" ")[1]; });
      Object.keys(seen[id].locs).forEach(function(l){ if(listed.indexOf(lessonOf(l)) === -1) probs.push({ msg: id + " used in " + lessonOf(l) + " but not listed in its src" }); });
    }
  });
  check("records used by two modules are shared records", probs);
})();

// 3. shared record facts match the module text
(function(){
  var probs = [];
  function need(ref, rx, what){ if(!rx.test(textAt(ref))) probs.push({ msg: what + " not found in " + ref }); }
  function md(d){ var x = /Sep (\d+)/.exec(d); return "9/" + x[1]; }
  Object.keys(RECORDS.orders).forEach(function(id){
    var o = RECORDS.orders[id], n = id.slice(1);
    o.src.forEach(function(s){ need(s, new RegExp("#?" + n + "\\b"), id); });
    need("module-9 m9-l3", new RegExp(n + "\\s*\\u2016?\\s*" + md(o.date) + "\\s*\\u2016?\\s*" + o.sku + "\\s*\\u2016?\\s*" + o.qty + "\\s*\\u2016?\\s*" + o.status), id + " row (" + o.date + ", " + o.sku + " x" + o.qty + ", " + o.status + ")");
  });
  Object.keys(RECORDS.returns).forEach(function(id){
    var r = RECORDS.returns[id];
    r.src.forEach(function(s){ need(s, new RegExp(id.replace("#", "#?").replace(/^Return /, "(Return )?")), id); need(s, new RegExp(r.sku), id + " SKU"); need(s, new RegExp(r.disposition, "i"), id + " disposition"); });
  });
  Object.keys(RECORDS.stock.movements).forEach(function(id){
    var v = RECORDS.stock.movements[id];
    need(v.src[0], new RegExp("date " + md(v.date) + ", SKU " + v.sku + ", quantity " + v.qty + ", event '" + v.event + "', reference 'Order " + v.ref + "', resulting balance " + v.balance), id);
  });
  Object.keys(RECORDS.stock.snapshots).forEach(function(id){
    var s = RECORDS.stock.snapshots[id];
    Object.keys(s.rows).forEach(function(sku){ var r = s.rows[sku];
      need(s.src[0], new RegExp(sku + "\\s*\\u2016?\\s*" + r.available + "\\s*\\u2016?\\s*" + r.reserved + "\\s*\\u2016?\\s*" + r.inbound), id + " " + sku + " row"); });
    // the movement row starts from this snapshot's EF-101 available figure
    var mv = RECORDS.stock.movements["mv-sep2-4021"];
    if(s.rows[mv.sku] && s.rows[mv.sku].available + mv.qty !== mv.balance) probs.push({ msg: id + " " + mv.sku + " available does not lead to " + mv.ref + "'s balance" });
  });
  Object.keys(RECORDS.stock.inbound).forEach(function(id){
    var v = RECORDS.stock.inbound[id];
    need(v.src[0], new RegExp(v.sku + ": 0 available, " + v.qty + " inbound expected " + md(v.expected)), id);
    var snap = RECORDS.stock.snapshots["stock-early-sep"].rows[v.sku];
    if(snap && snap.inbound !== v.qty) probs.push({ msg: id + " quantity differs from the snapshot's inbound" });
  });
  each(RECORDS, function(k, v, p){ if(k === "src") v.forEach(function(s){ if(!refExists(s)) probs.push({ msg: "RECORDS." + p + " cites missing lesson " + s }); }); });
  each(EVERFIELD, function(k, v, p){ if(k === "src") v.forEach(function(s){ if(!refExists(s)) probs.push({ msg: "EVERFIELD." + p + " cites missing lesson " + s }); }); });
  EVERFIELD.timeline.entries.forEach(function(e){
    if(e.ref && !(RECORDS.orders[e.ref] || RECORDS.returns[e.ref] || RECORDS.stock.snapshots[e.ref] || RECORDS.stock.movements[e.ref] || RECORDS.stock.inbound[e.ref]))
      probs.push({ msg: "timeline entry '" + e.what + "' references missing record " + e.ref });
  });
  check("shared records match module text; no missing references", probs);
})();

// 4. products
(function(){
  var probs = [], P = EVERFIELD.products, names = Object.keys(P).map(function(k){ return P[k]; });
  rows.forEach(function(r){
    var mm, rx = /EF-(\d{3})/g;
    while((mm = rx.exec(r.text))){ if(!P["EF-" + mm[1]]) probs.push({ loc: r.loc, msg: "unknown SKU EF-" + mm[1] + " in " + r.loc.split(".")[0] }); }
    // "EF-### -- Name", "EF-### Name", "EF-### (Name)" and "Name (EF-###)" must agree with the catalog
    var pr = /(EF-\d{3})\s*(?:--|\(|:)?\s*((?:[A-Z][a-z]+ ){1,4}(?:Bin|Set|Tray|Kit))\b/g;
    while((mm = pr.exec(r.text))){ if(P[mm[1]] && P[mm[1]] !== mm[2] && names.indexOf(mm[2]) !== -1) probs.push({ loc: r.loc, msg: mm[1] + " called '" + mm[2] + "' in " + r.loc.split(".")[0] }); }
    pr = /((?:[A-Z][a-z]+ ){1,4}(?:Bin|Set|Tray|Kit)) \((EF-\d{3})\)/g;
    while((mm = pr.exec(r.text))){ if(P[mm[2]] && P[mm[2]] !== mm[1] && names.indexOf(mm[1]) !== -1) probs.push({ loc: r.loc, msg: mm[2] + " called '" + mm[1] + "' in " + r.loc.split(".")[0] }); }
  });
  check("product IDs and names agree with the catalog", probs);

  probs = [];
  var F = EVERFIELD.productFacts;
  Object.keys(F).forEach(function(sku){
    var f = F[sku], all = f.src.map(textAt).join(" ");
    Object.keys(f).forEach(function(k){
      if(k === "src" || k === "variants") return;
      var vals = k === "kit" ? Object.keys(f.kit).map(function(c){ return f.kit[c] + " x " + c; }) : [String(f[k])];
      vals.forEach(function(v){ if(all.indexOf(v) === -1) probs.push({ msg: sku + "." + k + " = " + v + " is not stated in " + f.src.join(", ") }); });
    });
  });
  // dimensions stated anywhere must match the record of the nearest SKU named before them
  rows.forEach(function(r){
    var mm, rx = /(\d+in x \d+in x \d+in)/g;
    while((mm = rx.exec(r.text))){
      var before = r.text.slice(Math.max(0, mm.index - 160), mm.index).match(/EF-\d{3}/g);
      if(!before) continue;
      var sku = before[before.length - 1], f = F[sku];
      if(!f || f.dimensions !== mm[1]) probs.push({ loc: r.loc, msg: sku + " given dimensions " + mm[1] + " in " + r.loc.split(".")[0] + " (record: " + (f && f.dimensions || "undefined") + ")" });
    }
  });
  // every statement of the kit recipe must match it
  var kit = F["EF-200"].kit;
  rows.forEach(function(r){
    if(!/EF-200/.test(r.text) || !/kit/i.test(r.text)) return;
    var mm, rx = /(\d+) ?[x\u00d7] ?(EF-\d{3})/g;
    while((mm = rx.exec(r.text))){ if(kit[mm[2]] !== +mm[1]) probs.push({ loc: r.loc, msg: "kit recipe says " + mm[1] + " x " + mm[2] + " in " + r.loc.split(".")[0] + " (record: " + (kit[mm[2]] || 0) + ")" }); }
  });
  check("product facts agree with the course", probs);

  probs = [];
  rows.forEach(function(r){
    if(/(different|another|other) colou?r|in (red|blue|green|black|white|grey|gray)\b|size variant/i.test(r.text) && /EF-\d{3}|exchange/.test(r.text))
      probs.push({ loc: r.loc, msg: "colour/size variant implied in " + r.loc.split(".")[0] + " (" + EVERFIELD.productFacts.catalog.variants + ")" });
  });
  check("variants", probs);
})();

// 5. people and roles
(function(){
  var probs = [], T = EVERFIELD.team, ROLES = Object.keys(T).map(function(k){ return T[k].role; });
  Object.keys(T).forEach(function(k){
    var p = T[k], esc = function(s){ return s.replace(/[&()]/g, "\\$&"); };
    // hub lists "Name Role"; it is the Company Bible for people
    var hubRx = new RegExp(esc(p.name) + " (" + ROLES.map(esc).join("|") + ")");
    var hm = hubRx.exec(hub);
    if(!hm) probs.push({ msg: p.name + " not listed on the hub" });
    else if(hm[1] !== p.role) probs.push({ msg: p.name + " is '" + hm[1] + "' on the hub but '" + p.role + "' in everfield-data.js" });
    if(p.org !== "Everfield Goods" && hub.indexOf(p.name + " " + p.role + " (" + p.org + ")") === -1) probs.push({ msg: p.name + "'s organisation differs from the hub" });
    rows.forEach(function(r){
      var first = p.name.split(" ")[0], rx = new RegExp("\\b" + first + "(?: [A-Z][a-z]+)?(?:,| \\(|'s| is| as)?\\s*(?:the |Everfield's |\\(Everfield's )?(" + ["E-commerce Manager", "Operations Manager", "Procurement & Supply Manager", "3PL Account Manager", "account manager"].join("|") + ")", "g"), mm;
      while((mm = rx.exec(r.text))){ if(mm[1].toLowerCase() !== p.role.toLowerCase() && !(mm[1] === "account manager" && p.role === "3PL Account Manager")) probs.push({ loc: r.loc, msg: first + " called '" + mm[1] + "' in " + r.loc.split(".")[0] }); }
    });
  });
  // desk briefs may only come from known people
  rows.forEach(function(r){ if(/\.brief\.from$/.test(r.loc) && !T[r.text]) probs.push({ msg: "brief from unknown person '" + r.text + "' in " + r.loc.split(".")[0] }); });
  // any other "Firstname Lastname (… Manager)" is a new person who must be added to the team first
  rows.forEach(function(r){
    var rx = /\b([A-Z][a-z]+ [A-Z][a-z]+) \(([^)]*Manager[^)]*)\)/g, mm;
    while((mm = rx.exec(r.text))){ var known = Object.keys(T).some(function(k){ return T[k].name === mm[1]; });
      if(!known) probs.push({ loc: r.loc, msg: "unknown person " + mm[1] + " (" + mm[2] + ") in " + r.loc.split(".")[0] }); }
  });
  check("people and roles agree with the team", probs);
})();

// 6. policy clauses quoted on desk policy cards match the approved canon word for word
(function(){
  var probs = [], canon = {};
  fs.readFileSync("docs/everfield-continuity.md", "utf8").split("\n").forEach(function(line){
    var m = /^\| (P\d+) \| (.+?) \| [^|]*\|\s*$/.exec(line); if(m) canon[m[1]] = m[2];
  });
  if(!Object.keys(canon).length) probs.push({ msg: "no policy canon found in docs/everfield-continuity.md" });
  rows.forEach(function(r){
    var m = /^(P\d+) · (.+)$/.exec(r.text.trim());
    if(!m) return;
    if(!canon[m[1]]) probs.push({ loc: r.loc, msg: m[1] + " quoted in " + r.loc.split(".")[0] + " is not an approved clause" });
    else if(canon[m[1]] !== m[2]) probs.push({ loc: r.loc, msg: m[1] + " in " + r.loc.split(".")[0] + " differs from the approved wording" });
  });
  check("policy cards match the approved canon", probs);
})();

// 6b. Module 9's authored week stays inside its own ranges (design map W1): orders
// #5450-#5462 (plus the shared #4021 and its reference neighbour #4022), tracking
// CP-7731-06xx, and no EF-102, EF-103 or EF-106, so its stock sheet can't
// contradict Module 7's Sep 17 rows or the capstone's EF-103.
(function(){
  var probs = [];
  if(!fs.existsSync("module-9/desk-data.js")){ check("Module 9 week stays in its ranges", probs); return; }
  rows.filter(function(r){ return modOf(r.loc) === 9; }).forEach(function(r){
    var mm, rx = /#(\d{4})\b/g;
    while((mm = rx.exec(r.text))){ var n = +mm[1]; if(!(n >= 5450 && n <= 5462) && n !== 4021 && n !== 4022) probs.push({ loc: r.loc, msg: "order #" + n + " in " + r.loc.split(".")[0] + " is outside Module 9's #5450-#5462" }); }
    rx = /\bCP-(\d{4})-(\d{4})\b/g;
    while((mm = rx.exec(r.text))){ if(mm[1] !== "7731" || !/^06\d\d$/.test(mm[2])) probs.push({ loc: r.loc, msg: mm[0] + " in " + r.loc.split(".")[0] + " is outside Module 9's CP-7731-06xx" }); }
    rx = /EF-10[236]\b/g;
    while((mm = rx.exec(r.text))){ probs.push({ loc: r.loc, msg: mm[0] + " in " + r.loc.split(".")[0] + " (the Module 9 week excludes EF-102, EF-103 and EF-106)" }); }
  });
  check("Module 9 week stays in its ranges", probs);
})();

// 6c. Module 5's day stays inside its own ranges (design map W1): orders #4023-#4027
// plus the shared #4021, Return #229 only, and no tracking or later order numbers.
(function(){
  var probs = [];
  if(!fs.existsSync("module-5/desk-data.js")){ check("Module 5 day stays in its ranges", probs); return; }
  rows.filter(function(r){ return modOf(r.loc) === 5; }).forEach(function(r){
    var mm, rx = /#(\d{4})\b/g;
    while((mm = rx.exec(r.text))){ var n = +mm[1]; if(!(n >= 4023 && n <= 4027) && n !== 4021) probs.push({ loc: r.loc, msg: "order #" + n + " in " + r.loc.split(".")[0] + " is outside Module 5's #4023-#4027" }); }
    rx = /Return #(\d+)/g;
    while((mm = rx.exec(r.text))){ if(mm[1] !== "229") probs.push({ loc: r.loc, msg: "Return #" + mm[1] + " in " + r.loc.split(".")[0] + " (Module 5 uses only the shared Return #229)" }); }
  });
  check("Module 5 day stays in its ranges", probs);
})();

// 6e. Module 6's day stays inside its own ranges (design map D3): orders #5483-#5495,
// tracking CP-7731-08xx, the shared Return #229 as its only return, stock figures for
// EF-105 only, and no EF-103 anywhere.
(function(){
  var probs = [];
  if(!fs.existsSync("module-6/desk-data.js")){ check("Module 6 day stays in its ranges", probs); return; }
  rows.filter(function(r){ return modOf(r.loc) === 6; }).forEach(function(r){
    var mm, rx = /#(\d{4})\b/g, where = r.loc.split(".")[0];
    while((mm = rx.exec(r.text))){ var n = +mm[1]; if(!(n >= 5483 && n <= 5495)) probs.push({ loc: r.loc, msg: "order #" + n + " in " + where + " is outside Module 6's #5483-#5495" }); }
    rx = /Return #(\d+)|#(\d{3})\b/g;
    while((mm = rx.exec(r.text))){ if((mm[1] || mm[2]) !== "229") probs.push({ loc: r.loc, msg: "return #" + (mm[1] || mm[2]) + " in " + where + " (Module 6 uses only the shared Return #229)" }); }
    rx = /\bCP-(\d{4})-(\d{4})\b/g;
    while((mm = rx.exec(r.text))){ if(mm[1] !== "7731" || !/^08\d\d$/.test(mm[2])) probs.push({ loc: r.loc, msg: mm[0] + " in " + where + " is outside Module 6's CP-7731-08xx" }); }
    if(/EF-103\b/.test(r.text)) probs.push({ loc: r.loc, msg: "EF-103 in " + where + " (the Module 6 day never names EF-103)" });
    if(/\b\d+ available\b|\bAvailable\b|\bInbound\b/.test(r.text)){
      var skus = (r.text.match(/EF-\d{3}/g) || []).filter(function(x){ return x !== "EF-105"; });
      if(skus.length) probs.push({ loc: r.loc, msg: "stock figures for " + skus.join(", ") + " in " + where + " (Module 6's only stock line is EF-105)" });
    }
  });
  check("Module 6 day stays in its ranges", probs);
})();

// 6d. Module 13's week stays inside its own ranges (design map W1-a): orders #5465-#5482,
// returns #241 onward, tracking CP-7731-07xx, and no EF-103 on any line, so nothing can
// contradict the capstone's later EF-103. The one exception is Lesson 2's reference
// card, which keeps the legacy EF-103 "expected 9/6" line as a worked example from an
// earlier week (decision C2): it is the shared inbound record's only dated source.
(function(){
  var probs = [];
  if(!fs.existsSync("module-13/desk-data.js")){ check("Module 13 week stays in its ranges", probs); return; }
  rows.filter(function(r){ return modOf(r.loc) === 13; }).forEach(function(r){
    var mm, rx = /#(\d{4})\b/g, where = r.loc.split(".")[0];
    while((mm = rx.exec(r.text))){ var n = +mm[1]; if(!(n >= 5465 && n <= 5482)) probs.push({ loc: r.loc, msg: "order #" + n + " in " + where + " is outside Module 13's #5465-#5482" }); }
    rx = /Return #(\d+)|#(\d{3})\b/g;
    while((mm = rx.exec(r.text))){ var x = +(mm[1] || mm[2]); if(x < 241) probs.push({ loc: r.loc, msg: "Return #" + x + " in " + where + " is outside Module 13's #241 onward" }); }
    rx = /\bCP-(\d{4})-(\d{4})\b/g;
    while((mm = rx.exec(r.text))){ if(mm[1] !== "7731" || !/^07\d\d$/.test(mm[2])) probs.push({ loc: r.loc, msg: mm[0] + " in " + where + " is outside Module 13's CP-7731-07xx" }); }
    if(/EF-103\b/.test(r.text) && !/^M13 m13-l5\.reference\[/.test(r.loc)) probs.push({ loc: r.loc, msg: "EF-103 in " + where + " (the Module 13 week keeps EF-103 off every line; only Lesson 2's earlier-week reference example may name it)" });
  });
  check("Module 13 week stays in its ranges", probs);
})();

// 7. dates. Month-aware (decision C1): the operating period runs from September
// into October (Module 13's week ends Fri, Oct 2). A date is turned into a day
// number counted from Sep 1 (Sep d -> d, Oct d -> 30 + d), so weekday, numeric
// and "after the desk day" checks work across the month boundary. September
// results are exactly what the September-only version produced; run with
// EVERFIELD_TRACE=1 to print every date judgement (used to prove that).
(function(){
  var probs = [];
  var TR = process.env.EVERFIELD_TRACE ? function(){ console.log("TRACE " + [].slice.call(arguments).join(" | ")); } : function(){};
  var DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  var MONTH = { Sep: { n: 9, offset: 0 }, Oct: { n: 10, offset: 30 } };
  var MONTH_RX = "(Sep(?:t|tember)?|Oct(?:ober)?)";
  function mon(word){ return word.slice(0, 3); }                  // "September" -> "Sep"
  function ord(word, d){ return MONTH[mon(word)].offset + d; }     // day number from Sep 1
  var anchor = new RegExp("(\\w{3}), " + MONTH_RX + " (\\d+)").exec(EVERFIELD.timeline.weekdayAnchor);
  var anchorOrd = ord(anchor[2], +anchor[3]);
  function weekday(o){ return DAYS[(DAYS.indexOf(anchor[1]) + (o - anchorOrd) % 7 + 7 * 10) % 7]; }
  function checkStr(s, where, loc){
    var rx = new RegExp("\\b(Sun|Mon|Tue|Wed|Thu|Fri|Sat)[a-z]*,? " + MONTH_RX + " (\\d{1,2})\\b", "g"), mm;
    while((mm = rx.exec(s))){
      var w = weekday(ord(mm[2], +mm[3]));
      TR("wd", loc || where, mm[0], w === mm[1] ? "ok" : "bad");
      if(w !== mm[1]) probs.push({ loc: loc, msg: mm[0] + " in " + where + " -- " + mon(mm[2]) + " " + mm[3] + " is a " + w });
    }
  }
  rows.forEach(function(r){ checkStr(r.text, r.loc.split(".")[0], r.loc); });
  each(EVERFIELD, function(k, v, p){ if(typeof v === "string") checkStr(v, "EVERFIELD." + p); });
  each(RECORDS, function(k, v, p){ if(typeof v === "string") checkStr(v, "RECORDS." + p); });
  // numeric m/d dates are only allowed when the timeline or a shared record accounts for them
  var known = {};
  JSON.stringify([EVERFIELD.timeline, RECORDS]).replace(/(Sep|Oct) (\d+)/g, function(_, m, d){ known[MONTH[m].n + "/" + d] = 1; });
  TR("known", Object.keys(known).sort().join(","));
  var LOCAL_NUMERIC = { "M11 m11-l4": "9/2" }; // Return #229: illustrative, same day as #4021 (not its return)
  rows.forEach(function(r){
    if(/\.(rules|when)\[/.test(r.loc)) return; // desk validation keywords (accepted spellings), not statements
    var rx = /(?:^|[^\d/])(\d{1,2}\/\d{1,2})(?![\d/])/g, mm;
    while((mm = rx.exec(r.text))){
      var d = mm[1]; if(!/^(9|10|11|12|[1-8])\/\d+$/.test(d)) continue;
      TR("num", r.loc, d, known[d] ? "known" : LOCAL_NUMERIC[r.loc.split(".")[0]] === d ? "local" : "unknown");
      if(!known[d] && LOCAL_NUMERIC[r.loc.split(".")[0]] !== d) probs.push({ loc: r.loc, msg: "date " + d + " in " + r.loc.split(".")[0] + " is not on the Everfield timeline" });
    }
  });
  // every converted module's desk clock matches its calendar date -- or, for a
  // lesson that declares its own work date (task.workDate; Module 13 Lesson 1 runs
  // midweek), that date. A lesson's work date must be on the timeline and no later
  // than the module's calendar day. Nothing in a lesson is dated after its day.
  var workDate = {};
  rows.forEach(function(r){ var x = /^M(\d+) ([\w-]+)\.workDate$/.exec(r.loc); if(x) workDate[x[2]] = r.text; });
  var tlDates = EVERFIELD.timeline.entries.map(function(e){ return e.date; }).join(" ‖ ");
  function dayOf(s){ var dm = new RegExp(MONTH_RX + " (\\d+)").exec(s); return dm ? ord(dm[1], +dm[2]) : NaN; }
  Object.keys(EVERFIELD.calendar).forEach(function(mid){
    var n = +mid.slice(1), date = EVERFIELD.calendar[mid].date.replace(",", "");
    function dayFor(loc){ var w = workDate[lessonOf(loc)]; return w ? w.replace(",", "") : date; }
    Object.keys(workDate).forEach(function(lid){
      if(lid.split("-")[0] !== mid) return;
      if(tlDates.indexOf(workDate[lid]) === -1) probs.push({ msg: lid + " work date '" + workDate[lid] + "' is not on the Everfield timeline" });
      if(!(dayOf(workDate[lid]) <= dayOf(date))) probs.push({ msg: lid + " work date '" + workDate[lid] + "' is after calendar " + mid });
    });
    var nows = rows.filter(function(r){ return modOf(r.loc) === n && /\.now$/.test(r.loc); });
    nows.forEach(function(r){ var d = dayFor(r.loc); TR("clock", mid, r.loc, r.text.replace(",", "").indexOf(d) === 0 ? "ok" : "bad"); if(r.text.replace(",", "").indexOf(d) !== 0) probs.push({ msg: r.loc.split(".")[0] + " desk clock '" + r.text.split(" ·")[0] + "' differs from " + (d === date ? "calendar " + mid : "its work date") }); });
    if(!nows.length) probs.push({ msg: "calendar has " + mid + " but the module has no desk clock" });
    // nothing in that module is dated after its desk day (its lesson's work date, if declared)
    rows.filter(function(r){ return modOf(r.loc) === n && !/\.workDate$/.test(r.loc); }).forEach(function(r){
      var rx = new RegExp(MONTH_RX + " (\\d{1,2})\\b", "g"), mm, day = dayOf(dayFor(r.loc));
      while((mm = rx.exec(r.text))){
        var o = ord(mm[1], +mm[2]);
        TR("after", mid, r.loc, mm[0], o > day ? (/\.reference\[/.test(r.loc) ? "ref" : "after") : "ok");
        if(o > day && !/\.reference\[/.test(r.loc)) probs.push({ msg: mon(mm[1]) + " " + mm[2] + " in " + r.loc.split(".")[0] + " is after " + (workDate[lessonOf(r.loc)] ? "its work date" : mid + "'s desk day") });
      }
    });
  });
  check("dates agree with the Everfield calendar", probs);
})();

console.log("\n" + (failures ? failures + " problem(s)" : "Everfield continuity: all checks passed") + (warnings ? ", " + warnings + " deferred warning(s)" : ""));
process.exit(failures ? 1 : 0);
