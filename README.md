# Electricity Usage Analyzer

**AI-Based Electricity Consumption Analysis and Prediction System** — an intermediate final-year academic project. Voltwise is the interface name.

React + Vite · FastAPI · MySQL · SQLAlchemy · scikit-learn · Pandas · NumPy · Recharts · JWT / Argon2.

**Hosted application:** https://electricity-usage-analyzer.vercel.app — frontend on Vercel, FastAPI and MySQL on Railway. See `docs/HOSTED_DEPLOYMENT.md` for live verification, configuration and redeployment details.

Implemented and tested locally. See `docs/VERIFICATION.md` for actual results and remaining browser/deployment verification limits. The included `backend/requirements-lock.txt` records the tested Python package versions; `frontend/package-lock.json` records frontend versions.

## Features

- Account registration and login; protected, user-isolated records and admin permissions.
- Daily consumption create, edit, delete; atomic validated CSV imports and import history.
- Daily / weekly / monthly aggregation with billing-period date controls, coverage, monthly charts, dark theme and responsive navigation.
- Configurable flat-rate bill estimates, with one fixed charge per selected period. All estimates are labelled; no official utility tariff is claimed.
- Random Forest forecasts with persisted per-user models and chronological recursive holdout MAE, RMSE, MAPE. Isolation Forest unusual-usage alerts.
- Appliance CRUD, estimated daily shares, data-informed saving suggestions.
- CSV analytical reports including readings, billing, appliance estimates, anomalies and latest saved predictions.
- Admin user activation controls, tariff configuration, dataset monitoring and platform statistics.

## Windows setup

Prerequisites: Python 3.11–3.13, Node.js 22+, MySQL 8.0.16+ or 8.4, VS Code, PowerShell. No hardware required. PowerShell 7 is recommended for the helper script.

From this project folder:

```powershell
./scripts/setup.ps1
```

Manual equivalent (works without virtual-environment activation):

```powershell
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
Copy-Item backend/.env.example backend/.env
./.venv/Scripts/python.exe -c "import secrets; print(secrets.token_hex(48))"
# Put the generated value in backend/.env as JWT_SECRET.
./.venv/Scripts/python.exe scripts/generate_sample.py
Set-Location frontend
npm ci
npm run build
Set-Location ..
```

Use MySQL Workbench or the MySQL client as an administrator:

```sql
CREATE DATABASE electricity_analyzer CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'energy'@'localhost' IDENTIFIED BY 'your-own-strong-password';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, INDEX, REFERENCES, ALTER ON electricity_analyzer.* TO 'energy'@'localhost';
```

Edit `backend/.env`: set the password in `DATABASE_URL` (URL-encode special characters), a random `JWT_SECRET` of at least 32 characters, and the exact frontend origin in `CORS_ORIGINS`.

Terminal 1:

