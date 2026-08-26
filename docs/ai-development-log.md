# AI development log

## Tools and human review

Codex was used for architecture drafting, FastAPI route scaffolding, validation-test generation, documentation, and debugging. Every generated change was reviewed against the challenge brief and manually exercised through Swagger. AI is also used in-product through Groq only on reviewer request.

## Representative development prompts

1. “Design a FastAPI and MongoDB workflow for a human-in-the-loop loan validation console.”
2. “Generate deterministic tests for balance-over-principal, invalid state, and duplicate-ID validation rules.”
3. “Add a reviewer-decision endpoint that never lets an AI update a loan directly.”
4. “Debug a MongoDB index that prevents intentionally duplicated IDs from being imported as evidence.”
5. “Create a concise five-minute demo script showing upload, exception, AI review, verification, and audit.”

## Rejected or corrected output

- An early index design made `(loan_id, upload_id)` unique, which blocked duplicate source rows instead of creating an exception. It was replaced with a row-level unique index.
- An initial MongoDB truthiness check crashed on startup. It was corrected to an explicit `is not None` check.

## Estimate and lesson

Approximately 60% of first-draft code and documentation was AI-assisted; all workflow, safety, and data-lineage choices were human-reviewed. AI accelerated scaffolding and debugging, while the human decisions were essential for preserving evidence and enforcing no-silent-correction controls.
