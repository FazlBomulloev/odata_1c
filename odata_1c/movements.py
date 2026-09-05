import logging
from collections import defaultdict
from datetime import datetime

from .client import OData1C
from .exceptions import ODataError, ODataNotFoundError
from .models import MovementRecord

logger = logging.getLogger(__name__)

EMPTY_GUID = '00000000-0000-0000-0000-000000000000'
MIN_PERIOD = datetime(1900, 1, 1)
PAGE_SIZE = 1000
BATCH_KEYS = 40
RECORDER_TYPE_PREFIX = 'StandardODATA.'

REGISTER = 'AccumulationRegister_ЗапасыНаСкладах_RecordType'
NOMENCLATURE = 'Catalog_Номенклатура'
CHARACTERISTICS = 'Catalog_ХарактеристикиНоменклатуры'
BARCODES = 'InformationRegister_ШтрихкодыНоменклатуры'
ORGS_CATALOG = 'Catalog_Организации'
WAREHOUSES_CATALOG = 'Catalog_СтруктурныеЕдиницы'

DOCUMENT_OPERATION = {
    'Document_ПеремещениеЗапасов': 'перемещение',
    'Document_ПередачаТоваровМеждуОрганизациями': (
        'межфирменное'
    ),
    'Document_СписаниеЗапасов': 'списание',
    'Document_ОприходованиеЗапасов': 'оприходование',
    'Document_ВводНачальныхОстатков': 'оприходование',
    'Document_ПринятиеКУчетуВА': 'оприходование',
    'Document_ПриходныйОрдер': 'приход',
    'Document_ПриходнаяНакладная': 'приход',
    'Document_РасходныйОрдер': 'расход',
    'Document_РасходнаяНакладная': 'расход',
    'Document_ПересортицаЗапасов': 'пересортица',
    'Document_СборкаЗапасов': 'сборка',
    'Document_ОтчетПереработчика': 'переработка',
}

PAIRED_KINDS = frozenset({
    'Document_ПеремещениеЗапасов',
    'Document_ПередачаТоваровМеждуОрганизациями',
})

TRANSFER_KINDS = (
    'Document_ПеремещениеЗапасов',
    'Document_ПередачаТоваровМеждуОрганизациями',
)
WRITE_OFF_KINDS = ('Document_СписаниеЗапасов',)
RECEIPT_KINDS = (
    'Document_ОприходованиеЗапасов',
    'Document_ВводНачальныхОстатков',
    'Document_ПриходныйОрдер',
    'Document_ПриходнаяНакладная',
    'Document_ПринятиеКУчетуВА',
)
EXPENSE_KINDS = (
    'Document_РасходныйОрдер',
    'Document_РасходнаяНакладная',
)

def _iso(value) -> str:
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%dT%H:%M:%S')
    return str(value)

def _iso_to(value) -> str:
    if isinstance(value, datetime):
        no_time = (
            value.hour == 0 and value.minute == 0
            and value.second == 0 and value.microsecond == 0
        )
        if no_time:
            return value.strftime('%Y-%m-%d') + 'T23:59:59'
        return value.strftime('%Y-%m-%dT%H:%M:%S')
    s = str(value)
    if len(s) == 10 and s[4] == '-' and s[7] == '-':
        return f'{s}T23:59:59'
    if s.endswith('T00:00:00'):
        return s[:10] + 'T23:59:59'
    return s

def _period_bounds(date_from, date_to) -> tuple[str, str]:
    return _iso(date_from), _iso_to(date_to)

def _parse_dt(value):
    if not value:
        return None
    try:
        return datetime.strptime(
            value[:19], '%Y-%m-%dT%H:%M:%S',
        )
    except (ValueError, TypeError):
        logger.warning('Битая дата "%s", пропускаю', value)
        return None

def _short_kind(recorder_type: str) -> str:
    if not recorder_type:
        return ''
    return recorder_type.rsplit('.', 1)[-1]

def _parse_size(description: str, article: str = ''):
    if not description:
        return ('', '', '')
    body = description
    prefix = f'{article}-'
    if article and body.startswith(prefix):
        body = body[len(prefix):]
    if ', ' in body:
        left, right = body.split(', ', 1)
        left, right = left.strip(), right.strip()
        return (left, right, f'{left}, {right}')
    return ('', '', description)

def _chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]

def _batch_get_by_keys(
    client: OData1C,
    endpoint: str,
    keys,
    select: str = '',
) -> dict:
    result = {}
    unique = [
        k for k in set(keys)
        if k and k != EMPTY_GUID
    ]
    for chunk in _chunks(unique, BATCH_KEYS):
        cond = ' or '.join(
            f"Ref_Key eq guid'{k}'" for k in chunk
        )
        params = {
            '$filter': cond,
            '$format': 'json',
        }
        if select:
            params['$select'] = select
        try:
            data = client.get(endpoint, params)
        except ODataNotFoundError:
            logger.warning(
                'Справочник %s недоступен', endpoint,
            )
            return {}
        for item in data.get('value', []):
            result[item['Ref_Key']] = item
    return result

