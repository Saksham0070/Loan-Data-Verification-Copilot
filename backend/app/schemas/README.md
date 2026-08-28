# API contract ownership

FastAPI request and response models live next to the router that owns the workflow. This keeps each contract visible where its authorization and business rules are enforced:

- `routers/auth.py` owns login and registration contracts.
- `routers/uploads.py` owns multipart file-upload contracts.
- `routers/workflow.py` owns comments, review decisions and verification contracts.
- `routers/advanced.py` owns secondary-source, AI batch and validation-rule contracts.

As the project grows, reusable Pydantic models can move into this package without changing the API boundary. The OpenAPI contract is always available at `/docs` while the backend is running.
