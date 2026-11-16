import assert from "node:assert/strict";
import { test } from "node:test";
import { isWatch, listingBadge, listingChoice, readListingChoice, topTab } from "./listing.ts";

test("umbrellas and announcements are the listings to watch; a call or no kind yet is not", () => {
  assert.equal(isWatch("Umbrella"), true);
  assert.equal(isWatch("Announcement"), true);
  assert.equal(isWatch("Call"), false);
  assert.equal(isWatch(null), false);
  assert.equal(isWatch("Something else"), false);
});

test("a row shows a badge only when it is not a plain call", () => {
  assert.equal(listingBadge("Call"), null);
  assert.equal(listingBadge(null), null);
  assert.equal(listingBadge(undefined), null);
  const umbrella = listingBadge("Umbrella");
  assert.equal(umbrella?.text, "umbrella");
  assert.match(umbrella?.title ?? "", /calls come under it/);
  assert.equal(listingBadge("Announcement")?.text, "announcement");
  assert.match(listingBadge("Announcement")?.title ?? "", /nothing to submit yet/i);
});

test("Home opens the calls tab unless the link asks for the watch list", () => {
  assert.equal(topTab(undefined), "calls");
  assert.equal(topTab(""), "calls");
  assert.equal(topTab("watch"), "watch");
  assert.equal(topTab(["watch", "calls"]), "watch");
  assert.equal(topTab("nonsense"), "calls");
});

test("a person tags a listing from the Decide menu: Umbrella announcement only, or back to a call (David, 16 Nov 2026)", () => {
  assert.deepEqual(listingChoice(null), { value: "listing:Umbrella", label: "Umbrella announcement only" });
  assert.deepEqual(listingChoice("Call"), { value: "listing:Umbrella", label: "Umbrella announcement only" });
  assert.deepEqual(listingChoice("Umbrella"), { value: "listing:Call", label: "This is a call" });
  assert.deepEqual(listingChoice("Announcement"), { value: "listing:Call", label: "This is a call" });
  assert.equal(readListingChoice("listing:Umbrella"), "Umbrella");
  assert.equal(readListingChoice("listing:Call"), "Call");
  assert.equal(readListingChoice("listing:Announcement"), null);   // the menu offers only these two
  assert.equal(readListingChoice("pursue"), null);
  assert.equal(readListingChoice(null), null);
});
