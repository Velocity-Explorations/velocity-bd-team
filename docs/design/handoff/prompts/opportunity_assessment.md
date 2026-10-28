---
name: opportunity-assessment
description: "Pre-draft assessment for government contracting opportunities (SBIR, STTR, RFI, white papers, BAAs, pitch days and similar). Runs the Qualify stage of the dashboard's proposal workspace: Discovery, Opportunity summary, Alignment, Requirements and checklist, then the Go or no-go gate. Hands off to proposal-drafting on Go."
---

# Opportunity assessment: the Qualify stage

This prompt is the front half of Velocity Explorations' proposal pipeline. It takes a pursued call from first look to a go or no-go decision, and produces all the groundwork needed before any drafting begins. On Go it hands off to **proposal-drafting**.

The goal is to understand an opportunity, its fit to Velocity and its submission requirements before investing time in writing. Rushing to draft without this groundwork leads to weak proposals that miss requirements, or that chase opportunities that are not a good fit.

## How this runs

The dashboard's worker runs one phase at a time, as one workspace step. Each phase ends with a question for the proposal's **owner**, shown on the step's card as "Your call". The owner approves, asks for changes with a note (you redo the phase with the note), or adds material. Do not start the next phase until the step is approved. With key gates only, Phases 1 to 4 are approved automatically and only Phase 5 waits for the owner.

You are given:
- the call from the ledger: its title, portal, URL, description, deadline, type and tags;
- both judges' verdicts and reasons;
- the team's votes and notes;
- the owner's optional direction;
- the past work the owner chose to build on;
- the pursuit's Drive folder.

Save every document you produce to that folder.

---

## Phase 1: Discovery

**Goal:** Get the full picture of what this opportunity asks for.

The submission folder already exists. The worker created it when the owner chose Start the draft, using the Library convention: `Submissions/<YYYY-MM-DD_portal_short-title>/`, dated the day the draft started, with these subfolders:
- `00_solicitation/`
- `01_submitted/`
- `02_working/`
- `03_outcome/`

Work through these tasks in order, and report each one's state as you go:

1. **Re-check the call page.** Visit the URL. Confirm the call is still open and the deadline is unchanged. Note any amendments and posted questions and answers. Save the page as a PDF to `00_solicitation/`.
2. **Download every attachment** into `00_solicitation/`: BAA documents, topic description PDFs, proposal templates, forms, amendments and supplementary instructions. These often hold critical formatting requirements and evaluation criteria that are not on the main page. Starting the draft is the owner's approval to download them.
3. **Find the parent instructions** the call points to, for example the DoD SBIR/STTR Program BAA or the service-specific instructions, which hold page limits and format rules.
4. **Pull out the key facts:**
   - the topic or opportunity number, the agency and the point of contact;
   - every date, converted to the owner's time zone;
   - the phase, the funding and the period of performance;
   - eligibility and the submission portal;
   - whether an STTR needs a research institution partner;
   - when results are announced, if the call or its instructions say (for example "selections notified within 90 days of the close"). Quote the words and where you found them; the dashboard uses this as the result expected by date. If nothing says, write "not stated" and the dashboard sets 90 days after the deadline.
5. **Compare with past work.** Start from the past work the owner chose, then search past submissions for similar topics, the same agency or point of contact, wins, losses and debriefs, reusable sections, past performance and partners.
6. **Check for clashes:** an earlier submission to this topic, the same call on another portal, and other pursued calls closing near the same date.
7. **Bring in the dashboard's record:** both judges' reasons, and the team's votes and notes.
8. **Write the Discovery summary:** what was found, what is missing and why, and questions for the point of contact while asking is still allowed.

Anything behind a login that you cannot reach (for example a portal member page, or DSIP) is listed for the owner to fetch. Do not guess its contents.

**Ask the owner:** "Anything else to look at, or anything that needs a login?"

---

## Phase 2: Opportunity summary

**Goal:** Distill the opportunity into a clear summary, so the owner can quickly decide whether it is worth pursuing.

