import asyncio
import logging
from collections import defaultdict
from datetime import datetime
from typing import Any

from odata_1c.movements import (
    BATCH_KEYS,
    BARCODES,
    CHARACTERISTICS,
    DOCUMENT_OPERATION,
    EMPTY_GUID,
    EXPENSE_KINDS,
    MIN_PERIOD,
    NOMENCLATURE,
    ORGS_CATALOG,
    PAGE_SIZE,
    PAIRED_KINDS,
    RECEIPT_KINDS,
    RECORDER_TYPE_PREFIX,
    REGISTER,
    TRANSFER_KINDS,
    WAREHOUSES_CATALOG,
    WRITE_OFF_KINDS,
    _iso,
    _pair_transfers,
    _parse_dt,
    _parse_size,
    _short_kind,
)
from odata_1c.sales import (
    CHANNEL_RETAIL,
    CHANNEL_UNKNOWN,
    CONTRACTS,
    DOC_COMMISSION,
    DOC_COMMISSION_RETURNS,
    DOC_COMMISSION_SALES,
    DOC_RETAIL,
    DOC_RETAIL_SALES,
    TYPE_RETURN,
    TYPE_SALE,
    _resolve_channel,
)
from odata_1c.stock import QTY_FIELDS, STOCK, _row_qty

from .odata_async import AsyncOData1C

logger = logging.getLogger(__name__)


def _chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


async def _paginate(
    client: AsyncOData1C,
    endpoint: str,
    params: dict,
) -> list[dict]:
    rows: list[dict] = []
    skip = 0
    while True:
        p = dict(params)
        p['$top'] = str(PAGE_SIZE)
        p['$skip'] = str(skip)
        p['$format'] = 'json'
        try:
            data = await client.get(endpoint, p)
        except LookupError:
            logger.warning('Эндпоинт %s недоступен', endpoint)
            return rows
        page = data.get('value', [])
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            break
        skip += PAGE_SIZE
    return rows


async def _batch_by_keys(
    client: AsyncOData1C,
    endpoint: str,
    keys,
    select: str = '',
    key_field: str = 'Ref_Key',
) -> list[dict]:
    unique = [k for k in set(keys) if k and k != EMPTY_GUID]
    if not unique:
        return []

    async def one(chunk):
        cond = ' or '.join(
            f"{key_field} eq guid'{k}'" for k in chunk
        )
        params = {'$filter': cond, '$format': 'json'}
        if select:
            params['$select'] = select
        try:
            data = await client.get(endpoint, params)
        except LookupError:
            logger.warning('Эндпоинт %s недоступен', endpoint)
            return []
        return data.get('value', [])

    tasks = [one(c) for c in _chunks(unique, BATCH_KEYS)]
    parts = await asyncio.gather(*tasks)
    return [item for part in parts for item in part]


async def _resolve_by_keys(
    client: AsyncOData1C,
    endpoint: str,
    keys,
    select: str,
    key_field: str = 'Ref_Key',
) -> dict:
    rows = await _batch_by_keys(
        client, endpoint, keys, select, key_field,
    )
    return {r[key_field]: r for r in rows if key_field in r}


async def _resolve_barcodes(
    client: AsyncOData1C, nom_keys,
) -> dict:
    rows = await _batch_by_keys(
        client, BARCODES, nom_keys,
        select=(
            'Штрихкод,Номенклатура_Key,'
            'Характеристика_Key'
        ),
        key_field='Номенклатура_Key',
    )
    result: dict = {}
    for item in rows:
        key = (
            item.get('Номенклатура_Key', ''),
            item.get('Характеристика_Key', EMPTY_GUID),
        )
        if key not in result:
            result[key] = item.get('Штрихкод', '')
    return result


async def _resolve_documents(
    client: AsyncOData1C, recorders,
) -> dict:
    by_kind: dict[str, list[str]] = defaultdict(list)
    for guid, rtype in recorders:
        kind = _short_kind(rtype)
        if kind and guid and guid != EMPTY_GUID:
            by_kind[kind].append(guid)

    async def one_kind(kind, guids):
        rows = await _batch_by_keys(
            client, kind, guids,
            select='Ref_Key,Number,Date',
        )
        return kind, rows

    tasks = [
        one_kind(k, v) for k, v in by_kind.items()
    ]
    parts = await asyncio.gather(*tasks)
    docs: dict = {}
    for kind, rows in parts:
        for item in rows:
            item['_kind'] = kind
            docs[item['Ref_Key']] = item
    return docs


