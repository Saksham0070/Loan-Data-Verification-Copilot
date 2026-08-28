# Domain service ownership

The active import and workflow orchestration service is `services.py`. It remains a single file for the hackathon build because CSV parsing, normalization, validation execution, source lineage and hashing form one atomic workflow.

If the product is extended, this service can be split into ingestion, normalization, verification and audit services. A folder named `services/` is intentionally not used because it conflicts with Python's `services.py` import.
