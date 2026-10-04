/* Unit tests for the Work Desk core (shared/workdesk.js) and codec lint.
   No dependencies: node tests/unit/core.test.js */
var path = require("path"), assert = require("assert");
var ROOT = path.join(__dirname, "..", "..");
var Core = require(path.join(ROOT, "shared", "workdesk.js"));
var Codec = require(path.join(ROOT, "tools", "desk-codec.js"));
var fs = require("fs");

var passed = 0, failed = 0;
function test(name, fn){
  try{ Core._resetStoreRegistry(); fn(); passed++; console.log("PASS " + name); }
  catch(e){ failed++; console.log("FAIL " + name + "\n     " + (e && e.message)); }
}
function deskFor(id, extra, storage){ return Core.createDesk(Core.assign({ moduleId: id, salt: "test-salt-" + id }, extra), { storage: storage || Core.memoryStorage() }); }

/* ---------- answer protection ---------- */
test("hash matches the pilot's FNV-1a scheme (existing answer keys stay valid)", function(){
  function pilot(str){ var s = "everfield-desk-v1|" + str, x = 0x811c9dc5; for(var i = 0; i < s.length; i++){ x ^= s.charCodeAt(i); x = Math.imul(x, 0x01000193) >>> 0; } return ("0000000" + x.toString(16)).slice(-8); }
  var c = Core.createCodec({ salt: "everfield-desk-v1" });
  ["l1-a|f|paid|1", "x", "", "unicode — “quote”"].forEach(function(s){ assert.strictEqual(c.hash(s), pilot(s)); });
});
test("codec round-trips unicode content", function(){
  var c = Core.createCodec({ salt: "s", key: "K" }), obj = { a: "Sofia — “Open”", n: [1, 2] };
  assert.deepStrictEqual(c.decode(c.encode(obj)), obj);
});
test("salt is per module: the same answer hashes differently in two modules", function(){
  var a = Core.createCodec({ salt: "m4-salt" }), b = Core.createCodec({ salt: "m7-salt" });
  assert.notStrictEqual(a.keys.option("s1", "o1", true), b.keys.option("s1", "o1", true));
});
test("codec refuses to run without a module salt", function(){ assert.throws(function(){ Core.createCodec({}); }); });
test("shipped Module 4 content decodes and passes the content lint", function(){
  var shipped = Codec.readShipped(path.join(ROOT, "module-4", "desk-data.js"));
  assert.strictEqual(shipped.config.moduleId, "m4");
  var c = Core.createCodec(shipped.config), body = c.decode(shipped.payload);
  body.tasks.forEach(function(t){ t.stages.forEach(function(st){ Codec.unlockStage(st, c.keys); }); });
  var res = Codec.lint({ config: shipped.config, tasks: body.tasks });
  assert.deepStrictEqual(res.errors, []);
  assert.strictEqual(body.tasks.length, 8);
});
test("shipped Module 4 file contains no plaintext answer markers", function(){
  var txt = fs.readFileSync(path.join(ROOT, "module-4", "desk-data.js"), "utf8");
  ["\"correct\"", "\"accept\"", "\"answer\"", "\"correctOrder\""].forEach(function(m){ assert.ok(txt.indexOf(m) === -1, m); });
});

