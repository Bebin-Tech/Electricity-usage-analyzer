# Hosted deployment — 23 November 2026

The frontend is deployed to Vercel and connected to the FastAPI API on Railway. MySQL runs on Railway's private network with persistent storage.

| Component | Deployment |
| --- | --- |
| Application | https://electricity-usage-analyzer.vercel.app |
| API documentation | https://electricity-api-production-e75c466f.up.railway.app/docs |
| API health | https://electricity-api-production-e75c466f.up.railway.app/api/health |
| Vercel team | bebin-dotms-projects |
| Vercel project ID | prj_dlcSgObueagPuTQnl0LmkISne8vu |
| Connected frontend deployment | dpl_9Unq4KkLPkyfBRs1JWYte5wga826 — production, READY |
| Railway project ID | 648857c3-da32-46fb-acc8-4b99012e7b4a |
| Railway production environment | cbc29811-16c4-4f02-8eb0-8b6cd5042fb1 |
| Railway API service ID | 0ad790f4-d74f-4725-8610-b2144af67c0a |
| Railway API deployment | d53de55b-77cb-472c-9580-d625bfe60501 — SUCCESS |
| Railway MySQL service ID | 2b861c7f-f308-4ca7-a423-2308aa85aa1a |

No Git repository was present. Deployments used the actual local source files. Frontend source SHA-256: `5ca86bf78eb4f0e89c71c008c4d3284ce4357244171e3c15501a0b3671c9ffe5`. Backend runtime source SHA-256: `2e919cdb3df117258de46fdc6d5dce9c1e8fbf567dcbcbdb9dfa35a09692de3a`.

## Configuration

- Vercel `VITE_API_URL` points to the Railway HTTPS API. `VITE_BACKEND_PENDING=false` enables the real API integration. Both are frontend configuration, not secrets.
- Railway `DATABASE_URL` uses Railway variable references to the private MySQL service; no database port was exposed publicly.
- The production JWT signing key is independently generated and stored in Railway service variables. Local `.env` secrets were not uploaded.
- CORS permits the two stable production Vercel aliases. Unique preview deployment URLs require explicit CORS configuration before using the API.
- A 500 MB model volume is mounted at `/app/models_cache`. The database template has its own persistent data volume.
- Startup prepares model-volume ownership and drops to the `energy` user before executing Uvicorn. An isolated container test verified non-root execution and writable model storage. The API will not serve before the privilege drop completes.
- Backend memory and CPU limits are set to 1 GB and 1 vCPU, with a health check at `/api/health` and sleep mode enabled.

## Completed live checks

`scripts/check_deployed_api.py` ran against the hosted HTTPS API successfully. See `deployed-api-verification.json` for recorded results. Checks covered MySQL readiness, frontend CORS, registration and JWT login, a 365-row import, duplicate prevention, account isolation, monthly analytics, bill estimation, Random Forest training, persisted model loading, anomalies, appliance creation/deletion, CSV reports and admin access protection.

The Vercel production page and its actual JavaScript bundle returned HTTP 200. The deployed bundle contains the Railway API URL and no longer contains the temporary backend-pending message.

Browser automation timed out, so interactive visual verification of the hosted dashboard remains unverified. The real hosted HTTP checks passed.

## Verification fixtures

Two generated test accounts remain in the hosted database, with synthetic consumption on one account. Their random passwords were never written to disk or returned to the user. Exact cleanup identities are recorded only in ignored `.deploy/cloud-smoke-fixtures.json`.

Automated approval review initially rejected a temporary SSH credential and rejected a persistent destructive pre-deploy cleanup hook. The user subsequently explicitly approved a temporary key for one-time cleanup. The SSH connection timed out twice, including a bounded retry after waking the API, so account cleanup was not completed. Each temporary key was successfully revoked and every local key copy was deleted. No database cleanup hook was installed. The exact fixture identities remain available in the ignored metadata file for a later authorized cleanup through a working remote connection. The normal application is usable independently of those private verification accounts.

## Redeployment

For the backend, `python scripts/prepare_backend_deployment.py` stages only runtime files in ignored `.deploy/railway-api`. It refuses unexpected staged files and excludes `.env`, datasets, local databases and model artifacts. Deploy that directory through the Railway CLI using `--path-as-root` and the explicit project, environment and service IDs above. Do not deploy the whole workspace.

For the frontend, deploy `frontend/` to the existing Vercel project. Its `vercel.json` declares the Vite build. Environment changes require a fresh Vercel build. This checkout is not connected to Git autodeploys.