async def _resolve_names(
    client: AsyncOData1C, keys, endpoint: str,
) -> dict:
    got = await _resolve_by_keys(
        client, endpoint, keys,
        select='Ref_Key,Description',
    )
    return {
        k: v.get('Description', '') or ''
        for k, v in got.items()
    }


def _size_from(
    char_key: str,
    characteristics: dict,
    article: str,
) -> str | None:
    if not char_key or char_key == EMPTY_GUID:
        return None
    descr = characteristics.get(char_key, {}).get(
        'Description', '',
    ) or ''
    _, _, size = _parse_size(descr, article or '')
    return size or None


SALES_REGISTER = 'AccumulationRegister_Продажи'


async def _fetch_recorder_dims(
    client: AsyncOData1C,
    date_from: datetime,
    date_to: datetime,
) -> dict:
    """{Recorder_Key: (Склад_Key, Организация_Key)} из регистра Продажи.

    Регистр AccumulationRegister_Продажи для каждой строки хранит
    реальный Склад_Key и Организация_Key. Матчим по Recorder (это
    Ref_Key документа-регистратора — ОтчетКомиссионера,
    ОтчетОРозничныхПродажах, РасходнаяНакладная).
    """
    if date_from < MIN_PERIOD:
        date_from = MIN_PERIOD
    endpoint = (
        f"{SALES_REGISTER}/Turnovers("
        f"StartPeriod=datetime'{_iso(date_from)}',"
        f"EndPeriod=datetime'{_iso(date_to)}')"
    )
    rows = await _paginate(
        client, endpoint,
        {'$select': 'Документ,Склад_Key,Организация_Key'},
    )
    result: dict = {}
    for r in rows:
        rec = r.get('Документ') or ''
        wh = r.get('Склад_Key') or ''
        org = r.get('Организация_Key') or ''
        if not rec:
            continue
        prev = result.get(rec, ('', ''))
        result[rec] = (
            prev[0] or (wh if wh != EMPTY_GUID else ''),
            prev[1] or (org if org != EMPTY_GUID else ''),
        )
    return result