/* ---------- storage ---------- */
test("storage key is derived from the module id (Module 4 key unchanged)", function(){
  assert.strictEqual(deskFor("m4").storageKey, "pva-ecom-ft-m4-desk");
  assert.strictEqual(deskFor("m7").storageKey, "pva-ecom-ft-m7-desk");
});
test("modules are isolated: work in one never appears in another", function(){
  var mem = Core.memoryStorage(), a = deskFor("m4", null, mem), b = deskFor("m5", null, mem);
  a.store.attempt("t1", "s1", { f: ["x"] }, true); a.store.draft("t1", "s1:v", { n: "hello" });
  assert.deepStrictEqual(b.store.get("t1"), { views: 0, stages: {}, drafts: {} });
  assert.ok(mem.getItem("pva-ecom-ft-m4-desk")); assert.strictEqual(mem.getItem("pva-ecom-ft-m5-desk"), null);
});
test("the legacy progress key is never written by the engine", function(){
  var mem = Core.memoryStorage(), d = deskFor("m4", null, mem);
  d.store.touch("t1"); d.store.attempt("t1", "s1", {}, false);
  assert.strictEqual(mem.getItem("pva-ecom-ft-progress"), null);
});
test("a module id cannot claim the legacy progress key", function(){ assert.throws(function(){ deskFor("progress"); }, /reserved/); });
test("invalid module ids are refused", function(){ assert.throws(function(){ deskFor("M 4"); }); assert.throws(function(){ Core.createDesk({ salt: "x" }); }); });
test("two modules cannot share one storage key", function(){
  deskFor("m4", { storageKey: "shared-key" });
  assert.throws(function(){ deskFor("m5", { storageKey: "shared-key" }); }, /already used/);
});

/* ---------- stage fixtures ---------- */
function lock(stage, desk){ Codec.lockStage(stage, desk.codec.keys); return stage; }
function decisionStage(desk){
  return lock({ id: "d1", type: "decision", records: [{ title: "R1", fields: [] }],
    findings: [ { id: "a", text: "The invoice has been paid in full.", correct: true, miss: "Read the payment line on its own." },
                { id: "b", text: "The warehouse has the order.", correct: true, miss: "Check the warehouse line." },
                { id: "c", text: "It has already shipped.", wrong: "Look for shipping evidence first." } ],
    options: [ { id: "o1", text: "Report what the record shows, without promising a date.", correct: true, why: "Facts only." },
               { id: "o2", text: "Escalate it right away.", why: "Nothing is wrong yet." } ] }, desk);
}

/* ---------- tier 1: exact ---------- */
test("tier 1: decision passes only with all correct findings, no distractors, right action", function(){
  var d = deskFor("m4"), st = decisionStage(d);
  assert.ok(d.evaluate(st, { f: ["a", "b"], o: "o1" }).pass);
  assert.ok(!d.evaluate(st, { f: ["a"], o: "o1" }).pass, "missed finding");
  assert.ok(!d.evaluate(st, { f: ["a", "b", "c"], o: "o1" }).pass, "ticking everything");
  assert.ok(!d.evaluate(st, { f: ["a", "b"], o: "o2" }).pass, "wrong action");
});
test("tier 1: triage, sequence and structured fields check against hashes", function(){
  var d = deskFor("m4");
  var tri = lock({ id: "t1", type: "triage", choices: [{ id: "x" }, { id: "y" }], rows: [{ id: "r1", answer: "y", hint: "h" }, { id: "r2", answer: "x", hint: "h" }] }, d);
  assert.ok(d.evaluate(tri, { r1: "y", r2: "x" }).pass);
  assert.deepStrictEqual(d.evaluate(tri, { r1: "x", r2: "x" }).wrongRows.map(function(r){ return r.id; }), ["r1"]);
  var seq = lock({ id: "s1", type: "sequence", items: [{ id: "p" }, { id: "q" }, { id: "r" }], correctOrder: ["q", "p", "r"] }, d);
  assert.ok(d.evaluate(seq, { order: ["q", "p", "r"] }).pass);
  assert.strictEqual(d.evaluate(seq, { order: ["p", "q", "r"] }).firstWrong, 0);
  var comp = lock({ id: "c1", type: "compose", groups: [{ id: "g", title: "G", hint: "look", records: [] }],
    fields: [ { id: "s", group: "g", type: "select", label: "S", options: [{ value: "a" }, { value: "b" }], accept: ["b"] },
              { id: "m", group: "g", type: "multi", label: "M", options: [{ value: "1" }, { value: "2" }], accept: [["1", "2"], ["2"]] } ] }, d);
  assert.ok(d.evaluate(comp, { values: { s: "b", m: ["2", "1"] } }).pass);
  assert.ok(d.evaluate(comp, { values: { s: "b", m: ["2"] } }).pass);
  assert.ok(!d.evaluate(comp, { values: { s: "a", m: ["2"] } }).pass);
});

