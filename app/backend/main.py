import asyncio
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Awaitable, Callable

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import desc, func, select
from sqlalchemy.sql import ColumnElement
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.sessions import SessionMiddleware

from odata_1c.movements import (
    DOCUMENT_OPERATION,
    EXPENSE_KINDS,
    ORGS_CATALOG,
    RECEIPT_KINDS,
    TRANSFER_KINDS,
    WAREHOUSES_CATALOG,
    WRITE_OFF_KINDS,
)

from .auth import (
    ensure_owner,
    require_user,
    resolve_session_secret,
    router as auth_router,
    users_router,
)
from .config import (
    CORS_ORIGINS,
    SESSION_COOKIE_SECURE,
    SESSION_MAX_AGE,
    SYNC_ENABLED,
    SYNC_INTERVAL_HOURS,
)
from .db import (
    Movement,
    Organization,
    Run,
    Sale,
    SalesTurnover,
    SessionLocal,
    StockSnapshot,
    SyncRun,
    Warehouse,
    get_session,
    init_db,
    serialize_payload,
)
from .odata_async import AsyncOData1C
from .schemas import (
    AllSalesRequest,
    GrossProfitRequest,
    MarketplaceSalesRequest,
    MovementsRequest,
    RetailSalesRequest,
    RunDetail,
    RunSummary,
    StockByArticleRequest,
    StockRequest,
)
from .services import (
    MOVEMENT_KIND_MAP,
    fetch_all_sales,
    fetch_catalog_names,
    fetch_marketplace_sales,
    fetch_movements,
    fetch_retail_sales,
    fetch_stock,
    fetch_stock_by_article,
)
from .sync import run_sync_cycle, sync_loop

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s %(name)s: %(message)s',
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await ensure_owner()
    task: asyncio.Task | None = None
    if SYNC_ENABLED:
        logger.info(
            'Фоновая синхронизация включена, интервал %d ч',
            SYNC_INTERVAL_HOURS,
        )
        task = asyncio.create_task(sync_loop())
    yield
    if task is not None:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title='OData 1С — интерфейс клиента',
    version='0.3.0',
    lifespan=lifespan,
)

