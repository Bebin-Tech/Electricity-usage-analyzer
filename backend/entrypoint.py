"""Initialize a mounted model cache, then serve as the unprivileged app user."""
import os

if hasattr(os, 'geteuid') and os.geteuid() == 0:
    import pwd
    account = pwd.getpwnam('energy')
    cache = os.environ.get('MODEL_DIR', '/app/models_cache')
    os.makedirs(cache, exist_ok=True)
    os.chown(cache, account.pw_uid, account.pw_gid)
    os.setgroups([])
    os.setgid(account.pw_gid)
    os.setuid(account.pw_uid)

port = str(int(os.environ.get('PORT', '8000')))
os.execvp('uvicorn', ['uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', port])
