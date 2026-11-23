# REST API

Interactive documentation is generated from the real Pydantic schemas at `/docs`; machine-readable OpenAPI is `/openapi.json`. Prefix every route below with `/api`. Protected requests require `Authorization: Bearer <access_token>`.

| Method | Route | Purpose |
| --- | --- | --- |
| GET | /health | API / database readiness |
| POST | /auth/register | `{name,email,password}`; password at least 10 chars |
| POST | /auth/login | `{email,password}` → access token and public user |
| GET | /auth/me | Current account |
| GET, POST | /readings | List own readings / add `{date,kwh}` |
| PUT, DELETE | /readings/{id} | Update / delete own reading |
| POST | /uploads | Multipart `file` CSV; imported and skipped counts |
| GET | /uploads | Own import history |
| GET | /analytics | `start`, `end`, `period=daily\|weekly\|monthly` |
| GET | /tariff | Active estimate configuration |
| POST | /predictions | `days=1..30`; train / load and save forecast |
| GET | /predictions/history | Latest 20 forecast snapshots |
| GET | /anomalies | Isolation Forest flags and readiness message |
| GET, POST | /appliances | List / add `{name,watts,hours_per_day,quantity}` |
| PUT, DELETE | /appliances/{id} | Update / delete own appliance |
| GET | /reports | Download CSV for `start` / `end` |
| GET | /admin/stats | Platform aggregate counts and consumption |
| GET | /admin/users | Public account records |
| PATCH | /admin/users/{id} | `{active:boolean}`; cannot deactivate self |
| PUT | /admin/tariff | `{name,rate_per_kwh,fixed_charge,currency}` |
| GET | /admin/datasets | Import metadata across accounts |

Status codes: 201 creation, 204 successful deletion, 401 invalid/expired credentials, 403 insufficient role, 404 absent/unowned resource, 409 duplicate email/date/import conflict, 413 oversized upload, 422 invalid fields / inadequate training data. Errors use FastAPI `detail`, either a readable string or a Pydantic error array. No API response uses fabricated account data.

Dates use ISO 8601. Server validation uses the server's local calendar date; deploy with the intended timezone for consistent future-date validation. Default analytics/report period is current month-to-date. Weekly buckets begin Monday; boundary weeks include only readings within the requested period. Zero-usage days are recorded days, while absent days count as missing. Aggregation never silently treats missing days as measured zeroes.

Example PowerShell:

```powershell
$login = Invoke-RestMethod http://127.0.0.1:8000/api/auth/login -Method Post -ContentType 'application/json' -Body '{"email":"you@example.com","password":"your-password"}'
$headers = @{ Authorization = "Bearer $($login.access_token)" }
Invoke-RestMethod http://127.0.0.1:8000/api/readings -Headers $headers
```
