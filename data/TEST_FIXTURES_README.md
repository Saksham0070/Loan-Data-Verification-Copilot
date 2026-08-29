# Hackathon Test CSV Files

Use the test files in this order:

1. Upload `hackathon_test_loan_tape.csv` as **Loan tape**. It intentionally contains each main validation scenario.
2. Upload `hackathon_test_servicer_update.csv` as **Servicer update**. It creates source-conflict exceptions for matching loan IDs.
3. Upload `hackathon_test_document_manifest.csv` as **Document manifest**. It supplies document evidence and a document-status conflict.
4. Upload `hackathon_test_clean_loans.csv` as **Loan tape** when you want two records that should be immediately ready for reviewer verification.

The primary file is deliberately messy. Do not manually clean it before upload: the whole point of the demo is to show the application detecting, explaining, correcting, and auditing the issues.
