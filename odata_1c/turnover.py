import logging
from datetime import datetime

from .client import OData1C
from .exceptions import ODataError, ODataNotFoundError
from .models import TurnoverRecord
from .movements import (
    CHARACTERISTICS,
    EMPTY_GUID,
    MIN_PERIOD,
    NOMENCLATURE,
    ORGS_CATALOG,
    PAGE_SIZE,
    WAREHOUSES_CATALOG,
    _batch_get_by_keys,
    _iso,
    _parse_size,
    _resolve_names,
)

logger = logging.getLogger(__name__)

SALES_REGISTER = 'AccumulationRegister_Продажи'
CONTRACTORS_CATALOG = 'Catalog_Контрагенты'


def _turnovers_endpoint(date_from, date_to) -> str:
    # Период — параметрами виртуальной таблицы в скобках;
    # $filter по Period здесь отдаёт 500.
    d_from = _iso(date_from)
    d_to = _iso(date_to)
    return (
        f"{SALES_REGISTER}/Turnovers("
        f"StartPeriod=datetime'{d_from}',"
        f"EndPeriod=datetime'{d_to}')"
    )


def _fetch_turnover_rows(
    client: OData1C,
    date_from,
    date_to,
) -> list[dict]:
    if isinstance(date_from, datetime) and date_from < MIN_PERIOD:
        date_from = MIN_PERIOD
    endpoint = _turnovers_endpoint(date_from, date_to)

    rows: list[dict] = []
    skip = 0
    while True:
        params = {
            '$top': str(PAGE_SIZE),
            '$skip': str(skip),
            '$format': 'json',
        }
        try:
            data = client.get(endpoint, params)
        except ODataNotFoundError:
            logger.warning('%s недоступен', endpoint)
            return []
        page = data.get('value', [])
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            break
        skip += PAGE_SIZE
    logger.info(
        'Turnovers Продажи: %d строк за [%s..%s]',
        len(rows), _iso(date_from), _iso(date_to),
    )
    return rows


def _collect_refs(rows: list[dict]) -> tuple[set, set, set, set]:
    noms, chars, orgs, whs, contractors = (
        set(), set(), set(), set(), set(),
    )
    for r in rows:
        for k, dst in (
            ('Номенклатура_Key', noms),
            ('Характеристика_Key', chars),
            ('Организация_Key', orgs),
            ('Склад_Key', whs),
            ('Контрагент_Key', contractors),
        ):
            v = r.get(k) or ''
            if v and v != EMPTY_GUID:
                dst.add(v)
    return noms, chars, orgs, whs, contractors


def _to_record(
    r: dict,
    month: datetime,
    nomenclature: dict,
    characteristics: dict,
    warehouses: dict,
    organizations: dict,
    contractors: dict,
) -> TurnoverRecord:
    nk = r.get('Номенклатура_Key') or ''
    ck = r.get('Характеристика_Key') or ''
    if ck == EMPTY_GUID:
        ck = ''
    wk = r.get('Склад_Key') or ''
    ok = r.get('Организация_Key') or ''
    kk = r.get('Контрагент_Key') or ''

    nom = nomenclature.get(nk, {})
    article = nom.get('Артикул', '') or ''
    name = nom.get('Description', '') or ''

    char_descr = ''
    if ck:
        char_descr = characteristics.get(ck, {}).get(
            'Description', '',
        ) or ''
    _, _, size = _parse_size(char_descr, article)

    return TurnoverRecord(
        article=article,
        name=name,
        size=size,
        nomenclature_key=nk,
        characteristic_key=ck,
        warehouse=warehouses.get(wk, wk) if wk else '',
        warehouse_ref=wk,
        organization=(
            organizations.get(ok, ok) if ok else ''
        ),
        organization_ref=ok,
        contractor=contractors.get(kk, kk) if kk else '',
        contractor_ref=kk,
        month=month,
        quantity=float(r.get('КоличествоTurnover') or 0),
        revenue=float(r.get('СуммаTurnover') or 0),
        revenue_no_vat=float(
            r.get('СуммаБезСкидкиTurnover') or 0
        ) - float(r.get('СуммаНДСTurnover') or 0),
        cost=float(r.get('СебестоимостьTurnover') or 0),
        cost_no_vat=float(
            r.get('СебестоимостьБезНДСTurnover') or 0
        ),
    )


def get_sales_turnover(
    client: OData1C,
    date_from,
    date_to,
) -> list[TurnoverRecord]:
    if isinstance(date_from, datetime) and date_from < MIN_PERIOD:
        date_from = MIN_PERIOD

    rows = _fetch_turnover_rows(client, date_from, date_to)
    if not rows:
        return []

    noms, chars, orgs, whs, contractors = _collect_refs(rows)

    nomenclature = _batch_get_by_keys(
        client, NOMENCLATURE, noms,
        select='Ref_Key,Description,Артикул',
    )
    characteristics = _batch_get_by_keys(
        client, CHARACTERISTICS, chars,
        select='Ref_Key,Description',
    )
    warehouse_names = _resolve_names(
        client, whs, WAREHOUSES_CATALOG,
    )
    organization_names = _resolve_names(
        client, orgs, ORGS_CATALOG,
    )
    try:
        contractor_names = _resolve_names(
            client, contractors, CONTRACTORS_CATALOG,
        )
    except ODataError as exc:
        logger.warning('Контрагенты не резолвлю: %s', exc)
        contractor_names = {}

    month = (
        date_from if isinstance(date_from, datetime)
        else datetime.strptime(str(date_from)[:10], '%Y-%m-%d')
    )
    return [
        _to_record(
            r, month, nomenclature, characteristics,
            warehouse_names, organization_names, contractor_names,
        )
        for r in rows
    ]
