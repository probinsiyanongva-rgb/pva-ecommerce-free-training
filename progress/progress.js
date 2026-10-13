/* Export / Restore / Clear progress for E-commerce VA -- Beginner Foundations.
   Only this course's keys are touched. A restore writes the saved answers back;
   nothing in a backup is trusted: every module page and the certificate page
   re-validate the answers against their hashed keys, so edited flags or wrong
   answers restore as text but count for nothing. */
(function(){
  "use strict";
  var FORMAT = "pva-ecom-ft-progress-backup", VERSION = 1, COURSE = "E-commerce VA — Beginner Foundations";
  var KEY_RX = /^pva-ecom-ft-(progress|m(?:[1-9]|1[0-4])-desk|certificate)$/;
  var $ = function(id){ return document.getElementById(id); };
  function courseKeys(){
    var out = [];
    try{ for(var i = 0; i < localStorage.length; i++){ var k = localStorage.key(i); if(KEY_RX.test(k)) out.push(k); } }catch(e){}
    return out.sort();
  }
  function say(id, msg, cls){ var e = $(id); e.textContent = msg; e.className = "msg " + (cls || ""); }

  function render(){
    var keys = courseKeys();
    $("savedCount").textContent = keys.length ? keys.length + " saved item" + (keys.length > 1 ? "s" : "") + " in this browser." : "Nothing saved in this browser yet.";
    if(window.PVAEcomVerify) window.PVAEcomVerify.check(window.PVA_ECOM_CERT, "../").then(function(res){
      var ul = $("verifiedList"); ul.innerHTML = "";
      res.modules.forEach(function(m){
        var li = document.createElement("li");
        li.textContent = "Module " + m.n + ": " + (m.state === "verified" ? "all desk work checks out" : m.state === "pending" ? m.verified + " of " + m.total + " tasks check out" : "not available yet");
        ul.appendChild(li);
      });
    });
  }

  $("btnExport").addEventListener("click", function(){
    var keys = courseKeys(), data = {};
    keys.forEach(function(k){ try{ data[k] = localStorage.getItem(k); }catch(e){} });
    var d = new Date(), stamp = d.getFullYear() + "-" + ("0" + (d.getMonth() + 1)).slice(-2) + "-" + ("0" + d.getDate()).slice(-2);
    var file = { format: FORMAT, version: VERSION, course: COURSE, exportedAt: d.toISOString(),
                 note: "Progress backup for this course only. Restoring re-checks every answer; nothing in this file is trusted.",
                 summary: { savedItems: keys.length }, keys: data };
    var blob = new Blob([JSON.stringify(file, null, 1)], { type: "application/json" });
    var a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "E-commerce-VA-progress-backup-" + stamp + ".json";
    document.body.appendChild(a); a.click(); a.remove();
    say("exportMsg", "Backup downloaded. Keep it somewhere safe.", "ok");
  });

  var pending = null;
  $("fileRestore").addEventListener("change", function(ev){
    pending = null; $("restoreConfirm").hidden = true;
    var f = ev.target.files && ev.target.files[0]; if(!f) return;
    var rd = new FileReader();
    rd.onload = function(){
      var obj;
      try{ obj = JSON.parse(rd.result); }catch(e){ return say("restoreMsg", "This file isn't a progress backup (it isn't valid JSON).", "err"); }
      if(!obj || typeof obj !== "object") return say("restoreMsg", "This file isn't a progress backup.", "err");
      if(obj.format !== FORMAT){
        if(typeof obj.format === "string" && /^pva-/.test(obj.format)) return say("restoreMsg", "Backups from other PVA courses cannot be restored here.", "err");
        return say("restoreMsg", "This file isn't a progress backup for this course.", "err");
      }
      if(typeof obj.version !== "number" || obj.version > VERSION) return say("restoreMsg", "This backup was made by a newer version of the course and can't be restored here.", "err");
      var keys = obj.keys && typeof obj.keys === "object" ? Object.keys(obj.keys) : null;
      if(!keys || !keys.length) return say("restoreMsg", "This backup holds no saved progress.", "err");
      var bad = keys.filter(function(k){ if(!KEY_RX.test(k) || typeof obj.keys[k] !== "string") return true; try{ JSON.parse(obj.keys[k]); return false; }catch(e){ return true; } });
      if(bad.length) return say("restoreMsg", "This backup contains items that don't belong to this course, so it can't be restored.", "err");
      pending = obj;
      say("restoreMsg", "Backup from " + (obj.exportedAt ? new Date(obj.exportedAt).toLocaleString() : "an unknown date") + " with " + keys.length + " saved item" + (keys.length > 1 ? "s" : "") + ". Restoring replaces what's saved in this browser now.", "");
      $("restoreConfirm").hidden = false;
    };
    rd.readAsText(f);
  });
  $("btnRestore").addEventListener("click", function(){
    if(!pending) return;
    try{
      courseKeys().forEach(function(k){ localStorage.removeItem(k); });
      Object.keys(pending.keys).forEach(function(k){ localStorage.setItem(k, pending.keys[k]); });
    }catch(e){ return say("restoreMsg", "Your browser didn't allow the restore (storage may be blocked).", "err"); }
    pending = null; $("restoreConfirm").hidden = true; $("fileRestore").value = "";
    say("restoreMsg", "Restored. Every module re-checks your saved answers when it opens; anything that doesn't check out won't count.", "ok");
    render();
  });
  $("btnCancel").addEventListener("click", function(){ pending = null; $("restoreConfirm").hidden = true; $("fileRestore").value = ""; say("restoreMsg", "Restore cancelled. Nothing changed.", ""); });

  $("btnClear").addEventListener("click", function(){
    if(!window.confirm("Clear all saved progress for this course in this browser? This can't be undone unless you have a backup.")) return;
    try{ courseKeys().forEach(function(k){ localStorage.removeItem(k); }); }catch(e){}
    say("clearMsg", "This course's progress was cleared from this browser.", "ok");
    render();
  });
  render();
})();