```powershell
Set-Location backend
../.venv/Scripts/python.exe manage.py init-db
../.venv/Scripts/python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Terminal 2:

```powershell
Set-Location frontend
npm run dev
```

Open http://localhost:5173. API documentation: http://127.0.0.1:8000/docs (interactive OpenAPI) or `/redoc`. Register an account, then sign in. No default users or passwords are created.

### Optional: MySQL through Docker Desktop

With Docker Desktop running, you can use its MySQL container instead of installing MySQL on Windows. On a fresh checkout, run `python scripts/configure_local.py` **before** setup; it generates ignored environment files with independent random secrets and points the backend at port 3307. It preserves existing configuration.

```powershell
python scripts/configure_local.py
docker compose -f compose.yaml -f compose.dev.yaml up -d db
./scripts/setup.ps1
```

Then use the same two development terminals above. The override exposes only the database's development port on local loopback. To stop it: `docker compose -f compose.yaml -f compose.dev.yaml stop db`.

To grant administrator permissions to a registered account, stop neither server; run in another terminal:

```powershell
Set-Location backend
../.venv/Scripts/python.exe manage.py make-admin --email your-email@example.com
```

Sign out and back in to update the navigation. Admin role changes and deactivated accounts are checked against the database on each request.

## Try the complete flow

1. Register, log in, and add a daily reading. Edit it, then try creating a duplicate; the server returns a conflict.
2. Download the synthetic sample on Import data. Import it once. Its 365 daily readings cover 2025; select 2025-01-01 to 2025-12-31 to view it.
3. Switch daily, weekly and monthly views. Check recorded and missing days and the estimated bill.
4. Generate a 7-, 14- or 30-day forecast. The sample forecast begins in January 2026, after its last recorded date. A forecast always starts after the latest reading, even when that date is historical.
5. Add appliances, change their usage and inspect estimated shares. Download a report from Reports.
6. Register a second account to confirm isolation. Promote the first account with `manage.py` and inspect Administration.

The sample is **synthetic**, deterministic and suitable for demonstration only. It contains seasonal and weekly variation and three injected spikes. It is never automatically imported into an account.

## Data and machine learning

`date,kwh` means daily consumed energy, not a cumulative meter register. CSV uploads require exactly this header and UTF-8 encoding. Files over 2 MB, more than 10,000 rows, future dates, negatives, infinities, invalid dates, duplicate dates and existing dates are rejected. A failed import inserts nothing. Blank kWh values are skipped and counted. Daily uniqueness is also enforced by the database.

Training sorts dates and creates a daily index. At least 45 observed days and no more than 20% missing days are required. Missing days are forward-filled from earlier observations, preventing future information from leaking into training. Features are weekday, month, day of year, lag 1, lag 7 and trailing 7-day mean. First seven days are warm-up observations.

The first 80% of feature rows train the evaluation model; the final 20% form an untouched chronological test period. Test forecasts recurse from the training boundary without incorporating test targets. Evaluation scores only originally observed days, excluding imputed targets. MAE and RMSE use kWh; MAPE is a percentage and excludes zero actual values, with the excluded count reported. After evaluation, the production model is refit on all available rows. Future features use prior predictions recursively. No accuracy guarantee or confidence interval is asserted.

Models are stored in `backend/models_cache/`, keyed by internal user ID and dataset fingerprint; unchanged histories reuse the saved model and metrics. Changing readings invalidates that fingerprint at the next training request. Never load model files from untrusted sources. For concurrent or large deployments, move training to a worker queue and use a per-user lock / shared model registry; the academic deployment uses one API process.

Isolation Forest uses kWh values from that user's complete reading history, a fixed random seed and `contamination='auto'`; fewer than 14 readings return an informative empty result. Flags are unusual values, not proof of malfunction. K-Means and ARIMA are optional extensions and are not implemented.

Independent evaluation (does not require a database or account):

```powershell
Set-Location backend
../.venv/Scripts/python.exe train.py ../frontend/public/sample-consumption.csv
```

## Tests

```powershell
Set-Location backend
../.venv/Scripts/python.exe -m pytest -q
Set-Location ../frontend
npm run build
```

API tests use isolated in-memory SQLite with the same SQLAlchemy models, never the configured MySQL database. They cover authentication, ownership checks, duplicates, validation, transactional uploads, billing, model training/loading, reports, appliances, admin permissions and deactivation. A real MySQL environment is separately needed to verify the target database driver and engine constraints. See `docs/TESTING.md` for manual end-to-end checks and recorded verification.

## Structure

```text
backend/
  app/database.py       settings, six normalized ORM tables, database session
  app/main.py           validated REST API and authorization
  app/ml.py             preprocessing, forecasting, evaluation, anomaly detection
  tests/test_api.py     API integration tests
  train.py              standalone CSV evaluation
  manage.py             schema and admin commands
  requirements.txt     Python dependencies
frontend/
  src/main.jsx          authenticated React application and charts
  src/api.js            HTTP client, JWT handling and useful errors
  src/styles.css        responsive light/dark dashboard
  public/sample-consumption.csv
docs/                   API, schema, architecture, testing, deployment
scripts/                Windows setup and sample generation
compose.yaml            MySQL + FastAPI + frontend deployment
```

## Deployment

See `docs/DEPLOYMENT.md` for Docker Compose and separate-service deployment, and `docs/HOSTED_DEPLOYMENT.md` for the verified hosted deployment. This repository does not contain hosted credentials. Keep `.env`, database volumes, model files and backups out of version control.
