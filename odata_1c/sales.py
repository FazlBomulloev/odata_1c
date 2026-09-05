import logging
from datetime import datetime

from .client import OData1C
from .exceptions import ODataError, ODataNotFoundError
from .models import SaleRecord
from .movements import (
    BATCH_KEYS,
    CHARACTERISTICS,
    EMPTY_GUID,
    MIN_PERIOD,
    NOMENCLATURE,
    ORGS_CATALOG,
    PAGE_SIZE,
    RECORDER_TYPE_PREFIX,
    WAREHOUSES_CATALOG,
    _batch_get_by_keys,
    _chunks,
    _parse_dt,
    _parse_size,
    _period_bounds,
    _resolve_names,
)

logger = logging.getLogger(__name__)

DOC_COMMISSION = 'Document_ОтчетКомиссионера'
DOC_COMMISSION_SALES = 'Document_ОтчетКомиссионера_Запасы'
DOC_COMMISSION_RETURNS = (
    'Document_ОтчетКомиссионера_ЗапасыВозвраты'
)
DOC_RETAIL = 'Document_ОтчетОРозничныхПродажах'
DOC_RETAIL_SALES = 'Document_ОтчетОРозничныхПродажах_Запасы'
CONTRACTS = 'Catalog_ДоговорыКонтрагентов'
INCOME_EXPENSE_REG = (
    'AccumulationRegister_ДоходыИРасходы_RecordType'
)
COMMISSION_RECORDER_TYPE = (
    f'{RECORDER_TYPE_PREFIX}{DOC_COMMISSION}'
)

CHANNEL_TOKENS = (
    ('WB', ('wb', 'вб', 'рвб', 'wildberries', 'вайлдберриз')),
    ('Ozon', ('ozon', 'озон')),
    ('Lamoda', ('lamoda', 'ламода', 'купишуз')),
)
CHANNEL_UNKNOWN = 'unknown'
CHANNEL_RETAIL = 'магазин'

TYPE_SALE = 'продажа'
TYPE_RETURN = 'возврат'

def _resolve_channel(description: str) -> str:
    if not description:
        return CHANNEL_UNKNOWN
    low = description.lower()
    for channel, tokens in CHANNEL_TOKENS:
        if any(t in low for t in tokens):
            return channel
    return CHANNEL_UNKNOWN

def _fetch_headers(
    client: OData1C,
    endpoint: str,
    date_from,
    date_to,
    select: str,
) -> list[dict]:
    if isinstance(date_from, datetime) and date_from < MIN_PERIOD:
        date_from = MIN_PERIOD
    d_from, d_to = _period_bounds(date_from, date_to)

    flt = (
        f"Date ge datetime'{d_from}' and "
        f"Date le datetime'{d_to}'"
    )
    rows: list[dict] = []
    skip = 0

    while True:
        params = {
            '$filter': flt,
            '$select': select,
            '$top': str(PAGE_SIZE),
            '$skip': str(skip),
            '$orderby': 'Date,Ref_Key',
            '$format': 'json',
        }
        try:
            data = client.get(endpoint, params)
        except ODataNotFoundError:
            logger.warning('Документ %s недоступен', endpoint)
            return []
        page = data.get('value', [])
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            break
        skip += PAGE_SIZE
    logger.info(
        '%s: %d шапок за [%s .. %s]',
        endpoint, len(rows), d_from, d_to,
    )
    return rows

def _fetch_rows_by_refs(
    client: OData1C,
    endpoint: str,
    refs,
) -> list[dict]:
    result: list[dict] = []
    unique = [r for r in set(refs) if r and r != EMPTY_GUID]
    for chunk in _chunks(unique, BATCH_KEYS):
        cond = ' or '.join(
            f"Ref_Key eq guid'{r}'" for r in chunk
        )
        params = {
            '$filter': cond,
            '$format': 'json',
        }
        try:
            data = client.get(endpoint, params)
        except ODataNotFoundError:
            logger.warning('ТЧ %s недоступна', endpoint)
            return result
        except ODataError as exc:
            logger.warning(
                'Ошибка чтения ТЧ %s: %s', endpoint, exc,
            )
            continue
        result.extend(data.get('value', []))
    return result

