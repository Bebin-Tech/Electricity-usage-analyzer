"""One-time approved cleanup through an ephemeral Railway SSH key; always revoke it."""
import base64
import json
import os
import shlex
import subprocess
import urllib.request
from pathlib import Path

root = Path(__file__).resolve().parents[1]
key = Path.home() / '.ssh/id_ed25519_electricity_verification'
public_key = key.with_suffix('.pub')
railway = Path.home() / 'AppData/Local/npm-cache/_npx/79fa66f96c8fdacf/node_modules/@railway/cli/bin/railway.exe'
workspace='c7aa6c8b-91f8-4c7a-855b-f524b55dbf58'
fixtures=json.loads((root/'.deploy/cloud-smoke-fixtures.json').read_text())
fingerprint=subprocess.check_output(['ssh-keygen','-lf',str(public_key)],text=True).split()[1]
source='''import os
from pathlib import Path
from sqlalchemy import delete
from app.database import SessionLocal, User, Reading, Appliance, Dataset, Prediction, settings
fixtures=FIXTURES
api_uids=[]
for status in Path('/proc').glob('[0-9]*/status'):
    try:
        arguments=(status.parent/'cmdline').read_bytes().split(b'\\x00')
        if b'app.main:app' in arguments and any(argument.endswith(b'/uvicorn') or argument==b'uvicorn' for argument in arguments):
            uid_line=next(line for line in status.read_text().splitlines() if line.startswith('Uid:'))
            api_uids.append(int(uid_line.split()[2]))
    except (FileNotFoundError,PermissionError,ProcessLookupError):
        continue
if not api_uids or any(uid==0 for uid in api_uids):
    raise RuntimeError('API process must execute as an unprivileged user')
removed=[]
with SessionLocal() as db:
    for item in fixtures:
        user=db.get(User,item['id'])
        if user is None:
            continue
        if user.email!=item['email'] or user.name!='Deployment verification' or user.is_admin:
            raise RuntimeError('Fixture identity mismatch; nothing committed')
        for model in [Reading,Appliance,Dataset,Prediction]:
            db.execute(delete(model).where(model.user_id==user.id))
        db.delete(user)
        removed.append(user.id)
    db.commit()
    assert all(db.get(User,item['id']) is None for item in fixtures)
for identifier in removed:
    (Path(settings.model_dir)/f'user_{identifier}.joblib').unlink(missing_ok=True)
print('PASS: removed generated test accounts:',len(removed))
print('PASS: API process UIDs:',api_uids)
'''.replace('FIXTURES',repr(fixtures))
encoded=base64.b64encode(source.encode()).decode()
command='python -c '+shlex.quote(f'exec(__import__("base64").b64decode("{encoded}"))')
try:
    with urllib.request.urlopen('https://electricity-api-production-e75c466f.up.railway.app/api/health',timeout=30) as response:
        assert response.status==200
    process=subprocess.Popen([str(railway),'ssh','--project','648857c3-da32-46fb-acc8-4b99012e7b4a','--service','0ad790f4-d74f-4725-8610-b2144af67c0a','--environment','cbc29811-16c4-4f02-8eb0-8b6cd5042fb1','--identity-file',str(key),'--',command],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,stdin=subprocess.DEVNULL)
    try:
        stdout,stderr=process.communicate(timeout=45)
    except subprocess.TimeoutExpired:
        if os.name=='nt':
            subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True,timeout=10)
        process.kill()
        process.communicate(timeout=10)
        raise RuntimeError('SSH connection timed out; temporary key will be revoked') from None
    print(stdout)
    if process.returncode:
        print(stderr)
        raise SystemExit(process.returncode)
finally:
    revoked=subprocess.run([str(railway),'ssh','keys','remove',fingerprint,'--workspace',workspace],text=True,capture_output=True,stdin=subprocess.DEVNULL,timeout=60)
    print(revoked.stdout)
    if revoked.returncode:
        print(revoked.stderr)
        raise RuntimeError('Temporary key revocation failed; local key retained for recovery')
    key.unlink(missing_ok=True)
    public_key.unlink(missing_ok=True)
    (root/'.deploy/railway-verification-key').unlink(missing_ok=True)
    (root/'.deploy/railway-verification-key.pub').unlink(missing_ok=True)
    print('PASS: temporary SSH key revoked and local key files removed')
