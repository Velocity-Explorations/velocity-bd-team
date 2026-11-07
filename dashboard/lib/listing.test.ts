import assert from "node:assert/strict";
import { test } from "node:test";
import { isWatch, listingBadge, topTab } from "./listing.ts";

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