def _fetch_commission_warehouses(
    client: OData1C,
    date_from,
    date_to,
) -> dict:
    if isinstance(date_from, datetime) and date_from < MIN_PERIOD:
        date_from = MIN_PERIOD
    d_from, d_to = _period_bounds(date_from, date_to)

    flt = (
        f"Period ge datetime'{d_from}' and "
        f"Period le datetime'{d_to}' and "
        f"Recorder_Type eq '{COMMISSION_RECORDER_TYPE}'"
    )
    rows: list[dict] = []
    skip = 0
    while True:
        params = {
            '$filter': flt,
            '$select': 'Recorder,СтруктурнаяЕдиница_Key',
            '$top': str(PAGE_SIZE),
            '$skip': str(skip),
            '$orderby': 'Period,Recorder,LineNumber',
            '$format': 'json',
        }
        try:
            data = client.get(INCOME_EXPENSE_REG, params)
        except ODataNotFoundError:
            logger.warning(
                'Регистр %s недоступен', INCOME_EXPENSE_REG,
            )
            return {}
        except ODataError as exc:
            logger.warning(
                'Ошибка чтения %s: %s', INCOME_EXPENSE_REG, exc,
            )
            return {}
        page = data.get('value', [])
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            break
        skip += PAGE_SIZE

    result: dict = {}
    conflicts = 0
    for r in rows:
        rec = r.get('Recorder', '') or ''
        wh = r.get('СтруктурнаяЕдиница_Key', '') or ''
        if not rec or not wh or wh == EMPTY_GUID:
            continue
        prev = result.get(rec)
        if prev is None:
            result[rec] = wh
        elif prev != wh:
            conflicts += 1
    if conflicts:
        logger.warning(
            'В %d ОтчетКомиссионера склад проводок неоднороден, '
            'взят первый', conflicts,
        )
    logger.info(
        'Комиссионер: сматчил склад для %d документов', len(result),
    )
    return result

def _resolve_contracts(client: OData1C, keys) -> dict:
    contracts = _batch_get_by_keys(
        client, CONTRACTS, keys,
        select='Ref_Key,Description',
    )
    return {
        k: _resolve_channel(v.get('Description', '') or '')
        for k, v in contracts.items()
    }

def _resolve_nomenclature(
    client: OData1C, keys,
) -> dict:
    return _batch_get_by_keys(
        client, NOMENCLATURE, keys,
        select='Ref_Key,Description,Артикул',
    )

def _resolve_characteristics(
    client: OData1C, keys,
) -> dict:
    return _batch_get_by_keys(
        client, CHARACTERISTICS, keys,
        select='Ref_Key,Description',
    )

def _row_to_sale(
    row: dict,
    header: dict,
    channel: str,
    sale_type: str,
    nomenclature: dict,
    characteristics: dict,
    sign: int,
    warehouse_by_ref: dict | None = None,
    warehouse_names: dict | None = None,
    organization_names: dict | None = None,
) -> SaleRecord:
    nom_key = row.get('Номенклатура_Key', '') or ''
    char_key = row.get('Характеристика_Key', '') or ''
    if char_key == EMPTY_GUID:
        char_key = ''

    nom = nomenclature.get(nom_key, {}) if nom_key else {}
    article = nom.get('Артикул', '') or None

    char_descr = ''
    if char_key:
        char_descr = characteristics.get(
            char_key, {},
        ).get('Description', '') or ''
    _, _, size = _parse_size(char_descr, article or '')
    size = size or None

    qty = float(row.get('Количество', 0) or 0)
    amount = float(row.get('Сумма', 0) or 0)
    if sign < 0:
        qty = -qty
        amount = -amount

    ref = header.get('Ref_Key', '') or ''
    wh_key = ''
    if warehouse_by_ref:
        wh_key = warehouse_by_ref.get(ref, '') or ''
    warehouse = None
    if wh_key and warehouse_names is not None:
        warehouse = warehouse_names.get(wh_key) or wh_key

    org_key = header.get('Организация_Key', '') or ''
    organization = None
    if org_key and org_key != EMPTY_GUID:
        if organization_names is not None:
            organization = organization_names.get(org_key) or org_key
        else:
            organization = org_key

    return SaleRecord(
        nomenclature_key=nom_key,
        characteristic_key=char_key or None,
        article=article,
        size=size,
        channel=channel,
        quantity=qty,
        amount=amount,
        date=_parse_dt(header.get('Date')),
        type=sale_type,
        warehouse=warehouse,
        organization=organization,
    )

