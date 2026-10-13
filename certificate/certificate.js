/* Certificate of Completion page. Eligibility comes only from PVAEcomVerify
   (re-validated desk work); the saved name and acknowledgment live in this
   course's own key. No certificate ID, QR code or verification link: nothing on
   this site could verify one. */
(function(){
  "use strict";
  var CFG = window.PVA_ECOM_CERT, KEY = CFG.storageKey;
  var listEl = document.getElementById("reqList"), statusEl = document.getElementById("reqStatus"), panel = document.getElementById("certPanel");

  var REMINDER_TITLE = "A Gentle Reminder Before You Save";
  var REMINDER = [
    "You've put time and effort into your learning journey. As you complete this course, take a moment to reflect on what you've learned and the skills you've practiced.",
    "Your certificate records your completion of the course requirements. The real value, however, comes from the knowledge and skills you can carry into your work.",
    "Please make sure that your completed activities reflect your own effort and that you've approached the exercises with honesty and a willingness to learn.",
    "Keep practicing, keep improving, and let your skills speak for themselves.",
    "Thank you for being part of PVA Academy!"
  ];
  var ACK = "I've taken a moment to reflect on my learning and the work I've completed.";
  var FOOTER = "Proof of course completion. Not a professional license, a credential, or evidence of paid client work.";

  function el(tag, cls, text){ var e = document.createElement(tag); if(cls) e.className = cls; if(text !== undefined) e.textContent = text; return e; }
  function readSaved(){ try{ var r = localStorage.getItem(KEY); var s = r ? JSON.parse(r) : null; return s && typeof s.name === "string" ? s : null; }catch(e){ return null; } }
  function writeSaved(s){ try{ localStorage.setItem(KEY, JSON.stringify(s)); return true; }catch(e){ return false; } }
  function cleanName(v){ return String(v || "").replace(/\s+/g, " ").trim(); }
  function validName(v){ var n = cleanName(v); return n.length >= 2 && n.length <= 80 && /[A-Za-zÀ-ɏ]/.test(n); }
  function xml(s){ return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;"); }
  function today(){ return new Date().toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" }); }

  function renderList(res){
    listEl.innerHTML = "";
    res.modules.forEach(function(m){
      var li = el("li"), left = el("span");
      var link = el("a"); link.href = "../module-" + m.n + "/index.html"; link.appendChild(el("strong", null, "Module " + m.n + " · " + m.title));
      left.appendChild(link);
      var sub = null;
      if(m.state === "unavailable") sub = m.n === 1 ? "The updated Module 1 isn't released yet. It will be required." : "This module's desk work couldn't be loaded.";
      else if(m.state === "pending") sub = m.verified + " of " + m.total + " tasks check out" + (m.legacy ? ". A checkmark from the earlier version doesn't count on its own; do the desk work." : ".");
      if(sub) left.appendChild(el("span", "sub", sub));
      li.appendChild(left);
      li.appendChild(el("span", "st " + (m.state === "verified" ? "ok" : "no"), m.state === "verified" ? "Verified" : m.state === "unavailable" ? "Not available yet" : "Not yet"));
      listEl.appendChild(li);
    });
    var done = res.modules.filter(function(m){ return m.state === "verified"; }).length;
    statusEl.textContent = done + " of " + res.modules.length + " modules verified in this browser.";
  }

  function certSVG(name, date){
    var n = xml(name), d = xml(date);
    var size = name.length > 38 ? 34 : name.length > 26 ? 42 : 52;
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1100 780" role="img" aria-label="Certificate of Completion for ' + n + '">' +
      '<rect width="1100" height="780" fill="#FAF7EF"/>' +
      '<rect x="22" y="22" width="1056" height="736" fill="none" stroke="#1F3D2F" stroke-width="10"/>' +
      '<rect x="44" y="44" width="1012" height="692" fill="none" stroke="#A97A2E" stroke-width="2"/>' +
      '<text x="550" y="126" text-anchor="middle" font-family="IBM Plex Sans, Segoe UI, sans-serif" font-size="18" letter-spacing="4" fill="#4C594E">PROBINSIYANONG VA · PVA FREE TRAINING</text>' +
      '<text x="550" y="206" text-anchor="middle" font-family="Source Serif 4, Georgia, serif" font-size="58" font-weight="600" fill="#1F3D2F">Certificate of Completion</text>' +
      '<text x="550" y="270" text-anchor="middle" font-family="IBM Plex Sans, Segoe UI, sans-serif" font-size="20" fill="#4C594E">This certifies that</text>' +
      '<text x="550" y="350" text-anchor="middle" font-family="Source Serif 4, Georgia, serif" font-style="italic" font-size="' + size + '" fill="#1B2A20">' + n + '</text>' +
      '<line x1="250" y1="374" x2="850" y2="374" stroke="#C9BE9E" stroke-width="1.5"/>' +
      '<text x="550" y="420" text-anchor="middle" font-family="IBM Plex Sans, Segoe UI, sans-serif" font-size="20" fill="#4C594E">has completed the lessons and practical requirements of</text>' +
      '<text x="550" y="470" text-anchor="middle" font-family="Source Serif 4, Georgia, serif" font-size="34" font-weight="600" fill="#1F3D2F">' + xml(CFG.course) + '</text>' +
      '<text x="550" y="508" text-anchor="middle" font-family="IBM Plex Sans, Segoe UI, sans-serif" font-size="18" fill="#4C594E">' + xml(CFG.issuer) + '</text>' +
      '<text x="290" y="600" text-anchor="middle" font-family="IBM Plex Sans, Segoe UI, sans-serif" font-size="20" fill="#1B2A20">' + d + '</text>' +
      '<line x1="170" y1="616" x2="410" y2="616" stroke="#1B2A20" stroke-width="1"/>' +
      '<text x="290" y="640" text-anchor="middle" font-family="IBM Plex Sans, Segoe UI, sans-serif" font-size="15" fill="#4C594E">Date completed</text>' +
      '<text x="810" y="598" text-anchor="middle" font-family="Brush Script MT, Segoe Script, cursive" font-size="40" fill="#1F3D2F">' + xml(CFG.signature) + '</text>' +
      '<line x1="690" y1="616" x2="930" y2="616" stroke="#1B2A20" stroke-width="1"/>' +
      '<text x="810" y="640" text-anchor="middle" font-family="IBM Plex Sans, Segoe UI, sans-serif" font-size="15" fill="#4C594E">' + xml(CFG.signatureCaption) + '</text>' +
      '<text x="550" y="704" text-anchor="middle" font-family="IBM Plex Sans, Segoe UI, sans-serif" font-size="14" fill="#5A6657">' + xml(FOOTER) + '</text>' +
      '</svg>';
  }

  function showCertificate(saved){
    panel.innerHTML = "";
    var wrap = el("div", "cert-wrap"); wrap.id = "certificate";
    wrap.innerHTML = certSVG(saved.name, saved.date);
    panel.appendChild(wrap);
    var actions = el("div", "cert-actions no-print");
    var pr = el("button", "btn btn-primary", "Print / Save as PDF"); pr.type = "button"; pr.addEventListener("click", function(){ window.print(); });
    var dl = el("button", "btn btn-ghost", "Download (SVG)"); dl.type = "button";
    dl.addEventListener("click", function(){
      var blob = new Blob([certSVG(saved.name, saved.date)], { type: "image/svg+xml" });
      var a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "E-commerce-VA-certificate.svg"; document.body.appendChild(a); a.click(); a.remove();
    });
    var ed = el("button", "btn btn-ghost", "Change the name"); ed.type = "button"; ed.addEventListener("click", function(){ showForm(saved.name); });
    actions.appendChild(pr); actions.appendChild(dl); actions.appendChild(ed);
    panel.appendChild(actions);
  }

  function showForm(prefill){
    panel.innerHTML = "";
    var card = el("section", "card card-pad no-print"); card.id = "certForm"; card.style.marginTop = "20px";
    card.appendChild(el("h2", null, "Your certificate is ready to save"));
    var f = el("div", "field");
    var lab = el("label", null, "Your name, exactly as it should appear"); lab.htmlFor = "certName";
    var inp = el("input"); inp.id = "certName"; inp.type = "text"; inp.maxLength = 80; inp.autocomplete = "name"; inp.value = prefill || "";
    f.appendChild(lab); f.appendChild(inp); f.appendChild(el("p", "hint", "This is printed on your certificate as you type it."));
    card.appendChild(f);
    var rem = el("div", "reminder"); rem.id = "certReminder";
    rem.appendChild(el("h3", null, REMINDER_TITLE));
    REMINDER.forEach(function(p){ rem.appendChild(el("p", null, p)); });
    card.appendChild(rem);
    var ack = el("label", "ack"); var cb = el("input"); cb.type = "checkbox"; cb.id = "certAck";
    ack.appendChild(cb); ack.appendChild(el("span", null, ACK)); card.appendChild(ack);
    var save = el("button", "btn btn-primary", "Save Certificate"); save.type = "button"; save.id = "certSave";
    function sync(){ save.disabled = !(validName(inp.value) && cb.checked); }
    inp.addEventListener("input", sync); cb.addEventListener("change", sync); sync();
    save.addEventListener("click", function(){
      if(save.disabled) return;
      var s = { name: cleanName(inp.value), date: today(), acknowledged: true, savedAt: new Date().toISOString() };
      writeSaved(s); showCertificate(s);
    });
    card.appendChild(save);
    panel.appendChild(card);
  }

  function notOpen(){
    panel.innerHTML = "";
    var n = el("div", "notice"); n.id = "certNotOpen";
    n.appendChild(el("strong", null, "Certificates aren't open yet. "));
    n.appendChild(document.createTextNode("They open once the updated Module 1 is released, because every module, Module 1 included, is part of the requirements. Keep your work saved in this browser (or back it up from the Progress page): nothing you've done is lost."));
    panel.appendChild(n);
  }

  window.PVAEcomVerify.check(CFG, "../").then(function(res){
    renderList(res);
    if(!CFG.open){ notOpen(); return; }
    if(!res.eligible){
      panel.innerHTML = "";
      var n = el("div", "notice"); n.id = "certLocked";
      n.appendChild(el("strong", null, "Not unlocked yet. "));
      n.appendChild(document.createTextNode("Finish the desk work in every module above. Your certificate unlocks as soon as all of it checks out."));
      panel.appendChild(n); return;
    }
    var saved = readSaved();
    if(saved && saved.acknowledged && validName(saved.name) && saved.date) showCertificate(saved); else showForm("");
  });
})();
