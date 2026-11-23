# Verification record — 23 November 2026

This records the initial local implementation checks. A subsequent Vercel + Railway deployment succeeded; see `HOSTED_DEPLOYMENT.md` and `deployed-api-verification.json` for the current hosted application and live checks.

## Automated backend and ML checks

`python -m pytest -q` from `backend`: **7 passed**, 17.23 seconds on the final run. One dependency deprecation warning remains: the installed Starlette test client advises migrating from httpx to httpx2. It did not fail tests or affect the running API.

Coverage includes login failures, JWT protection, password-hash exclusion, cross-account access, duplicate readings, future and negative values, CSV validation and transactional rollback, appliance calculations and bounds, billing, forecast training and persisted loading, report content, CSV formula safety, admin permissions, account deactivation, past-only missing-value filling, zero-value MAPE handling, spike detection and exclusion of imputed evaluation targets.

`python -m pip check`: **No broken requirements found**. `python -m compileall -q backend scripts`: passed.

## Target MySQL checks

MySQL 8.4 container: healthy. Applied `docs/schema.sql` to the confirmed-empty database successfully. `python scripts/check_mysql_schema.py`: passed all six-table, daily uniqueness, user foreign key, nonnegative reading, appliance-hour, tariff-rate and transaction cleanup checks.

Live FastAPI running against that MySQL instance: `python smoke_mysql.py` exited successfully. It registered and logged in a generated account, imported **365** sample rows, returned **12** monthly buckets, trained a **7-day** forecast, downloaded a report including prediction metrics, and rejected normal-user access to admin routes. The generated account, related rows and its model artifact were cleaned up by the test.

## Actual sample evaluation

`python train.py ../frontend/public/sample-consumption.csv`: passed. Complete measured results are in `sample-evaluation.json`.

| Measure | Result |
| --- | --- |
| Dataset | 365 synthetic daily readings, 2025 |
| Training feature rows | 286, after 7 warm-up days |
| Chronological holdout | 72 observed days |
| MAE | 1.033137 kWh |
| RMSE | 1.211319 kWh |
| MAPE | 13.637314% |
| Imputed days | 0 |
| Zero targets excluded from MAPE | 0 |

These figures describe this synthetic dataset only and do not establish performance on real household data.

## Frontend and browser checks

`npm run build`: passed after the final UI changes. Recharts is separated into its own bundle. The development page returned HTTP 200. Desktop sign-in layout was visually inspected; a 390-pixel mobile check reported document width 390 with no horizontal overflow.

The browser control connection later timed out repeatedly, including after reset, so **authenticated dashboard interaction and visual QA remain unverified in the browser**. The live API flow above passed, but it does not substitute for the remaining manual browser checklist in `TESTING.md`.

## Deployment checks and limitations

`docker compose -f compose.yaml -f compose.dev.yaml config --quiet`: passed. The database service started successfully.

The complete Docker image build could not finish because Docker Hub returned a TLS handshake timeout while resolving `node:22-alpine`; the other image resolutions were cancelled. Thus the full Compose application deployment is **not verified**. Native Windows API and frontend builds were verified as described above. No public deployment was attempted.

Environment files contain generated local secrets and are ignored. No default account or user consumption data was seeded into the application. Development services were used for verification; follow the README to start the project.
