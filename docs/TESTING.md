# Testing

Automated backend integration tests run with an isolated SQLite database, actual password hashing, JWT verification, real CSV parsing and real scikit-learn training. They do not return mocked API data. Execute from `backend`: `../.venv/Scripts/python.exe -m pytest -q`.

Build the frontend from `frontend` with `npm run build`.

With the development MySQL container and schema initialized, run `python scripts/check_mysql_schema.py` from the project root to verify database constraints using transactions that roll back all generated records. With the local API on port 8000, run `../.venv/Scripts/python.exe smoke_mysql.py` from `backend` for a real MySQL import → analytics → forecasting → report check; it cleans up only its generated account and records.

## Manual end-to-end checklist

- With MySQL running, confirm `/api/health` and open `/docs`.
- Register account A, sign in, and verify an empty dashboard has helpful empty states.
- Add, edit and delete readings. Reject negative values, future dates and duplicate daily dates.
- Import the sample. Reimport it and confirm conflict with no additional readings. Try bad headers, malformed rows, non-finite values, oversized files and blank kWh values.
- Select the sample's 2025 dates. Check daily, weekly and monthly totals and graph rendering. Verify the estimate equals kWh × configured rate + one fixed charge.
- Add appliances, change hours and quantity, and check estimated shares. Confirm actual meter readings remain unchanged.
- Generate predictions, inspect non-fabricated metrics and forecast dates, and retry to exercise persisted model loading.
- Download an analytical report and compare its totals, tariff, anomaly flags and forecast with the UI.
- Register B and verify A's data is not visible. Try A's record IDs through B's bearer token; expect 404.
- Promote A with the CLI, reload login, update the tariff and deactivate B. B's existing token must stop working.
- Resize to 390 px and 1440 px, use navigation, theme switch, forms and dialogs. Verify loading, success, validation and API-offline messages.

Record test commands and observed results in `docs/VERIFICATION.md`. A frontend build alone does not establish browser behavior or target MySQL compatibility.