def _batch_get_barcodes(client: OData1C, nom_keys) -> dict:
    result = {}
    unique = [k for k in set(nom_keys) if k]
    for chunk in _chunks(unique, BATCH_KEYS):
        cond = ' or '.join(
            f"Номенклатура_Key eq guid'{k}'" for k in chunk
        )
        params = {
            '$filter': cond,
            '$select': (
                'Штрихкод,Номенклатура_Key,'
                'Характеристика_Key'
            ),
            '$format': 'json',
        }
        try:
            data = client.get(BARCODES, params)
        except ODataNotFoundError:
            logger.warning('Регистр штрихкодов недоступен')
            return {}
        for item in data.get('value', []):
            key = (
                item['Номенклатура_Key'],
                item.get('Характеристика_Key', EMPTY_GUID),
            )
            if key not in result:
                result[key] = item.get('Штрихкод', '')
    return result

def _batch_get_documents(client: OData1C, recorders) -> dict:
    by_kind: dict[str, list[str]] = defaultdict(list)
    for guid, rtype in recorders:
        kind = _short_kind(rtype)
        if kind and guid and guid != EMPTY_GUID:
            by_kind[kind].append(guid)

    docs = {}
    for kind, guids in by_kind.items():
        try:
            got = _batch_get_by_keys(
                client, kind, guids,
                select='Ref_Key,Number,Date',
            )
        except ODataError as exc:
            logger.warning(
                'Документы %s не получены: %s', kind, exc,
            )
            continue
        for guid, doc in got.items():
            doc['_kind'] = kind
            docs[guid] = doc
    return docs

def _query_register(
    client: OData1C,
    date_from,
    date_to,
    recorder_kinds=None,
    use_type_filter: bool = True,
    select: str = '',
) -> list[dict]:

    d_from, d_to = _period_bounds(date_from, date_to)

    conds = [
        f"Period ge datetime'{d_from}'",
        f"Period le datetime'{d_to}'",
    ]
    if recorder_kinds and use_type_filter:
        kind_expr = ' or '.join(
            f"Recorder_Type eq "
            f"'{RECORDER_TYPE_PREFIX}{k}'"
            for k in recorder_kinds
        )
        conds.append(f'({kind_expr})')

    base_filter = ' and '.join(conds)
    rows: list[dict] = []
    skip = 0

    order = 'Period,Recorder,LineNumber,RecordType'
    while True:
        params = {
            '$filter': base_filter,
            '$top': str(PAGE_SIZE),
            '$skip': str(skip),
            '$orderby': order,
            '$format': 'json',
        }
        if select:
            params['$select'] = select
        data = client.get(REGISTER, params)
        page = data.get('value', [])
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            break
        skip += PAGE_SIZE

    logger.info(
        'Регистр движений: %d строк за [%s .. %s]',
        len(rows), d_from, d_to,
    )
    return rows

def _fetch_rows(
    client: OData1C,
    date_from,
    date_to,
    recorder_kinds=None,
) -> list[dict]:
    try:
        return _query_register(
            client, date_from, date_to,
            recorder_kinds=recorder_kinds,
            use_type_filter=True,
        )
    except ODataError as exc:
        if not recorder_kinds:
            raise
        logger.warning(
            'Фильтр Recorder_Type не сработал (%s), '
            'фильтрую в Python', exc,
        )
        rows = _query_register(
            client, date_from, date_to,
            recorder_kinds=None,
            use_type_filter=False,
        )
        allowed = {
            f'{RECORDER_TYPE_PREFIX}{k}'
            for k in recorder_kinds
        }
        return [
            r for r in rows
            if r.get('Recorder_Type') in allowed
        ]

def _resolve_names(client: OData1C, keys, endpoint: str) -> dict:
    if not keys:
        return {}
    try:
        got = _batch_get_by_keys(
            client, endpoint, keys,
            select='Ref_Key,Description',
        )
    except ODataError as exc:
        logger.warning(
            'Не резолвлю имена из %s: %s', endpoint, exc,
        )
        return {}
    return {
        k: v.get('Description', '')
        for k, v in got.items()
    }

