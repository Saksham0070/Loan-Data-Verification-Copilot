# Validation rules

The validation engine is deterministic Python, not AI. Its rules are visible in `data/validation_rules.json`; that file may enable/disable a rule or override its severity, but it never edits a loan record.

Rules cover required fields, dates, numeric values, negative values, maturity ordering, balance versus principal, interest-rate range, recognized payment states, duplicate IDs, document status, stale records, state code, payment-status consistency, closed loans with balances, repeated borrower/amount/date combinations, and cross-source conflicting values.

Every import stores immutable rule evidence. Failed HIGH and MEDIUM results create reviewer exceptions. Groq only explains an existing exception or proposes a suggestion for a reviewer to accept, edit, or reject.
