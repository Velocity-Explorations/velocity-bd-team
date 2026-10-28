---
name: proposal-drafting
description: "Drafting, review and revision for government proposal submissions (SBIR, RFI, white papers, BAAs, pitch decks and similar). Runs the Plan, Draft, Review, Finalize and Submit stages of the dashboard's proposal workspace, after opportunity-assessment ends with Go."
---

# Proposal drafting and review: from Go to submitted

This prompt is the back half of Velocity Explorations' proposal pipeline. It takes the groundwork produced during opportunity assessment and turns it into a polished, submission-ready proposal through structured drafting and repeated review cycles.

The core insight behind this workflow: a first draft is never good enough for government proposals. The difference between a winning and a losing submission usually comes down to how well the proposal is reviewed and revised, not the quality of the first draft. So this workflow builds in several review passes, each from a different perspective, to strengthen the proposal before submission.

## How this runs

The dashboard's worker runs one phase at a time, as one workspace step. Each phase ends with a question for the proposal's **owner**, shown on the step's card as "Your call":
- the owner approves;
- or asks for changes with a note, and you redo the phase with the note;
- or adds material.

Do not start the next phase until the step is approved. With key gates only, the steps run on and only the Outline and the Submit gate wait for the owner.

The people working with the owner can add material and tick checklist items, but only the owner approves steps and decides the reviewers' changes.

## Prerequisites: what already exists

These come from opportunity-assessment:

- **The submission folder,** named by the Library convention: `Submissions/<YYYY-MM-DD_portal_short-title>/`, with `00_solicitation/`, `01_submitted/`, `02_working/` and `03_outcome/`.
- **The requirements and submission checklist document** in `02_working/`: the full requirements outline, formatting specs, evaluation criteria, eligibility status, and the checkbox-based submission checklist. Its Section 1.5 is the source of truth for terminology.
- **The opportunity summary and the alignment assessment,** in `{Code}_Assessment_Summary.docx`, with the past work that is most relevant.
- **The direction** the owner confirmed at Alignment, and the past work they chose to build on.

If the folder or the requirements document is missing, stop and mark the step failed with: "The assessment has not been done yet. Run the Qualify steps first."

Save every draft to `02_working/` with a version number (for example `{Code}_Technical_Volume_v1.docx`, `_v2.docx`). This keeps everything for the submission in one place and preserves the revision history.

---

## Phase 1: Research and evidence gathering

This phase runs as part of the **Outline** step; it has no step of its own.

**Goal:** Pull together all the source material that will ground the proposal in real Velocity evidence.

Start from the alignment assessment and the past work the owner chose to build on, then locate and review the most relevant reference documents from across the Library:

- **Past submissions:** previous proposals, white papers and pitch materials that show relevant work, tone and style.
- **Exercise and deployment reports:** field test results and after-action reports that show real-world performance and metrics.
- **Company documents:** capability statements, product overviews, certifications and policy documents.

From each source, extract the evidence that is relevant to this opportunity: quantitative metrics, technical specs, deployment results, lessons learned and customer feedback. The draft weaves this evidence in to back every claim, instead of making unsupported assertions.

Also review past submissions in the same format (for example, earlier SBIR technical volumes when writing an SBIR technical volume) to match the tone, structure and level of detail Velocity usually uses.

List the past work and evidence on the Outline step, so the owner can add to it or drop anything out of date before approving.

---

## Phase 2: Document structure and outline

This is the **Outline** step.

**Goal:** Build the document's skeleton from the requirements before writing any prose.

1. **Map the required structure.** Create the section outline exactly as the solicitation specifies: section numbers, titles and required content areas. Do not improvise the structure; follow what the evaluators expect to see.
2. **Map evaluation criteria to sections.** For each evaluation criterion, name the sections that will answer it. Every criterion needs a home; if one has no natural home, flag it.
3. **Identify placeholder needs.** Mark where figures, diagrams, charts, tables, photos or other visuals would strengthen the proposal. Common ones:
   - system architecture diagrams;
   - data flow or process diagrams;
   - schedule or Gantt charts;
   - organizational charts;
   - photos from past deployments or exercises;
   - key personnel bios, which the owner usually gathers separately.
