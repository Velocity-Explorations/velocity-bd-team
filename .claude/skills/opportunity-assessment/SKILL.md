---
name: opportunity-assessment
description: "Pre-draft assessment workflow for government contracting opportunities (SBIR, RFI, white papers, BAAs, pitch days, etc.). Use this skill whenever David brings up a new opportunity, solicitation, topic, or RFI to evaluate, even if he doesn't explicitly say 'assess' or 'evaluate.' Trigger on phrases like 'new opportunity,' 'check this out,' 'saw this solicitation,' 'should we go after this,' any SBIR/STTR topic number, any solicitation URL (e.g., DSIP, SAM.gov, SBIR.gov), or when he shares a PDF/document that looks like a government solicitation. This skill handles everything BEFORE drafting begins and hands off to the 'proposal-drafting' skill when ready."
---

# Opportunity Assessment: Pre-Draft Workflow

This skill is the front half of Velocity Explorations' proposal pipeline. It takes a new government contracting opportunity from first look through a go/no-go decision, producing all the groundwork needed before any drafting begins. When complete, it hands off to the **proposal-drafting** skill.

The goal is to make sure we fully understand an opportunity, its fit to Velocity, and its submission requirements before investing time in writing. Rushing to draft without this groundwork leads to weak proposals that miss requirements or chase opportunities that aren't a good fit.

## How This Skill Works

This is a **step-by-step playbook**. Work through each phase in order, pausing at the end of each phase to check in with David before advancing. Use the TodoList to track progress through the phases. Don't skip ahead; each phase builds on the previous one.

---

## Phase 1: Discovery & Folder Setup

**Goal:** Get the full picture of what this opportunity is asking for, and create the submission folder.

When David brings an opportunity, he may provide a URL, a PDF, a document, or just a topic number. Whatever the starting point:

1. **Create the submission folder.** As soon as you have the topic/opportunity number and a short title, create a dedicated folder for this submission inside the workspace's **"Submissions"** directory (this is the active/in-progress working folder). Use the naming convention: `{TopicNumber}_{ShortTitle}` (e.g., `DON26BZ01-NV022_Wideband_Digital_Recorder` or `DARPA-PA-25-01_Edge_AI_Mesh`). All documents produced for this submission (requirements docs, drafts, checklists, supporting materials) go in this folder. This keeps each opportunity self-contained and organized. Once a submission is finalized and sent (or a decision is made to pass), the folder gets moved to "Past Submissions" for archival.

2. **Obtain the solicitation.** If David provides a URL, visit it and read the full solicitation/topic description. If he provides a document, read it thoroughly. If he provides just a topic number or name, search for the solicitation online.