/* ---------- tier 2 + junk filter ---------- */
function noteStage(d, extra){
  return lock(Core.assign({ id: "n1", type: "compose", groups: [{ id: "g", title: "G", hint: "h", records: [] }],
    fields: [ { id: "issue", group: "g", type: "select", label: "Issue", options: [{ value: "none" }, { value: "track" }], accept: ["track"] },
              { id: "note", group: "g", type: "text", label: "Note", minWords: 8, minSentences: 1,
                when: [ { field: "issue", ne: "none", notAny: ["no issue", "all good"], msg: "your note contradicts the issue you selected." } ] } ],
    banned: [ { any: ["probably"], msg: "no guessing." } ], example: { text: "The order is in the pick queue and no tracking exists yet, which is expected." } }, extra), d);
}
test("tier 2: a note that contradicts the learner's own choice fails", function(){
  var d = deskFor("m4"), st = noteStage(d);
  var bad = d.evaluate(st, { values: { issue: "track", note: "No issue with this order at all, all good and it can be trusted today." } });
  assert.ok(!bad.pass && /contradicts/.test(bad.problems.map(function(p){ return p.msg; }).join(" ")));
  assert.ok(d.evaluate(st, { values: { issue: "track", note: "The tracking number is missing even though the order is marked as shipped." } }).pass);
});
test("junk filter: blank, filler, keyword lists, guesses and copied examples all fail", function(){
  var d = deskFor("m4"), st = noteStage(d);
  function msgs(note){ return d.evaluate(st, { values: { issue: "track", note: note } }).problems.map(function(p){ return p.msg; }).join(" | "); }
  assert.ok(/real words/.test(msgs("")));
  assert.ok(/real words/.test(msgs("asdf asdf asdf asdf asdf asdf asdf asdf asdf")));
  assert.ok(/list of keywords/.test(msgs("tracking missing shipped order record verify clearpath sofia update today")));
  assert.ok(/no guessing/.test(msgs("The tracking number is probably missing because the label was not printed.")));
  assert.ok(/close to the example/.test(msgs("The order is in the pick queue and no tracking exists yet, which is expected here.")));
});
test("junk filter thresholds are configurable per module", function(){
  var d = deskFor("m9", { text: { minFunctionWordRatio: 0 } }), st = noteStage(d);
  assert.ok(d.evaluate(st, { values: { issue: "track", note: "tracking missing shipped order record verify clearpath sofia update today" } }).pass);
});

