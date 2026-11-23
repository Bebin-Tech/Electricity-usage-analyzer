import csv
import io
import json
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from typing import Annotated
import jwt
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field, field_validator
from pwdlib import PasswordHash
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .database import Base, engine, get_db, settings, User, Reading, Appliance, Tariff, Dataset, Prediction
from .ml import forecast, anomalies

passwords = PasswordHash.recommended()
bearer = HTTPBearer(auto_error=False)
Db = Annotated[Session, Depends(get_db)]


@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        if db.get(Tariff, 1) is None:
            db.add(Tariff(id=1))
            db.commit()
    yield


app = FastAPI(title='Electricity Usage Analyzer API', version='1.0.0', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=['*'], allow_headers=['*'])


class Registration(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)

    @field_validator('name')
    @classmethod
    def clean_name(cls, value):
        if not value.strip():
            raise ValueError('Name is required')
        return value.strip()


class Login(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


class ReadingIn(BaseModel):
    date: date
    kwh: float = Field(ge=0, le=100000, allow_inf_nan=False)

    @field_validator('date')
    @classmethod
    def past_day(cls, value):
        if value > date.today():
            raise ValueError('Readings cannot be in the future')
        return value


class ApplianceIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    watts: float = Field(gt=0, le=100000, allow_inf_nan=False)
    hours_per_day: float = Field(ge=0, le=24, allow_inf_nan=False)
    quantity: int = Field(ge=1, le=1000)


class TariffIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    rate_per_kwh: float = Field(ge=0, le=10000, allow_inf_nan=False)
    fixed_charge: float = Field(ge=0, le=100000, allow_inf_nan=False)
    currency: str = Field(pattern='^[A-Z]{3}$')


class ActiveIn(BaseModel):
    active: bool


def public_user(user):
    return {'id': user.id, 'name': user.name, 'email': user.email, 'is_admin': user.is_admin, 'active': user.active}


def current_user(db: Db, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
    try:
        payload = jwt.decode(credentials.credentials if credentials else '', settings.jwt_secret, algorithms=['HS256'])
        user = db.get(User, int(payload['sub']))
        if not user or not user.active:
            raise ValueError()
        return user
    except (jwt.PyJWTError, ValueError, KeyError, TypeError):
        raise HTTPException(401, 'Please log in again', headers={'WWW-Authenticate': 'Bearer'})


Current = Annotated[User, Depends(current_user)]


def admin_user(user: Current):
    if not user.is_admin:
        raise HTTPException(403, 'Administrator access required')
    return user


Admin = Annotated[User, Depends(admin_user)]


def owned(db, model, identifier, user):
    obj = db.get(model, identifier)
    if obj is None or obj.user_id != user.id:
        raise HTTPException(404, 'Record not found')
    return obj


def readings(db, user):
    return list(db.scalars(select(Reading).where(Reading.user_id == user.id).order_by(Reading.date)))


def reading_dict(r):
    return {'id': r.id, 'date': r.date.isoformat(), 'kwh': r.kwh, 'source': r.source}


@app.get('/api/health')
def health(db: Db):
    db.execute(select(1))
    return {'status': 'ok'}


@app.post('/api/auth/register', status_code=201)
def register(data: Registration, db: Db):
    user = User(name=data.name, email=str(data.email).lower(), password_hash=passwords.hash(data.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'An account with this email already exists')
    return public_user(user)


@app.post('/api/auth/login')
def login(data: Login, db: Db):
    user = db.scalar(select(User).where(User.email == str(data.email).lower()))
    # Always verify a hash, so nonexistent accounts do not take a fast path.
    target = user.password_hash if user else DUMMY_HASH
    valid = passwords.verify(data.password, target)
    if not user or not valid or not user.active:
        raise HTTPException(401, 'Invalid email or password')
    token = jwt.encode({'sub': str(user.id), 'exp': datetime.now(timezone.utc) + timedelta(hours=8)}, settings.jwt_secret, algorithm='HS256')
    return {'access_token': token, 'token_type': 'bearer', 'user': public_user(user)}


DUMMY_HASH = passwords.hash('not-a-user-password')


@app.get('/api/auth/me')
def me(user: Current):
    return public_user(user)


@app.get('/api/readings')
def list_readings(db: Db, user: Current):
    return [reading_dict(r) for r in readings(db, user)]


@app.post('/api/readings', status_code=201)
def add_reading(data: ReadingIn, db: Db, user: Current):
    obj = Reading(user_id=user.id, **data.model_dump())
    db.add(obj)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'A reading already exists for this day')
    return reading_dict(obj)


@app.put('/api/readings/{identifier}')
def update_reading(identifier: int, data: ReadingIn, db: Db, user: Current):
    obj = owned(db, Reading, identifier, user)
    obj.date, obj.kwh = data.date, data.kwh
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'A reading already exists for this day')
    return reading_dict(obj)


@app.delete('/api/readings/{identifier}', status_code=204)
def delete_reading(identifier: int, db: Db, user: Current):
    db.delete(owned(db, Reading, identifier, user))
    db.commit()


@app.post('/api/uploads', status_code=201)
def upload(db: Db, user: Current, file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith('.csv'):
        raise HTTPException(422, 'Choose a .csv file with date,kwh columns')
    raw = file.file.read(2_000_001)
    if len(raw) > 2_000_000:
        raise HTTPException(413, 'CSV size limit is 2 MB')
    try:
        reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
        if reader.fieldnames != ['date', 'kwh']:
            raise ValueError('Header must be exactly date,kwh')
        items, seen, missing = [], set(), 0
        for index, row in enumerate(reader, start=2):
            if index > 10001:
                raise ValueError('Maximum 10,000 rows per upload')
            if None in row or None in row.values():
                raise ValueError(f'Row {index}: invalid column count')
            if not row['kwh'].strip():
                missing += 1
                continue
            try:
                parsed = ReadingIn(date=date.fromisoformat(row['date']), kwh=float(row['kwh']))
            except (ValueError, TypeError):
                raise ValueError(f'Row {index}: use YYYY-MM-DD and a finite non-negative kWh value')
            if parsed.date in seen:
                raise ValueError(f'Row {index}: duplicate date within this file')
            seen.add(parsed.date)
            items.append(parsed)
        if not items:
            raise ValueError('No usable readings found')
    except (UnicodeError, ValueError, csv.Error) as exc:
        raise HTTPException(422, str(exc))
    existing = set(db.scalars(select(Reading.date).where(Reading.user_id == user.id, Reading.date.in_(seen))))
    if existing:
        raise HTTPException(409, f'{len(existing)} dates already exist. Import cancelled; edit or remove those dates first.')
    db.add_all([Reading(user_id=user.id, source='csv', **item.model_dump()) for item in items])
    db.add(Dataset(user_id=user.id, filename=file.filename.replace('\\', '/').split('/')[-1][:255], row_count=len(items)))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Duplicate dates detected; no rows imported')
    return {'imported': len(items), 'skipped_missing_kwh': missing}


@app.get('/api/uploads')
def uploads(db: Db, user: Current):
    return list(db.scalars(select(Dataset).where(Dataset.user_id == user.id).order_by(Dataset.uploaded_at.desc())))


@app.get('/api/tariff')
def tariff(db: Db, user: Current):
    return db.get(Tariff, 1)


def analytics_data(db, user, start, end, period):
    if start > end:
        raise HTTPException(422, 'Start date must be before end date')
    rows = [r for r in readings(db, user) if start <= r.date <= end]
    tariff = db.get(Tariff, 1)
    total = sum(r.kwh for r in rows)
    grouped = {}
    monthly = {}
    for r in rows:
        day = r.date if period == 'daily' else r.date - timedelta(days=r.date.weekday()) if period == 'weekly' else r.date.replace(day=1)
        key = day.isoformat()
        grouped[key] = grouped.get(key, 0) + r.kwh
        month = r.date.strftime('%Y-%m')
        monthly[month] = monthly.get(month, 0) + r.kwh
    apps = list(db.scalars(select(Appliance).where(Appliance.user_id == user.id)))
    tips = ['Switch off standby devices and compare the next week with your baseline.', 'Record every day to improve forecast reliability.']
    if rows:
        peak = max(rows, key=lambda r: r.kwh)
        tips.insert(0, f'Review appliance use on {peak.date.isoformat()}, your highest recorded day in this period ({peak.kwh:.1f} kWh).')
    if apps:
        largest = max(apps, key=lambda a: a.watts * a.hours_per_day * a.quantity)
        tips.insert(0, f'Using {largest.name} one hour less per day would save approximately {largest.watts * largest.quantity / 1000 * 30:.1f} kWh over 30 days.')
    return {'total_kwh': round(total, 3), 'average_kwh': round(total / len(rows), 3) if rows else 0,
            'recorded_days': len(rows), 'missing_days': (end - start).days + 1 - len(rows),
            'estimated_bill': round(total * tariff.rate_per_kwh + tariff.fixed_charge, 2) if rows else 0,
            'currency': tariff.currency, 'rate_per_kwh': tariff.rate_per_kwh, 'fixed_charge': tariff.fixed_charge,
            'start': start.isoformat(), 'end': end.isoformat(), 'series': [{'date': k, 'kwh': round(v, 3)} for k, v in grouped.items()],
            'monthly': [{'month': k, 'kwh': round(v, 3)} for k, v in monthly.items()], 'recommendations': tips,
            'bill_notice': 'Estimate for recorded consumption only. One fixed charge per selected billing period; excludes taxes, concessions and slab tariffs. Not an official bill.'}


@app.get('/api/analytics')
def analytics(db: Db, user: Current, start: date | None = None, end: date | None = None, period: str = Query('daily', pattern='^(daily|weekly|monthly)$')):
    end = end or date.today()
    return analytics_data(db, user, start or end.replace(day=1), end, period)


@app.post('/api/predictions')
def predict(db: Db, user: Current, days: int = Query(7, ge=1, le=30)):
    try:
        result = forecast(readings(db, user), user.id, settings.model_dir, days)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    db.add(Prediction(user_id=user.id, result_json=json.dumps(result)))
    db.commit()
    return result


@app.get('/api/predictions/history')
def prediction_history(db: Db, user: Current):
    return [{'id': p.id, 'created_at': p.created_at, 'result': json.loads(p.result_json)} for p in db.scalars(select(Prediction).where(Prediction.user_id == user.id).order_by(Prediction.id.desc()).limit(20))]


@app.get('/api/anomalies')
def detect(db: Db, user: Current):
    return anomalies(readings(db, user))


def appliance_dict(a):
    return {'id': a.id, 'name': a.name, 'watts': a.watts, 'hours_per_day': a.hours_per_day, 'quantity': a.quantity, 'daily_kwh': round(a.watts * a.hours_per_day * a.quantity / 1000, 3)}


@app.get('/api/appliances')
def list_appliances(db: Db, user: Current):
    return [appliance_dict(a) for a in db.scalars(select(Appliance).where(Appliance.user_id == user.id))]


@app.post('/api/appliances', status_code=201)
def add_appliance(data: ApplianceIn, db: Db, user: Current):
    a = Appliance(user_id=user.id, **data.model_dump())
    db.add(a)
    db.commit()
    return appliance_dict(a)


@app.put('/api/appliances/{identifier}')
def update_appliance(identifier: int, data: ApplianceIn, db: Db, user: Current):
    a = owned(db, Appliance, identifier, user)
    for key, value in data.model_dump().items():
        setattr(a, key, value)
    db.commit()
    return appliance_dict(a)


@app.delete('/api/appliances/{identifier}', status_code=204)
def delete_appliance(identifier: int, db: Db, user: Current):
    db.delete(owned(db, Appliance, identifier, user))
    db.commit()


def safe_csv(value):
    text = str(value)
    return "'" + text if text.startswith(('=', '+', '-', '@', '\t', '\r')) else text


@app.get('/api/reports')
def report(db: Db, user: Current, start: date | None = None, end: date | None = None):
    end = end or date.today()
    start = start or end.replace(day=1)
    data = analytics_data(db, user, start, end, 'daily')
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(['Electricity Usage Analyzer', 'Analytical report'])
    writer.writerow(['Period', str(start), str(end)])
    writer.writerow(['Notice', data['bill_notice']])
    for key in ['total_kwh', 'average_kwh', 'recorded_days', 'missing_days', 'estimated_bill', 'currency', 'rate_per_kwh', 'fixed_charge']:
        writer.writerow([key, data[key]])
    writer.writerow([])
    writer.writerow(['date', 'kwh'])
    writer.writerows([[row['date'], row['kwh']] for row in data['series']])
    writer.writerow([])
    writer.writerow(['Appliance', 'Estimated daily kWh'])
    writer.writerows([[safe_csv(a['name']), a['daily_kwh']] for a in list_appliances(db, user)])
    writer.writerow([])
    writer.writerow(['Energy-saving recommendations'])
    writer.writerows([[safe_csv(tip)] for tip in data['recommendations']])
    writer.writerow([])
    writer.writerow(['Anomaly date', 'kWh', 'Direction'])
    writer.writerows([[a['date'], a['kwh'], a['direction']] for a in anomalies(readings(db, user))['alerts'] if start.isoformat() <= a['date'] <= end.isoformat()])
    latest = db.scalar(select(Prediction).where(Prediction.user_id == user.id).order_by(Prediction.id.desc()).limit(1))
    if latest:
        result = json.loads(latest.result_json)
        writer.writerow([])
        writer.writerow(['Latest forecast generated', latest.created_at.isoformat()])
        writer.writerow(['Forecast date', 'Predicted kWh'])
        writer.writerows([[p['date'], p['kwh']] for p in result['forecast']])
        for key in ['mae', 'rmse', 'mape']:
            writer.writerow([key, result['metrics'][key]])
    return Response(stream.getvalue(), media_type='text/csv', headers={'Content-Disposition': f'attachment; filename="energy-report-{start}-{end}.csv"'})


@app.get('/api/admin/stats')
def admin_stats(db: Db, admin: Admin):
    return {'users': db.scalar(select(func.count(User.id))), 'readings': db.scalar(select(func.count(Reading.id))), 'datasets': db.scalar(select(func.count(Dataset.id))), 'predictions': db.scalar(select(func.count(Prediction.id))), 'total_kwh': db.scalar(select(func.sum(Reading.kwh))) or 0}


@app.get('/api/admin/users')
def admin_users(db: Db, admin: Admin):
    return [public_user(u) for u in db.scalars(select(User).order_by(User.id))]


@app.patch('/api/admin/users/{identifier}')
def toggle_user(identifier: int, data: ActiveIn, db: Db, admin: Admin):
    user = db.get(User, identifier)
    if not user:
        raise HTTPException(404, 'User not found')
    if user.id == admin.id:
        raise HTTPException(422, 'You cannot deactivate your own account')
    user.active = data.active
    db.commit()
    return public_user(user)


@app.put('/api/admin/tariff')
def update_tariff(data: TariffIn, db: Db, admin: Admin):
    obj = db.get(Tariff, 1)
    for key, value in data.model_dump().items():
        setattr(obj, key, value)
    db.commit()
    return obj


@app.get('/api/admin/datasets')
def admin_datasets(db: Db, admin: Admin):
    return list(db.scalars(select(Dataset).order_by(Dataset.id.desc())))
