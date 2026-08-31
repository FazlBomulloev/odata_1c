import json
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .config import DB_URL


class Base(DeclarativeBase):
    pass


class User(Base):
    """Пользователь панели (owner или employee)."""
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True,
    )
    username: Mapped[str] = mapped_column(
        String(64), unique=True, index=True,
    )
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(
        String(16), default='employee', index=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow,
    )
    created_by: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
    )


class Run(Base):
    """Лог вызовов API (какой метод, параметры, результат)."""
    __tablename__ = 'runs'

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True,
    )
    method: Mapped[str] = mapped_column(String(64), index=True)
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(
        String(16), default='running', index=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True,
    )
    duration_ms: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
    )
    record_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
    )
    error: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )
    payload: Mapped[list | None] = mapped_column(
        JSON, nullable=True,
    )


class SyncRun(Base):
    """Лог фоновых синхронизаций из 1С в локальную БД."""
    __tablename__ = 'sync_runs'

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True,
    )
    kind: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(
        String(16), default='running', index=True,
    )
    # True = полный бэкфилл (за SYNC_BACKFILL_DAYS), False =
    # инкремент (окно SYNC_REFRESH_DAYS). Для каталогов/остатков
    # семантики нет — всегда False.
    full: Mapped[bool] = mapped_column(Boolean, default=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True,
    )
    duration_ms: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
    )
    record_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
    )
    error: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )


class Warehouse(Base):
    __tablename__ = 'warehouses'

    ref: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), index=True)


class Organization(Base):
    __tablename__ = 'organizations'

    ref: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), index=True)


class StockSnapshot(Base):
    """Плоская строка остатков на момент последнего синка."""
    __tablename__ = 'stock_snapshot'

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True,
    )
    name: Mapped[str] = mapped_column(String(512), default='')
    article: Mapped[str] = mapped_column(
        String(128), default='', index=True,
    )
    barcode: Mapped[str] = mapped_column(String(64), default='')
    size: Mapped[str] = mapped_column(String(64), default='')
    size_global: Mapped[str] = mapped_column(
        String(32), default='',
    )
    size_ru: Mapped[str] = mapped_column(String(32), default='')
    warehouse_ref: Mapped[str] = mapped_column(
        String(36), default='', index=True,
    )
    warehouse: Mapped[str] = mapped_column(
        String(256), default='',
    )
    organization_ref: Mapped[str] = mapped_column(
        String(36), default='', index=True,
    )
    organization: Mapped[str] = mapped_column(
        String(256), default='',
    )
    nomenclature_ref: Mapped[str] = mapped_column(
        String(36), default='', index=True,
    )
    quantity: Mapped[float] = mapped_column(Float, default=0.0)
    snapshot_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True,
    )


Index(
    'ix_stock_wh_org', StockSnapshot.warehouse_ref,
    StockSnapshot.organization_ref,
)
Index(
    'ix_stock_article_wh',
    StockSnapshot.article, StockSnapshot.warehouse_ref,
)


class Movement(Base):
    """Одно нормализованное движение (за окно синка)."""
    __tablename__ = 'movements'

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True,
    )
    period: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, index=True,
    )
    name: Mapped[str] = mapped_column(String(512), default='')
    article: Mapped[str] = mapped_column(
        String(128), default='', index=True,
    )
    barcode: Mapped[str] = mapped_column(String(64), default='')
    size: Mapped[str] = mapped_column(String(64), default='')
    size_global: Mapped[str] = mapped_column(
        String(32), default='',
    )
    size_ru: Mapped[str] = mapped_column(String(32), default='')
    quantity: Mapped[float] = mapped_column(Float, default=0.0)
    operation_type: Mapped[str] = mapped_column(
        String(64), default='', index=True,
    )
    warehouse_from: Mapped[str] = mapped_column(
        String(256), default='',
    )
    warehouse_to: Mapped[str] = mapped_column(
        String(256), default='',
    )
    warehouse_from_ref: Mapped[str] = mapped_column(
        String(36), default='', index=True,
    )
    warehouse_to_ref: Mapped[str] = mapped_column(
        String(36), default='', index=True,
    )
    organization_from: Mapped[str] = mapped_column(
        String(256), default='',
    )
    organization_to: Mapped[str] = mapped_column(
        String(256), default='',
    )
    organization_from_ref: Mapped[str] = mapped_column(
        String(36), default='', index=True,
    )
    organization_to_ref: Mapped[str] = mapped_column(
        String(36), default='', index=True,
    )
    document_kind: Mapped[str] = mapped_column(
        String(64), default='',
    )
    document_number: Mapped[str] = mapped_column(
        String(64), default='',
    )
    document_date: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True,
    )
    recorder: Mapped[str] = mapped_column(
        String(36), default='', index=True,
    )
    snapshot_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True,
    )

    __table_args__ = (
        Index(
            'ix_movements_period_op',
            'period', 'operation_type',
        ),
        Index(
            'ix_movements_period_article',
            'period', 'article',
        ),
    )


