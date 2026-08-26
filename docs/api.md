# API quick reference

`POST /api/auth/register` and `POST /api/auth/login` return a bearer token. Send `Authorization: Bearer <token>` for protected routes.

| Area | Routes |
| --- | --- |
| Upload | `POST /api/uploads`, `GET /api/uploads` |
| Review | `GET /api/exceptions`, `POST /api/exceptions/{id}/claim`, `POST /api/exceptions/{id}/comments` |
| AI | `POST /api/exceptions/{id}/ai-review` |
| Decision | `POST /api/exceptions/{id}/decision`, `POST /api/exceptions/{id}/verify` |
| Trust | `GET /api/audit/{loan_id}`, `GET /api/verified-records`, `GET /api/verified-records/export` |
| Metrics | `GET /api/dashboard` |
