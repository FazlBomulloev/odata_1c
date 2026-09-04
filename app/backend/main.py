import asyncio
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Awaitable, Callable

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from odata_1c.exceptions import (
    ArticleNotFoundError,
    ODataNotFoundError,
    ODataValidationError,
    ProductExistsError,
)
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
from .products_service import (
    article_exists_async,
    count_products_async,
    create_product_async,
    delete_product_async,
    get_product_async,
    list_products_async,
    next_article_async,
    photo_bytes_async,
    search_articles_async,
    update_product_async,
)
from .schemas import (
    AllSalesRequest,
    GrossProfitRequest,
    MarketplaceSalesRequest,
    MovementsRequest,
    ProductCreate,
    ProductListItem,
    ProductUpdate,
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


@app.get('/api/health')
async def health() -> dict:
    return {'ok': True}


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


PAGE_SIZE_DEFAULT = 50
PAGE_SIZE_MAX = 500


def _clamp_page(page: int, size: int) -> tuple[int, int]:
    page = max(1, int(page or 1))
    size = min(PAGE_SIZE_MAX, max(1, int(size or PAGE_SIZE_DEFAULT)))
    return page, size


async def _last_snapshot_at(
    session: AsyncSession, kind: str,
) -> str | None:
    q = (
        select(SyncRun)
        .where(SyncRun.kind == kind, SyncRun.status == 'ok')
        .order_by(desc(SyncRun.finished_at))
        .limit(1)
    )
    last = (await session.execute(q)).scalar_one_or_none()
    return last.finished_at.isoformat() if last else None


async def _paginate_stmt(
    session: AsyncSession,
    stmt,
    page: int,
    size: int,
    to_dict: Callable[[Any], dict],
) -> tuple[list[dict], int]:
    """(records, total) для запроса, возвращающего ORM-объекты."""
    count_stmt = select(func.count()).select_from(
        stmt.order_by(None).subquery(),
    )
    total = (
        await session.execute(count_stmt)
    ).scalar() or 0
    page_stmt = stmt.limit(size).offset((page - 1) * size)
    rows = (await session.execute(page_stmt)).scalars().all()
    return [to_dict(r) for r in rows], int(total)


async def _paged_cache(
    method: str,
    kind: str,
    session: AsyncSession,
    stmt,
    page: int,
    size: int,
    to_dict: Callable[[Any], dict],
) -> dict[str, Any]:
    page, size = _clamp_page(page, size)
    records, total = await _paginate_stmt(
        session, stmt, page, size, to_dict,
    )
    snapshot_at = await _last_snapshot_at(session, kind)
    return {
        'source': 'cache',
        'method': method,
        'snapshot_at': snapshot_at,
        'page': page,
        'size': size,
        'total': total,
        'record_count': len(records),
        'records': records,
    }


async def _cached_response(
    method: str,
    kind: str,
    records: list[dict],
) -> dict[str, Any]:
    """Legacy: неспагинированный ответ (для live-режима и
    gross-profit, где записи считаются в Python)."""
    async with SessionLocal() as session:
        snapshot_at = await _last_snapshot_at(session, kind)
    return {
        'source': 'cache',
        'method': method,
        'snapshot_at': snapshot_at,
        'page': 1,
        'size': len(records),
        'total': len(records),
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
    page: int = Query(1, ge=1),
    size: int = Query(PAGE_SIZE_DEFAULT, ge=1, le=PAGE_SIZE_MAX),
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
    stmt = select(Sale).where(*conds).order_by(Sale.date, Sale.id)
    return await _paged_cache(
        'sales.marketplace', 'sales', session,
        stmt, page, size, _sale_dict,
    )


@data_router.post('/api/sales/retail')
async def api_retail_sales(
    req: RetailSalesRequest,
    live: bool = Query(False),
    page: int = Query(1, ge=1),
    size: int = Query(PAGE_SIZE_DEFAULT, ge=1, le=PAGE_SIZE_MAX),
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
    stmt = (
        select(Sale)
        .where(
            Sale.date >= req.date_from,
            Sale.date <= req.date_to,
            Sale.channel == 'магазин',
        )
        .order_by(Sale.date, Sale.id)
    )
    return await _paged_cache(
        'sales.retail', 'sales', session,
        stmt, page, size, _sale_dict,
    )


@data_router.post('/api/sales/all')
async def api_all_sales(
    req: AllSalesRequest,
    live: bool = Query(False),
    page: int = Query(1, ge=1),
    size: int = Query(PAGE_SIZE_DEFAULT, ge=1, le=PAGE_SIZE_MAX),
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
    stmt = (
        select(Sale)
        .where(
            Sale.date >= req.date_from,
            Sale.date <= req.date_to,
        )
        .order_by(Sale.date, Sale.id)
    )
    return await _paged_cache(
        'sales.all', 'sales', session,
        stmt, page, size, _sale_dict,
    )


@data_router.post('/api/movements')
async def api_movements(
    req: MovementsRequest,
    live: bool = Query(False),
    page: int = Query(1, ge=1),
    size: int = Query(PAGE_SIZE_DEFAULT, ge=1, le=PAGE_SIZE_MAX),
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
    stmt = (
        select(Movement)
        .where(*conds)
        .order_by(Movement.period, Movement.id)
    )
    return await _paged_cache(
        f'movements.{req.kind}', 'movements', session,
        stmt, page, size, _movement_dict,
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
    page: int = Query(1, ge=1),
    size: int = Query(PAGE_SIZE_DEFAULT, ge=1, le=PAGE_SIZE_MAX),
    session: AsyncSession = Depends(get_session),
):
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

    page, size = _clamp_page(page, size)
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = int(
        (await session.execute(count_stmt)).scalar() or 0
    )
    paged = stmt.limit(size).offset((page - 1) * size)
    rows = (await session.execute(paged)).all()

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

    snapshot_at = await _last_snapshot_at(
        session, 'sales_turnover',
    )
    return {
        'source': 'cache',
        'method': 'gross_profit',
        'snapshot_at': snapshot_at,
        'page': page,
        'size': size,
        'total': total,
        'record_count': len(records),
        'records': records,
    }


def _month_floor(dt: datetime) -> datetime:
    return datetime(dt.year, dt.month, 1)


@data_router.post('/api/stock')
async def api_stock(
    req: StockRequest,
    live: bool = Query(False),
    page: int = Query(1, ge=1),
    size: int = Query(PAGE_SIZE_DEFAULT, ge=1, le=PAGE_SIZE_MAX),
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
    stmt = select(StockSnapshot)
    if conds:
        stmt = stmt.where(*conds)
    # Товары без артикула (прочие ТМЦ / оборудование) — в конец списка,
    # чтобы первые страницы показывали основную одежду.
    stmt = stmt.order_by(
        (StockSnapshot.article == '').asc(),
        StockSnapshot.article,
        StockSnapshot.warehouse,
        StockSnapshot.id,
    )
    return await _paged_cache(
        'stock', 'stock', session,
        stmt, page, size, _stock_dict,
    )


@data_router.post('/api/stock/by-article')
async def api_stock_by_article(
    req: StockByArticleRequest,
    live: bool = Query(False),
    page: int = Query(1, ge=1),
    size: int = Query(PAGE_SIZE_DEFAULT, ge=1, le=PAGE_SIZE_MAX),
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
    stmt = (
        select(StockSnapshot)
        .where(StockSnapshot.article == req.article)
        .order_by(StockSnapshot.warehouse, StockSnapshot.id)
    )
    return await _paged_cache(
        'stock.by_article', 'stock', session,
        stmt, page, size, _stock_dict,
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


_EXT_MIME = {
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'png': 'image/png',
    'webp': 'image/webp',
    'gif': 'image/gif',
}


@data_router.get('/api/products')
async def api_products_list(
    prefix: str = Query(''),
    page: int = Query(1, ge=1),
    size: int = Query(PAGE_SIZE_DEFAULT, ge=1, le=PAGE_SIZE_MAX),
    only_active: bool = Query(True),
    include_service: bool = Query(False),
):
    page, size = _clamp_page(page, size)
    try:
        rows, total = await asyncio.gather(
            list_products_async(
                prefix=prefix,
                limit=size,
                offset=(page - 1) * size,
                only_active=only_active,
                include_service=include_service,
            ),
            count_products_async(
                prefix=prefix,
                only_active=only_active,
                include_service=include_service,
            ),
        )
    except Exception as exc:
        logger.exception('Ошибка получения товаров')
        raise HTTPException(status_code=502, detail=str(exc))
    return {
        'source': 'live',
        'method': 'products',
        'snapshot_at': None,
        'page': page,
        'size': size,
        'total': int(total),
        'record_count': len(rows),
        'records': rows,
    }


@data_router.get('/api/products/next-article')
async def api_products_next_article(
    prefix: str = Query(..., min_length=1),
):
    try:
        article = await next_article_async(prefix)
    except Exception as exc:
        logger.exception('Ошибка подбора артикула')
        raise HTTPException(status_code=502, detail=str(exc))
    return {'article': article}


@data_router.get('/api/products/exists')
async def api_products_exists(
    article: str = Query(..., min_length=1),
):
    try:
        exists = await article_exists_async(article)
    except Exception as exc:
        logger.exception('Ошибка проверки артикула')
        raise HTTPException(status_code=502, detail=str(exc))
    return {'article': article, 'exists': exists}


@data_router.get('/api/products/search')
async def api_products_search(
    prefix: str = Query(..., min_length=1),
):
    try:
        articles = await search_articles_async(prefix)
    except Exception as exc:
        logger.exception('Ошибка поиска артикулов')
        raise HTTPException(status_code=502, detail=str(exc))
    return {'prefix': prefix, 'articles': articles}


@data_router.get('/api/products/photo/{file_key}')
async def api_products_photo(file_key: str):
    try:
        content, ext = await photo_bytes_async(file_key)
    except ODataNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception('Ошибка получения фото')
        raise HTTPException(status_code=502, detail=str(exc))
    mime = _EXT_MIME.get(ext.lower(), 'application/octet-stream')
    return Response(
        content=content,
        media_type=mime,
        headers={'Cache-Control': 'public, max-age=86400'},
    )


@data_router.get('/api/products/{article}')
async def api_products_get(article: str):
    try:
        data = await get_product_async(article)
    except ArticleNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception('Ошибка получения товара')
        raise HTTPException(status_code=502, detail=str(exc))
    return data


@data_router.post('/api/products')
async def api_products_create(req: ProductCreate):
    payload = req.model_dump(by_alias=False)
    article = (payload.get('article') or '').strip()
    prefix = (payload.pop('article_prefix', None) or '').strip()
    if not article:
        if not prefix:
            raise HTTPException(
                status_code=400,
                detail=(
                    'Нужен либо article, либо article_prefix'
                ),
            )
        try:
            article = await next_article_async(prefix)
        except Exception as exc:
            logger.exception('Ошибка подбора артикула')
            raise HTTPException(
                status_code=502, detail=str(exc),
            )
    payload['article'] = article

    try:
        result = await create_product_async(payload)
    except ProductExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ODataValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception('Ошибка создания товара')
        raise HTTPException(status_code=502, detail=str(exc))
    return {'article': article, 'result': result}


@data_router.patch('/api/products/{article}')
async def api_products_update(
    article: str, req: ProductUpdate,
):
    payload: dict = {}
    if req.name is not None:
        payload['name'] = req.name
    if req.price is not None:
        payload['price'] = req.price
    if req.sizes:
        payload['sizes'] = [
            {
                'global': s.global_size,
                'ru': s.ru_size,
                'barcode': s.barcode,
            }
            for s in req.sizes
        ]
    if not payload:
        raise HTTPException(
            status_code=400,
            detail='Нечего обновлять',
        )
    try:
        result = await update_product_async(article, payload)
    except ArticleNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ODataValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception('Ошибка обновления товара')
        raise HTTPException(status_code=502, detail=str(exc))
    return result


@data_router.delete('/api/products/{article}')
async def api_products_delete(article: str):
    try:
        await delete_product_async(article)
    except ArticleNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception('Ошибка удаления товара')
        raise HTTPException(status_code=502, detail=str(exc))
    return {'ok': True, 'article': article}


app.include_router(data_router)
