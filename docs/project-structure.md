# Project Structure and Requirement Map

This repository is organised around the Loan Data Verification Copilot workflow: ingest a source file, preserve the evidence, validate it, review exceptions with human-controlled AI assistance, and publish traceable verified records.

```text
Loan Data Verification Copilot/
|- backend/
|  |- app/
|  |  |- routers/                 # API boundary and role-protected workflows
|  |  |  |- auth.py               # Login and demo-user registration
|  |  |  |- uploads.py            # Primary loan-tape ingestion
|  |  |  |- workflow.py           # Exceptions, AI review, decisions, audit
|  |  |  `- advanced.py           # API catalogue, secondary files, summaries
|  |  |- validators/              # Deterministic, configurable data rules
|  |  |  |- base.py               # Rule definitions and validation results
|  |  |  `- core_rules.py         # Required, date, numeric, duplicate, stale rules
|  |  |- models/                  # MongoDB collection ownership notes
|  |  |- schemas/                 # API contract ownership notes
|  |  |- services.py              # Import, normalization, lineage, hashing
|  |  |- database.py              # MongoDB connection and indexes
|  |  |- security.py              # JWT, roles and password handling
|  |  `- main.py                  # FastAPI application composition
|  `- tests/                      # Validation and API smoke tests
|- frontend/
|  `- src/
|     |- components/              # Reusable UI: navigation and AI panel
|     |- features/                # Feature ownership map for auth/upload/review/audit
|     |- lib/                     # API client and shared constants
|     |- pages/                   # Route/page ownership map
|     `- main.jsx                 # Current Vite application entry and workflow UI
|- data/                          # Synthetic demo sources and configurable rules
|- docs/                          # Architecture, API, demo, deployment and AI log
`- scripts/                       # Demo-user seeding and operational helpers
```

## Challenge modules to implementation

| Challenge module | Primary implementation locations |
| --- | --- |
| A. Data ingestion | `backend/app/routers/uploads.py`, `backend/app/services.py`, `data/` |
| B. Validation engine | `backend/app/validators/`, `data/validation_rules.json` |
| C. Exception queue | `backend/app/routers/workflow.py`, `frontend/src/features/exceptions/` |
| D. AI review assistant | `backend/app/routers/workflow.py`, `backend/app/routers/advanced.py`, `frontend/src/components/AiReviewPanel.jsx` |
| E. Verified loan record | `backend/app/services.py`, `backend/app/routers/workflow.py` |
| F. Audit trail | `backend/app/services.py`, `backend/app/routers/workflow.py`, `frontend/src/features/audit/` |
| G. Role dashboards | `backend/app/routers/advanced.py`, `frontend/src/pages/` |
| H. Verified records API | `backend/app/routers/advanced.py`, `backend/app/routers/workflow.py` |

## Data lifecycle

`CSV source -> raw row + normalized loan -> validation results -> exception -> AI recommendation (optional) -> human decision -> verified loan + SHA-256 hash -> audit trail`

The `models/` and `schemas/` folders contain ownership documentation because MongoDB documents and request contracts are deliberately kept close to their corresponding routers during the hackathon. This makes the flow easier to trace while avoiding an unnecessary ORM layer.
