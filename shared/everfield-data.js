/* PVA Free Training -- E-commerce VA Foundations
   Everfield Goods reference data (fictional company, training use only).

   SHARED AUTHORED STATE. Plain, answer-free facts about the simulated company
   that any module may read: team, partners, channels, products, and the
   Everfield calendar (which simulated working day each converted module uses).

   Learner state never lives here. The object is deep-frozen, so nothing a
   learner does in one module can change what another module sees; per-learner
   work lives only in each module's own desk storage key.

   Add shared records (orders, customers, stock rows that recur across modules)
   here or in a sibling file only when a second module actually needs them. */

(function(){
  var EVERFIELD = {
    company: "Everfield Goods LLC",
    team: {
      sofia:  { name: "Sofia Ramirez", role: "E-commerce Manager" },
      maya:   { name: "Maya Collins",  role: "Operations Manager" },
      daniel: { name: "Daniel Brooks", role: "Everfield team" },
      marcus: { name: "Marcus Lee",    role: "Everfield team" }
    },
    partners: {
      clearpath: { name: "ClearPath Fulfillment", role: "3PL (warehouse, pick, pack, ship)" }
    },
    channels: ["Brand store", "Online marketplace"],
    products: {
      "EF-101": "Stackable Storage Bin",
      "EF-102": "Drawer Label Set",
      "EF-103": "Bamboo Organizer Tray",
      "EF-104": "Cable Management Set",
      "EF-105": "Travel Packing Pouch Set",
      "EF-106": "Closet Divider Set",
      "EF-107": "Reusable Storage Bag Set",
      "EF-200": "Home Organization Starter Kit"
    },
    /* Simulated working day per converted module. Keeps dates consistent
       across modules; extend as modules are converted. */
    calendar: {
      m4: { date: "Tue, Sep 15" }
    }
  };
  (function freeze(o){
    if(o && typeof o === "object" && !Object.isFrozen(o)){ Object.freeze(o); Object.keys(o).forEach(function(k){ freeze(o[k]); }); }
  })(EVERFIELD);
  window.EVERFIELD = EVERFIELD;
})();
