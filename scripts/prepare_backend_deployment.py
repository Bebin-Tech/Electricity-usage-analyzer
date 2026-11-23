"""Stage only runtime source; never upload environment files, user data or model artifacts."""
from pathlib import Path
import hashlib
import json
import shutil

root = Path(__file__).resolve().parents[1]
source = root / 'backend'
target = root / '.deploy' / 'railway-api'
names = ['Dockerfile','.dockerignore','requirements.txt','requirements-lock.txt','manage.py','entrypoint.py','railway.json']
names += [str(path.relative_to(source)).replace('\\','/') for path in (source/'app').glob('*.py')]
target.mkdir(parents=True,exist_ok=True)
allowed = set(names)
existing = {str(path.relative_to(target)).replace('\\','/') for path in target.rglob('*') if path.is_file()}
if existing - allowed:
    raise SystemExit('Unexpected staged files found. Review the deployment directory before uploading.')
digest = hashlib.sha256()
for name in sorted(names):
    output = target / name
    output.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(source/name, output)
    digest.update(name.encode()+b'\0'+output.read_bytes())
print(json.dumps({'files':len(names),'source_sha256':digest.hexdigest(),'path':str(target)}))
