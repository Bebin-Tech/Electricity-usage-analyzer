"""Check target-engine constraints using disposable transactions, without Python DB dependencies."""
import secrets
import subprocess

command = ['docker', 'compose', 'exec', '-T', 'db', 'sh', '-c', 'env MYSQL_PWD="$MYSQL_PASSWORD" mysql -u energy --batch --skip-column-names electricity_analyzer']


def execute(sql):
    return subprocess.run(command, input=sql, text=True, capture_output=True)


tables = execute('SHOW TABLES;')
assert tables.returncode == 0, tables.stderr
assert set(tables.stdout.split()) == {'users','readings','appliances','tariff_settings','prediction_history','uploaded_datasets'}, tables.stdout
email = f'schema-{secrets.token_hex(8)}@example.com'
prefix = f"START TRANSACTION; INSERT INTO users (name,email,password_hash,is_admin,active,created_at) VALUES ('Schema test','{email}','not-a-login-hash',0,1,UTC_TIMESTAMP()); SET @test_user=LAST_INSERT_ID(); "
cases = [
    ("INSERT INTO readings (user_id,date,kwh,source) VALUES (@test_user,'2025-01-01',1,'manual'); INSERT INTO readings (user_id,date,kwh,source) VALUES (@test_user,'2025-01-01',2,'manual');", '1062', 'daily uniqueness'),
    ("INSERT INTO readings (user_id,date,kwh,source) VALUES (@test_user,'2025-01-01',-1,'manual');", '3819', 'nonnegative consumption'),
    ("INSERT INTO readings (user_id,date,kwh,source) VALUES (-1,'2025-01-01',1,'manual');", '1452', 'user foreign key'),
    ("INSERT INTO appliances (user_id,name,watts,hours_per_day,quantity) VALUES (@test_user,'test',10,25,1);", '3819', 'appliance hours'),
    ("INSERT INTO tariff_settings (name,rate_per_kwh,fixed_charge,currency) VALUES ('test',-1,0,'INR');", '3819', 'tariff rate'),
]
for sql, expected, label in cases:
    result = execute(prefix + sql + ' ROLLBACK;')
    assert result.returncode != 0 and expected in result.stderr, (label, result.stderr)
    print(f'PASS: {label}')
remaining = execute(f"SELECT COUNT(*) FROM users WHERE email='{email}';")
assert remaining.stdout.strip() == '0', 'Fixture rollback failed'
print('PASS: all six tables and transaction cleanup')