async def fetch_marketplace_sales(
    client: AsyncOData1C,
    date_from: datetime,
    date_to: datetime,
    channel: str | None = None,
) -> list[dict]:
    if date_from < MIN_PERIOD:
        date_from = MIN_PERIOD
    flt = (
        f"Date ge datetime'{_iso(date_from)}' and "
        f"Date le datetime'{_iso(date_to)}'"
    )
    headers = await _paginate(
        client, DOC_COMMISSION,
        {
            '$filter': flt,
            '$select': 'Ref_Key,Date,Договор_Key,Организация_Key',
            '$orderby': 'Date',
        },
    )
    if not headers:
        return []

    headers_by_ref = {h['Ref_Key']: h for h in headers}
    contract_keys = {
        (h.get('Договор_Key') or '') for h in headers
    }
    contracts = await _resolve_by_keys(
        client, CONTRACTS, contract_keys,
        select='Ref_Key,Description',
    )
    channel_by_contract = {
        k: _resolve_channel(v.get('Description', '') or '')
        for k, v in contracts.items()
    }
    channel_by_ref: dict = {}
    for h in headers:
        dk = h.get('Договор_Key') or ''
        channel_by_ref[h['Ref_Key']] = (
            channel_by_contract.get(dk, CHANNEL_UNKNOWN)
        )

    if channel:
        wanted = {
            r for r, c in channel_by_ref.items() if c == channel
        }
        if not wanted:
            return []
    else:
        wanted = set(headers_by_ref)

    refs = list(wanted)
    rows_sales, rows_returns, dims_by_ref = await asyncio.gather(
        _batch_by_keys(client, DOC_COMMISSION_SALES, refs),
        _batch_by_keys(client, DOC_COMMISSION_RETURNS, refs),
        _fetch_recorder_dims(client, date_from, date_to),
    )

    nom_keys: set = set()
    char_keys: set = set()
    for r in rows_sales + rows_returns:
        nk = r.get('Номенклатура_Key', '')
        ck = r.get('Характеристика_Key', '')
        if nk:
            nom_keys.add(nk)
        if ck and ck != EMPTY_GUID:
            char_keys.add(ck)

    org_keys: set = {
        (h.get('Организация_Key') or '')
        for h in headers if h['Ref_Key'] in wanted
    }
    wh_keys: set = set()
    for wh, org in dims_by_ref.values():
        if wh:
            wh_keys.add(wh)
        if org:
            org_keys.add(org)

    (
        nomenclature, characteristics,
        organization_names, warehouse_names,
    ) = await asyncio.gather(
        _resolve_by_keys(
            client, NOMENCLATURE, nom_keys,
            select='Ref_Key,Description,Артикул',
        ),
        _resolve_by_keys(
            client, CHARACTERISTICS, char_keys,
            select='Ref_Key,Description',
        ),
        _resolve_names(client, org_keys, ORGS_CATALOG),
        _resolve_names(client, wh_keys, WAREHOUSES_CATALOG),
    )

    out: list[dict] = []
    for rows, sale_type, sign in (
        (rows_sales, TYPE_SALE, 1),
        (rows_returns, TYPE_RETURN, -1),
    ):
        for row in rows:
            ref = row.get('Ref_Key', '')
            hdr = headers_by_ref.get(ref)
            if not hdr:
                continue
            ch = channel_by_ref.get(ref, CHANNEL_UNKNOWN)
            if channel and ch != channel:
                continue
            nk = row.get('Номенклатура_Key', '') or ''
            ck = row.get('Характеристика_Key', '') or ''
            if ck == EMPTY_GUID:
                ck = ''
            article = (
                nomenclature.get(nk, {}).get('Артикул', '')
                or None
            )
            size = _size_from(ck, characteristics, article or '')
            qty = float(row.get('Количество', 0) or 0) * sign
            amount = float(row.get('Сумма', 0) or 0) * sign

            wh_key, org_key_reg = dims_by_ref.get(ref, ('', ''))
            warehouse = None
            if wh_key:
                warehouse = warehouse_names.get(wh_key) or wh_key
            org_key = hdr.get('Организация_Key') or org_key_reg or ''
            organization = None
            if org_key and org_key != EMPTY_GUID:
                organization = (
                    organization_names.get(org_key) or org_key
                )

            out.append({
                'nomenclature_key': nk,
                'characteristic_key': ck or None,
                'article': article,
                'size': size,
                'channel': ch,
                'quantity': qty,
                'amount': amount,
                'date': _parse_dt(hdr.get('Date')),
                'type': sale_type,
                'warehouse': warehouse,
                'organization': organization,
            })
    return out