/* ---------- tier 3: criteria ---------- */
test("tier 3: criteria rules accept several right answers and explain misses", function(){
  var d = deskFor("m8");
  var st = lock({ id: "r1", type: "compose", groups: [{ id: "g", title: "G", hint: "h", records: [] }], fields: [
    { id: "price", group: "g", type: "text", label: "Price", minWords: 1, criteria: [{ kind: "matchesSource", sources: ["$24.99", "$22.50"], msg: "use a price from the source cards." }] },
    { id: "obs", group: "g", type: "text", label: "Observation", minWords: 6, criteria: [{ kind: "distinctFrom", field: "rec", max: 0.5, msg: "keep the observation separate from the recommendation." }] },
    { id: "rec", group: "g", type: "text", label: "Recommendation", minWords: 6 },
    { id: "picks", group: "g", type: "multi", label: "Picks", options: [{ value: "a" }, { value: "b" }, { value: "c" }], criteria: [{ kind: "minItems", n: 2, msg: "pick at least two." }] },
    { id: "tier", group: "g", type: "select", label: "Tier", options: [{ value: "x" }, { value: "y" }, { value: "z" }], criteria: [{ kind: "oneOf", values: ["x", "y"], msg: "that tier is not supported by the sources." }] } ] }, d);
  var good = { price: "$22.50", obs: "Two of three competitors sell a three-piece set.", rec: "We could test a bundle at a lower price point soon.", picks: ["a", "c"], tier: "y" };
  assert.ok(d.evaluate(st, { values: good }).pass);
  var bad = d.evaluate(st, { values: Core.assign({}, good, { price: "$19.00", picks: ["a"], tier: "z", rec: good.obs }) });
  var all = bad.problems.map(function(p){ return p.msg; }).join(" | ");
  ["use a price", "pick at least two", "not supported", "keep the observation separate"].forEach(function(m){ assert.ok(all.indexOf(m) !== -1, m); });
});
test("tier 3: unknown criteria kinds fail loudly instead of passing silently", function(){
  var d = deskFor("m8");
  var st = { id: "r2", type: "compose", groups: [{ id: "g", title: "G", hint: "", records: [] }], fields: [{ id: "x", group: "g", type: "text", label: "X", minWords: 1, criteria: [{ kind: "nope" }] }] };
  assert.ok(!d.evaluate(st, { values: { x: "anything" } }).pass);
});

/* ---------- tier 4 + 5 ---------- */
test("tier 4: self-review needs every confirmation, and nothing else", function(){
  var d = deskFor("m4"), st = noteStage(d, { confirm: ["I checked A", "I checked B"] });
  var v = { issue: "track", note: "The tracking number is missing even though the order is marked as shipped." };
  assert.ok(!d.evaluate(st, { values: v, confirms: [true, false] }).pass);
  assert.ok(d.evaluate(st, { values: v, confirms: [true, true] }).pass);
});
test("tier 5: human review is declared and passed through, never computed", function(){
  var d = deskFor("m3"), st = noteStage(d, { humanReview: { note: "Judged at certification." } });
  var res = d.evaluate(st, { values: { issue: "track", note: "The tracking number is missing even though the order is marked as shipped." } });
  assert.ok(res.pass); assert.deepStrictEqual(res.humanReview, { required: true, note: "Judged at certification." });
});