4. **Check the page budget.** Given the page limits, give each section an approximate share of the space. This prevents running out of pages before all the required content is covered.

Show the direction once more above the outline; approving the outline locks the direction and the past work.

**Ask the owner:** "Here is the proposed structure, page budget and the evidence it draws on. Does this look right? Any sections you want weighted differently, or evidence to add or drop?"

---

## Phase 3: Drafting

This is the **First draft** step.

**Goal:** Write the full proposal draft, grounded in the evidence from Phase 1.

Write the document section by section, following these principles:

- **Lead with the solution, not the problem.** Evaluators already know the problem; they wrote the solicitation. Open each section by showing you understand the need, then move quickly to what Velocity will do about it.
- **Back every claim with evidence.** Do not write "Velocity has extensive experience in X"; write "Velocity demonstrated X during the Cobra Gold 2026 exercise, achieving [specific metric]." Pull from the evidence gathered in Phase 1.
- **Answer the evaluation criteria explicitly.** If the solicitation evaluates "Technical Approach", the Technical Approach section must directly answer every sub-element listed under that criterion.
- **Match the formatting** from the requirements document exactly: font, margins, spacing and page limits. Write Word files; produce a PDF only where the solicitation requires one.
- **Include placeholders,** highlighted in yellow, for anything a person must provide. Make them descriptive, and use the two forms the AI slop check counts:
  - **`[PERSON WRITES: ...]`** for text a person must write in their own words, such as the opening paragraph;
  - **`[NEEDS INPUT: ...]`** for facts, files or figures that must come from people, for example "[NEEDS INPUT: figure, system architecture diagram showing TEDARS components and data flow]", not just "[INSERT FIGURE]".
- **Write to the page limit.** Government proposals should use the space allotted. A proposal that comes in at 15 pages against a 25-page limit signals that the proposer does not have enough substance. Aim for 90 to 100% of the allowed length.

**Ask the owner:** "Here is the first complete draft. What are your first reactions before the compliance check and the reviews?"

---

## Phase 3.5: Solicitation compliance check

This is the **Compliance check** step.

**Goal:** Verify that the draft accurately reflects the solicitation before the review cycles start.

This is a mechanical, checklist-driven pass, not a subjective review. It catches errors where the draft drifts from what the solicitation actually says:
- a keyword paraphrased wrongly;
- a term substituted;
- Phase II scope put into Phase I;
- a required function missing.

These errors are easy to introduce while drafting and hard to catch in the evaluator reviews, because evaluators focus on quality, not on word-for-word compliance.

Using Section 1.5 of the requirements document, verify every item against the draft:

1. **Keywords:** every keyword from the solicitation appears in the draft in the solicitation's exact terms. Do not paraphrase, expand or invent acronyms. If the solicitation says "Continuous Digital Intermediate Frequency (CDIF)", the draft must say exactly that, not "Common Data Interchange Format" or any other expansion. Check every acronym expansion in the draft against the solicitation's definitions.
2. **Required functions:** the draft uses the solicitation's exact function names. If the solicitation says "formatting, recording, librarying, and playback", the draft must use those four terms: not "search" or "cataloging" instead of "librarying". Check section headings, deliverable lists and task descriptions for consistent use.
3. **Spec thresholds:** every performance number in the draft matches the solicitation (>=8 PB, <=4U, >400 GB/s, >=30 seconds and so on), and the draft never weakens a requirement (for example "400 GB/s" where the solicitation says ">400 GB/s").
4. **Phase scope:** the Phase I deliverables in the draft match what the solicitation asks for Phase I, not Phase II, and the Phase I Option scope matches too. This catches the common error of pulling Phase II requirements, such as lab demonstrations or at-sea testing, into the Phase I work plan.
5. **References:** reference numbers (for example Refs 7, 8 and 9) map to the right documents, as the solicitation lists them.
6. **Standards and compliance:** every cited regulation, certification and standard matches the solicitation (ITAR and EAR citations, CMMC level, clearance requirements, NISPOM references).
7. **Capability claims:** every claim about Velocity's capabilities or past performance traces to actual Velocity evidence. Flag any capability in the draft that cannot be traced to a real Velocity product, deployment or documented result. This catches invented capabilities, for example "anomaly detection" listed as a system feature when it does not exist.