async def fetch_retail_sales(
    client: AsyncOData1C,
    date_from: datetime,
    date_to: datetime,
) -> list[dict]:
    if date_from < MIN_PERIOD:
        date_from = MIN_PERIOD
    flt = (
        f"Date ge datetime'{_iso(date_from)}' and "
        f"Date le datetime'{_iso(date_to)}'"
    )
    headers = await _paginate(
        client, DOC_RETAIL,
        {
            '$filter': flt,
            '$select': (
                'Ref_Key,Date,Организация_Key,'
                'СтруктурнаяЕдиница_Key'
            ),
            '$orderby': 'Date',
        },
    )
    if not headers:
        return []
    headers_by_ref = {h['Ref_Key']: h for h in headers}
    refs = list(headers_by_ref)
    rows = await _batch_by_keys(client, DOC_RETAIL_SALES, refs)

    nom_keys: set = set()
    char_keys: set = set()
    for r in rows:
        nk = r.get('Номенклатура_Key', '')
        ck = r.get('Характеристика_Key', '')
        if nk:
            nom_keys.add(nk)
        if ck and ck != EMPTY_GUID:
            char_keys.add(ck)

    org_keys = {(h.get('Организация_Key') or '') for h in headers}
    wh_keys = {
        (h.get('СтруктурнаяЕдиница_Key') or '') for h in headers
    }

    (
        nomenclature, characteristics,
        organization_names, warehouse_names,
    ) = await asyncio.gather(
        _resolve_by_keys(
            client, NOMENCLATURE, nom_keys,
            select='Ref_Key,Description,Артикул',
        ),
        _resolve_by_keys(
            client, CHARACTERISTICS, char_keys,
            select='Ref_Key,Description',
        ),
        _resolve_names(client, org_keys, ORGS_CATALOG),
        _resolve_names(client, wh_keys, WAREHOUSES_CATALOG),
    )

    out: list[dict] = []
    for row in rows:
        ref = row.get('Ref_Key', '')
        hdr = headers_by_ref.get(ref)
        if not hdr:
            continue
        nk = row.get('Номенклатура_Key', '') or ''
        ck = row.get('Характеристика_Key', '') or ''
        if ck == EMPTY_GUID:
            ck = ''
        article = (
            nomenclature.get(nk, {}).get('Артикул', '')
            or None
        )
        size = _size_from(ck, characteristics, article or '')
        qty = float(row.get('Количество', 0) or 0)
        amount = float(row.get('Сумма', 0) or 0)
        sale_type = (
            TYPE_RETURN if qty < 0 or amount < 0 else TYPE_SALE
        )

        wh_key = hdr.get('СтруктурнаяЕдиница_Key') or ''
        warehouse = None
        if wh_key and wh_key != EMPTY_GUID:
            warehouse = warehouse_names.get(wh_key) or wh_key
        org_key = hdr.get('Организация_Key') or ''
        organization = None
        if org_key and org_key != EMPTY_GUID:
            organization = (
                organization_names.get(org_key) or org_key
            )

        out.append({
            'nomenclature_key': nk,
            'characteristic_key': ck or None,
            'article': article,
            'size': size,
            'channel': CHANNEL_RETAIL,
            'quantity': qty,
            'amount': amount,
            'date': _parse_dt(hdr.get('Date')),
            'type': sale_type,
            'warehouse': warehouse,
            'organization': organization,
        })
    return out


async def fetch_all_sales(
    client: AsyncOData1C,
    date_from: datetime,
    date_to: datetime,
) -> list[dict]:
    mp, rt = await asyncio.gather(
        fetch_marketplace_sales(client, date_from, date_to),
        fetch_retail_sales(client, date_from, date_to),
    )
    return list(mp) + list(rt)


def _op_type(kind: str, rtype: str) -> str:
    return DOCUMENT_OPERATION.get(kind, kind or rtype)


async def _fetch_register(
    client: AsyncOData1C,
    date_from: datetime,
    date_to: datetime,
    recorder_kinds=None,
) -> list[dict]:
    if date_from < MIN_PERIOD:
        date_from = MIN_PERIOD
    conds = [
        f"Period ge datetime'{_iso(date_from)}'",
        f"Period le datetime'{_iso(date_to)}'",
    ]
    if recorder_kinds:
        kind_expr = ' or '.join(
            f"Recorder_Type eq "
            f"'{RECORDER_TYPE_PREFIX}{k}'"
            for k in recorder_kinds
        )
        conds.append(f'({kind_expr})')
    flt = ' and '.join(conds)
    try:
        return await _paginate(
            client, REGISTER,
            {'$filter': flt, '$orderby': 'Period'},
        )
    except ConnectionError:
        if not recorder_kinds:
            raise
        logger.warning(
            'Фильтр Recorder_Type не сработал, беру всё',
        )
        base_flt = (
            f"Period ge datetime'{_iso(date_from)}' and "
            f"Period le datetime'{_iso(date_to)}'"
        )
        rows = await _paginate(
            client, REGISTER,
            {'$filter': base_flt, '$orderby': 'Period'},
        )
        allowed = {
            f'{RECORDER_TYPE_PREFIX}{k}' for k in recorder_kinds
        }
        return [
            r for r in rows
            if r.get('Recorder_Type') in allowed
        ]


