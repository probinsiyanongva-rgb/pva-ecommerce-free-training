/* PVA Free Training -- E-commerce VA Foundations
   Everfield Goods reference data (fictional company, training use only).

   Plain, answer-free facts about the simulated company: team, partners,
   products. Kept separate from any module's task data so later modules can
   share one source of truth for Everfield (cross-module continuity).
   Currently loaded only by the Module 4 pilot. */

(function(){
  var EVERFIELD = {
    company: "Everfield Goods LLC",
    simDate: "Tue, Sep 15",          /* the working day used across the Module 4 desk */
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
    }
  };
  window.EVERFIELD = EVERFIELD;
})();