def _build_records(
    rows: list[dict],
    headers_by_ref: dict,
    channel_by_ref: dict,
    nomenclature: dict,
    characteristics: dict,
    sale_type: str,
    sign: int,
    channel_filter: str | None = None,
    warehouse_by_ref: dict | None = None,
    warehouse_names: dict | None = None,
    organization_names: dict | None = None,
) -> list[SaleRecord]:
    result: list[SaleRecord] = []
    for row in rows:
        ref = row.get('Ref_Key', '') or ''
        header = headers_by_ref.get(ref)
        if not header:
            continue
        channel = channel_by_ref.get(ref, CHANNEL_UNKNOWN)
        if channel_filter and channel != channel_filter:
            continue
        result.append(_row_to_sale(
            row, header, channel, sale_type,
            nomenclature, characteristics, sign,
            warehouse_by_ref=warehouse_by_ref,
            warehouse_names=warehouse_names,
            organization_names=organization_names,
        ))
    return result

def _collect_catalogs(
    client: OData1C,
    rows_sales: list[dict],
    rows_returns: list[dict],
) -> tuple[dict, dict]:
    nom_keys = set()
    char_keys = set()
    for row in rows_sales + rows_returns:
        nk = row.get('Номенклатура_Key', '')
        ck = row.get('Характеристика_Key', '')
        if nk:
            nom_keys.add(nk)
        if ck and ck != EMPTY_GUID:
            char_keys.add(ck)
    nomenclature = _resolve_nomenclature(client, nom_keys)
    characteristics = _resolve_characteristics(client, char_keys)
    return nomenclature, characteristics

def get_marketplace_sales(
    client: OData1C,
    date_from,
    date_to,
    channel: str | None = None,
) -> list[SaleRecord]:
    headers = _fetch_headers(
        client, DOC_COMMISSION, date_from, date_to,
        select='Ref_Key,Date,Договор_Key,Организация_Key',
    )
    if not headers:
        return []

    headers_by_ref = {h['Ref_Key']: h for h in headers}
    contract_keys = {
        (h.get('Договор_Key') or '') for h in headers
    }
    channel_by_contract = _resolve_contracts(
        client, contract_keys,
    )
    channel_by_ref = {}
    for h in headers:
        dk = h.get('Договор_Key') or ''
        channel_by_ref[h['Ref_Key']] = channel_by_contract.get(
            dk, CHANNEL_UNKNOWN,
        )

    if channel:
        wanted_refs = {
            ref for ref, ch in channel_by_ref.items()
            if ch == channel
        }
        if not wanted_refs:
            return []
    else:
        wanted_refs = set(headers_by_ref)

    refs = list(wanted_refs)
    rows_sales = _fetch_rows_by_refs(
        client, DOC_COMMISSION_SALES, refs,
    )
    rows_returns = _fetch_rows_by_refs(
        client, DOC_COMMISSION_RETURNS, refs,
    )
    logger.info(
        'Комиссионер: %d строк продаж, %d строк возвратов',
        len(rows_sales), len(rows_returns),
    )

    nomenclature, characteristics = _collect_catalogs(
        client, rows_sales, rows_returns,
    )

    warehouse_by_ref = _fetch_commission_warehouses(
        client, date_from, date_to,
    )
    warehouse_by_ref = {
        ref: wh for ref, wh in warehouse_by_ref.items()
        if ref in wanted_refs
    }
    warehouse_names = _resolve_names(
        client,
        set(warehouse_by_ref.values()),
        WAREHOUSES_CATALOG,
    )
    org_keys = {
        (h.get('Организация_Key') or '')
        for h in headers
        if h['Ref_Key'] in wanted_refs
    }
    organization_names = _resolve_names(
        client, org_keys, ORGS_CATALOG,
    )

    result: list[SaleRecord] = []
    result.extend(_build_records(
        rows_sales, headers_by_ref, channel_by_ref,
        nomenclature, characteristics,
        sale_type=TYPE_SALE, sign=1,
        channel_filter=channel,
        warehouse_by_ref=warehouse_by_ref,
        warehouse_names=warehouse_names,
        organization_names=organization_names,
    ))
    result.extend(_build_records(
        rows_returns, headers_by_ref, channel_by_ref,
        nomenclature, characteristics,
        sale_type=TYPE_RETURN, sign=-1,
        channel_filter=channel,
        warehouse_by_ref=warehouse_by_ref,
        warehouse_names=warehouse_names,
        organization_names=organization_names,
    ))
    return result

