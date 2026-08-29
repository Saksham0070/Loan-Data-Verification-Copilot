# Loan Data Verification Copilot

An AI-assisted, human-controlled console that turns messy loan tapes into validated, traceable, verified records.

## Run locally

1. Configure `backend/.env` from `backend/.env.example` with MongoDB Atlas, JWT, and Groq values.
2. `cd backend && python -m pip install -r requirements.txt && uvicorn app.main:app --reload`
3. In a second terminal: `cd backend && python ../scripts/seed_users.py`
4. `cd frontend && npm install && npm run dev`

Open `http://localhost:5173`. The API Swagger UI runs at `http://127.0.0.1:8000/docs`.

Demo accounts are `operator@demo.local`, `reviewer@demo.local`, and `consumer@demo.local`; the local-only password is `DemoPass123!`.

## Environment variables

`MONGODB_URI`, `MONGODB_DATABASE`, `JWT_SECRET`, `GROQ_API_KEY`, `GROQ_MODEL`, and `CORS_ORIGINS` are documented in `backend/.env.example`. Never commit `backend/.env`.

## Complete setup and demo guide

### Start the application

1. Copy `backend/.env.example` to `backend/.env` and enter your MongoDB Atlas, JWT, and Groq values.
2. Start the backend:

   ```powershell
   cd "D:\Loan Data Verification Copilot\backend"
   python -m pip install -r requirements.txt
   uvicorn app.main:app --reload
   ```

3. Confirm the backend at `http://127.0.0.1:8000/health` and API documentation at `http://127.0.0.1:8000/docs`.
4. Seed demo accounts in another terminal:

   ```powershell
   cd "D:\Loan Data Verification Copilot\backend"
   python ..\scripts\seed_users.py
   ```

5. Start the frontend in a third terminal:

   ```powershell
   cd "D:\Loan Data Verification Copilot\frontend"
   npm install
   npm run dev
   ```

6. Open `http://localhost:5173`.

### Demo accounts and role permissions

All three accounts use the password `DemoPass123!`.

| Role | Email | Main responsibilities |
|---|---|---|
| Data Operator | `operator@demo.local` | Uploads CSV source files and checks import batches. |
| Reviewer | `reviewer@demo.local` | Reviews exceptions, requests AI guidance, adds notes, edits/rejects/requests correction, and verifies records. |
| Data Consumer | `consumer@demo.local` | Views verified records, audit history, and exports verified data. |

### CSV types and correct upload order

The `data` folder has coordinated demo files. Upload them in this order:

| Order | File | Source type to select | Why it is used |
|---|---|---|---|
| 1 | `data/hackathon_test_loan_tape.csv` | **Loan tape** | Primary messy data. It triggers the validation and exception workflow. |
| 2 | `data/hackathon_test_servicer_update.csv` | **Servicer update** | Secondary source evidence that exposes conflicting values for matching loan IDs. |
| 3 | `data/hackathon_test_document_manifest.csv` | **Document manifest** | Supporting document-status evidence. |
| 4 | `data/hackathon_test_clean_loans.csv` | **Loan tape** | Clean loans that are ready for reviewer verification and export. |

Do **not** manually clean the messy primary CSV before upload. The intended product flow is:

```text
Upload → Normalize → Validate → Review → Verify → Audit
```

The application preserves secondary files separately as source evidence; they never silently overwrite the primary canonical record. Select a secondary-file batch in **Batches** to view its evidence rows, then use the Exception Queue to compare and review conflicts.

### Suggested presentation flow

1. Sign in as the Data Operator and upload the primary loan tape.
2. Show the normalized batch and the generated exceptions.
3. Upload the Servicer update and Document manifest; show their evidence rows in **Batches**.
4. Sign in as the Reviewer, open an exception, inspect source lineage, and request Groq AI guidance.
5. Show that AI recommendations are separate from human decisions. Add a note, edit/reject/request correction as appropriate.
6. Upload the clean-loans CSV, then verify one clean record as the Reviewer.
7. Sign in as the Data Consumer, inspect the record hash and audit timeline, then export verified data.

### Reset before a presentation

To clear every uploaded batch and all related loans, exceptions, AI reviews, verified records, and audit logs—while preserving user accounts and CSV files—run:

```powershell
cd "D:\Loan Data Verification Copilot"
python scripts\reset_demo_data.py
```

Refresh the browser after the reset completes.

### Deployment summary

Deploy the FastAPI backend on **Render** using `render.yaml`. Deploy the React frontend on **Vercel** with root directory `frontend` and `VITE_API_URL` set to the Render API URL (without `/api`). Then set the deployed Vercel URL in Render `CORS_ORIGINS` and redeploy the backend. Keep all MongoDB, JWT, and Groq secrets out of the frontend and Git repository.

## Deliverables

- [Project structure and challenge-module map](docs/project-structure.md)
- [Architecture](docs/architecture.md)
- [API reference](docs/api.md)
- [Validation rules](data/validation_rules.json)
- [Demo walkthrough](docs/demo-script.md)
- [AI development log](docs/ai-development-log.md)
- [Deployment guide](docs/deployment.md)
