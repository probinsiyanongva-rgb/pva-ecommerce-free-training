/* PVA Free Training -- E-commerce VA Foundations
   Everfield Goods reference data (fictional company, training use only).

   SHARED AUTHORED STATE -- the static "Company Bible" facts any module may
   read: company, team, partners, channels, product master facts, and the
   Everfield calendar. Recurring operational records (orders, stock rows) live
   in the sibling file shared/everfield-records.js.

   Every fact here was first authored in the course itself; `src` says where
   (hub = the course home page's "Meet Everfield Goods" panel). tools/
   everfield-check.js fails if a module and this file drift apart.

   Learner state never lives here. The object is deep-frozen, so nothing a
   learner does in one module can change what another module sees; per-learner
   work lives only in each module's own desk storage key.

   Authority limits and policies are deliberately NOT here: this file is loaded
   on desk pages, and the authority canon would hint at desk answers. They are
   kept for authors in docs/everfield-continuity.md. */

(function(root){
  var EVERFIELD = {
    company: "Everfield Goods LLC",
    /* Keys are used by desk briefs (`from`). marcus works for the 3PL, not
       Everfield; org says so. src: hub "Who you'll hear from"; module-1 m1-l6. */
    team: {
      sofia:  { name: "Sofia Ramirez", role: "E-commerce Manager", org: "Everfield Goods" },
      maya:   { name: "Maya Collins",  role: "Operations Manager", org: "Everfield Goods" },
      daniel: { name: "Daniel Brooks", role: "Procurement & Supply Manager", org: "Everfield Goods" },
      marcus: { name: "Marcus Lee",    role: "3PL Account Manager", org: "ClearPath Fulfillment" }
    },
    partners: {
      clearpath: { name: "ClearPath Fulfillment", role: "3PL (warehouse, pick, pack, ship)" }
    },
    /* src: hub "How Everfield sells". */
    channels: ["Brand store", "Online marketplace", "B2B / bulk"],
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
    /* Product master facts that the course states as Everfield's own. Only
       facts some module already asserts, or approved product canon recorded in
       docs/everfield-continuity.md (src "docs everfield-continuity.md"; the
       unit costs, decision D5); anything absent is undefined -- add it here
       before a module relies on it. */
    productFacts: {
      catalog:  { variants: "none -- no size/color variants on any SKU", src: ["module-2 m2-l1"] },
      "EF-101": { category: "Home Organization", unitCost: "$4.20", dimensions: "16in x 11in x 9in", weight: "2.2 lb",
                  src: ["docs everfield-continuity.md", "module-2 m2-l2", "module-3 m3-l2", "module-6 m6-l4"] },
      "EF-102": { pack: "40 Pieces", src: ["module-2 m2-l1", "module-3 m3-l8"] },
      "EF-103": { category: "Home Organization", supplier: "Pinecrest Manufacturing", leadTime: "14 days", unit: "Each",
                  src: ["module-2 m2-l2"] },
      "EF-104": { pack: "12-Piece", src: ["module-11 m11-l7"] },
      "EF-105": { category: "Travel Organization", unitCost: "$3.85", src: ["docs everfield-continuity.md", "module-2 m2-l7"] },
      "EF-107": { pack: "3-piece set", src: ["module-6 m6-l9"] },
      "EF-200": { kit: { "EF-101": 2, "EF-102": 1, "EF-103": 1 }, listingCategory: "Kits",
                  src: ["docs everfield-continuity.md", "module-2 m2-l2", "module-3 m3-l8"] }
    },
    /* Simulated working day per converted module. The desk engine reads
       calendar[moduleId].date; keep this a plain module -> date map. */
    calendar: {
      m4: { date: "Tue, Sep 15" },
      m7: { date: "Thu, Sep 17" },
      m5: { date: "Wed, Sep 2" },
      m9: { date: "Fri, Sep 25" },
      m2: { date: "Tue, Sep 8" },
      m3: { date: "Wed, Sep 9" },
      m8: { date: "Fri, Sep 11" },
      m10: { date: "Fri, Sep 18" },
      m6: { date: "Thu, Sep 10" },
      m13: { date: "Fri, Oct 2" }   // the report day; Lesson 1 declares its own work date (Wed, Sep 30)
    },
    /* The canonical operating timeline (docs/everfield-continuity.md has the
       reasoning). One operating period from September into early October; the
       year is never shown to learners -- weekdays follow a calendar in which
       Sep 15 is a Tuesday (so Oct 2 is a Friday). */
    timeline: {
      period: "September – October",
      weekdayAnchor: "Tue, Sep 15",
      entries: [
        { date: "on or before Wed, Sep 2", what: "Early-September stock snapshot (Module 5's 8:00 AM stock sheet)", ref: "stock-early-sep", src: ["module-5 m5-l7"] },
        { date: "Tue, Sep 1 - Wed, Sep 2", what: "Module 5 records: orders #4023-#4027, EF-101 movements, ClearPath's 7:00 AM cycle count", src: ["module-5 desk-data"] },
        { date: "Wed, Sep 2", what: "Module 5 desk day (inventory check, 9:15 AM - 4:30 PM)", src: ["module-5 desk-data"] },
        { date: "Wed, Sep 2", what: "Order #4021 ships; EF-101 balance 34 -> 32", ref: "#4021", src: ["module-5 m5-l7", "module-9 m9-l3"] },
        { date: "Wed, Sep 2", what: "Return #229 (EF-101 x2, unopened) restocked", ref: "Return #229", src: ["module-11 m11-l4", "module-5 m5-l7", "module-6 m6-l2"] },
        { date: "before Sun, Sep 6", what: "Weekly report notes EF-103 inbound", ref: "inbound-ef103-sep6", src: ["module-13 m13-l5"] },
        { date: "Sun, Sep 6", what: "EF-103 inbound (25 units) expected", ref: "inbound-ef103-sep6", src: ["module-13 m13-l5"] },
        { date: "Sat, Sep 5 - Tue, Sep 15", what: "Module 4 order records", src: ["module-4 desk-data"] },
        { date: "Tue, Sep 15", what: "Module 4 desk day", src: ["module-4 desk-data"] },
        { date: "Thu, Sep 3 - Tue, Sep 8", what: "Module 2 records: product master rows, Pinecrest's spec sheet and a superseded draft, a marketplace listing-ID cross-reference, three EF-200 shipments (orders #5496-#5498) and a carrier weight notice (Module 2-local)", src: ["module-2 desk-data"] },
        { date: "Tue, Sep 8", what: "Module 2 desk day (product data, 9:00 AM - 2:30 PM)", src: ["module-2 desk-data"] },
        { date: "Mon, Sep 7 - Wed, Sep 9", what: "Module 3 records: approved product records, draft listings, supplier copy, image files and a listing QA queue (Module 3-local; no orders, stock figures or prices)", src: ["module-3 desk-data"] },
        { date: "Wed, Sep 9", what: "Module 3 desk day (listings, 9:30 AM - 3:00 PM)", src: ["module-3 desk-data"] },
        { date: "Thu, Sep 10 - Fri, Sep 11", what: "Module 8 research material: simulated outside stores' listings, prices, shipping terms and reviews (fictional training data, Module 8-local; no Everfield orders, stock or prices)", src: ["module-8 desk-data"] },
        { date: "Fri, Sep 11", what: "Module 8 desk day (research, 9:30 AM - 3:30 PM)", src: ["module-8 desk-data"] },
        { date: "Tue, Sep 1 - Fri, Sep 18", what: "Module 10 admin records: two simulated store admins (brand store and marketplace seller center), last month's discount code, Sofia's autumn promotion decision, banners, integration status lines and admin accounts (Module 10-local; no orders, stock or prices)", src: ["module-10 desk-data"] },
        { date: "Fri, Sep 18", what: "Module 10 desk day (store admin, 9:15 AM - 2:30 PM)", src: ["module-10 desk-data"] },
        { date: "Mon, Sep 7 - Thu, Sep 10", what: "Module 6 records: customer messages, orders #5483-#5495, an EF-105 stock card (Module 6-local)", src: ["module-6 desk-data"] },
        { date: "Thu, Sep 10", what: "Module 6 desk day (the support inbox, 9:30 AM - 3:15 PM)", src: ["module-6 desk-data"] },
        { date: "Thu, Sep 3 - Thu, Sep 17", what: "Module 7 order and return records", src: ["module-7 desk-data"] },
        { date: "Thu, Sep 17", what: "Module 7 desk day", src: ["module-7 desk-data"] },
        { date: "Mon, Sep 21 - Fri, Sep 25", what: "Module 9 week: order export, ClearPath weekly report, stock sheet, open-items log", src: ["module-9 desk-data"] },
        { date: "Fri, Sep 25", what: "Module 9 desk day (Everfield's weekly report day)", src: ["module-9 desk-data"] },
        { date: "Mon, Sep 28 - Fri, Oct 2", what: "Module 13 week: customer contacts, returns, exceptions, the VA work log and the verified Operations Tracker (Module 13-local records)", src: ["module-13 desk-data"] },
        { date: "Wed, Sep 30", what: "Module 13 Lesson 1 work date (midweek items; ClearPath's missed carrier pickup)", src: ["module-13 m13-l2"] },
        { date: "Fri, Oct 2", what: "Module 13 report day (Lessons 2 and 3; the weekly report for Sofia)", src: ["module-13 desk-data"] },
        { date: "after the EF-103 inbound sells through", what: "Capstone week (EF-103 at 0 available, 0 inbound); exact week not yet fixed", src: ["module-14 m14-t4"] }
      ]
    },
    /* Operating rhythm stated in the course. */
    operating: {
      weeklyReport: { day: "Friday", src: ["module-13 m13-l2"] }
    }
  };
  (function freeze(o){
    if(o && typeof o === "object" && !Object.isFrozen(o)){ Object.freeze(o); Object.keys(o).forEach(function(k){ freeze(o[k]); }); }
  })(EVERFIELD);
  root.EVERFIELD = EVERFIELD;
  if(typeof module !== "undefined" && module.exports) module.exports = EVERFIELD;
})(typeof window !== "undefined" ? window : globalThis);
