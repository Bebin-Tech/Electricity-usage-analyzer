import os
import tempfile
from pathlib import Path
from datetime import date, timedelta
os.environ['DATABASE_URL'] = 'sqlite://'
os.environ['JWT_SECRET'] = 'test-only-secret-with-more-than-32-characters'
os.environ['MODEL_DIR'] = tempfile.mkdtemp()
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from app import database
database.engine = create_engine('sqlite://', connect_args={'check_same_thread':False}, poolclass=StaticPool)
database.SessionLocal.configure(bind=database.engine)
from app import main
main.engine = database.engine
import pytest


@pytest.fixture()
def client():
    database.Base.metadata.drop_all(database.engine)
    with TestClient(main.app) as client:
        yield client


def account(client, email='one@example.com'):
    assert client.post('/api/auth/register', json={'name':'Test User','email':email,'password':'test-password-123'}).status_code == 201
    result = client.post('/api/auth/login',json={'email':email,'password':'test-password-123'})
    assert result.status_code == 200
    return {'Authorization': 'Bearer ' + result.json()['access_token']}


def test_auth_and_isolation(client):
    assert client.get('/api/readings').status_code == 401
    a = account(client)
    b = account(client, 'two@example.com')
    row = client.post('/api/readings',headers=a,json={'date':'2025-01-01','kwh':5}).json()
    assert client.get('/api/readings',headers=b).json() == []
    assert client.delete(f'/api/readings/{row["id"]}',headers=b).status_code == 404
    assert client.put(f'/api/readings/{row["id"]}',headers=b,json={'date':'2025-01-01','kwh':9}).status_code == 404
    assert client.get('/api/admin/users',headers=a).status_code == 403
    assert 'password_hash' not in client.get('/api/auth/me',headers=a).text
    assert client.get('/api/predictions/history',headers=b).json()==[]
    assert client.get('/api/uploads',headers=b).json()==[]
    assert client.post('/api/auth/login',json={'email':'one@example.com','password':'incorrect'}).status_code == 401


def test_readings_and_billing(client):
    a=account(client)
    payload={'date':'2025-01-01','kwh':10}
    response=client.post('/api/readings',headers=a,json=payload)
    assert response.status_code == 201
    assert client.post('/api/readings',headers=a,json=payload).status_code == 409
    assert client.post('/api/readings',headers=a,json={'date':'2025-01-02','kwh':-1}).status_code == 422
    assert client.post('/api/readings',headers=a,json={'date':'2099-01-01','kwh':1}).status_code == 422
    result=client.get('/api/analytics?start=2025-01-01&end=2025-01-31',headers=a).json()
    assert result['estimated_bill']==60
    assert result['missing_days']==30
    assert client.get('/api/analytics?start=2025-02-01&end=2025-01-01',headers=a).status_code == 422
    assert client.put(f'/api/readings/{response.json()["id"]}',headers=a,json={'date':'2025-01-01','kwh':20}).status_code==200
    assert client.delete(f'/api/readings/{response.json()["id"]}',headers=a).status_code==204


def test_csv_transaction_validation(client):
    a=account(client)
    def upload(text):
        return client.post('/api/uploads',headers=a,files={'file':('test.csv',text,'text/csv')})
    assert upload('date,kwh\n2025-01-01,10\n2025-01-02,NaN').status_code==422
    assert client.get('/api/readings',headers=a).json()==[]
    assert upload('date,kwh\n2025-01-01,10\n2025-01-01,20').status_code==422
    result=upload('date,kwh\n2025-01-01,10\n2025-01-02,\n2025-01-03,12')
    assert result.json()=={'imported':2,'skipped_missing_kwh':1}
    assert upload('date,kwh\n2025-01-01,10\n2025-01-04,12').status_code==409
    assert len(client.get('/api/readings',headers=a).json())==2
    assert client.post('/api/uploads',headers=a,files={'file':('bad.txt','date,kwh')}).status_code==422
    assert upload('date,kwh\n2025-01-05,10,extra').status_code==422


def test_forecast_appliances_reports_admin(client):
    a=account(client)
    assert client.post('/api/predictions',headers=a).status_code==422
    assert client.get('/api/anomalies',headers=a).json()['alerts']==[]
    csv='date,kwh\n'+'\n'.join(f'{date(2025,1,1)+timedelta(days=i)},{8+i%7}' for i in range(90))
    assert client.post('/api/uploads',headers=a,files={'file':('sample.csv',csv)}).status_code==201
    forecast=client.post('/api/predictions?days=7',headers=a)
    assert forecast.status_code==200,forecast.text
    result=forecast.json()
    assert len(result['forecast'])==7 and result['metrics']['test_days']>0
    assert result['metrics']['rmse']>=result['metrics']['mae']
    assert len(client.get('/api/predictions/history',headers=a).json())==1
    assert client.post('/api/predictions?days=7',headers=a).json()['forecast']==result['forecast']
    app=client.post('/api/appliances',headers=a,json={'name':'=unsafe','watts':1000,'hours_per_day':2,'quantity':2})
    assert app.json()['daily_kwh']==4
    assert client.post('/api/appliances',headers=a,json={'name':'Bad','watts':100,'hours_per_day':25,'quantity':1}).status_code==422
    assert client.put(f'/api/appliances/{app.json()["id"]}',headers=a,json={'name':'=unsafe','watts':500,'hours_per_day':2,'quantity':2}).json()['daily_kwh']==2
    b=account(client,'two@example.com')
    assert client.delete(f'/api/appliances/{app.json()["id"]}',headers=b).status_code==404
    report=client.get('/api/reports?start=2025-01-01&end=2025-03-31',headers=a)
    assert report.status_code==200 and "'=unsafe" in report.text and 'mae' in report.text
    with database.SessionLocal() as db:
        user=db.get(database.User,1);user.is_admin=True;db.commit()
    assert client.get('/api/admin/stats',headers=a).json()['readings']==90
    assert client.put('/api/admin/tariff',headers=a,json={'name':'Test','rate_per_kwh':2,'fixed_charge':10,'currency':'INR'}).status_code==200
    assert client.get('/api/analytics?start=2025-01-01&end=2025-01-01',headers=a).json()['estimated_bill']==26
    assert client.patch('/api/admin/users/1',headers=a,json={'active':False}).status_code==422
    assert client.patch('/api/admin/users/2',headers=a,json={'active':False}).status_code==200
    assert client.get('/api/readings',headers=b).status_code==401