def _build_record(
    period,
    quantity: float,
    nom_key: str,
    char_key: str,
    operation_type: str,
    warehouse_from: str,
    warehouse_to: str,
    organization_from: str,
    organization_to: str,
    recorder: str,
    document: dict,
    catalogs: dict,
) -> MovementRecord:
    noms = catalogs['nomenclature']

    chars = catalogs['characteristics']
    barcodes = catalogs['barcodes']
    orgs = catalogs['organizations']
    whs = catalogs['warehouses']

    nom = noms.get(nom_key, {})
    article = nom.get('Артикул', '')
    name = nom.get('Description', '')
    if not nom and nom_key and nom_key != EMPTY_GUID:
        logger.warning(
            'Номенклатура %s не найдена', nom_key,
        )

    char_descr = ''
    if char_key and char_key != EMPTY_GUID:
        char_descr = chars.get(char_key, {}).get(
            'Description', '',
        )
    sg, sr, size = _parse_size(char_descr, article)

    barcode = barcodes.get(
        (nom_key, char_key or EMPTY_GUID), '',
    )

    kind = document.get('_kind', '')
    doc_number = document.get('Number', '')
    doc_date = _parse_dt(document.get('Date'))

    kind_short = kind.replace('Document_', '') if kind else ''

    return MovementRecord(
        period=_parse_dt(period),
        name=name,
        article=article,
        barcode=barcode,
        size=size,
        size_global=sg,
        size_ru=sr,
        quantity=float(quantity or 0),
        operation_type=operation_type,
        warehouse_from=whs.get(
            warehouse_from, warehouse_from,
        ) if warehouse_from else '',
        warehouse_to=whs.get(
            warehouse_to, warehouse_to,
        ) if warehouse_to else '',
        organization_from=orgs.get(
            organization_from, organization_from,
        ) if organization_from else '',
        organization_to=orgs.get(
            organization_to, organization_to,
        ) if organization_to else '',
        document_kind=kind_short,
        document_number=doc_number,
        document_date=doc_date,
        recorder=recorder,
    )

def _pair_transfers(rows):

    by_rec: dict = defaultdict(list)
    for row in rows:
        by_rec[row.get('Recorder', '')].append(row)

    pairs = []
    orphans = []
    for rec, group in by_rec.items():
        exps = [
            r for r in group
            if r.get('RecordType') == 'Expense'
        ]
        recs = [
            r for r in group
            if r.get('RecordType') == 'Receipt'
        ]
        if not exps or not recs:
            orphans.extend(group)
            continue

        rec_index: dict = defaultdict(list)
        for r in recs:
            key = (
                r.get('Номенклатура_Key', ''),
                r.get('Характеристика_Key', ''),
                r.get('Количество'),
            )
            rec_index[key].append(r)

        used_ids = set()
        matched_exp_ids = set()
        for e in exps:
            key = (
                e.get('Номенклатура_Key', ''),
                e.get('Характеристика_Key', ''),
                e.get('Количество'),
            )
            for r in rec_index.get(key, ()):
                if id(r) in used_ids:
                    continue
                pairs.append((e, r))
                used_ids.add(id(r))
                matched_exp_ids.add(id(e))
                break

        for e in exps:
            if id(e) not in matched_exp_ids:
                orphans.append(e)
        for r in recs:
            if id(r) not in used_ids:
                orphans.append(r)

    if orphans:
        logger.warning(
            'Непарных строк перемещения: %d', len(orphans),
        )
    return pairs, orphans

def _collect_catalogs(client, rows, extra_recorders=None):
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
    if extra_recorders:
        recorders.update(extra_recorders)

    nomenclature = _batch_get_by_keys(
        client, NOMENCLATURE, nom_keys,
        select='Ref_Key,Description,Артикул',
    )
    characteristics = _batch_get_by_keys(
        client, CHARACTERISTICS, char_keys,
        select='Ref_Key,Description',
    )
    barcodes = _batch_get_barcodes(client, nom_keys)
    documents = _batch_get_documents(client, recorders)
    organizations = _resolve_names(
        client, org_keys, ORGS_CATALOG,
    )
    warehouses = _resolve_names(
        client, wh_keys, WAREHOUSES_CATALOG,
    )
    return {
        'nomenclature': nomenclature,
        'characteristics': characteristics,
        'barcodes': barcodes,
        'documents': documents,
        'organizations': organizations,
        'warehouses': warehouses,
    }

