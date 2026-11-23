# Deployment

## Docker Compose

Install and start Docker Desktop with Linux containers. From the project root, copy `.env.example` to `.env` and replace all three values with independent random hexadecimal secrets. Hex avoids URL-escaping issues in the MySQL connection string. Use `python -c "import secrets; print(secrets.token_hex(32))"` to generate each value.

```powershell
Copy-Item .env.example .env
# Edit .env before starting.
docker compose up --build -d
docker compose ps
docker compose logs backend
```

Open http://localhost:8080. Register your account, then promote it:

```powershell
docker compose exec backend python manage.py make-admin --email you@example.com
```

MySQL and model artifacts persist in named volumes. No database port is exposed. The UI port binds to local loopback by default. Use `docker compose down` to stop; do not delete volumes unless intentionally erasing data. Back up MySQL before upgrades. Schema creation is automatic for a fresh database; existing schema changes require reviewed migrations.

For public deployment, place an HTTPS reverse proxy in front of the frontend and restrict direct API and database access. Add server-side login rate limiting, account recovery, monitoring and secure backups. Set the server timezone to Asia/Kolkata if that is the intended billing calendar. The bundled Compose file is a local academic deployment, not a claim of production hardening.

## Separate services

1. Provision MySQL 8.0.16+ with a private network and a dedicated application account. Initialize the schema using `python manage.py init-db` or `docs/schema.sql`.
2. Run the backend on a Python-capable host with `DATABASE_URL`, `JWT_SECRET`, `MODEL_DIR` and `CORS_ORIGINS` configured through host secrets. Use persistent storage for `MODEL_DIR`.
3. Start one API process: `uvicorn app.main:app --host 0.0.0.0 --port 8000`. Avoid multiple training workers until model write coordination is implemented.
4. Build frontend with `npm ci` then `npm run build`. Serve `frontend/dist` through an HTTPS web server. Proxy `/api` to FastAPI, as shown in `frontend/nginx.conf`.
5. For a separate API domain, set `VITE_API_URL=https://your-api-host` **before building**, then configure that exact frontend origin in backend `CORS_ORIGINS`. The Vite development proxy does not apply to production builds.
6. Verify `/api/health`, login, CSV import, prediction, report download, account isolation and admin controls against MySQL before publishing.

Python/scikit-learn cannot execute in a static frontend host. Keep the Python API on a suitable server; never embed database credentials or JWT signing keys in frontend environment values.
