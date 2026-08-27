# Five-minute demo script

1. Run `python ../scripts/seed_users.py` from `backend/`, start the API, and start the Vite frontend.
2. Sign in as `operator@demo.local` with `DemoPass123!`; upload `data/sample_loans.csv` from the Upload screen.
3. Show the upload summary, dashboard counts, and the exception queue. Mention that raw rows and deterministic validation evidence are stored unchanged.
4. Sign in as `reviewer@demo.local`; search `LN-10002`, claim the balance exception, and open the Loan Review panel.
5. Request Groq AI Review. Show the distinct recommendation and explain that it has not changed the loan.
6. Accept the suggestion or manually edit `current_balance` to `82000`, then create the verified record.
7. Sign in as `consumer@demo.local`; show the verified record, quality score, SHA-256 hash, export button, and audit timeline for `LN-10002`.
8. Open `docs/ai-development-log.md` and briefly show how AI-assisted development was reviewed and corrected.

Never use the demo password in a public deployment.
