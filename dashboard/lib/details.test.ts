import { test } from "node:test";
import assert from "node:assert/strict";
import { callDetails, deadlineNote } from "./details.ts";

const SAM = {
  portal: "SAM.gov",
  type: "Solicitation",
  department: "DEPT OF DEFENSE / DEPT OF THE ARMY / AMC / ACC / ACC-APG",
  naics_code: "541715",
  set_aside: "Total Small Business Set-Aside (FAR 19.5)",
  extra: JSON.stringify({
    samgov_solicitation_number: "W911-26-R-0001",
    samgov_contacts: [{ name: "Pat Example", email: "pat.example@army.mil", phone: "5550100", role: "primary" }],
    samgov_attachments: ["https://sam.gov/a", "https://sam.gov/b"],
    samgov_closed: false,
  }),
};

test("a SAM.gov call shows its type, office, set-aside, NAICS, solicitation number, contact and attachments", () => {
  assert.deepEqual(callDetails(SAM), [
    { text: "Solicitation" },
    { text: "DEPT OF THE ARMY", title: "DEPT OF DEFENSE / DEPT OF THE ARMY / AMC / ACC / ACC-APG" },
    { text: "Total Small Business Set-Aside (FAR 19.5)" },
    { text: "NAICS 541715" },
    { text: "W911-26-R-0001" },
    { text: "Pat Example", href: "mailto:pat.example@army.mil", title: "pat.example@army.mil, 5550100" },
    { text: "2 attachments" },
  ]);
});

test("an NSTXL member-only call carries a warn badge", () => {
  const row = {
    portal: "NSTXL", type: "OTA opportunity", department: "SpEC", naics_code: "", set_aside: "",
    extra: JSON.stringify({ nstxl_members_only: true, nstxl_no_deadline: true, nstxl_consortium: "SpEC" }),
  };
  assert.deepEqual(callDetails(row), [
    { text: "OTA opportunity" },
    { text: "SpEC" },
    { text: "members only", tone: "warn", title: "Member-only page on NSTXL: sign in as a member to read it." },
  ]);
});

test("a Front Door repost links to the SAM.gov notice", () => {
  const row = {
    portal: "SSC Front Door", type: "RFI", department: "Space Systems Command", naics_code: null, set_aside: null,
    extra: JSON.stringify({ sscfd_location: "Los Angeles, CA", sscfd_sam_url: "https://sam.gov/opp/abc/view", sscfd_closed: false }),
  };
  assert.deepEqual(callDetails(row), [
    { text: "RFI" },
    { text: "Space Systems Command" },
    { text: "Los Angeles, CA" },
    { text: "also on SAM.gov", href: "https://sam.gov/opp/abc/view" },
  ]);
});

test("without extra, or with extra that cannot be read, only the columns show", () => {
  const plain = { portal: "Vulcan SOF", type: "CSO", department: "USSOCOM", naics_code: null, set_aside: null, extra: null };
  assert.deepEqual(callDetails(plain), [{ text: "CSO" }, { text: "USSOCOM" }]);
  assert.deepEqual(callDetails({ ...plain, extra: "{not json" }), [{ text: "CSO" }, { text: "USSOCOM" }]);
  assert.deepEqual(callDetails({ portal: "NSTXL", type: null, department: "NSTXL", naics_code: null, set_aside: null, extra: null }), []);
});

test("the due date's hover text says where the deadline came from", () => {
  assert.equal(deadlineNote(JSON.stringify({ nstxl_deadline_text: "The deadline is now 26 October at 11:00 AM PT." })),
    "From the page: The deadline is now 26 October at 11:00 AM PT.");
  assert.equal(deadlineNote(JSON.stringify({ nstxl_no_deadline: true })), "No deadline in the page text; see its documents.");
  assert.equal(deadlineNote(JSON.stringify({ nstxl_no_deadline: true, nstxl_members_only: true })),
    "Member-only page: sign in to NSTXL to see the deadline.");
  assert.equal(deadlineNote(JSON.stringify({ diu_close: "2026-10-28 23:59:59 US/Eastern Time" })), "DIU: 2026-10-28 23:59:59 US/Eastern Time");
  assert.equal(deadlineNote(JSON.stringify({ vulcan_closed: false })), null);
  assert.equal(deadlineNote(null), null);
  assert.equal(deadlineNote("{oops"), null);
});
