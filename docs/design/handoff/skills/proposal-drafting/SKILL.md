---
name: proposal-drafting
description: "Drafting, review, and revision workflow for government proposal submissions (SBIR, RFI, white papers, BAAs, pitch decks, etc.). Use this skill whenever David is ready to start writing a proposal, technical volume, white paper, or response document for a government opportunity, especially after completing the 'opportunity-assessment' skill. Also trigger when David says things like 'let's start drafting,' 'write the proposal,' 'build the technical volume,' 'let's put this together,' or references a specific volume to write. This skill assumes the pre-draft assessment work has been done (opportunity summary, alignment assessment, requirements doc, submission checklist), either through the opportunity-assessment skill or through prior conversation. If that groundwork hasn't been done, prompt David to run opportunity-assessment first."
---

# Proposal Drafting & Review: Post-Assessment Workflow

This skill is the back half of Velocity Explorations' proposal pipeline. It takes the groundwork produced during opportunity assessment and turns it into a polished, submission-ready proposal through structured drafting and iterative review cycles.

The core insight behind this workflow: a first draft is never good enough for government proposals. The difference between a winning and losing submission usually comes down to how well the proposal is reviewed and revised, not the quality of the initial draft. This skill builds in multiple review passes from different perspectives to systematically strengthen the proposal before submission.

## Prerequisites: What Should Already Exist

Before starting this skill, the following should be available (typically produced by the **opportunity-assessment** skill, but could also come from prior conversation):

- **Submission folder**: a dedicated folder in the active **Submissions** directory for this opportunity (e.g., `Submissions/DON26BZ01-NV022_Wideband_Digital_Recorder/`). All drafts and supporting documents go here.
- **Requirements & Submission Checklist document**: a `.docx` file in the submission folder with the full requirements outline, formatting specs, evaluation criteria, eligibility status, and checkbox-based submission checklist
- **Opportunity summary**: what the solicitation is asking for
- **Alignment assessment**: how Velocity's capabilities map to the requirements, and which past work/reference documents are most relevant

If the submission folder or requirements document doesn't exist, suggest running the opportunity-assessment skill first: "It looks like we haven't done the pre-draft assessment yet. Want me to run through the opportunity assessment workflow first so we have a solid foundation to draft from?"

All proposal drafts should be saved into the submission folder with version numbers (e.g., `{TopicNumber}_Technical_Volume_DRAFT_v1.docx`, `_v2.docx`, etc.). This keeps everything for a given submission in one place and preserves the revision history.

## How This Skill Works

This is a **step-by-step playbook** with built-in review cycles. Work through each phase in order, pausing at the end of each phase to check in with David. Use the TodoList to track progress. The review phases are where the real value is; don't rush through them.

---

## Phase 1: Research & Evidence Gathering

**Goal:** Pull together all the source material that will ground the proposal in real Velocity evidence.

Using the alignment assessment from the pre-draft work, locate and review the most relevant reference documents. These typically come from across the workspace:

- **Past Submissions**: previous proposals, white papers, pitch materials showing relevant work, tone, and style
- **Exercise/Deployment Reports**: field test results, after-action reports demonstrating real-world performance and metrics
- **Company Documents**: capability statements, product overviews, certifications, policy documents

For each source, extract the specific evidence that's relevant to this opportunity: quantitative metrics, technical specs, deployment results, lessons learned, customer feedback. This evidence will be woven into the draft to substantiate claims rather than making unsupported assertions.

Also review past submissions in the same format (e.g., if writing an SBIR Technical Volume, look at previous SBIR Technical Volumes) to understand the tone, structure, and level of detail that Velocity typically uses.

**Check in with David:** "Here's the reference material I'm planning to draw from. Is there anything else I should pull in, or anything here that's outdated and shouldn't be used?"

---

## Phase 2: Document Structure & Outline

**Goal:** Build the document skeleton based on the requirements, before writing any prose.

Using the requirements document from the pre-draft work:

