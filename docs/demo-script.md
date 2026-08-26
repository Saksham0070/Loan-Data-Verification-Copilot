# Five-minute demo script

1. Run `python ../scripts/seed_users.py` from `backend/`.
2. Sign in as `operator@demo.local` with `DemoPass123!`.
3. Upload `data/sample_loans.csv` at `POST /api/uploads`.
4. Sign in as `reviewer@demo.local`; open `GET /api/exceptions?severity=HIGH`.
5. Claim a balance-over-principal exception, request `POST /api/exceptions/{id}/ai-review`, then record a human decision.
6. Call `POST /api/exceptions/{id}/verify` to create the immutable verified record and SHA-256 hash.
7. Show `GET /api/audit/{loan_id}` and `GET /api/verified-records`.

Never use the demo password in a public deployment.
