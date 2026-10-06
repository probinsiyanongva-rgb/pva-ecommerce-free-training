/* PVA Free Training -- E-commerce VA Foundations
   Everfield shared authored records (fictional, training use only).

   Operational records that more than one module deliberately shows: the same
   order, stock row or inbound shipment, with the same facts everywhere. This
   is authored continuity, not a simulation: records never change at run time,
   and nothing a learner does (an "adjustment" in an inventory exercise, an
   answer, a draft) is written here or derived from here.

   What belongs here: a record two or more modules reference by ID or by
   identical facts. What does not: records only one module needs (they stay in
   that module's content), answer keys, correct/incorrect markers, feedback,
   hints, and any learner state. tools/everfield-check.js enforces this.

   `src` lists every place the record appears today. Legacy (non-desk) modules
   still carry their own text; the checker fails if that text drifts from the
   record. Converted modules should read from here instead of restating it. */

(function(root){
  var EVERFIELD_RECORDS = {
    orders: {
      "#4021": { date: "Wed, Sep 2", sku: "EF-101", qty: 2, status: "Shipped",
                 src: ["module-5 m5-l7", "module-9 m9-l3"] }
    },
    stock: {
      snapshots: {
        "stock-early-sep": {
          asOf: "on or before Wed, Sep 2",
          columns: ["Available", "Reserved", "Inbound"],
          rows: {
            "EF-101": { available: 34, reserved: 6, inbound: 50 },
            "EF-103": { available: 0, reserved: 2, inbound: 25 }
          },
          src: ["module-5 m5-l2", "module-5 m5-l3", "module-5 m5-l5", "module-13 m13-l5", "module-14 m14-t4"]
        }
      },
      movements: {
        "mv-sep2-4021": { date: "Wed, Sep 2", sku: "EF-101", qty: -2, event: "customer shipment", ref: "#4021", balance: 32,
                          src: ["module-5 m5-l7"] }
      },
      inbound: {
        "inbound-ef103-sep6": { sku: "EF-103", qty: 25, expected: "Sun, Sep 6", src: ["module-13 m13-l5", "module-5 m5-l2"] }
      }
    },
    customers: {},
    cases: {}
  };
  (function freeze(o){
    if(o && typeof o === "object" && !Object.isFrozen(o)){ Object.freeze(o); Object.keys(o).forEach(function(k){ freeze(o[k]); }); }
  })(EVERFIELD_RECORDS);
  root.EVERFIELD_RECORDS = EVERFIELD_RECORDS;
  if(typeof module !== "undefined" && module.exports) module.exports = EVERFIELD_RECORDS;
})(typeof window !== "undefined" ? window : globalThis);
