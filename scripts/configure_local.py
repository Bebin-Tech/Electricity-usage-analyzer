"""Generate local secret files once; never overwrite existing configuration."""
from pathlib import Path
import secrets

root = Path(__file__).resolve().parents[1]
root_env = root / '.env'
if not root_env.exists():
    root_env.write_text(f'MYSQL_PASSWORD={secrets.token_hex(24)}\nMYSQL_ROOT_PASSWORD={secrets.token_hex(24)}\nJWT_SECRET={secrets.token_hex(48)}\n', encoding='utf-8')
values = dict(line.split('=', 1) for line in root_env.read_text(encoding='utf-8').splitlines() if '=' in line and not line.startswith('#'))
backend_env = root / 'backend' / '.env'
if not backend_env.exists():
    backend_env.write_text(f"DATABASE_URL=mysql+pymysql://energy:{values['MYSQL_PASSWORD']}@127.0.0.1:3307/electricity_analyzer\nJWT_SECRET={values['JWT_SECRET']}\nCORS_ORIGINS=[\"http://localhost:5173\",\"http://127.0.0.1:5174\"]\nMODEL_DIR=models_cache\n", encoding='utf-8')
print('Local environment files ready; existing files were preserved.')
