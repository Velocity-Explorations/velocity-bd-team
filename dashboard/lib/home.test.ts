import { test } from "node:test";
import assert from "node:assert/strict";
import { dayMonth, daysLeftText, kindsLine, portalLogo, topTenOrder } from "./home.ts";

test("days left reads as words", () => {
  assert.equal(daysLeftText(null), "");
  assert.equal(daysLeftText(0), "closes today");
  assert.equal(daysLeftText(1), "1 day left");
  assert.equal(daysLeftText(402), "402 days left");
  assert.equal(daysLeftText(-1), "closed yesterday");
  assert.equal(daysLeftText(-3), "closed 3 days ago");
});

test("the requests waiting, by kind, in a few words", () => {
  assert.equal(kindsLine([]), "");
  assert.equal(kindsLine(["keyword_change", "scan"]), "a keyword change, a scan");
  assert.equal(kindsLine(["scan", "scan", "rereview"]), "2 scans, a re-review");
  assert.equal(kindsLine(["fault_report", "draft", "mystery"]), "a fault report, a draft, a mystery request");
});

test("a day and month in the dashboard's zone", () => {
  assert.equal(dayMonth(new Date("2026-11-11T05:00:00Z"), "America/Denver"), "10 Nov");
  assert.equal(dayMonth(new Date("2026-11-11T12:00:00Z"), "America/Denver"), "11 Nov");
});

test("each portal shows its logo, or an initials tile when it has none", () => {
  assert.deepEqual(portalLogo("SAM.gov"), { src: "/logos/sam-gov.png" });
  assert.deepEqual(portalLogo("SSC Front Door"), { src: "/logos/ssc.png" });
  assert.deepEqual(portalLogo("NASA Forecast"), { src: "/logos/nasa.png" });
  assert.deepEqual(portalLogo("DOE SBIR"), { initials: "DOE" });
  assert.deepEqual(portalLogo("Space Florida"), { initials: "SF" });
  assert.deepEqual(portalLogo("APFIT"), { initials: "AP" });
  assert.deepEqual(portalLogo("Somewhere New"), { initials: "SN" });
});

test("Top 10 keeps the brief's order and drops calls the ledger no longer has", () => {
  assert.deepEqual(topTenOrder(["c", "a", "zz", "b"], new Set(["a", "b", "c"])), ["c", "a", "b"]);
  assert.deepEqual(topTenOrder([], new Set(["a"])), []);
});