app.add_middleware(
    SessionMiddleware,
    secret_key=resolve_session_secret(),
    session_cookie='odata1c_session',
    max_age=SESSION_MAX_AGE,
    same_site='lax',
    https_only=SESSION_COOKIE_SECURE,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(auth_router)
app.include_router(users_router)


# Публичный health — без авторизации, для docker healthcheck.
@app.get('/api/health')
async def health() -> dict:
    return {'ok': True}


# Все data-эндпоинты живут под require_user. Owner-only ручки
# (users) висят на своём роутере в auth.py.
data_router = APIRouter(dependencies=[Depends(require_user)])


_KIND_TO_OPS = {
    'transfers': tuple({
        DOCUMENT_OPERATION[k] for k in TRANSFER_KINDS
    }),
    'write_offs': tuple({
        DOCUMENT_OPERATION[k] for k in WRITE_OFF_KINDS
    }),
    'receipts': tuple({
        DOCUMENT_OPERATION[k] for k in RECEIPT_KINDS
    }),
    'expenses': tuple({
        DOCUMENT_OPERATION[k] for k in EXPENSE_KINDS
    }),
}


async def _record_run(
    method: str,
    params: dict,
    fn: Callable[[AsyncOData1C], Awaitable[list[dict]]],
) -> dict[str, Any]:
    async with SessionLocal() as session:
        run = Run(
            method=method,
            params=params,
            status='running',
            started_at=datetime.utcnow(),
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)
        run_id = run.id

    started = time.perf_counter()
    payload: list[dict] = []
    error: str | None = None
    try:
        async with AsyncOData1C() as client:
            payload = await fn(client)
    except Exception as exc:
        error = f'{type(exc).__name__}: {exc}'
        logger.exception('Ошибка запроса %s', method)
    duration_ms = int((time.perf_counter() - started) * 1000)

    async with SessionLocal() as session:
        run = await session.get(Run, run_id)
        run.finished_at = datetime.utcnow()
        run.duration_ms = duration_ms
        if error:
            run.status = 'error'
            run.error = error
            run.record_count = 0
        else:
            run.status = 'ok'
            run.record_count = len(payload)
            run.payload = serialize_payload(payload)
        await session.commit()

    if error:
        raise HTTPException(status_code=502, detail=error)
    return {
        'run_id': run_id,
        'duration_ms': duration_ms,
        'record_count': len(payload),
        'records': serialize_payload(payload),
    }


async def _cached_response(
    method: str,
    kind: str,
    records: list[dict],
) -> dict[str, Any]:
    async with SessionLocal() as session:
        q = (
            select(SyncRun)
            .where(SyncRun.kind == kind, SyncRun.status == 'ok')
            .order_by(desc(SyncRun.finished_at))
            .limit(1)
        )
        last = (await session.execute(q)).scalar_one_or_none()
    snapshot_at = last.finished_at.isoformat() if last else None
    return {
        'source': 'cache',
        'method': method,
        'snapshot_at': snapshot_at,
        'record_count': len(records),
        'records': records,
    }


def _sale_dict(r: Sale) -> dict:
    return {
        'nomenclature_key': r.nomenclature_key,
        'characteristic_key': r.characteristic_key,
        'article': r.article,
        'size': r.size,
        'channel': r.channel,
        'quantity': r.quantity,
        'amount': r.amount,
        'date': r.date.isoformat() if r.date else None,
        'type': r.type,
        'warehouse': r.warehouse,
        'organization': r.organization,
    }


def _movement_dict(r: Movement) -> dict:
    return {
        'period': r.period.isoformat() if r.period else None,
        'name': r.name,
        'article': r.article,
        'barcode': r.barcode,
        'size': r.size,
        'size_global': r.size_global,
        'size_ru': r.size_ru,
        'quantity': r.quantity,
        'operation_type': r.operation_type,
        'warehouse_from': r.warehouse_from,
        'warehouse_to': r.warehouse_to,
        'organization_from': r.organization_from,
        'organization_to': r.organization_to,
        'document_kind': r.document_kind,
        'document_number': r.document_number,
        'document_date': (
            r.document_date.isoformat() if r.document_date else None
        ),
        'recorder': r.recorder,
    }


def _stock_dict(r: StockSnapshot) -> dict:
    return {
        'name': r.name,
        'article': r.article,
        'barcode': r.barcode,
        'size': r.size,
        'size_global': r.size_global,
        'size_ru': r.size_ru,
        'warehouse': r.warehouse,
        'organization': r.organization,
        'quantity': r.quantity,
    }


@data_router.post('/api/sales/marketplace')
async def api_marketplace_sales(
    req: MarketplaceSalesRequest,
    live: bool = Query(False),
    session: AsyncSession = Depends(get_session),
):
    if live:
        async def fn(client):
            return await fetch_marketplace_sales(
                client, req.date_from, req.date_to, req.channel,
            )
        return await _record_run(
            'sales.marketplace', req.model_dump(mode='json'), fn,
        )

    conds = [
        Sale.date >= req.date_from,
        Sale.date <= req.date_to,
        Sale.channel != 'магазин',
    ]
    if req.channel:
        conds.append(Sale.channel == req.channel)
    q = select(Sale).where(*conds).order_by(Sale.date)
    rows = (await session.execute(q)).scalars().all()
    return await _cached_response(
        'sales.marketplace', 'sales', [_sale_dict(r) for r in rows],
    )


@data_router.post('/api/sales/retail')
async def api_retail_sales(
    req: RetailSalesRequest,
    live: bool = Query(False),
    session: AsyncSession = Depends(get_session),
):
    if live:
        async def fn(client):
            return await fetch_retail_sales(
                client, req.date_from, req.date_to,
            )
        return await _record_run(
            'sales.retail', req.model_dump(mode='json'), fn,
        )
    q = (
        select(Sale)
        .where(
            Sale.date >= req.date_from,
            Sale.date <= req.date_to,
            Sale.channel == 'магазин',
        )
        .order_by(Sale.date)
    )
    rows = (await session.execute(q)).scalars().all()
    return await _cached_response(
        'sales.retail', 'sales', [_sale_dict(r) for r in rows],
    )


@data_router.post('/api/sales/all')
async def api_all_sales(
    req: AllSalesRequest,
    live: bool = Query(False),
    session: AsyncSession = Depends(get_session),
):
    if live:
        async def fn(client):
            return await fetch_all_sales(
                client, req.date_from, req.date_to,
            )
        return await _record_run(
            'sales.all', req.model_dump(mode='json'), fn,
        )
    q = (
        select(Sale)
        .where(
            Sale.date >= req.date_from,
            Sale.date <= req.date_to,
        )
        .order_by(Sale.date)
    )
    rows = (await session.execute(q)).scalars().all()
    return await _cached_response(
        'sales.all', 'sales', [_sale_dict(r) for r in rows],
    )


@data_router.post('/api/movements')
async def api_movements(
    req: MovementsRequest,
    live: bool = Query(False),
    session: AsyncSession = Depends(get_session),
):
    if req.kind not in MOVEMENT_KIND_MAP:
        raise HTTPException(status_code=400, detail='Неизвестный kind')

    if live:
        kinds = MOVEMENT_KIND_MAP.get(req.kind, None)

        async def fn(client):
            return await fetch_movements(
                client, req.date_from, req.date_to,
                organization=req.organization,
                warehouse=req.warehouse,
                kinds=kinds,
            )
        return await _record_run(
            f'movements.{req.kind}',
            req.model_dump(mode='json'), fn,
        )

    conds = [
        Movement.period >= req.date_from,
        Movement.period <= req.date_to,
    ]
    if req.organization:
        conds.append(
            (Movement.organization_from_ref == req.organization)
            | (Movement.organization_to_ref == req.organization)
        )
    if req.warehouse:
        conds.append(
            (Movement.warehouse_from_ref == req.warehouse)
            | (Movement.warehouse_to_ref == req.warehouse)
        )
    if req.kind != 'all':
        op_types = _KIND_TO_OPS.get(req.kind, ())
        if op_types:
            conds.append(Movement.operation_type.in_(op_types))
    q = select(Movement).where(*conds).order_by(Movement.period)
    rows = (await session.execute(q)).scalars().all()
    return await _cached_response(
        f'movements.{req.kind}', 'movements',
        [_movement_dict(r) for r in rows],
    )


_GP_GROUP_COLS: dict[str, ColumnElement] = {
    'article': SalesTurnover.article,
    'size': SalesTurnover.size,
    'warehouse': SalesTurnover.warehouse,
    'organization': SalesTurnover.organization,
    'contractor': SalesTurnover.contractor,
    'month': SalesTurnover.month,
}


@data_router.post('/api/gross-profit')
async def api_gross_profit(
    req: GrossProfitRequest,
    session: AsyncSession = Depends(get_session),
):
    """Валовая прибыль по номенклатуре из кэша Продажи/Turnovers.

    Всегда возвращает агрегат: SUM по выбранным group_by-ключам.
    По умолчанию (article, size) — как в отчёте УНФ. Пустой
    group_by = один тотал по всему периоду.
    """
    group_cols: list[ColumnElement] = []
    for key in req.group_by or []:
        col = _GP_GROUP_COLS.get(key)
        if col is None:
            raise HTTPException(
                status_code=400,
                detail=f'Неизвестный ключ группировки: {key}',
            )
        group_cols.append(col)

    conds = [
        SalesTurnover.month >= _month_floor(req.date_from),
        SalesTurnover.month <= req.date_to,
    ]
    if req.article:
        conds.append(SalesTurnover.article == req.article)
    if req.warehouse:
        conds.append(SalesTurnover.warehouse_ref == req.warehouse)
    if req.organization:
        conds.append(
            SalesTurnover.organization_ref == req.organization,
        )
    if req.contractor:
        conds.append(
            SalesTurnover.contractor_ref == req.contractor,
        )

    agg_cols = [
        func.sum(SalesTurnover.quantity).label('quantity'),
        func.sum(SalesTurnover.revenue).label('revenue'),
        func.sum(SalesTurnover.revenue_no_vat).label(
            'revenue_no_vat',
        ),
        func.sum(SalesTurnover.cost).label('cost'),
        func.sum(SalesTurnover.cost_no_vat).label('cost_no_vat'),
    ]
    stmt = select(*group_cols, *agg_cols).where(*conds)
    if group_cols:
        stmt = stmt.group_by(*group_cols).order_by(*group_cols)
    rows = (await session.execute(stmt)).all()

    keys = list(req.group_by or [])
    records: list[dict] = []
    for r in rows:
        rec: dict = {}
        for i, k in enumerate(keys):
            v = r[i]
            if isinstance(v, datetime):
                rec[k] = v.isoformat()
            else:
                rec[k] = v
        base = len(keys)
        qty = float(r[base] or 0)
        rev = float(r[base + 1] or 0)
        rev_nv = float(r[base + 2] or 0)
        cost = float(r[base + 3] or 0)
        cost_nv = float(r[base + 4] or 0)
        gross = rev - cost
        rec.update({
            'quantity': qty,
            'revenue': rev,
            'revenue_no_vat': rev_nv,
            'cost': cost,
            'cost_no_vat': cost_nv,
            'gross_profit': gross,
            'profitability': (
                gross / rev * 100 if rev else 0.0
            ),
            'unit_cost': cost / qty if qty else 0.0,
        })
        records.append(rec)

    return await _cached_response(
        'gross_profit', 'sales_turnover', records,
    )


def _month_floor(dt: datetime) -> datetime:
    return datetime(dt.year, dt.month, 1)


@data_router.post('/api/stock')
async def api_stock(
    req: StockRequest,
    live: bool = Query(False),
    session: AsyncSession = Depends(get_session),
):
    if live:
        async def fn(client):
            return await fetch_stock(
                client,
                warehouse=req.warehouse,
                organization=req.organization,
                nomenclature=req.nomenclature,
                only_positive=req.only_positive,
            )
        return await _record_run(
            'stock', req.model_dump(mode='json'), fn,
        )

    conds = []
    if req.warehouse:
        conds.append(StockSnapshot.warehouse_ref == req.warehouse)
    if req.organization:
        conds.append(
            StockSnapshot.organization_ref == req.organization,
        )
    if req.nomenclature:
        conds.append(
            StockSnapshot.nomenclature_ref == req.nomenclature,
        )
    if req.only_positive:
        conds.append(StockSnapshot.quantity > 0)
    q = select(StockSnapshot)
    if conds:
        q = q.where(*conds)
    q = q.order_by(StockSnapshot.article, StockSnapshot.warehouse)
    rows = (await session.execute(q)).scalars().all()
    return await _cached_response(
        'stock', 'stock', [_stock_dict(r) for r in rows],
    )


@data_router.post('/api/stock/by-article')
async def api_stock_by_article(
    req: StockByArticleRequest,
    live: bool = Query(False),
    session: AsyncSession = Depends(get_session),
):
    if live:
        async def fn(client):
            return await fetch_stock_by_article(client, req.article)
        return await _record_run(
            'stock.by_article', req.model_dump(mode='json'), fn,
        )
    if not req.article:
        return await _cached_response(
            'stock.by_article', 'stock', [],
        )
    q = (
        select(StockSnapshot)
        .where(StockSnapshot.article == req.article)
        .order_by(StockSnapshot.warehouse)
    )
    rows = (await session.execute(q)).scalars().all()
    return await _cached_response(
        'stock.by_article', 'stock',
        [_stock_dict(r) for r in rows],
    )


@data_router.get('/api/catalog/warehouses')
async def api_warehouses(
    live: bool = Query(False),
    session: AsyncSession = Depends(get_session),
):
    if live:
        async with AsyncOData1C() as client:
            return await fetch_catalog_names(
                client, WAREHOUSES_CATALOG,
            )
    q = select(Warehouse).order_by(Warehouse.name)
    rows = (await session.execute(q)).scalars().all()
    return [{'ref': r.ref, 'name': r.name} for r in rows]


@data_router.get('/api/catalog/organizations')
async def api_organizations(
    live: bool = Query(False),
    session: AsyncSession = Depends(get_session),
):
    if live:
        async with AsyncOData1C() as client:
            return await fetch_catalog_names(
                client, ORGS_CATALOG,
            )
    q = select(Organization).order_by(Organization.name)
    rows = (await session.execute(q)).scalars().all()
    return [{'ref': r.ref, 'name': r.name} for r in rows]


@data_router.get('/api/sync/status')
async def api_sync_status(
    session: AsyncSession = Depends(get_session),
):
    subq = (
        select(
            SyncRun.kind,
            func.max(SyncRun.started_at).label('last_started'),
        )
        .group_by(SyncRun.kind)
        .subquery()
    )
    q = (
        select(SyncRun)
        .join(
            subq,
            (SyncRun.kind == subq.c.kind)
            & (SyncRun.started_at == subq.c.last_started),
        )
        .order_by(SyncRun.kind)
    )
    rows = (await session.execute(q)).scalars().all()
    return {
        'interval_hours': SYNC_INTERVAL_HOURS,
        'runs': [
            {
                'kind': r.kind,
                'status': r.status,
                'started_at': r.started_at,
                'finished_at': r.finished_at,
                'duration_ms': r.duration_ms,
                'record_count': r.record_count,
                'error': r.error,
            }
            for r in rows
        ],
    }


@data_router.post('/api/sync/refresh')
async def api_sync_refresh(full: bool = Query(False)):
    asyncio.create_task(run_sync_cycle(full=full))
    return {'ok': True, 'started': True, 'full': full}


@data_router.get('/api/runs', response_model=list[RunSummary])
async def api_runs(
    limit: int = 100,
    session: AsyncSession = Depends(get_session),
):
    q = (
        select(Run)
        .order_by(desc(Run.started_at))
        .limit(min(max(limit, 1), 500))
    )
    rows = (await session.execute(q)).scalars().all()
    return [
        RunSummary(
            id=r.id, method=r.method, status=r.status,
            started_at=r.started_at, finished_at=r.finished_at,
            duration_ms=r.duration_ms,
            record_count=r.record_count,
            error=r.error, params=r.params or {},
        )
        for r in rows
    ]


@data_router.get('/api/runs/{run_id}', response_model=RunDetail)
async def api_run_detail(
    run_id: int,
    session: AsyncSession = Depends(get_session),
):
    r = await session.get(Run, run_id)
    if not r:
        raise HTTPException(status_code=404, detail='Не найдено')
    return RunDetail(
        id=r.id, method=r.method, status=r.status,
        started_at=r.started_at, finished_at=r.finished_at,
        duration_ms=r.duration_ms, record_count=r.record_count,
        error=r.error, params=r.params or {}, payload=r.payload,
    )


@data_router.delete('/api/runs/{run_id}')
async def api_run_delete(
    run_id: int,
    session: AsyncSession = Depends(get_session),
):
    r = await session.get(Run, run_id)
    if not r:
        raise HTTPException(status_code=404, detail='Не найдено')
    await session.delete(r)
    await session.commit()
    return {'ok': True}


app.include_router(data_router)