/* ---------- feedback ---------- */
test("feedback names the choice and points to evidence without revealing answers", function(){
  var d = deskFor("m4"), st = decisionStage(d);
  var fb = d.decisionFeedback(st, d.evaluate(st, { f: ["a", "c"], o: "o2" }));
  var all = JSON.stringify(fb);
  assert.strictEqual(fb.chosen, "Escalate it right away.");
  assert.deepStrictEqual(fb.pointers, ["Check the warehouse line."]);
  assert.ok(all.indexOf("The warehouse has the order") === -1, "missed finding text leaked");
  assert.ok(all.indexOf("Report what the record shows") === -1, "correct option leaked");
});
test("feedback safety filter withholds any line that quotes an answer", function(){
  var d = deskFor("m4"), st = decisionStage(d);
  st.findings[1].miss = "You missed that the warehouse has the order.";      /* bad authoring */
  st.options[1].why = "Better: report what the record shows, without promising a date.";
  var fb = d.decisionFeedback(st, d.evaluate(st, { f: ["a"], o: "o2" }));
  assert.deepStrictEqual(fb.pointers, []);
  assert.strictEqual(fb.why, null);
});
test("feedback supports principle + where-to-look fields", function(){
  var d = deskFor("m4"), st = decisionStage(d);
  delete st.findings[1].miss; st.findings[1].principle = "Paid is not the same as picked."; st.findings[1].look = "Read the warehouse line.";
  var fb = d.decisionFeedback(st, d.evaluate(st, { f: ["a"], o: "o1" }));
  assert.deepStrictEqual(fb.pointers, ["Paid is not the same as picked. Read the warehouse line."]);
  assert.ok(/isn't complete/.test(fb.why), "right action + wrong read explains the reasoning gap");
});
test("module copy overrides generic wording", function(){
  var d = deskFor("m4", { copy: { reasoningFallback: "Module-specific line." } }), st = decisionStage(d);
  assert.ok(/Module-specific line\./.test(d.decisionFeedback(st, d.evaluate(st, { f: ["a"], o: "o1" })).why));
});

/* ---------- retry ---------- */
test("pause and re-check starts at the configured failed attempt (default 2)", function(){
  var d = deskFor("m4");
  assert.ok(!d.shouldPause({ fails: 1 })); assert.ok(d.shouldPause({ fails: 2 }));
  var d3 = deskFor("m5", { retry: { pauseAfterFails: 3 } });
  assert.ok(!d3.shouldPause({ fails: 2 })); assert.ok(d3.shouldPause({ fails: 3 }));
});
test("attempts, fails and first-try are recorded; there is no attempt limit", function(){
  var d = deskFor("m4");
  for(var i = 0; i < 25; i++) d.store.attempt("t", "s", {}, false);
  var st = d.store.attempt("t", "s", { ok: 1 }, true);
  assert.strictEqual(st.attempts, 26); assert.strictEqual(st.fails, 25); assert.strictEqual(st.firstTry, false);
});

/* ---------- verified work vs forged state ---------- */
test("completion is derived from answers that re-validate; forged flags do nothing", function(){
  var mem = Core.memoryStorage(), d = deskFor("m4", null, mem), st = decisionStage(d);
  var task = { id: "t1", stages: [st] };
  mem.setItem(d.storageKey, JSON.stringify({ v: 1, tasks: { t1: { completed: true, verified: true, stages: { d1: { passed: true, answer: { f: ["a"], o: "o1" } } }, drafts: {} } } }));
  assert.strictEqual(d.taskStatus(task).passed, 0);
  assert.strictEqual(d.verifiedWork([task]).t1.verified, false);
  d.store.attempt("t1", "d1", { f: ["a", "b"], o: "o1" }, true);
  assert.strictEqual(d.verifiedWork([task]).t1.verified, true);
});
test("a work sample counts as earned only when its stage verifies", function(){
  var d = deskFor("m4"), st = noteStage(d, { evidence: { title: "Log" } });
  var task = { id: "t2", stages: [st] };
  d.store.draft("t2", "n1:v", { issue: "track", note: "drafts never count" });
  assert.deepStrictEqual(d.verifiedWork([task]).t2.samplesEarned, []);
  d.store.attempt("t2", "n1", { values: { issue: "track", note: "The tracking number is missing even though the order is marked as shipped." } }, true);
  assert.deepStrictEqual(d.verifiedWork([task]).t2.samplesEarned, ["n1"]);
});

/* ---------- extensibility ---------- */
test("new stage types can be registered without touching the engine", function(){
  Core.registerStageType("checklist", { evaluate: function(stage, answer){ return { pass: (answer.ticked || []).length === stage.items.length }; } });
  var d = deskFor("m11");
  assert.ok(d.evaluate({ id: "c", type: "checklist", items: [1, 2] }, { ticked: [1, 2] }).pass);
  assert.ok(!d.evaluate({ id: "c", type: "unknown-type" }, {}).pass, "unknown types never pass");
});

/* ---------- content lint ---------- */
test("lint catches answer-pattern and feedback problems", function(){
  function decision(id, correctLongest){
    return { id: id, type: "decision", label: "L", cta: "Go",
      findings: [{ id: "a", text: "A real finding here.", correct: true, miss: "Look at X." }, { id: "b", text: "Distractor.", wrong: "No." }],
      options: [{ id: "o1", text: correctLongest ? "The right answer, which is much longer than the others." : "Right.", correct: true, why: "Because." },
                { id: "o2", text: "Wrong.", why: "Because not." }] };
  }
  var src = { tasks: [{ id: "t", title: "T", objective: "O", brief: { from: "x", subject: "y" }, stages: [decision("a", true), decision("b", true), decision("c", true), decision("d", true)] }] };
  var res = Codec.lint(src);
  assert.ok(res.errors.some(function(e){ return /longest in 4 of 4/.test(e); }), res.errors.join("; "));
  assert.ok(res.errors.some(function(e){ return /always in position 1/.test(e); }));
  src.tasks[0].stages = [decision("e", false)];
  src.tasks[0].stages[0].findings[1].correct = true; src.tasks[0].stages[0].findings[1].miss = "m";
  assert.ok(Codec.lint(src).errors.some(function(e){ return /every finding is correct/.test(e); }));
  src.tasks[0].stages = [decision("f", false)];
  src.tasks[0].stages[0].findings[1].wrong = "Unlike 'a real finding here', this is wrong.";
  assert.ok(Codec.lint(src).errors.some(function(e){ return /quotes a correct finding/.test(e); }));
});

/* ---------- typed numbers (compose field type "number", engine 2.1) ---------- */
function numberStage(d, extra){
  return lock({ id: "q1", type: "compose", groups: [{ id: "g", title: "G", hint: "look again", records: [] }],
    fields: [ Core.assign({ id: "units", group: "g", type: "number", label: "Units shipped", unit: "units", max: 500, accept: ["58"], msg: "count only the rows the question asks for." }, extra || {}),
              { id: "cost", group: "g", type: "number", label: "Cost", unit: "$", decimals: 2, max: 5000, accept: ["243.60"] } ] }, d);
}
test("number: normalisation is shared by lock and check (currency, commas, spaces, trailing zeros)", function(){
  var N = Core.normalizeNumber;
  assert.strictEqual(N("58", {}).value, "58"); assert.strictEqual(N(" 58.0 ", {}).value, "58");
  assert.strictEqual(N("$1,234.5", { decimals: 2 }).value, "1234.50"); assert.strictEqual(N("1 234", {}).value, "1234");
  ["5 units", "abc", "12,34", "58.5", ""].forEach(function(v){ assert.ok(!N(v, {}).ok, v); });
  assert.ok(!N("12.345", { decimals: 2 }).ok, "more decimals than declared is refused, never rounded into a pass");
});
test("number: exact match against a hashed value; formats that mean the same number all pass", function(){
  var d = deskFor("m90"), st = numberStage(d);
  assert.ok(!JSON.stringify(st).includes("243.60") && !JSON.stringify(st).includes('"58"'), "no plaintext answer after locking");
  ["58", " 58 ", "58.0"].forEach(function(u){ ["243.60", "$243.6", "243.6"].forEach(function(c){ assert.ok(d.evaluate(st, { values: { units: u, cost: c } }).pass, u + " / " + c); }); });
  var r = d.evaluate(st, { values: { units: "57", cost: "243.60" } });
  assert.ok(!r.pass); assert.deepStrictEqual(r.badGroups, ["g"]);
  assert.ok(r.problems.some(function(p){ return /count only the rows/.test(p.msg); }));
});
test("number: feedback never states the value or which way the miss lies", function(){
  var d = deskFor("m91"), st = numberStage(d);
  [["57", "243.60"], ["59", "243.60"], ["58", "243.59"]].forEach(function(v){
    var msgs = d.evaluate(st, { values: { units: v[0], cost: v[1] } }).problems.map(function(p){ return p.msg; }).join(" ");
    assert.ok(!/58|243\.6|higher|lower|too (high|low|many|few)|more|less/i.test(msgs), msgs);
  });
});
test("number: blank or non-numeric entries get a format message, not a correctness verdict", function(){
  var d = deskFor("m92"), st = numberStage(d);
  var r = d.evaluate(st, { values: { units: "58 units", cost: "" } });
  assert.ok(!r.pass); assert.deepStrictEqual(r.badGroups, []);
  assert.strictEqual(r.problems.filter(function(p){ return /enter a number/.test(p.msg); }).length, 2);
  assert.ok(r.problems.some(function(p){ return /up to 2 decimal places/.test(p.msg); }));
});
test("number: several accepted values and tier 3 criteria work like other fields", function(){
  var d = deskFor("m93"), st = numberStage(d, { accept: ["58", "61"] });
  assert.ok(d.evaluate(st, { values: { units: "61", cost: "243.60" } }).pass);
  var d2 = deskFor("m94"), st2 = lock({ id: "q2", type: "compose", groups: [{ id: "g", title: "G", hint: "h", records: [] }],
    fields: [{ id: "n", group: "g", type: "number", label: "N", criteria: [{ kind: "oneOf", values: ["3", "4"], msg: "pick a count the evidence supports." }] }] }, d2);
  assert.ok(d2.evaluate(st2, { values: { n: "4" } }).pass);
  assert.ok(!d2.evaluate(st2, { values: { n: "5" } }).pass);
});
test("number: codec round-trips the answer by searching the declared range", function(){
  var d = deskFor("m95"), src = { id: "q3", type: "compose", groups: [], fields: [
    { id: "a", group: "g", type: "number", label: "A", max: 500, accept: ["58"] },
    { id: "b", group: "g", type: "number", label: "B", decimals: 2, min: 100, max: 1000, accept: ["243.6"] } ] };
  var st = JSON.parse(JSON.stringify(src)); Codec.lockStage(st, d.codec.keys); Codec.unlockStage(st, d.codec.keys);
  assert.deepStrictEqual(st.fields[0].accept, ["58"]); assert.deepStrictEqual(st.fields[1].accept, ["243.60"]);
});
test("number: lint requires a max, a valid in-range answer and a bounded search", function(){
  function src(f){ return { tasks: [{ id: "t", title: "T", objective: "O", brief: { from: "x", subject: "y" }, stages: [{ id: "s", type: "compose", label: "L", cta: "c", groups: [], fields: [f] }] }] }; }
  function errs(f){ return Codec.lint(src(f)).errors.join("; "); }
  assert.ok(/needs a numeric max/.test(errs({ id: "n", group: "g", type: "number", label: "N", accept: ["5"] })));
  assert.ok(/not a valid number/.test(errs({ id: "n", group: "g", type: "number", label: "N", max: 9, accept: ["5.5"] })));
  assert.ok(/outside min..max/.test(errs({ id: "n", group: "g", type: "number", label: "N", max: 9, accept: ["12"] })));
  assert.ok(/range too large/.test(errs({ id: "n", group: "g", type: "number", label: "N", decimals: 2, max: 1e6, accept: ["5"] })));
  assert.strictEqual(errs({ id: "n", group: "g", type: "number", label: "N", max: 9, accept: ["5"] }), "");
  assert.ok(Codec.lint(src({ id: "n", group: "g", type: "number", label: "N" })).warnings.some(function(w){ return /any number passes/.test(w); }));
});
test("number: adding the field type leaves existing field types unchanged", function(){
  var d = deskFor("m96");
  var st = lock({ id: "c9", type: "compose", groups: [{ id: "g", title: "G", hint: "h", records: [] }],
    fields: [ { id: "s", group: "g", type: "select", label: "S", options: [{ value: "a" }, { value: "b" }], accept: ["b"] },
              { id: "t", group: "g", type: "text", label: "T", minWords: 2 } ] }, d);
  assert.ok(d.evaluate(st, { values: { s: "b", t: "two words" } }).pass);
  assert.ok(/choose an option/.test(d.evaluate(st, { values: { s: "", t: "two words" } }).problems[0].msg));
});

console.log("\n" + (passed + failed) + " unit tests, " + failed + " failed");
process.exit(failed ? 1 : 0);