1. **Map the required structure**: create the section outline exactly as specified in the solicitation (section numbers, titles, required content areas). Don't improvise the structure; follow what the evaluators expect to see.

2. **Map evaluation criteria to sections**: for each evaluation criterion, identify which section(s) of the proposal will address it. Every evaluation criterion should be addressed somewhere. If a criterion doesn't have a natural home, flag it.

3. **Identify placeholder needs**: determine where figures, diagrams, charts, tables, photos, or other visual elements would strengthen the proposal. Mark these as placeholders in the outline. Common placeholders include:
   - System architecture diagrams
   - Data flow or process diagrams
   - Schedule/Gantt charts
   - Organizational charts
   - Photos from past deployments or exercises
   - Key personnel bios (David typically gathers these separately)

4. **Check page budget**: given the page limits, allocate approximate space to each section. This prevents the common problem of running out of pages before covering all required content.

**Check in with David:** "Here's the proposed structure and page allocation. Does this look right? Any sections you want weighted differently?"

---

## Phase 3: Drafting

**Goal:** Write the full proposal draft, grounded in evidence from the research phase.

Write the document section by section, following these principles:

- **Lead with the solution, not the problem.** Evaluators already know the problem; they wrote the solicitation. Start each section by showing you understand the need, then quickly pivot to what Velocity will do about it.

- **Substantiate every claim.** Don't say "Velocity has extensive experience in X"; say "Velocity demonstrated X during the Cobra Gold 2026 exercise, achieving [specific metric]." Pull from the evidence gathered in Phase 1.

- **Address evaluation criteria explicitly.** If the solicitation says they'll evaluate "Technical Approach," make sure the Technical Approach section directly addresses every sub-element they listed under that criterion.

- **Use the right document generation approach.** For Word documents (.docx), use the docx skill. For PDFs, use the pdf skill. Match the formatting requirements from the requirements document exactly (font, margins, spacing, page limits).

- **Include placeholders.** Use yellow-highlighted placeholder text for figures, bios, and any content David needs to provide. Make placeholders descriptive (e.g., "[INSERT FIGURE: System Architecture Diagram showing TEDARS components and data flow]" not just "[INSERT FIGURE]").

- **Write to the page limit.** Government proposals should use the space allotted. A 25-page limit proposal that comes in at 15 pages signals that the proposer doesn't have enough substance. Aim for 90-100% of the allowed length.

**Check in with David:** "Here's the first complete draft. Take a look and let me know your initial reactions before we start the compliance check and review cycles."

---

## Phase 3.5: Solicitation Compliance Check

**Goal:** Verify that the draft accurately reflects the solicitation before entering review cycles.

This is a mechanical, checklist-driven pass, not a subjective review. It catches the category of errors where the draft drifts from what the solicitation actually says. These errors are easy to introduce during drafting (paraphrasing a keyword wrong, substituting a term, putting Phase II scope into Phase I, missing a required function) and hard to catch during evaluator reviews because evaluators focus on quality, not verbatim compliance.

**Using the Solicitation Terminology & Keywords section from the Requirements document (Section 1.5), verify every item against the draft:**

1. **Keyword verification**: confirm that every keyword from the solicitation appears in the draft using the solicitation's exact terminology. Do NOT paraphrase, expand, or invent acronyms. If the solicitation says "Continuous Digital Intermediate Frequency (CDIF)," the draft must say exactly that, not "Common Data Interchange Format" or any other expansion. Check every acronym expansion in the draft against the solicitation's definitions.

2. **Required functions verification**: confirm the draft uses the solicitation's exact function names. If the solicitation says "formatting, recording, librarying, and playback," the draft must use those four terms, not "search" instead of "librarying," not "cataloging" instead of "librarying." Check section headings, deliverable lists, and task descriptions for consistent use.

3. **Spec threshold verification**: confirm every performance number in the draft matches the solicitation (>=8 PB, <=4U, >400 GB/s, >=30 seconds, etc.). Verify the draft doesn't accidentally weaken requirements (e.g., saying "400 GB/s" when the solicitation says ">400 GB/s").