async def _collect_movement_catalogs(
    client: AsyncOData1C, rows,
) -> dict:
    nom_keys = {r.get('Номенклатура_Key', '') for r in rows}
    char_keys = {r.get('Характеристика_Key', '') for r in rows}
    org_keys = {r.get('Организация_Key', '') for r in rows}
    wh_keys = {
        r.get('СтруктурнаяЕдиница_Key', '') for r in rows
    }
    recorders = {
        (r.get('Recorder', ''), r.get('Recorder_Type', ''))
        for r in rows
    }
    (
        nomenclature,
        characteristics,
        barcodes,
        documents,
        organizations,
        warehouses,
    ) = await asyncio.gather(
        _resolve_by_keys(
            client, NOMENCLATURE, nom_keys,
            select='Ref_Key,Description,Артикул',
        ),
        _resolve_by_keys(
            client, CHARACTERISTICS, char_keys,
            select='Ref_Key,Description',
        ),
        _resolve_barcodes(client, nom_keys),
        _resolve_documents(client, recorders),
        _resolve_names(client, org_keys, ORGS_CATALOG),
        _resolve_names(client, wh_keys, WAREHOUSES_CATALOG),
    )
    return {
        'nomenclature': nomenclature,
        'characteristics': characteristics,
        'barcodes': barcodes,
        'documents': documents,
        'organizations': organizations,
        'warehouses': warehouses,
    }


def _movement_record(
    period,
    quantity: float,
    nom_key: str,
    char_key: str,
    operation_type: str,
    wh_from: str,
    wh_to: str,
    org_from: str,
    org_to: str,
    recorder: str,
    document: dict,
    catalogs: dict,
) -> dict:
    noms = catalogs['nomenclature']
    chars = catalogs['characteristics']
    barcodes = catalogs['barcodes']
    orgs = catalogs['organizations']
    whs = catalogs['warehouses']
    nom = noms.get(nom_key, {})
    article = nom.get('Артикул', '') or ''
    name = nom.get('Description', '') or ''
    char_descr = ''
    if char_key and char_key != EMPTY_GUID:
        char_descr = chars.get(char_key, {}).get(
            'Description', '',
        ) or ''
    sg, sr, size = _parse_size(char_descr, article)
    barcode = barcodes.get(
        (nom_key, char_key or EMPTY_GUID), '',
    )
    kind = document.get('_kind', '')
    kind_short = (
        kind.replace('Document_', '') if kind else ''
    )
    return {
        'period': _parse_dt(period),
        'name': name,
        'article': article,
        'barcode': barcode,
        'size': size,
        'size_global': sg,
        'size_ru': sr,
        'quantity': float(quantity or 0),
        'operation_type': operation_type,
        'warehouse_from': (
            whs.get(wh_from, wh_from) if wh_from else ''
        ),
        'warehouse_to': (
            whs.get(wh_to, wh_to) if wh_to else ''
        ),
        'organization_from': (
            orgs.get(org_from, org_from) if org_from else ''
        ),
        'organization_to': (
            orgs.get(org_to, org_to) if org_to else ''
        ),
        'warehouse_from_ref': wh_from,
        'warehouse_to_ref': wh_to,
        'organization_from_ref': org_from,
        'organization_to_ref': org_to,
        'document_kind': kind_short,
        'document_number': document.get('Number', ''),
        'document_date': _parse_dt(document.get('Date')),
        'recorder': recorder,
    }


def _prefilter(rows, organization: str, warehouse: str):
    paired_rtypes = {
        f'{RECORDER_TYPE_PREFIX}{k}' for k in PAIRED_KINDS
    }

    def row_hit(r):
        if organization and (
            r.get('Организация_Key', '') != organization
        ):
            return False
        if warehouse and (
            r.get('СтруктурнаяЕдиница_Key', '') != warehouse
        ):
            return False
        return True

    paired_recorders = {
        r.get('Recorder', '')
        for r in rows
        if r.get('Recorder_Type') in paired_rtypes
        and row_hit(r)
    }

    def keep(r):
        if r.get('Recorder_Type') in paired_rtypes:
            return r.get('Recorder', '') in paired_recorders
        return row_hit(r)

    return [r for r in rows if keep(r)]