Cover:
- **Sponsoring agency or organization** and program (for example Navy SBIR Phase I, DARPA, AFWERX)
- **Topic or opportunity title and number**
- **What they are looking for:** the core technical problem or capability gap, in plain language
- **Funding details:** dollar amounts, phases, period of performance
- **Key dates:** the submission deadline with its time zone, question periods, anticipated awards
- **Why this might be interesting for Velocity:** a first-pass check on fit

Keep it tight. It is a decision aid, not a research paper; the owner should be able to read it in under two minutes and know whether to keep going. Save it as `{Code}_Opportunity_Summary.docx`.

**Ask the owner:** "Worth digging deeper?" If it is clearly not a fit, say so; the owner can stop here with Stop here, no-go, and save the effort.

---

## Phase 3: Alignment

**Goal:** Assess how well this opportunity maps to Velocity's actual capabilities, products and past performance.

This is where the opportunity meets reality. Review Velocity's reference materials and identify genuine alignment: not aspirational fit, but things Velocity has actually built, deployed or demonstrated.

**Where to look for evidence:**
- **Company documents:** capability statements, product overviews (for example Echo C2 AI), policy documents, one-pagers
- **Past submissions:** previous proposals, white papers and pitch materials that show relevant work
- **Exercise and deployment reports:** field test results and after-action reports (for example Cobra Gold) that show real-world performance
- **The past work the owner chose**, and what Discovery found

The key principle: **identify which past work is most relevant to this specific opportunity, wherever it lives.** For example:
- a hardware-focused SBIR might lean heavily on exercise reports showing physical system deployments;
- an AI-focused RFI might lean on the Echo C2 AI documentation and past AI proposals;
- a space opportunity might draw from the Hoverslam submissions.

Do not default to any single folder; let the opportunity's requirements guide which evidence you pull.

Produce an alignment assessment that maps Velocity's capabilities to the opportunity's requirements:
- **Strong alignment:** areas where Velocity has direct, demonstrable experience
- **Partial alignment:** areas where Velocity has adjacent capabilities that could extend
- **Gaps:** areas where Velocity would need to develop new capabilities or partner

Be honest about gaps. A proposal that overpromises on capabilities Velocity does not have is worse than one that acknowledges its limits and proposes a realistic path forward.

Give a one-line verdict on the fit. Then propose an **angle**: what to lead with and how to close each gap. Set it beside the owner's direction from Start the draft, if they gave one, and say where they agree and differ. Save the assessment as `{Code}_Alignment.docx`.

**Ask the owner:** "Does this match your read? Are there capabilities or past work I am missing?" The owner keeps their direction, takes your angle or writes a new one. The result is the direction for everything after.

---

## Phase 4: Requirements and submission checklist

**Goal:** A polished Word document of the requirements and the submission checklist, saved to `02_working/` as `{Code}_Requirements_and_Submission_Checklist.docx`.

This is not a conversation summary. It is a document the owner can print, share with the team and check off as the submission progresses. The dashboard turns Section 2 into the workspace's checklist.

### Document structure

**Page 1, overview table:** a header with the opportunity name and topic number, then a table of:
- Sponsoring agency and program
- Topic or opportunity number
- Funding details (amounts, phases, period of performance)
- Submission portal (URL)
- Submission deadline (exact date, time and time zone)
- Solicitation page (the direct URL to the solicitation or topic)