4. **Phase scope verification**: confirm that Phase I deliverables described in the draft match what the solicitation asks for Phase I, not Phase II. Confirm Phase I Option scope matches. This catches the common error of pulling Phase II requirements (like lab demonstrations or at-sea testing) into the Phase I work plan.

5. **Reference verification**: confirm that reference numbers (e.g., Refs 7, 8, 9) are mapped to the correct documents per the solicitation.

6. **Standards and compliance verification**: confirm all cited regulations, certifications, and standards match the solicitation (ITAR/EAR citations, CMMC level, clearance requirements, NISPOM references).

7. **Capability claim verification**: for every claim the draft makes about Velocity's capabilities or past performance, confirm it is substantiated by actual Velocity evidence. Flag any capability that appears in the draft but cannot be traced to a real Velocity product, deployment, or documented result. This catches fabricated or hallucinated capabilities (e.g., listing "anomaly detection" as a system feature when it doesn't exist).

**Present findings as a compliance checklist**: items that pass, items that need correction, and the specific corrections needed. Make all corrections, then proceed to review cycles.

**Check in with David:** "I've completed the solicitation compliance check. Here's what I found and fixed. Ready to move into the review cycles?"

---

## Phase 4: Review Cycles

**Goal:** Systematically strengthen the proposal through multiple review perspectives.

This is the most important phase. Each review pass looks at the proposal through a different lens, catching issues that the previous pass missed. Run these in order:

### Review 1: External Evaluator (Criteria-Based)

Evaluate the draft as if you are an independent government evaluator scoring it against the published evaluation criteria. For each criterion:

- Assign a rating (Outstanding / Good / Acceptable / Marginal / Unacceptable, or whatever scale the solicitation uses)
- Identify specific strengths the evaluator would note
- Identify specific weaknesses or gaps
- Flag any requirements that aren't adequately addressed
- **Verify that every claim about the proposer's capabilities is substantiated and not fabricated.** If the draft says the company can do X, there must be evidence (a deployment, a contract, a test result) to back it up. Generic claims without evidence should be flagged as weaknesses.

Present findings to David as a structured evaluation, then revise the draft to address the weaknesses identified.

### Review 2: Second Independent Evaluator

Run a second evaluation pass, but approach it fresh, as a different evaluator would. Different evaluators catch different things. Focus on:

- Technical soundness and feasibility of the proposed approach
- Whether the schedule and budget are realistic
- Whether claims are adequately substantiated with evidence
- Clarity and readability: can a non-expert evaluator follow the argument?

Present findings, then revise again.

### Review 3: Internal Velocity Leadership

Now switch perspective to a Velocity insider: someone who knows the company's actual capabilities, ongoing commitments, and strategic direction. Look for:

- **Overpromises**: anything the proposal commits to that Velocity can't realistically deliver
- **Missed strengths**: Velocity capabilities or differentiators that weren't highlighted
- **Strategic alignment**: does this proposal position Velocity well for follow-on work?
- **Voice and tone**: does it sound like Velocity, or does it sound generic?
- **Resource conflicts**: are the proposed key personnel and facilities actually available?

Present findings, then make final revisions.

**After each review-revise cycle, check in with David:** "Here's what the [evaluator/leadership] review found and the changes I've made. Want to review before we move to the next pass?"

---

## Phase 5: Finalization (Post-Review)

**Goal:** Polish the document and verify submission readiness.

1. **Formatting check**: verify compliance with all formatting requirements (font, margins, spacing, page count, headers/footers, section numbering).

2. **Final compliance re-check**: run the Phase 3.5 checks again on the final version. The review cycles rewrite a lot of text, and every rewrite is a chance to reintroduce a paraphrased keyword, a softened threshold, or Phase II scope. Also confirm that every evaluation criterion still has a home, using the mapping from Phase 2.