def _normalize(
    rows, catalogs,
    organization: str = '', warehouse: str = '',
):

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

    result: list[MovementRecord] = []

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
        op_type = (
            'межфирменное'
            if org_from and org_to and org_from != org_to
            else 'перемещение'
        )
        result.append(_build_record(
            period=exp.get('Period'),
            quantity=rec.get('Количество', 0),
            nom_key=rec.get('Номенклатура_Key', ''),
            char_key=rec.get(
                'Характеристика_Key', EMPTY_GUID,
            ),
            operation_type=op_type,
            warehouse_from=exp.get(
                'СтруктурнаяЕдиница_Key', '',
            ),
            warehouse_to=rec.get(
                'СтруктурнаяЕдиница_Key', '',
            ),
            organization_from=org_from,
            organization_to=org_to,
            recorder=recorder,
            document=doc,
            catalogs=catalogs,
        ))

    def _row_passes(row):
        if organization and (
            row.get('Организация_Key', '') != organization
        ):
            return False
        if warehouse and (
            row.get('СтруктурнаяЕдиница_Key', '') != warehouse
        ):
            return False
        return True

    for row in orphans:
        if not _row_passes(row):
            continue
        result.append(_row_to_record(row, docs, catalogs))

    for row in other_rows:
        if not _row_passes(row):
            continue
        result.append(_row_to_record(row, docs, catalogs))

    return result

def _row_to_record(row, docs, catalogs):
    recorder = row.get('Recorder', '')
    doc = docs.get(recorder, {})
    kind = _short_kind(row.get('Recorder_Type', ''))
    rtype = row.get('RecordType', '')
    warehouse = row.get('СтруктурнаяЕдиница_Key', '')
    organization = row.get('Организация_Key', '')

    op_type = DOCUMENT_OPERATION.get(kind, kind or rtype)

    if rtype == 'Expense':
        wh_from, wh_to = warehouse, ''
        org_from, org_to = organization, ''
    elif rtype == 'Receipt':
        wh_from, wh_to = '', warehouse
        org_from, org_to = '', organization
    else:
        wh_from, wh_to = warehouse, ''
        org_from, org_to = organization, ''

    return _build_record(
        period=row.get('Period'),
        quantity=row.get('Количество', 0),
        nom_key=row.get('Номенклатура_Key', ''),
        char_key=row.get(
            'Характеристика_Key', EMPTY_GUID,
        ),
        operation_type=op_type,
        warehouse_from=wh_from,
        warehouse_to=wh_to,
        organization_from=org_from,
        organization_to=org_to,
        recorder=recorder,
        document=doc,
        catalogs=catalogs,
    )

def _get_movements(
    client: OData1C,
    date_from,
    date_to,
    organization: str = '',
    warehouse: str = '',
    recorder_kinds=None,
) -> list[MovementRecord]:
    if isinstance(date_from, datetime) and date_from < MIN_PERIOD:
        date_from = MIN_PERIOD

    rows = _fetch_rows(
        client, date_from, date_to,
        recorder_kinds=recorder_kinds,
    )
    if not rows:
        return []

    if organization or warehouse:
        rows = _prefilter_rows(rows, organization, warehouse)
        if not rows:
            return []

    catalogs = _collect_catalogs(client, rows)
    return _normalize(
        rows, catalogs,
        organization=organization or '',
        warehouse=warehouse or '',
    )

def _prefilter_rows(rows, organization: str, warehouse: str):
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

def get_transfers(
    client: OData1C,
    date_from,
    date_to,
    organization: str = '',
    warehouse: str = '',
) -> list[MovementRecord]:
    return _get_movements(
        client, date_from, date_to,
        organization, warehouse,
        recorder_kinds=TRANSFER_KINDS,
    )

def get_write_offs(
    client: OData1C,
    date_from,
    date_to,
    organization: str = '',
    warehouse: str = '',
) -> list[MovementRecord]:
    return _get_movements(
        client, date_from, date_to,
        organization, warehouse,
        recorder_kinds=WRITE_OFF_KINDS,
    )

def get_receipts(
    client: OData1C,
    date_from,
    date_to,
    organization: str = '',
    warehouse: str = '',
) -> list[MovementRecord]:
    return _get_movements(
        client, date_from, date_to,
        organization, warehouse,
        recorder_kinds=RECEIPT_KINDS,
    )

def get_expenses(
    client: OData1C,
    date_from,
    date_to,
    organization: str = '',
    warehouse: str = '',
) -> list[MovementRecord]:
    return _get_movements(
        client, date_from, date_to,
        organization, warehouse,
        recorder_kinds=EXPENSE_KINDS,
    )

def get_all_movements(
    client: OData1C,
    date_from,
    date_to,
    organization: str = '',
    warehouse: str = '',
) -> list[MovementRecord]:
    return _get_movements(
        client, date_from, date_to,
        organization, warehouse,
        recorder_kinds=None,
    )

def list_recorder_types(
    client: OData1C,
    date_from,
    date_to,
) -> list[str]:
    rows = _query_register(
        client, date_from, date_to,
        use_type_filter=False,
        select='Recorder_Type',
    )
    return sorted({
        r.get('Recorder_Type', '')
        for r in rows
        if r.get('Recorder_Type')
    })