**Section 1, requirements outline:**
- **1.1 Proposal structure and required volumes:** a table of each required volume or document, with page limits and notes.
- **1.2 Technical volume detailed requirements:** formatting (font, margins, spacing, file format), and the required sections with what each must contain.
- **1.3 Evaluation criteria:** a table mapping each criterion to what evaluators look for, so drafting can answer each one explicitly.
- **1.4 Eligibility requirements:** a table of each requirement, Velocity's current status, and any action needed.
- **1.5 Solicitation terminology and keywords:** critical for drafting accuracy. Extract and list:
  - **Exact keywords** from the solicitation's KEYWORDS field (for example "Continuous Digital Intermediate Frequency; CDIF; Burst Digital Intermediate Frequency; BDIF"). The draft must use these exact terms; never paraphrase them or invent acronym expansions.
  - **Required function names:** the exact terms the solicitation uses for what the system must do (for example "formatting, recording, librarying, and playback"). The draft must use the same terms consistently, not substitutes.
  - **Named networking and interface types:** every technology the solicitation lists (for example "InfiniBand, NVLINK, PCIe, Ethernet"). All must appear in the draft.
  - **Named standards and references:** reference numbers mapped to their full titles (for example "Ref 7 = CSfC DAR v5.0"). The draft must cite them correctly.
  - **Specific performance thresholds:** the exact numbers from the solicitation (for example ">=8 PB", "<=4U", ">400 GB/s", ">=30 seconds"), in the solicitation's own notation.
  - **Security and compliance requirements:** certifications, clearance levels and regulations cited (for example "ITAR 22 CFR 120-130", "CMMC Level 2 (Self)", "secret level facility clearance").

  This section is the source of truth for terminology during drafting. Proposal-drafting's compliance check verifies the draft against it.

**Section 2, submission checklist:**
Use checkbox tables (☐ / ☑ format) organized into subsections, so anyone on the team can see at a glance what is done and what is still open. Give each table the columns **Item**, **Owner**, **Due**, and **Status / Notes**. The owner of an item is Claude, the proposal's owner, or another named person. Mark items that are already satisfied as ☑ (for example, a SAM.gov registration you confirmed is active in 1.4) and leave everything else ☐.

Make every item specific to this solicitation. "Technical Volume: 20 pages max, 10 pt Times New Roman, 1-inch margins, PDF" is useful; "Prepare technical volume" is not. When an item comes from a specific requirement, cite it (for example "per BAA Section 5.4") so nobody has to hunt for the source later.

Typical subsections:
- **2.1 Registrations and eligibility:** every action item from the eligibility table in 1.4, plus the standing items for this kind of submission:
  - SAM.gov registration active, with the UEI and CAGE code;
  - submission portal account working;
  - SBA Company Registry, for SBIR and STTR;
  - size and ownership certifications;
  - CMMC level and facility clearance;
  - export control registration, if the topic is ITAR-controlled.
- **2.2 Required documents and volumes:** one row per required document from 1.1, with its page limit and any mandatory template (technical volume, cost volume, commercialization report, supporting documents, certifications, letters of support, quad chart, and so on).
- **2.3 Inputs needed from the owner and the team:** items that have to come from people, such as key personnel bios and resumes, labor rates and cost inputs, letters of support, past performance points of contact and contract numbers, photos and figures from deployments, and signatures.
- **2.4 Formatting and packaging:** font, size, margins, spacing, page count, headers and footers, required markings (proprietary or distribution statements, export control notices), file format, file naming convention, and file size limits.
- **2.5 Reviews and approvals:** the review gates proposal-drafting will run (solicitation compliance check, evaluator reviews, leadership review, finalization checks), plus the owner's final sign-off at the Submit gate.
- **2.6 Submission:** portal login tested, upload slots and order confirmed, final files uploaded, and the confirmation receipt saved to `01_submitted/`. Set an internal submit-by date at least one business day before the deadline. Portals slow down and fail near the cutoff, and a late submission is almost always rejected outright.

Adapt the subsections to the opportunity. An RFI response might need only 2.2, 2.4 and 2.6; a full SBIR Phase I proposal needs all six. The dashboard turns these tables into the workspace's checklist.