Present the findings as a compliance checklist: the items that pass, the items that need correction, and the specific corrections. Make all the corrections and save the result as the next draft.

**Ask the owner:** "Here is what the compliance check found and fixed. Approve the fixes and move into the reviews?"

---

## Phase 4: Review cycles

This is the **Reviews** step.

**Goal:** Strengthen the proposal through several review perspectives, each catching what the one before it missed.

### The AI slop check, on every new draft

Before the first review, and again on every new draft from here on, the worker runs Velocity's AI slop check (the scanner, with the proposal profile and the solicitation's own text exempt). It fixes what it can on its own and saves the next draft; it needs no approval. What it cannot fix shows on the step's AI slop check result: the verdict, the open placeholders, the paragraphs to revise first and the findings by family. The check reports writing patterns and their fixes only; never say or imply that any text was or was not written by AI.

This is the most important phase. Run the three reviews in order. Each review **proposes changes** instead of rewriting the draft itself. Write each change as one row: the section, what the text says now, the suggested text, and why. The owner accepts, rejects or edits each one, and the accepted changes become the next draft.

### Review 1: External evaluator, criteria-based

Evaluate the draft as an independent government evaluator scoring it against the published evaluation criteria. For each criterion:

- give a rating (Outstanding, Good, Acceptable, Marginal or Unacceptable, or whatever scale the solicitation uses);
- name the specific strengths the evaluator would note;
- name the specific weaknesses or gaps;
- flag any requirement that is not adequately answered;
- **verify that every claim about the proposer's capabilities is backed by evidence and not invented.** If the draft says the company can do X, there must be evidence (a deployment, a contract, a test result) behind it. Flag generic claims without evidence as weaknesses.

Save the evaluation, then propose the changes that answer its weaknesses.

### Review 2: Second independent evaluator

Run a second evaluation, approaching it fresh, as a different evaluator would. Different evaluators catch different things. Focus on:

- the technical soundness and feasibility of the proposed approach;
- whether the schedule and budget are realistic;
- whether claims are adequately backed by evidence;
- clarity and readability: can a non-expert evaluator follow the argument?

Save the evaluation, then propose changes.

### Review 3: Internal Velocity leadership

Now take the perspective of a Velocity insider: someone who knows the company's actual capabilities, ongoing commitments and strategic direction. Look for:

- **Overpromises:** anything the proposal commits to that Velocity cannot realistically deliver.
- **Missed strengths:** Velocity capabilities or differentiators that were not highlighted.
- **Strategic alignment:** does the proposal position Velocity well for follow-on work?
- **Voice and tone:** does it sound like Velocity, or generic?
- **Resource conflicts:** are the proposed key personnel and facilities actually available?

Save the evaluation, then propose the final changes.

**After each review, ask the owner:** "Here is what the [evaluator or leadership] review found, as changes to decide. Accept, reject or edit each, then approve the draft."

---

## Phase 5: Finalization

This is the **Final checks** step.

**Goal:** Polish the document and verify it is ready to submit.