3. **Placeholder sweep**: find every remaining placeholder (yellow highlights, "[INSERT ...]" markers, missing figures, bios, and signatures) and list each one with what it needs and who will provide it, grouped by type: personnel, cost and pricing, past performance, technical, and administrative. Nothing can go to the government with a placeholder in it, so this list is exactly what stands between the draft and submission.

4. **AI-slop check**: read the whole document as an evaluator who has seen hundreds of machine-written proposals, and rewrite anything that reads like one. Evaluators discount generic prose, and it costs credibility exactly where the proposal needs it most. Look for:
   - **Em dashes and en dashes.** Dash-check the final file: it must contain neither the em dash (U+2014) nor the en dash (U+2013). Replace each with a comma, colon, semicolon, parentheses, or a new sentence.
   - **Filler and hype**: words like "cutting-edge," "state-of-the-art," "seamless," "robust," "leverage," and "holistic," and openers like "in today's rapidly evolving threat landscape" that make no checkable claim.
   - **Unsupported claims**: every capability claim should already cite a Velocity deployment, metric, or result from Phase 1. If one slipped through, substantiate it or cut it.
   - **Mechanical rhythm**: paragraphs that all open the same way, reflexive lists of three, "not only X but also Y" constructions, and closing sentences that restate the section.
   - **Restating the problem**: the evaluators wrote the solicitation and don't need it read back to them.

   Keep the solicitation's exact terminology from Section 1.5 intact through this pass. A style edit must never paraphrase a required keyword, function name, or performance threshold.

5. **Submission package check**: confirm the final files match the requirements document: file format, naming convention, size limits, required markings on every page (proprietary or distribution statements, export control notices), and every volume and attachment listed in Section 1.1. If the submission is a PDF, convert it and check the PDF itself: page count unchanged, fonts embedded, figures and tables intact.

6. **Update the submission checklist**: go through Section 2 of the Requirements & Submission Checklist document, mark ☑ everything that is now complete, and give every open item an owner and a date. Save the updated checklist in the submission folder.

7. **Save the final version**: save the document as `{TopicNumber}_Technical_Volume_FINAL.docx` (plus the PDF, if one is required) in the submission folder. Keep the numbered drafts; they are the revision history.

**Check in with David:** "The final version is saved in Submissions/{folder_name}. Here's the updated checklist, with what's complete and what's still open (and who owns it). Do you want to review the final before we go through the submission steps?"

---

## Phase 6: Submission & Archival

**Goal:** Get the package submitted on time, then file everything so future proposals can learn from this one.

### The Submit Gate

Before David submits, confirm each of the following, and say plainly which ones are not yet true:

- Every item in the submission checklist is ☑, or David has explicitly waived it.
- The placeholder sweep found nothing left.
- The final compliance re-check and the dash-check both pass on the final files.
- The final files open correctly in the format the portal requires.
- The internal submit-by date set during assessment hasn't passed. If it has, flag the risk of a late submission.

### Submission

David submits through the portal, not you. Portals use the company's credentials and certifications, and submitting is a formal representation on Velocity's behalf. Make it fast for him: list each file with the portal slot it goes into, summarize the portal steps from the solicitation, and restate the deadline with its time and timezone.

### After Submission

1. **File the confirmation.** Save the receipt email, confirmation number, or a screenshot in the submission folder.
2. **Write a submission record.** Create `{TopicNumber}_Submission_Record.docx` with the date and time submitted, the confirmation number, the files submitted, and the expected decision date.
3. **Archive the folder.** Move the submission folder to "Past Submissions," the archive the opportunity-assessment skill draws on for alignment evidence.
4. **Record the outcome.** When the result arrives, add it to the submission record: win or loss, evaluator comments or debrief notes, and what to do differently next time. These notes are some of the most valuable evidence for the next alignment assessment on a similar topic.

**Check in with David:** "Once it's submitted, send me the confirmation and I'll file it and archive the folder."