class Sale(Base):
    """Одна нормализованная строка продажи/возврата."""
    __tablename__ = 'sales'

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True,
    )
    nomenclature_key: Mapped[str] = mapped_column(
        String(36), default='', index=True,
    )
    characteristic_key: Mapped[str | None] = mapped_column(
        String(36), nullable=True,
    )
    article: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True,
    )
    size: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
    )
    channel: Mapped[str] = mapped_column(
        String(32), default='', index=True,
    )
    quantity: Mapped[float] = mapped_column(Float, default=0.0)
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    date: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, index=True,
    )
    type: Mapped[str] = mapped_column(
        String(16), default='', index=True,
    )
    warehouse: Mapped[str | None] = mapped_column(
        String(256), nullable=True,
    )
    organization: Mapped[str | None] = mapped_column(
        String(256), nullable=True,
    )
    snapshot_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True,
    )

    __table_args__ = (
        Index('ix_sales_date_channel', 'date', 'channel'),
        Index('ix_sales_date_type', 'date', 'type'),
        Index('ix_sales_channel_type', 'channel', 'type'),
    )


class SalesTurnover(Base):
    """Строка регистра Продажи/Turnovers за конкретный месяц.

    Гранулярность — (номенклатура, характеристика, склад, орг,
    контрагент, месяц). Даёт колонки отчёта «Валовая прибыль по
    номенклатуре»: количество, выручка, себестоимость, прибыль.
    """
    __tablename__ = 'sales_turnover'

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True,
    )
    nomenclature_key: Mapped[str] = mapped_column(
        String(36), default='', index=True,
    )
    characteristic_key: Mapped[str] = mapped_column(
        String(36), default='', index=True,
    )
    article: Mapped[str] = mapped_column(
        String(128), default='', index=True,
    )
    name: Mapped[str] = mapped_column(String(512), default='')
    size: Mapped[str] = mapped_column(String(64), default='')
    warehouse_ref: Mapped[str] = mapped_column(
        String(36), default='', index=True,
    )
    warehouse: Mapped[str] = mapped_column(
        String(256), default='',
    )
    organization_ref: Mapped[str] = mapped_column(
        String(36), default='', index=True,
    )
    organization: Mapped[str] = mapped_column(
        String(256), default='',
    )
    contractor_ref: Mapped[str] = mapped_column(
        String(36), default='', index=True,
    )
    contractor: Mapped[str] = mapped_column(
        String(256), default='',
    )
    month: Mapped[datetime] = mapped_column(
        DateTime, index=True,
    )
    quantity: Mapped[float] = mapped_column(Float, default=0.0)
    revenue: Mapped[float] = mapped_column(Float, default=0.0)
    revenue_no_vat: Mapped[float] = mapped_column(
        Float, default=0.0,
    )
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    cost_no_vat: Mapped[float] = mapped_column(Float, default=0.0)
    snapshot_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True,
    )

    __table_args__ = (
        Index('ix_turnover_article_month', 'article', 'month'),
        Index('ix_turnover_month_wh', 'month', 'warehouse_ref'),
        Index('ix_turnover_month_org', 'month', 'organization_ref'),
    )


engine = create_async_engine(DB_URL, echo=False, future=True)
SessionLocal = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession,
)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session


def _json_default(obj: Any):
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f'Type {type(obj)} not serializable')


def serialize_payload(payload: Any) -> Any:
    """dataclass-friendly сериализация через json.loads(json.dumps)."""
    return json.loads(json.dumps(payload, default=_json_default))
