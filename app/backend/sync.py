import asyncio
import logging
import time
from datetime import datetime, timedelta

from sqlalchemy import and_, delete, select

from odata_1c import OData1C
from odata_1c.movements import ORGS_CATALOG, WAREHOUSES_CATALOG
from odata_1c.turnover import get_sales_turnover

from .config import (
    SYNC_BACKFILL_DAYS,
    SYNC_CHUNK_DAYS,
    SYNC_FULL_REBUILD_DAYS,
    SYNC_INTERVAL_HOURS,
    SYNC_REFRESH_DAYS,
)
from .db import (
    Movement,
    Organization,
    Sale,
    SalesTurnover,
    SessionLocal,
    StockSnapshot,
    SyncRun,
    Warehouse,
)
from .odata_async import AsyncOData1C
from .services import (
    fetch_all_sales,
    fetch_catalog_names,
    fetch_movements,
    fetch_stock,
)

logger = logging.getLogger(__name__)

# Ручной триггер должен дождаться текущего цикла, а не запускать
# параллельный — иначе двойная нагрузка на 1С.
_lock = asyncio.Lock()


async def _has_prior_success(kind: str) -> bool:
    async with SessionLocal() as session:
        q = (
            select(SyncRun.id)
            .where(
                SyncRun.kind == kind,
                SyncRun.status == 'ok',
            )
            .limit(1)
        )
        return (await session.execute(q)).first() is not None


async def _last_full_success_at(kind: str) -> datetime | None:
    async with SessionLocal() as session:
        q = (
            select(SyncRun.finished_at)
            .where(
                SyncRun.kind == kind,
                SyncRun.status == 'ok',
                SyncRun.full.is_(True),
            )
            .order_by(SyncRun.finished_at.desc())
            .limit(1)
        )
        return (await session.execute(q)).scalar_one_or_none()


def _window(is_first: bool) -> tuple[datetime, datetime]:
    date_to = datetime.utcnow()
    days = SYNC_BACKFILL_DAYS if is_first else SYNC_REFRESH_DAYS
    return date_to - timedelta(days=days), date_to


def _iter_chunks(
    date_from: datetime,
    date_to: datetime,
    chunk_days: int,
):
    cur = date_from
    step = timedelta(days=chunk_days)
    while cur < date_to:
        nxt = min(cur + step, date_to)
        yield cur, nxt
        cur = nxt


async def _record_sync(
    kind: str,
    coro,
    full: bool = False,
) -> int:
    async with SessionLocal() as session:
        run = SyncRun(
            kind=kind, status='running', full=full,
            started_at=datetime.utcnow(),
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)
        run_id = run.id

    started = time.perf_counter()
    count = 0
    error: str | None = None
    try:
        count = await coro
    except Exception as exc:
        error = f'{type(exc).__name__}: {exc}'
        logger.exception('Синк %s упал', kind)
    duration_ms = int((time.perf_counter() - started) * 1000)

    async with SessionLocal() as session:
        r = await session.get(SyncRun, run_id)
        r.finished_at = datetime.utcnow()
        r.duration_ms = duration_ms
        r.record_count = count
        if error:
            r.status = 'error'
            r.error = error
        else:
            r.status = 'ok'
        await session.commit()
    return count


async def sync_warehouses(client: AsyncOData1C) -> int:
    rows = await fetch_catalog_names(client, WAREHOUSES_CATALOG)
    async with SessionLocal() as session:
        await session.execute(delete(Warehouse))
        session.add_all([
            Warehouse(ref=r['ref'], name=r['name'])
            for r in rows if r.get('ref')
        ])
        await session.commit()
    logger.info('Синк складов: %d', len(rows))
    return len(rows)


async def sync_organizations(client: AsyncOData1C) -> int:
    rows = await fetch_catalog_names(client, ORGS_CATALOG)
    async with SessionLocal() as session:
        await session.execute(delete(Organization))
        session.add_all([
            Organization(ref=r['ref'], name=r['name'])
            for r in rows if r.get('ref')
        ])
        await session.commit()
    logger.info('Синк организаций: %d', len(rows))
    return len(rows)