def _normalize_movements(rows, catalogs, organization, warehouse):
    docs = catalogs['documents']
    paired_rtypes = {
        f'{RECORDER_TYPE_PREFIX}{k}' for k in PAIRED_KINDS
    }
    transfer_rows = [
        r for r in rows
        if r.get('Recorder_Type') in paired_rtypes
    ]
    other_rows = [
        r for r in rows
        if r.get('Recorder_Type') not in paired_rtypes
    ]
    result: list[dict] = []
    pairs, orphans = _pair_transfers(transfer_rows)
    for exp, rec in pairs:
        if organization and organization not in (
            exp.get('Организация_Key', ''),
            rec.get('Организация_Key', ''),
        ):
            continue
        if warehouse and warehouse not in (
            exp.get('СтруктурнаяЕдиница_Key', ''),
            rec.get('СтруктурнаяЕдиница_Key', ''),
        ):
            continue
        recorder = exp.get('Recorder', '')
        doc = docs.get(recorder, {})
        org_from = exp.get('Организация_Key', '')
        org_to = rec.get('Организация_Key', '')
        op = (
            'межфирменное'
            if org_from and org_to and org_from != org_to
            else 'перемещение'
        )
        result.append(_movement_record(
            period=exp.get('Period'),
            quantity=rec.get('Количество', 0),
            nom_key=rec.get('Номенклатура_Key', ''),
            char_key=rec.get(
                'Характеристика_Key', EMPTY_GUID,
            ),
            operation_type=op,
            wh_from=exp.get('СтруктурнаяЕдиница_Key', ''),
            wh_to=rec.get('СтруктурнаяЕдиница_Key', ''),
            org_from=org_from,
            org_to=org_to,
            recorder=recorder,
            document=doc,
            catalogs=catalogs,
        ))

    def _passes(r):
        if organization and (
            r.get('Организация_Key', '') != organization
        ):
            return False
        if warehouse and (
            r.get('СтруктурнаяЕдиница_Key', '') != warehouse
        ):
            return False
        return True

    for row in orphans + other_rows:
        if not _passes(row):
            continue
        recorder = row.get('Recorder', '')
        doc = docs.get(recorder, {})
        kind = _short_kind(row.get('Recorder_Type', ''))
        rtype = row.get('RecordType', '')
        wh = row.get('СтруктурнаяЕдиница_Key', '')
        org = row.get('Организация_Key', '')
        if rtype == 'Expense':
            wf, wt, of_, ot = wh, '', org, ''
        elif rtype == 'Receipt':
            wf, wt, of_, ot = '', wh, '', org
        else:
            wf, wt, of_, ot = wh, '', org, ''
        result.append(_movement_record(
            period=row.get('Period'),
            quantity=row.get('Количество', 0),
            nom_key=row.get('Номенклатура_Key', ''),
            char_key=row.get(
                'Характеристика_Key', EMPTY_GUID,
            ),
            operation_type=_op_type(kind, rtype),
            wh_from=wf, wh_to=wt,
            org_from=of_, org_to=ot,
            recorder=recorder,
            document=doc,
            catalogs=catalogs,
        ))
    return result


async def fetch_movements(
    client: AsyncOData1C,
    date_from: datetime,
    date_to: datetime,
    organization: str = '',
    warehouse: str = '',
    kinds: tuple | None = None,
) -> list[dict]:
    rows = await _fetch_register(
        client, date_from, date_to, recorder_kinds=kinds,
    )
    if not rows:
        return []
    if organization or warehouse:
        rows = _prefilter(rows, organization, warehouse)
        if not rows:
            return []
    catalogs = await _collect_movement_catalogs(client, rows)
    return _normalize_movements(
        rows, catalogs,
        organization=organization or '',
        warehouse=warehouse or '',
    )


MOVEMENT_KIND_MAP = {
    'transfers': TRANSFER_KINDS,
    'write_offs': WRITE_OFF_KINDS,
    'receipts': RECEIPT_KINDS,
    'expenses': EXPENSE_KINDS,
    'all': None,
}


