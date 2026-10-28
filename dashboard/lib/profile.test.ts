import { test } from "node:test";
import assert from "node:assert/strict";
import { callsHref, isFreshArrival, isValidTimeZone, parseDefaultFilters, profileFromForm, sameOrigin, withDefaultFilters } from "./profile.ts";

const KNOWN = { portals: ["NSTXL", "SAM.gov", "Vulcan SOF"], tags: ["Software", "Space"] };

test("default filters read defensively from their JSON, unknown values dropped", () => {
  assert.deepEqual(parseDefaultFilters(JSON.stringify({ portals: ["NSTXL", 3, "SAM.gov"], tag: "Space", state: "open" })),
    { portals: ["NSTXL", "SAM.gov"], tag: "Space", state: "open" });
  assert.deepEqual(parseDefaultFilters(JSON.stringify({ state: "sideways" })), { portals: [], tag: "", state: "" });
  assert.deepEqual(parseDefaultFilters("{oops"), { portals: [], tag: "", state: "" });
  assert.deepEqual(parseDefaultFilters(null), { portals: [], tag: "", state: "" });
});

test("Calls opens with the default filters, and plain when there are none (U4)", () => {
  assert.equal(callsHref({ portals: ["NSTXL", "SAM.gov"], tag: "Space", state: "open" }), "/review?portal=NSTXL&portal=SAM.gov&tag=Space&state=open");
  assert.equal(callsHref({ portals: [], tag: "", state: "" }), "/review");
  assert.equal(callsHref(null), "/review");
});

test("the form is read and checked: names trimmed, initials letters only, filters among the known ones", () => {
  const form = new Map<string, string[]>([
    ["display_name", ["  Dave W  "]],
    ["initials", ["d.w9x"]],
    ["opens", ["calls"]],
    ["portal", ["NSTXL", "Nowhere"]],
    ["tag", ["Space"]],
    ["state", ["closed"]],
    ["time_zone", ["America/New_York"]],
  ]);
  assert.deepEqual(profileFromForm(form, "David Wood", KNOWN), {
    display_name: "Dave W",
    initials: "DWX",
    opens: "calls",
    default_filters: { portals: ["NSTXL"], tag: "Space", state: "closed" },
    time_zone: "America/New_York",
  });
});

test("what equals the default is stored as no setting", () => {
  const form = new Map<string, string[]>([
    ["display_name", ["David Wood"]],
    ["initials", [""]],
    ["opens", ["somewhere"]],
    ["tag", ["Not a tag"]],
    ["time_zone", ["Mars/Olympus_Mons"]],
  ]);
  assert.deepEqual(profileFromForm(form, "David Wood", KNOWN), {
    display_name: null,
    initials: null,
    opens: "home",
    default_filters: null,
    time_zone: null,
  });
  assert.equal(profileFromForm(new Map([["display_name", ["x".repeat(80)]]]), "David Wood", KNOWN).display_name, "x".repeat(60));
});

test("a time zone is one the runtime knows", () => {
  assert.equal(isValidTimeZone("America/Denver"), true);
  assert.equal(isValidTimeZone("Mars/Olympus_Mons"), false);
  assert.equal(isValidTimeZone(""), false);
});

test("opening the dashboard fresh is any arrival not from one of its own pages (U3)", () => {
  assert.equal(sameOrigin("http://localhost:8000/calls", "localhost:8000"), true);
  assert.equal(sameOrigin("https://slack.com/archives/x", "localhost:8000"), false);
  assert.equal(sameOrigin("not a url", "localhost:8000"), false);
  assert.equal(isFreshArrival(null, "localhost:8000"), true);
  assert.equal(isFreshArrival("http://localhost:8000/review", "localhost:8000"), false);
  assert.equal(isFreshArrival("https://mail.google.com/", "localhost:8000"), true);
});

test("Calls opened fresh with no bar filters in its address takes the defaults; a link's own filters win (U4)", () => {
  const defaults = { portals: ["NSTXL"], tag: "", state: "open" as const };
  assert.equal(withDefaultFilters("/review", { view: "due-soon" }, defaults), "/review?view=due-soon&portal=NSTXL&state=open");
  assert.equal(withDefaultFilters("/calls", {}, defaults), "/calls?portal=NSTXL&state=open");
  assert.equal(withDefaultFilters("/review", { portal: "SAM.gov" }, defaults), null);
  assert.equal(withDefaultFilters("/review", { state: "" }, defaults), null);
  assert.equal(withDefaultFilters("/review", {}, null), null);
  assert.equal(withDefaultFilters("/review", {}, { portals: [], tag: "", state: "" }), null);
});
