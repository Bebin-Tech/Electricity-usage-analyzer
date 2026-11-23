"""Run against a local live API and clean up only this script's generated records."""
import json
import secrets
from pathlib import Path
import httpx
from sqlalchemy import delete, select
from app.database import SessionLocal, User, Reading, Appliance, Dataset, Prediction, settings

email = f'smoke-{secrets.token_hex(6)}@example.com'
password = secrets.token_hex(16)
user_id = None
try:
    with httpx.Client(base_url='http://127.0.0.1:8000/api', timeout=120) as client:
        assert client.get('/health').status_code == 200
        register = client.post('/auth/register', json={'name':'Integration test','email':email,'password':password})
        assert register.status_code == 201, register.text
        user_id = register.json()['id']
        login = client.post('/auth/login', json={'email':email,'password':password})
        assert login.status_code == 200, login.text
        client.headers['Authorization'] = 'Bearer ' + login.json()['access_token']
        sample = Path(__file__).resolve().parents[1] / 'frontend/public/sample-consumption.csv'
        with sample.open('rb') as file:
            imported = client.post('/uploads', files={'file':('sample.csv',file,'text/csv')})
        assert imported.status_code == 201, imported.text
        assert imported.json()['imported'] == 365
        analytics = client.get('/analytics',params={'start':'2025-01-01','end':'2025-12-31','period':'monthly'})
        assert analytics.status_code == 200 and len(analytics.json()['series'])==12, analytics.text
        forecast = client.post('/predictions?days=7')
        assert forecast.status_code == 200, forecast.text
        assert len(forecast.json()['forecast']) == 7
        report = client.get('/reports?start=2025-01-01&end=2025-12-31')
        assert report.status_code == 200 and 'Predicted kWh' in report.text
        assert client.get('/admin/users').status_code == 403
        print(json.dumps({'database':'MySQL','imported':365,'monthly_buckets':12,'report_download':'passed','authorization':'passed','metrics':forecast.json()['metrics']},indent=2))
finally:
    if user_id:
        with SessionLocal() as db:
            for model in [Reading,Appliance,Dataset,Prediction]:
                db.execute(delete(model).where(model.user_id==user_id))
            db.execute(delete(User).where(User.id==user_id,User.email==email))
            db.commit()
        artifact = Path(settings.model_dir) / f'user_{user_id}.joblib'
        artifact.unlink(missing_ok=True)