async def sync_stock(client: AsyncOData1C) -> int:
    rows = await fetch_stock(client, only_positive=False)
    now = datetime.utcnow()

    async with SessionLocal() as session:
        await session.execute(delete(StockSnapshot))
        objs = [
            StockSnapshot(
                name=r.get('name') or '',
                article=r.get('article') or '',
                barcode=r.get('barcode') or '',
                size=r.get('size') or '',
                size_global=r.get('size_global') or '',
                size_ru=r.get('size_ru') or '',
                warehouse_ref=r.get('warehouse_ref') or '',
                warehouse=r.get('warehouse') or '',
                organization_ref=r.get('organization_ref') or '',
                organization=r.get('organization') or '',
                nomenclature_ref=r.get('nomenclature_ref') or '',
                quantity=float(r.get('quantity') or 0),
                snapshot_at=now,
            )
            for r in rows
        ]
        for chunk_start in range(0, len(objs), 500):
            session.add_all(objs[chunk_start:chunk_start + 500])
            await session.flush()
        await session.commit()
    logger.info('Синк остатков: %d строк', len(objs))
    return len(objs)


def _movement_row_to_obj(r: dict, now: datetime) -> Movement:
    return Movement(
        period=r.get('period'),
        name=r.get('name') or '',
        article=r.get('article') or '',
        barcode=r.get('barcode') or '',
        size=r.get('size') or '',
        size_global=r.get('size_global') or '',
        size_ru=r.get('size_ru') or '',
        quantity=float(r.get('quantity') or 0),
        operation_type=r.get('operation_type') or '',
        warehouse_from=r.get('warehouse_from') or '',
        warehouse_to=r.get('warehouse_to') or '',
        warehouse_from_ref=r.get('warehouse_from_ref') or '',
        warehouse_to_ref=r.get('warehouse_to_ref') or '',
        organization_from=r.get('organization_from') or '',
        organization_to=r.get('organization_to') or '',
        organization_from_ref=(
            r.get('organization_from_ref') or ''
        ),
        organization_to_ref=r.get('organization_to_ref') or '',
        document_kind=r.get('document_kind') or '',
        document_number=r.get('document_number') or '',
        document_date=r.get('document_date'),
        recorder=r.get('recorder') or '',
        snapshot_at=now,
    )


def _sale_row_to_obj(r: dict, now: datetime) -> Sale:
    return Sale(
        nomenclature_key=r.get('nomenclature_key') or '',
        characteristic_key=r.get('characteristic_key'),
        article=r.get('article'),
        size=r.get('size'),
        channel=r.get('channel') or '',
        quantity=float(r.get('quantity') or 0),
        amount=float(r.get('amount') or 0),
        date=r.get('date'),
        type=r.get('type') or '',
        warehouse=r.get('warehouse'),
        organization=r.get('organization'),
        snapshot_at=now,
    )


async def _sync_chunk_movements(
    client: AsyncOData1C,
    date_from: datetime,
    date_to: datetime,
    now: datetime,
) -> int:
    rows = await fetch_movements(client, date_from, date_to)
    async with SessionLocal() as session:
        await session.execute(
            delete(Movement).where(
                and_(
                    Movement.period >= date_from,
                    Movement.period < date_to,
                ),
            ),
        )
        objs = [_movement_row_to_obj(r, now) for r in rows]
        for i in range(0, len(objs), 500):
            session.add_all(objs[i:i + 500])
            await session.flush()
        await session.commit()
    return len(rows)


async def _sync_chunk_sales(
    client: AsyncOData1C,
    date_from: datetime,
    date_to: datetime,
    now: datetime,
) -> int:
    rows = await fetch_all_sales(client, date_from, date_to)
    async with SessionLocal() as session:
        await session.execute(
            delete(Sale).where(
                and_(
                    Sale.date >= date_from,
                    Sale.date < date_to,
                ),
            ),
        )
        objs = [_sale_row_to_obj(r, now) for r in rows]
        for i in range(0, len(objs), 500):
            session.add_all(objs[i:i + 500])
            await session.flush()
        await session.commit()
    return len(rows)


async def sync_movements(
    client: AsyncOData1C,
    full: bool = False,
) -> int:
    is_first = full or not await _has_prior_success('movements')
    date_from, date_to = _window(is_first)
    now = datetime.utcnow()

    logger.info(
        'Sync движений: %s, окно [%s .. %s], чанк %d дн.',
        'бэкфилл' if is_first else 'инкремент',
        date_from.date(), date_to.date(), SYNC_CHUNK_DAYS,
    )

    total = 0
    for cs, ce in _iter_chunks(date_from, date_to, SYNC_CHUNK_DAYS):
        n = await _sync_chunk_movements(client, cs, ce, now)
        total += n
        logger.info(
            '  чанк [%s .. %s]: %d строк',
            cs.date(), ce.date(), n,
        )
    logger.info('Синк движений: всего %d строк', total)
    return total


