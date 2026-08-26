# Architecture note

The React/Vite frontend calls FastAPI through HTTPS/REST. FastAPI stores immutable evidence in MongoDB Atlas: uploads, raw source rows, normalized loans, validation results, exceptions, AI reviews, decisions, verified snapshots, and audit logs. Deterministic Python rules detect issues; Groq is only called on demand to explain, summarize, or propose a correction. It cannot write a loan record. A reviewer accepts, edits, or rejects a suggestion, after which the backend creates a canonical verified snapshot and a SHA-256 hash.

The ingestion layer handles the primary loan tape plus servicer and document-manifest files. Secondary-source disagreements become `CONFLICTING_VALUES` exceptions rather than silent changes. MongoDB is selected for flexible raw-row preservation and lineage. The trade-off is a deliberately simple MVP: synchronous uploads and no background queue, which is appropriate for the hackathon’s 1,000-5,000-row synthetic datasets.