**Section 3, timeline, questions and source documents:**
- **3.1 Key dates and internal milestones:** a table with the official dates (Q&A window, any industry day or pre-proposal conference, the submission deadline with its time and time zone, the anticipated award date). Follow it with internal milestones worked backward from the internal submit-by date: outline approved, first draft complete, compliance check done, review cycles done, final package ready. If the time remaining cannot fit the work, say so here rather than discovering it mid-draft. The dashboard uses these milestones as the steps' target dates.
- **3.2 Questions for the government:** ambiguities in the solicitation worth raising during the Q&A window. Write each as the question you would actually submit, with the Q&A deadline and the channel to use. Respect the solicitation's communication rules. For DoD SBIR and STTR, for example, direct contact with topic authors is allowed only during the pre-release period; after that, questions go through the topic Q&A system.
- **3.3 Source documents:** every solicitation document saved in `00_solicitation/`, with its filename, what it is, and its version or amendment date. Amendments can change page limits, dates or requirements, so check the solicitation page for new ones again before submission.

### Finishing the document

Build the document as a Word file, so the tables, checkboxes and headings come out clean and printable. Before saving it, re-check Section 1.5 against the solicitation one more time, because everything downstream treats it as the source of truth. Then apply Velocity's writing standards: tables over prose, no filler, and no em dashes or en dashes anywhere in the file.

**Ask the owner:** "The requirements and submission checklist is saved as {Code}_Requirements_and_Submission_Checklist.docx. The items that need your input are in 2.3, and any open eligibility actions are in 1.4. Anything to add or correct before we make the go or no-go call?"

---

## Phase 5: Go or no-go decision

**Goal:** Make an explicit decision about whether to pursue this opportunity, based on everything gathered so far.

The summary, the alignment assessment and the requirements document now give a complete picture. Bring them together into a short decision brief:

- **Fit rating:** Strong fit, Moderate fit, Stretch fit or Poor fit, with a two- or three-sentence justification drawn from the alignment assessment.
- **Win themes:** the two or three strengths that would make this proposal stand out to these evaluators, each tied to real Velocity evidence.
- **Critical gaps:** the gaps that could sink the proposal, each with a mitigation (adjacent experience, a teaming partner, a credible plan to build the capability, or a reframing of existing work). Call out anything disqualifying, such as an eligibility requirement Velocity cannot meet before the deadline.
- **Effort and timing:** the days remaining against the milestones in Section 3.1, and any conflict with other proposals or commitments.
- **Recommendation:** Go, Go with conditions (name them), or No-go, with your reasoning.

Give a real recommendation, including No-go when the evidence points there. A clear "this is a stretch, and here is why" is worth more to the owner than optimism, and passing on a weak fit frees time for a strong one. The decision itself is the owner's. Save the brief to `02_working/` as `{Code}_Go_No-Go_Brief.docx`.

**Ask the owner:** "Here is the decision brief and my recommendation. Do we go, go with conditions, or pass?"
- **Go:** continue to Phase 6.
- **Go with conditions:** each condition becomes an item in the submission checklist, with its owner and due date, then continue to Phase 6.
- **No-go:** the owner writes the reason. Save a short decision note to the folder as `{Code}_No-Go_Decision.docx` with the date, the reasons, and anything that would change the answer (a teaming partner, a better-matched future topic). The dashboard marks the call Not relevant with the reason as its note, and the worker moves the folder to `Submissions/_no-go/`. These notes make the next assessment of a similar topic faster.

---

## Phase 6: Handoff to proposal-drafting

**Goal:** Leave everything proposal-drafting needs in the submission folder, so drafting can start straight away without losing context.

1. **Save the assessment.** Write the opportunity summary, the alignment assessment and the go or no-go brief into `02_working/` as `{Code}_Assessment_Summary.docx`, so the whole case for pursuing it is in one file.
2. **Confirm the prerequisites.** Proposal-drafting expects four things: the submission folder, the requirements and submission checklist document, the opportunity summary, and the alignment assessment. Confirm all four exist and are current.
3. **List the open items.** Note anything still pending that drafting depends on (bios, cost inputs, answers to Q&A questions), each as a checklist item with its owner, so it is visible from the first day of drafting.
4. **Hand off.** Proposal-drafting starts at its outline, with the direction the owner confirmed in Phase 3. No question is asked here; the Go decision is the handoff.
