/* Re-checks every required module's stored desk work, read-only.
   Loads each module's shipped desk-data.js and asks the Work Desk core to
   re-validate the learner's stored answers against the module's hashed keys --
   the same check each module page runs. Stored "completed"/"verified" flags and
   legacy checkmarks are never trusted. Nothing here writes to storage. */
(function(root){
  "use strict";
  function loadScript(src){
    return new Promise(function(resolve){
      var s = document.createElement("script");
      s.src = src; s.async = false;
      s.onload = function(){ resolve(true); };
      s.onerror = function(){ resolve(false); };
      document.head.appendChild(s);
    });
  }
  function legacyLessons(){
    try{ var raw = root.localStorage.getItem("pva-ecom-ft-progress"); var s = raw ? JSON.parse(raw) : null; return (s && s.lessons) || {}; }
    catch(e){ return {}; }
  }
  /* Returns a promise of { modules: [{n, id, title, state, verified, total, legacy}], eligible } */
  function check(cfg, base){
    var Core = root.PVADeskCore, legacy = legacyLessons();
    return Promise.all(cfg.modules.map(function(m){
      return loadScript(base + "module-" + m.n + "/desk-data.js").then(function(ok){
        var out = { n: m.n, id: m.id, title: m.title, state: "unavailable", verified: 0, total: 0, legacy: false };
        var mod = ok && root.PVA_DESK_MODULES && root.PVA_DESK_MODULES[m.id];
        out.legacy = Object.keys(legacy).some(function(k){ return legacy[k] && k.indexOf(m.id + "-") === 0; });
        if(!mod || !Core) return out;
        try{
          var desk = Core.createDesk(mod.config, { storageScope: "certificate-check" });
          var data = desk.decode(mod.payload);
          var vw = desk.verifiedWork(data.tasks);
          out.total = data.tasks.length;
          out.verified = data.tasks.filter(function(t){ return vw[t.id] && vw[t.id].verified; }).length;
          out.state = out.verified === out.total && out.total > 0 ? "verified" : "pending";
        }catch(e){ out.state = "unavailable"; }
        return out;
      });
    })).then(function(mods){
      return { modules: mods, eligible: !!cfg.open && mods.every(function(x){ return x.state === "verified"; }) };
    });
  }
  root.PVAEcomVerify = { check: check };
})(window);