3. **Download and review attachments.** Many solicitations have separate BAA documents, topic description PDFs, proposal templates, or supplementary instructions. Identify and download these (with David's permission) into the submission folder. These often contain critical formatting requirements and evaluation criteria that aren't on the main page.

4. **Read everything.** Read the full solicitation, all attachments, and any referenced instructions (e.g., DoD SBIR/STTR Program BAA, service-specific instructions). Pay close attention to evaluation criteria; these are the rubric the proposal will be scored against.

**Check in with David:** "I've created the submission folder at Submissions/{folder_name} and gathered the solicitation materials. Is there anything else related to this opportunity I should look at?"

---

## Phase 2: Opportunity Summary

**Goal:** Distill the opportunity into a clear summary so David can quickly assess whether it's worth pursuing.

Create a concise summary that covers:

- **Sponsoring agency/organization** and program (e.g., Navy SBIR Phase I, DARPA, AFWERX)
- **Topic/opportunity title and number**
- **What they're looking for**: the core technical problem or capability gap, in plain language
- **Funding details**: dollar amounts, phases, period of performance
- **Key dates**: submission deadline (with timezone), Q&A periods, anticipated awards
- **Why this might be interesting for Velocity**: a first-pass gut check on fit

Keep this summary tight; it's a decision aid, not a research paper. David should be able to read it in under 2 minutes and know whether to keep going.

**Check in with David:** Present the summary and ask if this looks like something worth digging deeper on. If it's clearly not a fit, we stop here and save the effort.

---

## Phase 3: Alignment Assessment

**Goal:** Assess how well this opportunity maps to Velocity's actual capabilities, products, and past performance.

This is where the opportunity meets reality. Review Velocity's reference materials to identify genuine alignment: not aspirational fit, but things Velocity has actually built, deployed, or demonstrated.

**Where to look for evidence of alignment:**
- **Company Documents**: Capability statements, product overviews (e.g., Echo C2 AI), policy documents, one-pagers
- **Past Submissions**: Previous proposals, white papers, pitch materials that show relevant work
- **Exercise/Deployment Reports**: Field test results, after-action reports (e.g., Cobra Gold) that demonstrate real-world performance

The key principle: **identify which past work is most relevant to THIS specific opportunity, wherever it lives.** A hardware-focused SBIR might lean heavily on exercise reports showing physical system deployments. An AI-focused RFI might lean on Echo C2 AI documentation and past AI proposals. A space opportunity might draw from Hoverslam submissions. Don't default to any single folder; let the opportunity's requirements guide which evidence you pull.

Produce an alignment assessment that maps Velocity's capabilities to the opportunity's requirements, noting:
- **Strong alignment**: areas where Velocity has direct, demonstrable experience
- **Partial alignment**: areas where Velocity has adjacent capabilities that could extend
- **Gaps**: areas where Velocity would need to develop new capabilities or partner

Be honest about gaps. A proposal that overpromises on capabilities Velocity doesn't have is worse than one that acknowledges limitations and proposes a realistic path forward.

**Check in with David:** "Here's how I see the alignment. Does this match your read? Are there capabilities or past work I'm missing?"

---

## Phase 4: Requirements & Submission Checklist Document

**Goal:** Create a polished `.docx` requirements and submission checklist document and save it to the submission folder.

This is not just a conversation summary; produce an actual Word document (using the `docx` skill) that David can print, share with the team, and check off as the submission progresses. Save it to the submission folder created in Phase 1, named `{TopicNumber}_Requirements_and_Submission_Checklist.docx`.

### Document Structure

The document should follow this structure (modeled on the NV022 checklist template):

**Page 1: Overview Table**
A professional header/title block with the opportunity name and topic number, followed by a summary table with key fields:
- Sponsoring Agency / Program
- Topic/Opportunity Number
- Funding details (amounts, phases, period of performance)
- Submission Portal (URL)
- Submission Deadline (exact date, time, timezone)
- Solicitation Page (direct URL to the solicitation/topic)

**Section 1: Requirements Outline**
- **1.1 Proposal Structure & Required Volumes**: table listing each required volume/document with page limits and notes
- **1.2 Technical Volume Detailed Requirements**: formatting specs (font, margins, spacing, file format) and required sections with descriptions of what each must contain
- **1.3 Evaluation Criteria**: table mapping each criterion to what evaluators look for, so the drafting phase can address them explicitly
- **1.4 Eligibility Requirements**: table with each requirement, Velocity's current status, and any action needed
- **1.5 Solicitation Terminology & Keywords**: this section is critical for drafting accuracy. Extract and list:
  - **Exact keywords** from the solicitation's KEYWORDS field (e.g., "Continuous Digital Intermediate Frequency; CDIF; Burst Digital Intermediate Frequency; BDIF"). The draft must use these exact terms; never paraphrase or invent acronym expansions.
  - **Required function names**: the exact terms the solicitation uses for what the system must do (e.g., "formatting, recording, librarying, and playback"). The draft must use these same terms consistently, not substitutes.
  - **Named networking/interface types**: any specific technologies the solicitation lists (e.g., "InfiniBand, NVLINK, PCIe, Ethernet"). All must appear in the draft.
  - **Named standards and references**: reference numbers mapped to their full titles (e.g., "Ref 7 = CSfC DAR v5.0"). The draft must cite these correctly.
  - **Specific performance thresholds**: the exact numbers from the solicitation (e.g., ">=8 PB," "<=4U," ">400 GB/s," ">=30 seconds"). Use the solicitation's exact notation.
  - **Security/compliance requirements**: specific certifications, clearance levels, regulations cited (e.g., "ITAR 22 CFR 120-130," "CMMC Level 2 (Self)," "secret level facility clearance").
  
  This section serves as the "source of truth" for terminology during drafting. When the proposal-drafting skill runs its solicitation compliance check, it will verify the draft against this list.

**Section 2: Submission Checklist**
Use checkbox tables (☐ / ☑ format) organized into subsections, so anyone on the team can see at a glance what is done and what is still open. Give each table the columns **Item**, **Owner**, **Due**, and **Status / Notes**. Mark items that are already satisfied as ☑ (for example, a SAM.gov registration you confirmed is active in 1.4) and leave everything else ☐.

Make every item specific to this solicitation. "Technical Volume: 20 pages max, 10 pt Times New Roman, 1-inch margins, PDF" is useful; "Prepare technical volume" is not. When an item comes from a specific requirement, cite it (e.g., "per BAA Section 5.4") so nobody has to hunt for the source later.

Typical subsections:
- **2.1 Registrations & Eligibility**: every action item from the eligibility table in 1.4, plus the standing items for this kind of submission (SAM.gov registration active with UEI and CAGE code, submission portal account working, SBA Company Registry for SBIR/STTR, size and ownership certifications, CMMC level, facility clearance, export control registration if the topic is ITAR-controlled).
- **2.2 Required Documents & Volumes**: one row per required document from 1.1, with its page limit and any mandatory template (technical volume, cost volume, commercialization report, supporting documents, certifications, letters of support, quad chart, etc.).
- **2.3 Inputs Needed from David & the Team**: items that have to come from people, such as key personnel bios and resumes, labor rates and cost inputs, letters of support, past performance points of contact and contract numbers, photos and figures from deployments, and signatures.
- **2.4 Formatting & Packaging**: font, size, margins, spacing, page count, headers and footers, required markings (proprietary or distribution statements, export control notices), file format, file naming convention, and file size limits.
- **2.5 Reviews & Approvals**: the review gates the proposal-drafting skill will run (solicitation compliance check, evaluator reviews, leadership review, finalization checks), plus David's final sign-off.
- **2.6 Submission**: portal login tested, upload slots and order confirmed, final files uploaded, confirmation receipt saved to the submission folder. Set an internal submit-by date at least one business day before the deadline. Portals slow down and fail near the cutoff, and a late submission is almost always rejected outright.

Adapt the subsections to the opportunity. An RFI response might need only 2.2, 2.4, and 2.6; a full SBIR Phase I proposal needs all six.

**Section 3: Timeline, Questions & Source Documents**
- **3.1 Key Dates & Internal Milestones**: a table with the official dates (Q&A window, any industry day or pre-proposal conference, submission deadline with time and timezone, anticipated award date), followed by internal milestones worked backward from the internal submit-by date: outline approved, first draft complete, compliance check done, review cycles done, final package ready. If the time remaining can't fit the work, say so here rather than discovering it mid-draft.
- **3.2 Questions for the Government**: ambiguities in the solicitation worth raising during the Q&A window, each written as the question you would actually submit, with the Q&A deadline and the channel to use. Respect the solicitation's communication rules. For DoD SBIR/STTR, for example, direct contact with topic authors is allowed only during the pre-release period; after that, questions go through the topic Q&A system.
- **3.3 Source Documents**: every solicitation document saved in the submission folder, with its filename, what it is, and its version or amendment date. Amendments can change page limits, dates, or requirements, so check the solicitation page for new ones again before submission.

### Finishing the Document

Build the document with the `docx` skill so the tables, checkboxes, and headings come out clean and printable. Before presenting it, re-check Section 1.5 against the solicitation one more time, because everything downstream treats it as the source of truth. Then apply David's writing standards: tables over prose, no filler, and no em dashes or en dashes anywhere in the file.

**Check in with David:** "The requirements and submission checklist is saved at Submissions/{folder_name}/{TopicNumber}_Requirements_and_Submission_Checklist.docx. The items that need your input are in 2.3, and any open eligibility actions are in 1.4. Anything to add or correct before we make the go/no-go call?"

---

## Phase 5: Go/No-Go Decision

**Goal:** Make an explicit decision about whether to pursue this opportunity, based on everything gathered so far.

The summary, alignment assessment, and requirements document now give a complete picture. Bring them together into a short decision brief:

- **Fit rating**: Strong Fit, Moderate Fit, Stretch Fit, or Poor Fit, with a two- or three-sentence justification drawn from the alignment assessment.
- **Win themes**: the two or three strengths that would make this proposal stand out to these evaluators, each tied to real Velocity evidence.
- **Critical gaps**: the gaps that could sink the proposal, each with a mitigation (adjacent experience, a teaming partner, a credible plan to build the capability, or a reframing of existing work). Call out anything disqualifying, such as an eligibility requirement Velocity can't meet before the deadline.
- **Effort and timing**: the days remaining against the milestones in Section 3.1, and any conflict with other proposals or commitments.
- **Recommendation**: Go, Go with conditions (name them), or No-Go, with your reasoning.

Give a real recommendation, including No-Go when the evidence points there. A clear "this is a stretch, and here is why" is worth more to David than optimism, and passing on a weak fit frees time for a strong one. The decision itself is David's.

**If No-Go:** save a short decision note to the submission folder (`{TopicNumber}_No-Go_Decision.docx`) with the date, the reasons, and anything that would change the answer (a teaming partner, a better-matched future topic). Then move the folder to "Past Submissions," following the convention from Phase 1. These notes make the next assessment of a similar topic faster.

**If Go:** continue to Phase 6.

**Check in with David:** "Here's the decision brief and my recommendation. Do we go, go with conditions, or pass?"

---

## Phase 6: Handoff to Proposal Drafting

**Goal:** Leave everything the proposal-drafting skill needs in the submission folder, so drafting can start now or in a later conversation without losing context.

1. **Save the assessment.** Write the opportunity summary, the alignment assessment, and the go/no-go brief into the submission folder as `{TopicNumber}_Assessment_Summary.docx`. Until now these may have existed only in the conversation; saved in the folder, they survive a new chat.

2. **Confirm the prerequisites.** The proposal-drafting skill expects four things: the submission folder, the Requirements & Submission Checklist document, the opportunity summary, and the alignment assessment. Confirm all four exist and are current.

3. **List the open items.** Note anything still pending that drafting depends on (bios, cost inputs, answers to Q&A questions) so it is visible from the first day of drafting.

4. **Hand off.** Switch to the proposal-drafting skill and begin at its Phase 1. If drafting will happen later or in another conversation, tell David which folder to point it at.

**Check in with David:** "The assessment is complete and saved in Submissions/{folder_name}. Ready to start drafting now, or do you want to pick this up later?"