def _retail_row_to_sale(
    row: dict,
    header: dict,
    nomenclature: dict,
    characteristics: dict,
    warehouse_names: dict | None = None,
    organization_names: dict | None = None,
) -> SaleRecord:
    nom_key = row.get('Номенклатура_Key', '') or ''
    char_key = row.get('Характеристика_Key', '') or ''
    if char_key == EMPTY_GUID:
        char_key = ''

    nom = nomenclature.get(nom_key, {}) if nom_key else {}
    article = nom.get('Артикул', '') or None

    char_descr = ''
    if char_key:
        char_descr = characteristics.get(
            char_key, {},
        ).get('Description', '') or ''
    _, _, size = _parse_size(char_descr, article or '')
    size = size or None

    qty = float(row.get('Количество', 0) or 0)
    amount = float(row.get('Сумма', 0) or 0)
    sale_type = TYPE_RETURN if qty < 0 or amount < 0 else TYPE_SALE

    wh_key = header.get('СтруктурнаяЕдиница_Key', '') or ''
    warehouse = None
    if wh_key and wh_key != EMPTY_GUID:
        if warehouse_names is not None:
            warehouse = warehouse_names.get(wh_key) or wh_key
        else:
            warehouse = wh_key

    org_key = header.get('Организация_Key', '') or ''
    organization = None
    if org_key and org_key != EMPTY_GUID:
        if organization_names is not None:
            organization = organization_names.get(org_key) or org_key
        else:
            organization = org_key

    return SaleRecord(
        nomenclature_key=nom_key,
        characteristic_key=char_key or None,
        article=article,
        size=size,
        channel=CHANNEL_RETAIL,
        quantity=qty,
        amount=amount,
        date=_parse_dt(header.get('Date')),
        type=sale_type,
        warehouse=warehouse,
        organization=organization,
    )

def get_retail_sales(
    client: OData1C,
    date_from,
    date_to,
) -> list[SaleRecord]:
    headers = _fetch_headers(
        client, DOC_RETAIL, date_from, date_to,
        select=(
            'Ref_Key,Date,Организация_Key,СтруктурнаяЕдиница_Key'
        ),
    )
    if not headers:
        return []
    headers_by_ref = {h['Ref_Key']: h for h in headers}

    refs = list(headers_by_ref)
    rows = _fetch_rows_by_refs(
        client, DOC_RETAIL_SALES, refs,
    )
    logger.info('Розница: %d строк продаж', len(rows))

    nom_keys = set()
    char_keys = set()
    for row in rows:
        nk = row.get('Номенклатура_Key', '')
        ck = row.get('Характеристика_Key', '')
        if nk:
            nom_keys.add(nk)
        if ck and ck != EMPTY_GUID:
            char_keys.add(ck)
    nomenclature = _resolve_nomenclature(client, nom_keys)
    characteristics = _resolve_characteristics(client, char_keys)

    org_keys = {
        (h.get('Организация_Key') or '') for h in headers
    }
    wh_keys = {
        (h.get('СтруктурнаяЕдиница_Key') or '') for h in headers
    }
    organization_names = _resolve_names(
        client, org_keys, ORGS_CATALOG,
    )
    warehouse_names = _resolve_names(
        client, wh_keys, WAREHOUSES_CATALOG,
    )

    result: list[SaleRecord] = []
    for row in rows:
        ref = row.get('Ref_Key', '') or ''
        header = headers_by_ref.get(ref)
        if not header:
            continue
        result.append(_retail_row_to_sale(
            row, header, nomenclature, characteristics,
            warehouse_names=warehouse_names,
            organization_names=organization_names,
        ))
    return result

def get_all_sales(
    client: OData1C,
    date_from,
    date_to,
) -> list[SaleRecord]:
    result = get_marketplace_sales(client, date_from, date_to)
    result.extend(get_retail_sales(client, date_from, date_to))
    return result
