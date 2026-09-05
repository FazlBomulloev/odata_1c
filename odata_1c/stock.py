import logging

from .client import OData1C
from .exceptions import ODataError
from .models import StockRecord
from .search import _esc
from .movements import (
    CHARACTERISTICS,
    EMPTY_GUID,
    NOMENCLATURE,
    ORGS_CATALOG,
    PAGE_SIZE,
    WAREHOUSES_CATALOG,
    _batch_get_barcodes,
    _batch_get_by_keys,
    _parse_size,
    _resolve_names,
)

logger = logging.getLogger(__name__)

STOCK = 'AccumulationRegister_ЗапасыНаСкладах/Balance'

QTY_FIELDS = ('КоличествоBalance', 'КоличествоИнтBalance')

def _row_qty(row) -> float:
    return sum(float(row.get(f, 0) or 0) for f in QTY_FIELDS)

def _build_filter(
    warehouse: str,
    organization: str,
    nomenclature: str,
    only_positive: bool,
) -> str:
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
    return ' and '.join(conds)

def _fetch_balance(
    client: OData1C,
    warehouse: str = '',
    organization: str = '',
    nomenclature: str = '',
    only_positive: bool = True,
    use_server_filter: bool = True,
    stable_order: bool = True,
) -> list[dict]:
    flt = ''
    if use_server_filter:
        flt = _build_filter(
            warehouse, organization,
            nomenclature, only_positive,
        )

    rows: list[dict] = []
    skip = 0

    order = (
        'Организация_Key,СтруктурнаяЕдиница_Key,'
        'Номенклатура_Key,Характеристика_Key'
    )
    while True:
        params = {
            '$top': str(PAGE_SIZE),
            '$skip': str(skip),
            '$format': 'json',
        }
        if flt:
            params['$filter'] = flt
        if stable_order:
            params['$orderby'] = order
        data = client.get(STOCK, params)
        page = data.get('value', [])
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            break
        skip += PAGE_SIZE
    return rows

def _python_filter(
    rows,
    warehouse: str,
    organization: str,
    nomenclature: str,
    only_positive: bool,
) -> list[dict]:
    def ok(r):
        if warehouse and r.get(
            'СтруктурнаяЕдиница_Key', ''
        ) != warehouse:
            return False
        if organization and r.get(
            'Организация_Key', ''
        ) != organization:
            return False
        if nomenclature and r.get(
            'Номенклатура_Key', ''
        ) != nomenclature:
            return False
        if only_positive and _row_qty(r) <= 0:
            return False
        return True
    return [r for r in rows if ok(r)]

def _fetch_rows(
    client: OData1C,
    warehouse: str,
    organization: str,
    nomenclature: str,
    only_positive: bool,
) -> list[dict]:
    try:
        return _fetch_balance(
            client, warehouse, organization,
            nomenclature, only_positive,
            use_server_filter=True,
            stable_order=True,
        )
    except ODataError as exc:
        logger.warning(
            'Первичный запрос остатков не прошёл (%s), '
            'пробую без $orderby', exc,
        )
        try:
            return _fetch_balance(
                client, warehouse, organization,
                nomenclature, only_positive,
                use_server_filter=True,
                stable_order=False,
            )
        except ODataError as exc2:
            if not (warehouse or organization
                    or nomenclature or only_positive):
                raise
            logger.warning(
                'Серверный $filter тоже не сработал (%s), '
                'фильтрую в Python', exc2,
            )
            rows = _fetch_balance(
                client,
                use_server_filter=False,
                stable_order=False,
            )
            return _python_filter(
                rows, warehouse, organization,
                nomenclature, only_positive,
            )

def _collect_catalogs(client: OData1C, rows) -> dict:
    nom_keys = {r.get('Номенклатура_Key', '') for r in rows}
    char_keys = {r.get('Характеристика_Key', '') for r in rows}
    org_keys = {r.get('Организация_Key', '') for r in rows}
    wh_keys = {r.get('СтруктурнаяЕдиница_Key', '') for r in rows}

    return {
        'nomenclature': _batch_get_by_keys(
            client, NOMENCLATURE, nom_keys,
            select='Ref_Key,Description,Артикул',
        ),
        'characteristics': _batch_get_by_keys(
            client, CHARACTERISTICS, char_keys,
            select='Ref_Key,Description',
        ),
        'barcodes': _batch_get_barcodes(client, nom_keys),
        'organizations': _resolve_names(
            client, org_keys, ORGS_CATALOG,
        ),
        'warehouses': _resolve_names(
            client, wh_keys, WAREHOUSES_CATALOG,
        ),
    }

def _build_stock_record(row, catalogs) -> StockRecord:
    nom_key = row.get('Номенклатура_Key', '')
    char_key = row.get('Характеристика_Key', EMPTY_GUID)
    wh_key = row.get('СтруктурнаяЕдиница_Key', '')
    org_key = row.get('Организация_Key', '')

    nom = catalogs['nomenclature'].get(nom_key, {})
    article = nom.get('Артикул', '') or ''
    name = nom.get('Description', '') or ''
    if not nom and nom_key and nom_key != EMPTY_GUID:
        logger.warning('Номенклатура %s не найдена', nom_key)

    char_descr = ''
    if char_key and char_key != EMPTY_GUID:
        char_descr = catalogs['characteristics'].get(
            char_key, {},
        ).get('Description', '') or ''
    sg, sr, size = _parse_size(char_descr, article)

    barcode = catalogs['barcodes'].get(
        (nom_key, char_key or EMPTY_GUID), '',
    )

    whs = catalogs['warehouses']
    orgs = catalogs['organizations']

    return StockRecord(
        name=name,
        article=article,
        barcode=barcode,
        size=size,
        size_global=sg,
        size_ru=sr,
        warehouse=whs.get(wh_key, wh_key) if wh_key else '',
        organization=(
            orgs.get(org_key, org_key)
            if org_key and org_key != EMPTY_GUID else ''
        ),
        quantity=_row_qty(row),
    )

def get_stock(
    client: OData1C,
    warehouse: str = '',
    organization: str = '',
    nomenclature: str = '',
    only_positive: bool = True,
) -> list[StockRecord]:
    rows = _fetch_rows(
        client, warehouse, organization,
        nomenclature, only_positive,
    )
    logger.info(
        'Остатки: %d строк (склад=%s, орг=%s, ном=%s, '
        'only_positive=%s)',
        len(rows), warehouse or '*', organization or '*',
        nomenclature or '*', only_positive,
    )
    if not rows:
        return []

    catalogs = _collect_catalogs(client, rows)
    result = [_build_stock_record(r, catalogs) for r in rows]

    if only_positive:
        result = [r for r in result if r.quantity > 0]
    return result

def get_stock_by_article(
    client: OData1C,
    article: str,
) -> list[StockRecord]:
    if not article:
        return []
    try:
        data = client.get(NOMENCLATURE, {
            '$filter': f"Артикул eq '{_esc(article)}'",
            '$select': 'Ref_Key',
            '$format': 'json',
        })
    except ODataError as exc:
        logger.warning(
            'Поиск по артикулу "%s" не удался: %s',
            article, exc,
        )
        return []

    items = data.get('value', [])
    if not items:
        logger.warning(
            'Номенклатура с артикулом "%s" не найдена', article,
        )
        return []

    result: list[StockRecord] = []
    for item in items:
        ref = item.get('Ref_Key', '')
        if not ref:
            continue
        result.extend(get_stock(client, nomenclature=ref))
    return result
