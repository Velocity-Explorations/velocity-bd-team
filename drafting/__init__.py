"""The Writer: drafts proposal responses from a call (Writer Plan, docs/plans/writer-plan.html).

W0 ports the retired Yukon pipeline with its prompts intact: `drafting.pipeline.run_pipeline`
runs the phases in `drafting.phases`, calling the model through `drafting.llm.generate`, and
`python -m drafting.cli dev` runs it from an inputs JSON file into a local folder.
"""