async def fetch_stock(
    client: AsyncOData1C,
    warehouse: str = '',
    organization: str = '',
    nomenclature: str = '',
    only_positive: bool = True,
) -> list[dict]:
    conds = []
    if warehouse:
        conds.append(
            f"СтруктурнаяЕдиница_Key eq guid'{warehouse}'"
        )
    if organization:
        conds.append(
            f"Организация_Key eq guid'{organization}'"
        )
    if nomenclature:
        conds.append(
            f"Номенклатура_Key eq guid'{nomenclature}'"
        )
    if only_positive:
        or_expr = ' or '.join(
            f'{f} gt 0' for f in QTY_FIELDS
        )
        conds.append(f'({or_expr})')
    params = {}
    if conds:
        params['$filter'] = ' and '.join(conds)

    rows = await _paginate(client, STOCK, params)
    if not rows:
        return []

    nom_keys = {r.get('Номенклатура_Key', '') for r in rows}
    char_keys = {r.get('Характеристика_Key', '') for r in rows}
    org_keys = {r.get('Организация_Key', '') for r in rows}
    wh_keys = {
        r.get('СтруктурнаяЕдиница_Key', '') for r in rows
    }
    (
        nomenclature_r,
        characteristics,
        barcodes,
        organizations,
        warehouses,
    ) = await asyncio.gather(
        _resolve_by_keys(
            client, NOMENCLATURE, nom_keys,
            select='Ref_Key,Description,Артикул',
        ),
        _resolve_by_keys(
            client, CHARACTERISTICS, char_keys,
            select='Ref_Key,Description',
        ),
        _resolve_barcodes(client, nom_keys),
        _resolve_names(client, org_keys, ORGS_CATALOG),
        _resolve_names(client, wh_keys, WAREHOUSES_CATALOG),
    )

    result: list[dict] = []
    for row in rows:
        nk = row.get('Номенклатура_Key', '')
        ck = row.get('Характеристика_Key', EMPTY_GUID)
        wk = row.get('СтруктурнаяЕдиница_Key', '')
        ok = row.get('Организация_Key', '')
        nom = nomenclature_r.get(nk, {})
        article = nom.get('Артикул', '') or ''
        name = nom.get('Description', '') or ''
        char_descr = ''
        if ck and ck != EMPTY_GUID:
            char_descr = characteristics.get(
                ck, {},
            ).get('Description', '') or ''
        sg, sr, size = _parse_size(char_descr, article)
        qty = _row_qty(row)
        if only_positive and qty <= 0:
            continue
        result.append({
            'name': name,
            'article': article,
            'barcode': barcodes.get(
                (nk, ck or EMPTY_GUID), '',
            ),
            'size': size,
            'size_global': sg,
            'size_ru': sr,
            'warehouse': (
                warehouses.get(wk, wk) if wk else ''
            ),
            'organization': (
                organizations.get(ok, ok)
                if ok and ok != EMPTY_GUID else ''
            ),
            'quantity': qty,
            'nomenclature_ref': nk,
            'warehouse_ref': wk,
            'organization_ref': (
                ok if ok and ok != EMPTY_GUID else ''
            ),
        })
    return result


async def fetch_stock_by_article(
    client: AsyncOData1C,
    article: str,
) -> list[dict]:
    if not article:
        return []
    try:
        data = await client.get(NOMENCLATURE, {
            '$filter': f"Артикул eq '{article}'",
            '$select': 'Ref_Key',
            '$format': 'json',
        })
    except LookupError:
        return []
    items = data.get('value', [])
    if not items:
        return []
    tasks = [
        fetch_stock(client, nomenclature=it['Ref_Key'])
        for it in items if it.get('Ref_Key')
    ]
    parts = await asyncio.gather(*tasks)
    return [row for part in parts for row in part]


async def fetch_catalog_names(
    client: AsyncOData1C, endpoint: str,
) -> list[dict]:
    """Список {ref, name} для селекторов на фронте."""
    rows = await _paginate(
        client, endpoint,
        {'$select': 'Ref_Key,Description', '$orderby': 'Description'},
    )
    return [
        {'ref': r['Ref_Key'], 'name': r.get('Description', '') or ''}
        for r in rows if r.get('Ref_Key')
    ]
