"""Verify startup drops root before executing the API command in an isolated container."""
from pathlib import Path
import subprocess

backend = Path(__file__).resolve().parents[1] / 'backend'
code = r'''
import os, pathlib, pwd, runpy, subprocess, sys
try:
    account = pwd.getpwnam('energy')
except KeyError:
    subprocess.run(['useradd', '--uid', '10001', 'energy'], check=True)
    account = pwd.getpwnam('energy')
folder = pathlib.Path('/tmp/privilege-probe')
folder.mkdir(mode=0o755)
probe = folder / 'uvicorn'
probe.write_text('#!' + sys.executable + '\nimport os, pwd\naccount=pwd.getpwnam("energy")\nassert os.geteuid()==account.pw_uid and os.geteuid()!=0\nassert os.getegid()==account.pw_gid\nassert os.stat(os.environ["MODEL_DIR"]).st_uid==os.geteuid()\nprint("PASS: API command runs as UID", os.geteuid(), "and owns model storage")\n')
probe.chmod(0o755)
os.environ['PATH'] = str(folder) + ':' + os.environ['PATH']
os.environ['MODEL_DIR'] = '/tmp/model-volume-probe'
runpy.run_path('/project/entrypoint.py', run_name='__main__')
'''
result = subprocess.run(['docker','run','--rm','--network','none','--user','0','--entrypoint','python','-v',f'{backend}:/project:ro','aibasedsoilfertilityanalysis-backend:latest','-c',code],text=True,capture_output=True)
print(result.stdout)
if result.returncode:
    print(result.stderr)
    raise SystemExit(result.returncode)
