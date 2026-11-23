# Architecture and phase map

Browser → React/Vite → same-origin `/api` → FastAPI → SQLAlchemy → MySQL.
FastAPI invokes scikit-learn / Pandas in synchronous worker threads for training and inference. Model artifacts live on a private server-side filesystem. Reports are generated on request; raw uploaded files are validated then discarded, while import metadata and readings persist.

| Phase | Implementation | Verification |
| --- | --- | --- |
| 1 Architecture | This document, source tree, environment examples | Structure inspection |
| 2 Database / backend | Six ORM entities, MySQL DDL, dependency injection | Schema compilation and API tests |
| 3 Authentication | Argon2, expiring HS256 JWT, current-user and admin dependencies | Invalid credentials, anonymous access, cross-user mutations, deactivation |
| 4 Frontend | React/Vite, responsive sidebar, themes, shared HTTP client | Production build and browser checklist |
| 5 Readings / import | CRUD, daily uniqueness, transactional CSV | Invalid data, duplicate dates, rollback |
| 6 ML | Past-only features, recursive chronological holdout, persistence | Training and cached inference integration test |
| 7 Analytics | Period aggregation, Recharts, coverage, estimates, alerts | Known-value bill checks and date filters |
| 8 Reports / admin | CSV export, user access controls, tariff and dataset management | Export content and admin authorization tests |
| 9 Testing | Pytest integration suite and manual UI checks | `docs/TESTING.md` |
| 10 Deployment | Dockerfiles, Compose, Windows setup | Build checks; environment-dependent live deployment |

The server controls identity and ownership; the UI's visibility rules are not authorization. Registration never accepts an admin role. Every record lookup for user mutations includes an ownership check; analytics, downloads and forecasts select records only for the authenticated user. Deactivating an account prevents use of existing tokens. Tokens expire after eight hours and are held in browser session storage; logout clears the token, though a copied token remains valid until expiry unless the account is deactivated.

The global tariff table contains the active flat-rate configuration at ID 1. Its calculation is isolated in `analytics_data` for future replacement by versioned regional slab policies. For Tamil Nadu expansion, add effective dates, service category, slab boundaries, billing cycle, fixed charges and concession eligibility, then validate against current official schedules. Current estimates do not implement those rules.

Readings are daily aggregates with a composite user/date key. Appliances belong to a single user. Predictions retain a timestamped evaluation/forecast JSON snapshot. Dataset records track imported source names and counts without storing raw private files. Foreign keys tie user-owned records to users. Accounts are deactivated rather than deleted to preserve relational history.

The current academic app loads user histories in memory and trains in request workers. Large-scale pagination, background jobs, login rate limiting, password reset, email verification, refresh-token rotation, migrations and audit trails are future production improvements. Do not run multiple training workers writing the same model directory without adding coordination.
