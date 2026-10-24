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

const NOW = new Date("2026-10-24T12:00:00Z");
const CYCLE = {
  portal: "AFWERX", type: "SBIR cycle", department: "Department of the Air Force", naics_code: "", set_aside: "",
  extra: JSON.stringify({ afwerx_branches: ["Air Force", "Space Force"], afwerx_pre_release: "2026-10-07",
                          afwerx_open: "2026-10-28", afwerx_no_deadline: false, afwerx_closed: false }),
};

test("an AFWERX cycle in pre-release shows its services and when it opens", () => {
  assert.deepEqual(callDetails(CYCLE, NOW), [
    { text: "SBIR cycle" },
    { text: "Department of the Air Force" },
    { text: "Air Force", tone: "info", title: "Includes U.S. Air Force topics" },
    { text: "Space Force", tone: "info", title: "Includes U.S. Space Force topics" },
    { text: "opens 28 Oct", tone: "warn", title: "Pre-release from 7 Oct; submissions open 28 Oct" },
  ]);
  const openDay = new Date("2026-10-28T12:00:00Z");
  assert.equal(callDetails(CYCLE, openDay).some((d) => d.text.startsWith("opens")), false);   // open from that day
  const nextYear = { ...CYCLE, extra: JSON.stringify({ afwerx_branches: ["Air Force"], afwerx_open: "2027-01-05" }) };
  assert.deepEqual(callDetails(nextYear, NOW).slice(2), [
    { text: "Air Force", tone: "info", title: "Includes U.S. Air Force topics" },
    { text: "opens 5 Jan 2027", tone: "warn" },
  ]);
});

test("a SpaceWERX listing already open shows no open date, and one with no close date says so on hover", () => {
  const row = {
    portal: "SpaceWERX", type: "TACFI", department: "U.S. Space Force", naics_code: "", set_aside: "",
    extra: JSON.stringify({ spacewerx_branches: [], spacewerx_pre_release: null, spacewerx_open: "2026-06-05",
                            spacewerx_no_deadline: true, spacewerx_closed: false }),
  };
  assert.deepEqual(callDetails(row, NOW), [{ text: "TACFI" }, { text: "U.S. Space Force" }]);
  assert.equal(deadlineNote(row.extra), "No close date on the Get Funded page (TBD, or submissions on a continuous basis).");
  assert.equal(deadlineNote(CYCLE.extra), null);
});

test("a NASA forecast row shows the expected solicitation quarter, the value and the first contact", () => {
  const row = {
    portal: "NASA Forecast", type: "Forecast", department: "NASA MSFC", naics_code: "541512",
    set_aside: "Small Business Set Aside - Total",
    extra: JSON.stringify({ nasa_solicitation_expected: "Q3 FY2026", nasa_award_expected: "Q2 FY2027",
                            nasa_estimated_value: "$5M - $10M", nasa_no_deadline: true, nasa_closed: false,
                            nasa_contacts: [{ name: "Example, Pat", email: "pat.example@nasa.gov", role: "technical" }] }),
  };
  assert.deepEqual(callDetails(row, NOW), [
    { text: "Forecast" },
    { text: "NASA MSFC" },
    { text: "Small Business Set Aside - Total" },
    { text: "NAICS 541512" },
    { text: "solicitation Q3 FY2026", title: "Award expected Q2 FY2027" },
    { text: "$5M - $10M", title: "Estimated contract value" },
    { text: "Example, Pat", href: "mailto:pat.example@nasa.gov", title: "pat.example@nasa.gov" },
  ]);
  assert.equal(deadlineNote(row.extra), "A forecast: NASA expects to release the solicitation in Q3 FY2026.");
  assert.equal(deadlineNote(JSON.stringify({ nasa_no_deadline: true })), "A forecast: no solicitation yet.");
});

test("DOE's upcoming badge, and the words its deadline was read from", () => {
  const row = {
    portal: "DOE SBIR", type: "SBIR/STTR Phase I", department: "DOE Office of Technology Commercialization",
    naics_code: "", set_aside: "",
    extra: JSON.stringify({ doe_status: "Upcoming", doe_deadline_text: "Submission Deadline: TBD", doe_no_deadline: true }),
  };
  assert.deepEqual(callDetails(row, NOW), [
    { text: "SBIR/STTR Phase I" },
    { text: "DOE Office of Technology Commercialization" },
    { text: "upcoming", tone: "warn", title: "DOE lists this solicitation as upcoming: it is not open yet." },
  ]);
  assert.equal(deadlineNote(row.extra), "From the page: Submission Deadline: TBD");
  const active = { ...row, extra: JSON.stringify({ doe_status: "Active", doe_deadline_text: "Submission Deadline: December 3, 2026 at 5 PM ET" }) };
  assert.equal(callDetails(active, NOW).length, 2);
  assert.equal(deadlineNote(active.extra), "From the page: Submission Deadline: December 3, 2026 at 5 PM ET");
});

test("Space Florida's documents, linked to the first, and its intent-to-award badge", () => {
  const links = [{ name: "RFP-SF-02-0-2026 Space Based Data Pilot Program", url: "https://cdn.example/rfp.pdf" },
                 { name: "RFP-SF-02-0-2026 Notice of Intent to Award", url: "https://cdn.example/nia.docx" }];
  const row = {
    portal: "Space Florida", type: "RFP", department: "Space Florida", naics_code: "", set_aside: "",
    extra: JSON.stringify({ spacefl_documents: links.map((d) => d.name), spacefl_document_links: links,
                            spacefl_intent_to_award: true, spacefl_closed: true }),
  };
  assert.deepEqual(callDetails(row, NOW), [
    { text: "RFP" },
    { text: "2 documents", href: "https://cdn.example/rfp.pdf",
      title: "RFP-SF-02-0-2026 Space Based Data Pilot Program; RFP-SF-02-0-2026 Notice of Intent to Award" },
    { text: "intent to award", tone: "warn", title: "Space Florida has posted a notice of intent to award." },
  ]);
  const one = { ...row, extra: JSON.stringify({ spacefl_document_links: links.slice(0, 1) }) };
  assert.equal(callDetails(one, NOW)[1].text, "1 document");
});

test("an APFIT cycle's due date says each organization sets its own deadline", () => {
  assert.equal(deadlineNote(JSON.stringify({ apfit_cycle: "FY27-2", apfit_no_deadline: true })),
    "No deadline here: each participating organization sets its own.");
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
