"""Exercise the real hosted API with generated fixtures, recording only non-secret results."""
import argparse
import json
import secrets
from pathlib import Path
import httpx

parser = argparse.ArgumentParser()
parser.add_argument('base_url')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
fixtures = []
fixture_path = root / '.deploy/cloud-smoke-fixtures.json'
fixture_path.parent.mkdir(parents=True,exist_ok=True)
checks = []


def expect(response, status):
    assert response.status_code == status, f'{response.request.method} {response.request.url.path}: {response.status_code} {response.text[:200]}'
    return response


def account(client):
    email = f'cloud-check-{secrets.token_hex(10)}@example.com'
    password = secrets.token_hex(24)
    user = expect(client.post('/auth/register',json={'name':'Deployment verification','email':email,'password':password}),201).json()
    fixtures.append({'id':user['id'],'email':email})
    fixture_path.write_text(json.dumps(fixtures),encoding='utf-8')
    token = expect(client.post('/auth/login',json={'email':email,'password':password}),200).json()['access_token']
    return {'Authorization':f'Bearer {token}'}


with httpx.Client(base_url=args.base_url.rstrip('/')+'/api',timeout=120) as client:
    assert expect(client.get('/health'),200).json()['status']=='ok'
    checks.append('MySQL-backed health check')
    expect(client.get('/readings'),401)
    origin='https://electricity-usage-analyzer.vercel.app'
    preflight=expect(client.options('/auth/login',headers={'Origin':origin,'Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'content-type'}),200)
    assert preflight.headers['access-control-allow-origin']==origin
    checks.append('Frontend CORS preflight')
    a=account(client)
    b=account(client)
    checks.append('Registration and JWT login')
    sample=(root/'frontend/public/sample-consumption.csv').read_bytes()
    expect(client.post('/uploads',headers=a,files={'file':('synthetic.csv',sample,'text/csv')}),201)
    expect(client.post('/uploads',headers=a,files={'file':('synthetic.csv',sample,'text/csv')}),409)
    rows=expect(client.get('/readings',headers=a),200).json()
    assert len(rows)==365
    assert expect(client.get('/readings',headers=b),200).json()==[]
    expect(client.delete(f'/readings/{rows[0]["id"]}',headers=b),404)
    checks.append('365-row CSV import, duplicate rejection and account isolation')
    result=expect(client.get('/analytics?start=2025-01-01&end=2025-12-31&period=monthly',headers=a),200).json()
    assert result['recorded_days']==365 and len(result['monthly'])==12
    checks.append('Monthly analytics and billing estimate')
    forecast=expect(client.post('/predictions?days=7',headers=a),200).json()
    again=expect(client.post('/predictions?days=7',headers=a),200).json()
    assert forecast['forecast']==again['forecast'] and len(forecast['forecast'])==7
    checks.append('Random Forest training and persisted model loading')
    expect(client.get('/anomalies',headers=a),200)
    appliance=expect(client.post('/appliances',headers=a,json={'name':'Test light','watts':10,'hours_per_day':5,'quantity':2}),201).json()
    assert appliance['daily_kwh']==.1
    expect(client.delete(f'/appliances/{appliance["id"]}',headers=a),204)
    checks.append('Anomaly detection and appliance create/delete')
    report=expect(client.get('/reports?start=2025-01-01&end=2025-12-31',headers=a),200)
    assert 'text/csv' in report.headers['content-type'] and 'Predicted kWh' in report.text
    checks.append('Analytical report download')
    expect(client.get('/admin/users',headers=a),403)
    checks.append('Admin access protection')
    metrics={k:v for k,v in forecast['metrics'].items() if k!='holdout'}
    output={'api_url':args.base_url,'checks':checks,'metrics_on_synthetic_sample':metrics,'status':'passed'}
    (root/'docs/deployed-api-verification.json').write_text(json.dumps(output,indent=2),encoding='utf-8')
    print(json.dumps(output,indent=2))