async def sync_sales(
    client: AsyncOData1C,
    full: bool = False,
) -> int:
    is_first = full or not await _has_prior_success('sales')
    date_from, date_to = _window(is_first)
    now = datetime.utcnow()

    logger.info(
        'Sync продаж: %s, окно [%s .. %s], чанк %d дн.',
        'бэкфилл' if is_first else 'инкремент',
        date_from.date(), date_to.date(), SYNC_CHUNK_DAYS,
    )

    total = 0
    for cs, ce in _iter_chunks(date_from, date_to, SYNC_CHUNK_DAYS):
        n = await _sync_chunk_sales(client, cs, ce, now)
        total += n
        logger.info(
            '  чанк [%s .. %s]: %d строк',
            cs.date(), ce.date(), n,
        )
    logger.info('Синк продаж: всего %d строк', total)
    return total


def _month_starts(date_from: datetime, date_to: datetime):
    cur = datetime(date_from.year, date_from.month, 1)
    end = datetime(date_to.year, date_to.month, 1)
    while cur <= end:
        if cur.month == 12:
            nxt = datetime(cur.year + 1, 1, 1)
        else:
            nxt = datetime(cur.year, cur.month + 1, 1)
        yield cur, nxt
        cur = nxt


async def _sync_chunk_turnover(
    date_from: datetime,
    date_to: datetime,
    now: datetime,
) -> int:
    # get_sales_turnover — синхронный (использует requests),
    # уводим в executor, чтобы не блокировать event loop.
    loop = asyncio.get_running_loop()

    def _load() -> list:
        return get_sales_turnover(OData1C(), date_from, date_to)

    records = await loop.run_in_executor(None, _load)

    async with SessionLocal() as session:
        await session.execute(
            delete(SalesTurnover).where(
                SalesTurnover.month == date_from,
            ),
        )
        objs = [
            SalesTurnover(
                nomenclature_key=r.nomenclature_key,
                characteristic_key=r.characteristic_key,
                article=r.article,
                name=r.name,
                size=r.size,
                warehouse_ref=r.warehouse_ref,
                warehouse=r.warehouse,
                organization_ref=r.organization_ref,
                organization=r.organization,
                contractor_ref=r.contractor_ref,
                contractor=r.contractor,
                month=date_from,
                quantity=r.quantity,
                revenue=r.revenue,
                revenue_no_vat=r.revenue_no_vat,
                cost=r.cost,
                cost_no_vat=r.cost_no_vat,
                snapshot_at=now,
            )
            for r in records
        ]
        for i in range(0, len(objs), 500):
            session.add_all(objs[i:i + 500])
            await session.flush()
        await session.commit()
    return len(records)


async def sync_sales_turnover(
    client: AsyncOData1C,
    full: bool = False,
) -> int:
    is_first = (
        full or not await _has_prior_success('sales_turnover')
    )
    date_from, date_to = _window(is_first)
    now = datetime.utcnow()

    logger.info(
        'Sync валовой прибыли: %s, окно [%s .. %s]',
        'бэкфилл' if is_first else 'инкремент',
        date_from.date(), date_to.date(),
    )
    total = 0
    for cs, ce in _month_starts(date_from, date_to):
        n = await _sync_chunk_turnover(cs, ce, now)
        total += n
        logger.info('  месяц %s: %d строк', cs.date(), n)
    logger.info('Синк валовой прибыли: всего %d строк', total)
    return total


async def _should_full_rebuild() -> bool:
    threshold = timedelta(days=SYNC_FULL_REBUILD_DAYS)
    now = datetime.utcnow()
    for kind in ('movements', 'sales', 'sales_turnover'):
        last = await _last_full_success_at(kind)
        if last is None or (now - last) >= threshold:
            return True
    return False


async def run_sync_cycle(full: bool = False) -> None:
    if _lock.locked():
        logger.info('Синк уже идёт, пропускаю запуск')
        return
    async with _lock:
        async with AsyncOData1C() as client:
            await _record_sync(
                'warehouses', sync_warehouses(client),
            )
            await _record_sync(
                'organizations', sync_organizations(client),
            )
            await _record_sync('stock', sync_stock(client))
            await _record_sync(
                'movements',
                sync_movements(client, full=full),
                full=full,
            )
            await _record_sync(
                'sales',
                sync_sales(client, full=full),
                full=full,
            )
            await _record_sync(
                'sales_turnover',
                sync_sales_turnover(client, full=full),
                full=full,
            )


async def sync_loop() -> None:
    interval = SYNC_INTERVAL_HOURS * 3600
    while True:
        try:
            full = await _should_full_rebuild()
            if full:
                logger.info(
                    'Прошло >=%d дн. с последнего full, '
                    'запускаю полный ребилд',
                    SYNC_FULL_REBUILD_DAYS,
                )
            await run_sync_cycle(full=full)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception('Цикл синка упал, продолжаю')
        try:
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            raise
