from datetime import date as DateValue, datetime, timezone
from sqlalchemy import create_engine, String, Float, Integer, Boolean, Date, DateTime, ForeignKey, UniqueConstraint, CheckConstraint, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.dialects.mysql import LONGTEXT
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = 'mysql+pymysql://energy:change-me@localhost:3306/electricity_analyzer'
    jwt_secret: str
    cors_origins: list[str] = ['http://localhost:5173']
    model_dir: str = 'models_cache'
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')


settings = Settings()
if len(settings.jwt_secret) < 32 or settings.jwt_secret.startswith('replace-'):
    raise RuntimeError('JWT_SECRET must be a generated secret containing at least 32 characters; replace the example value')
engine = create_engine(settings.database_url, pool_pre_ping=True, **({'connect_args': {'check_same_thread': False}} if settings.database_url.startswith('sqlite') else {}))
SessionLocal = sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class Reading(Base):
    __tablename__ = 'readings'
    __table_args__ = (UniqueConstraint('user_id', 'date', name='uq_daily_reading'), CheckConstraint('kwh >= 0'))
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    date: Mapped[DateValue] = mapped_column(Date)
    kwh: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(20), default='manual')


class Appliance(Base):
    __tablename__ = 'appliances'
    __table_args__ = (CheckConstraint('watts > 0'), CheckConstraint('hours_per_day >= 0 AND hours_per_day <= 24'), CheckConstraint('quantity >= 1'))
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    name: Mapped[str] = mapped_column(String(100))
    watts: Mapped[float] = mapped_column(Float)
    hours_per_day: Mapped[float] = mapped_column(Float)
    quantity: Mapped[int] = mapped_column(Integer, default=1)


class Tariff(Base):
    __tablename__ = 'tariff_settings'
    __table_args__ = (CheckConstraint('rate_per_kwh >= 0'), CheckConstraint('fixed_charge >= 0'))
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), default='Standard estimate')
    rate_per_kwh: Mapped[float] = mapped_column(Float, default=6.0)
    fixed_charge: Mapped[float] = mapped_column(Float, default=0)
    currency: Mapped[str] = mapped_column(String(3), default='INR')


class Prediction(Base):
    __tablename__ = 'prediction_history'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    result_json: Mapped[str] = mapped_column(Text().with_variant(LONGTEXT, 'mysql'))


class Dataset(Base):
    __tablename__ = 'uploaded_datasets'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    row_count: Mapped[int] = mapped_column(Integer)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


def get_db():
    with SessionLocal() as db:
        yield db
