import assert from "node:assert/strict";
import { test } from "node:test";
import { buildFitRows, isRating, sectionOfKey, sectorOf, slug, type EvidenceCall, type RatingRow } from "./fitratings.ts";

function rated(key: string, section: string, name: string, rating: string, extra: Partial<RatingRow> = {}): RatingRow {
  return { key, section, name, rating, note: null, loaded_at: "2026-11-06T12:00:00Z", changed_by: null, ...extra };
}

function call(id: string, fields: Partial<EvidenceCall> = {}): EvidenceCall {
  return { id, title: `Title ${id}`, url: `https://example.mil/${id}`, type: null, naics_code: null, matched_keywords: "[]", human_status: null, ...fields };
}

const TAGS = [
  { name: "Software", tag_group: "work", covers: "building software" },
  { name: "AI and ML", tag_group: "work", covers: "models" },
  { name: "USSF", tag_group: "customer", covers: "the Space Force" },
  { name: "OTA", tag_group: "type", covers: "prototypes" },
  { name: "Members only", tag_group: "access", covers: "members" },
];

test("names key the same way as review/fit.py", () => {
  assert.equal(slug("AI and ML"), "ai-and-ml");
  assert.equal(slug("SBIR or STTR"), "sbir-or-sttr");
  assert.equal(slug("31-33 Manufacturing"), "31-33-manufacturing");
  assert.equal(sectorOf("236220"), "23");
  assert.equal(sectorOf("325120"), "31-33");
  assert.equal(sectorOf("481212"), "48-49");
});

test("a rating's key must be well formed and says its section", () => {
  assert.equal(sectionOfKey("work.ai-and-ml"), "work");
  assert.equal(sectionOfKey("naics.541511"), "naics");
  assert.equal(sectionOfKey("naics-sector.31-33"), "naics");
  assert.equal(sectionOfKey("notice.special-notice"), "type");
  assert.equal(sectionOfKey("keyword.c2"), "keyword");
  assert.equal(sectionOfKey("people.david"), null);
  assert.equal(sectionOfKey("work.Bad Key"), null);
  assert.equal(isRating("core"), true);
  assert.equal(isRating("great"), false);
});

test("each row counts its calls, both judges' newest verdicts, the team's decisions and the main work", () => {
  const rows = buildFitRows({
    ratings: [rated("work.software", "work", "Software", "core", { note: "yes please", changed_by: "David" })],
    tags: TAGS,
    calls: [call("a", { human_status: "pursue" }), call("b"), call("c", { human_status: "not_relevant" })],
    callTags: [{ call_id: "a", tag: "Software" }, { call_id: "a", tag: "Software" }, { call_id: "b", tag: "Software" }, { call_id: "c", tag: "Software" }],
    judges: [
      { call_id: "a", judge: "claude", verdict: "no", main_work: null },
      { call_id: "a", judge: "claude", verdict: "yes", main_work: "Software" },   // newer, so it stands
      { call_id: "a", judge: "grok", verdict: "maybe", main_work: "AI and ML" },
      { call_id: "b", judge: "claude", verdict: "no", main_work: "Software" },
      { call_id: "c", judge: "claude", verdict: "yes", main_work: "AI and ML" },
    ],
  });
  const software = rows.find((r) => r.key === "work.software");
  assert.ok(software);
  assert.equal(software.calls, 3);
  assert.deepEqual(software.claude, [2, 0, 1]);
  assert.deepEqual(software.grok, [0, 1, 0]);
  assert.equal(software.mainWork, 2);
  assert.deepEqual(new Map(software.team), new Map([["pursue", 1], ["not_relevant", 1]]));
  assert.equal(software.rating, "core");
  assert.equal(software.note, "yes please");
  assert.equal(software.changedBy, "David");
  assert.equal(software.examples[0].id, "a");   // what the team pursued comes first
  assert.equal(rows.find((r) => r.key === "work.ai-and-ml")?.mainWork, 2);
});

test("anything the ledger holds that nobody rated shows up to be rated, first in its section", () => {
  const rows = buildFitRows({
    ratings: [rated("work.software", "work", "Software", "core"), rated("keyword.data", "keyword", "data", "good"), rated("naics.541511", "naics", "541511", "good")],
    tags: TAGS,
    calls: [
      call("a", { matched_keywords: '["data","jadc2"]', naics_code: "541511" }),
      call("b", { matched_keywords: '["data"]', naics_code: "541512" }),
      call("c", { matched_keywords: "not json", naics_code: "236220" }),
      call("d", { naics_code: "325120" }),
    ],
    callTags: [],
    judges: [],
  });
  const keys = (section: string) => rows.filter((r) => r.section === section).map((r) => r.key);
  assert.deepEqual(keys("work"), ["work.ai-and-ml", "work.software"]);
  assert.deepEqual(keys("keyword"), ["keyword.jadc2", "keyword.data"]);
  assert.deepEqual(keys("naics").slice(0, 3), ["naics.541512", "naics-sector.23", "naics-sector.31-33"]);
  assert.equal(rows.find((r) => r.key === "keyword.jadc2")?.rating, null);
  assert.equal(rows.find((r) => r.key === "naics.541512")?.covers, "Computer systems design services");
  const sector = rows.find((r) => r.key === "naics-sector.23");
  assert.equal(sector?.name, "23 Construction");
  assert.deepEqual(sector?.codes, [{ code: "236220", title: "Commercial and institutional building construction", calls: 1 }]);
});

test("a code with its own rating leaves its sector's list, and a rated row with no calls stays", () => {
  const rows = buildFitRows({
    ratings: [rated("naics.236220", "naics", "236220", "poor"), rated("naics-sector.23", "naics", "23 Construction", "never"), rated("keyword.sbir", "keyword", "sbir", "core")],
    tags: [],
    calls: [call("a", { naics_code: "236220" }), call("b", { naics_code: "238160" })],
    callTags: [],
    judges: [],
  });
  const code = rows.find((r) => r.key === "naics.236220");
  const sector = rows.find((r) => r.key === "naics-sector.23");
  assert.equal(code?.calls, 1);
  assert.equal(sector?.calls, 1);
  assert.deepEqual(sector?.codes.map((c) => c.code), ["238160"]);
  assert.equal(rows.find((r) => r.key === "keyword.sbir")?.calls, 0);
});

test("the portal's notice types sit under Type where they have a rating", () => {
  const rows = buildFitRows({
    ratings: [rated("notice.special-notice", "type", "Special notice", "neutral"), rated("type.ota", "type", "OTA", "core")],
    tags: TAGS,
    calls: [call("a", { type: "Special notice" }), call("b", { type: "Solicitation" })],
    callTags: [],
    judges: [],
  });
  const notice = rows.find((r) => r.key === "notice.special-notice");
  assert.equal(notice?.kind, "notice");
  assert.equal(notice?.section, "type");
  assert.equal(notice?.calls, 1);
  assert.equal(rows.filter((r) => r.key.startsWith("notice.")).length, 1);
});

test("a rating that isn't on the scale reads as no rating", () => {
  const rows = buildFitRows({ ratings: [rated("work.software", "work", "Software", "great")], tags: TAGS, calls: [], callTags: [], judges: [] });
  assert.equal(rows.find((r) => r.key === "work.software")?.rating, null);
});
