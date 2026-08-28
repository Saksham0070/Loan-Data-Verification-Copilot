# Data model ownership

MongoDB is the persistence layer. The runtime collection shapes are intentionally documented here and created/indexed in `../database.py`.

| Collection | Purpose |
| --- | --- |
| `uploads` | Source-file metadata, import summary and raw-file lineage |
| `loans` | Normalized canonical loan records, including the original CSV row |
| `failed_rows` | CSV rows that could not be imported |
| `validation_results` | Immutable pass/fail result for each validation rule |
| `exceptions` | Actionable validation failures and their review state |
| `ai_reviews` | Stored AI prompts, model metadata and recommendations |
| `review_decisions` | Human approve/reject/request-correction decisions |
| `verified_loans` | Human-approved canonical record with a SHA-256 hash |
| `audit_events` | Append-only workflow events for traceability |
| `users` | Role-based demo and registered accounts |

Document construction stays close to the workflow service so a reviewer can trace every field from raw source evidence to the verified record without an ORM abstraction hiding the lineage.
