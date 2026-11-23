"""Administrative commands. Run from backend with the same .env as the API."""
import argparse
from sqlalchemy import select
from app.database import Base, engine, SessionLocal, User, Tariff

parser = argparse.ArgumentParser()
parser.add_argument('command', choices=['init-db', 'make-admin', 'schema'])
parser.add_argument('--email')
args = parser.parse_args()
if args.command == 'schema':
    from sqlalchemy.schema import CreateTable
    from sqlalchemy.dialects import mysql
    for table in Base.metadata.sorted_tables:
        print(str(CreateTable(table).compile(dialect=mysql.dialect())) + ';')
else:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.get(Tariff, 1) is None:
            db.add(Tariff(id=1))
        if args.command == 'make-admin':
            user = db.scalar(select(User).where(User.email == (args.email or '').lower()))
            if not user:
                raise SystemExit('Register this account first, then provide --email')
            user.is_admin = True
        db.commit()
    print('Done')