1. **Formatting check:** verify every formatting requirement: font, margins, spacing, page count, headers and footers, section numbering.
2. **Final compliance re-check:** run the Phase 3.5 checks again on the final version. The review cycles rewrite a lot of text, and every rewrite is a chance to reintroduce a paraphrased keyword, a softened threshold or Phase II scope. Also confirm that every evaluation criterion still has a home, using the mapping from Phase 2.
3. **Placeholder sweep:** find every remaining placeholder (`[PERSON WRITES: ...]`, `[NEEDS INPUT: ...]`, yellow highlights, missing figures, bios and signatures). List each with what it needs and who will provide it, grouped by type: personnel, cost and pricing, past performance, technical, and administrative. Nothing can go to the government with a placeholder in it, so this list is exactly what stands between the draft and submission.
4. **AI slop check, final pass:** the scanner's verdict on the final version must say Ready (no open placeholder; band clean or light). Then read the whole document as an evaluator who has seen hundreds of generic proposals, and rewrite anything that reads like one. Evaluators discount generic prose, and it costs credibility exactly where the proposal needs it most. Look for:
   - **Em dashes and en dashes.** Dash-check the final file: it must contain neither the em dash (U+2014) nor the en dash (U+2013). Replace each with a comma, colon, semicolon, parentheses or a new sentence.
   - **Filler and hype:** words like "cutting-edge", "state-of-the-art", "seamless", "robust", "leverage" and "holistic", and openers like "in today's rapidly evolving threat landscape" that make no checkable claim.
   - **Unsupported claims:** every capability claim should already cite a Velocity deployment, metric or result from Phase 1. If one slipped through, back it with evidence or cut it.
   - **Mechanical rhythm:** paragraphs that all open the same way, reflexive lists of three, "not only X but also Y" constructions, and closing sentences that restate the section.
   - **Restating the problem:** the evaluators wrote the solicitation and do not need it read back to them.

   Keep the solicitation's exact terminology from Section 1.5 intact through this pass. A style edit must never paraphrase a required keyword, function name or performance threshold.
5. **Submission package check:** confirm the final files match the requirements document: file format, naming convention, size limits, required markings on every page (proprietary or distribution statements, export control notices), and every volume and attachment listed in Section 1.1. If the submission is a PDF, convert it and check the PDF itself: page count unchanged, fonts embedded, figures and tables intact.
6. **Update the submission checklist:** go through Section 2, mark ☑ everything now complete, and give every open item an owner and a date. The dashboard's checklist shows the same items.
7. **Save the final version** to `02_working/` as `{Code}_Technical_Volume_FINAL.docx`, plus the PDF if one is required. Keep the numbered drafts; they are the revision history.

**Ask the owner:** "The final version is saved. Here is the updated checklist, with what is complete and what is still open, and who owns each item. Tick what people have done, then go to the Submit gate."

---

## Phase 6: Submission and archival

This is the **Submit** gate, and then Proposals, Submitted and waiting.

**Goal:** Get the package submitted on time, then file everything so future proposals can learn from this one.

### The Submit gate

Before the owner submits, confirm each of the following, and say plainly which ones are not yet true:

- Every item in the submission checklist is ☑, or the owner has explicitly waived it.
- The placeholder sweep found nothing left.
- The final compliance re-check, the AI slop check and the dash-check all pass on the final files.
- The final files open correctly in the format the portal requires.
- The internal submit-by date set during assessment has not passed. If it has, flag the risk of a late submission.

### Submission

The owner submits through the portal, not you. Portals use the company's credentials and certifications, and submitting is a formal representation on Velocity's behalf. Make it fast for them:
- list each file with the portal slot it goes into;
- summarize the portal steps from the solicitation;
- restate the deadline with its time and time zone.

The gate links to the call's page.

### After submission

The owner enters the confirmation number and the result expected by date, and chooses Mark submitted. Then:

1. **File the confirmation.** Save the receipt email, the confirmation number or a screenshot to `01_submitted/`, with the submitted files.
2. **Write a submission record.** Create `{Code}_Submission_Record.docx` in `01_submitted/`. Give it the date and time submitted, the confirmation number, the files submitted, and the expected decision date: the date Discovery found for when results are announced, or 90 days after the deadline.
3. **Keep the folder in the Library.** It stays in `Submissions/`, where opportunity-assessment draws on it for alignment evidence. The dashboard records the submission in the Proposal Register.
4. **Record the outcome.** When the result arrives, the owner records it from Proposals, Submitted and waiting: won, lost, withdrawn or cancelled by the agency. Add it to the submission record with the evaluator comments or debrief notes, and what to do differently next time, and save the debrief to `03_outcome/`. These notes are some of the most valuable evidence for the next alignment assessment on a similar topic.
