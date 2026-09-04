import base64
import hashlib
import logging
from datetime import datetime, timezone

import requests

from .client import OData1C
from .config import (
    ODATA_COLOR_PROP_GUID,
    ODATA_PRICE_TYPE_GUID,
    ODATA_PRICE_TYPE_GUIDS,
)
from .exceptions import (
    ODataNotFoundError,
    ODataValidationError,
    ProductExistsError,
)
from .models import ProductData, SizeData
from .search import (
    article_exists,
    get_nomenclature_by_article,
)


def _parse_size_lenient(
    description: str, article: str = '',
) -> tuple[str, str]:
    """Толерантный разбор Description характеристики.

    Понимает форматы, встречающиеся в разных базах 1С:
    '{арт}-{global}, {ru}', '{global}, {ru}', 'L, 50',
    просто 'L' (только глобальный), просто '42' (только ru).
    Возвращает (global, ru).
    """
    if not description:
        return ('', '')
    body = description.strip()
    if article:
        prefix = f'{article}-'
        if body.lower().startswith(prefix.lower()):
            body = body[len(prefix):].strip()
    if ', ' in body:
        left, right = body.split(', ', 1)
        return (left.strip(), right.strip())
    if body.replace(' ', '').isdigit():
        return ('', body)
    return (body, '')

logger = logging.getLogger(__name__)

EMPTY_GUID = '00000000-0000-0000-0000-000000000000'
_PHOTO_TIMEOUT = 30
_PAGE_SIZE = 1000


def _esc(value: str) -> str:
    """Экранирует одинарную кавычку для OData $filter."""
    return value.replace("'", "''")


def _format_char_name(article: str, size: SizeData) -> str:
    """Формат: '18057-2XL, 54'."""
    return f'{article}-{size.global_size}, {size.ru_size}'


def _find_color_guid(
    client: OData1C,
    color_name: str,
) -> str:
    """Ищет GUID цвета по названию (регистронезависимо)."""
    if not color_name:
        return ''

    exact = {
        '$filter': (
            f"Owner_Key eq guid'{ODATA_COLOR_PROP_GUID}'"
            f" and Description eq '{_esc(color_name)}'"
        ),
        '$select': 'Ref_Key,Description',
        '$format': 'json',
    }
    result = client.get(
        'Catalog_ЗначенияСвойствОбъектов', exact,
    )
    items = result.get('value', [])
    if items:
        return items[0]['Ref_Key']

    all_params = {
        '$filter': (
            f"Owner_Key eq guid'{ODATA_COLOR_PROP_GUID}'"
        ),
        '$select': 'Ref_Key,Description',
        '$format': 'json',
    }
    all_colors = client.get(
        'Catalog_ЗначенияСвойствОбъектов', all_params,
    )
    needle = color_name.strip().lower()
    for c in all_colors.get('value', []):
        if c['Description'].strip().lower() == needle:
            return c['Ref_Key']
    logger.warning('Цвет "%s" не найден', color_name)
    return ''


def _find_group_key(
    client: OData1C,
    group_name: str,
) -> str:
    """Ищет группу номенклатуры по названию через $filter."""
    if not group_name:
        return ''

    params = {
        '$filter': (
            f"IsFolder eq true and "
            f"Description eq '{_esc(group_name)}'"
        ),
        '$select': 'Ref_Key,Description',
        '$format': 'json',
    }
    result = client.get('Catalog_Номенклатура', params)
    items = result.get('value', [])
    if items:
        return items[0]['Ref_Key']
    logger.warning('Группа "%s" не найдена', group_name)
    return ''


def _find_or_create_category(
    client: OData1C,
    category_name: str,
) -> str:
    """Ищет категорию, создаёт если нет."""
    if not category_name:
        return ''

    params = {
        '$filter': (
            f"Description eq '{_esc(category_name)}'"
        ),
        '$select': 'Ref_Key',
        '$format': 'json',
    }
    result = client.get(
        'Catalog_КатегорииНоменклатуры', params,
    )
    items = result.get('value', [])
    if items:
        return items[0]['Ref_Key']

    logger.info('Создаю категорию "%s"', category_name)
    created = client.post(
        'Catalog_КатегорииНоменклатуры',
        {'Description': category_name},
    )
    return created['Ref_Key']


def _create_nomenclature(
    client: OData1C,
    data: ProductData,
    category_key: str,
    group_key: str,
    color_guid: str,
) -> dict:
    """Создаёт запись номенклатуры."""
    payload = {
        'Description': data.name,
        'НаименованиеПолное': data.name,
        'Артикул': data.article,
        'ИспользоватьХарактеристики': bool(data.sizes),
        'ВидСтавкиНДС': 'БезНДС',
    }
    if category_key:
        payload['КатегорияНоменклатуры_Key'] = category_key
    if group_key:
        payload['Parent_Key'] = group_key

    if color_guid:
        payload['ДополнительныеРеквизиты'] = [{
            'LineNumber': '1',
            'Свойство_Key': ODATA_COLOR_PROP_GUID,
            'Значение': color_guid,
            'Значение_Type': (
                'StandardODATA.'
                'Catalog_ЗначенияСвойствОбъектов'
            ),
            'ТекстоваяСтрока': '',
        }]

    logger.info(
        'Создаю номенклатуру "%s" (%s)',
        data.name, data.article,
    )
    return client.post('Catalog_Номенклатура', payload)


def _create_characteristic(
    client: OData1C,
    owner_key: str,
    article: str,
    size: SizeData,
) -> dict:
    """Создаёт характеристику номенклатуры."""
    char_name = _format_char_name(article, size)
    payload = {
        'Owner': owner_key,
        'Owner_Type': (
            'StandardODATA.Catalog_Номенклатура'
        ),
        'Description': char_name,
        'НаименованиеДляПечати': char_name,
    }
    logger.info('Создаю характеристику "%s"', char_name)
    return client.post(
        'Catalog_ХарактеристикиНоменклатуры', payload,
    )


def _create_barcode(
    client: OData1C,
    nom_key: str,
    char_key: str,
    barcode: str,
) -> dict:
    """Записывает штрихкод."""
    payload = {
        'Штрихкод': barcode,
        'Номенклатура_Key': nom_key,
        'Характеристика_Key': char_key,
        'Партия_Key': EMPTY_GUID,
        'ЕдиницаИзмерения_Key': EMPTY_GUID,
    }
    logger.info('Записываю штрихкод %s', barcode)
    return client.post(
        'InformationRegister_ШтрихкодыНоменклатуры',
        payload,
    )


def _resolve_price_keys(
    price_type_keys: list[str] | None,
) -> list[str]:
    """Возвращает список GUID видов цен для записи."""
    if price_type_keys:
        return [k for k in price_type_keys if k]
    if ODATA_PRICE_TYPE_GUIDS:
        return list(ODATA_PRICE_TYPE_GUIDS)
    if ODATA_PRICE_TYPE_GUID:
        return [ODATA_PRICE_TYPE_GUID]
    raise ODataValidationError(
        'Не указан GUID вида цен '
        '(ODATA_PRICE_TYPE_GUIDS в .env)'
    )


def _set_price_one(
    client: OData1C,
    nom_key: str,
    char_key: str,
    price: float,
    price_type_key: str,
) -> dict:
    """Пишет одну запись в регистр цен."""
    now = datetime.now(timezone.utc).strftime(
        '%Y-%m-%dT%H:%M:%S',
    )
    payload = {
        'Period': now,
        'Номенклатура_Key': nom_key,
        'Характеристика_Key': char_key,
        'ВидЦен_Key': price_type_key,
        'Цена': price,
        'Актуальность': True,
    }
    return client.post(
        'InformationRegister_ЦеныНоменклатуры', payload,
    )


def _set_price(
    client: OData1C,
    nom_key: str,
    char_key: str,
    price: float,
    price_type_keys: list[str] | None = None,
) -> list[dict]:
    """Записывает цену во все переданные виды цен."""
    keys = _resolve_price_keys(price_type_keys)
    logger.info(
        'Устанавливаю цену %.2f в %d вид(ов) цен',
        price, len(keys),
    )
    return [
        _set_price_one(client, nom_key, char_key, price, k)
        for k in keys
    ]


def _detect_ext(url: str) -> str:
    """Определяет расширение файла по URL."""
    lower = url.lower().split('?', 1)[0]
    if lower.endswith('.png'):
        return 'png'
    if lower.endswith('.webp'):
        return 'webp'
    if lower.endswith('.jpeg'):
        return 'jpeg'
    return 'jpg'


def _upload_photo(
    client: OData1C,
    nom_key: str,
    photo_url: str,
    index: int = 0,
) -> dict:
    """Загружает фото в 1С через 3 объекта."""
    logger.info('Загружаю фото %s', photo_url)
    try:
        resp = requests.get(photo_url, timeout=_PHOTO_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.warning('Не удалось скачать фото: %s', exc)
        return {}

    photo_bytes = resp.content
    photo_b64 = base64.b64encode(photo_bytes).decode()
    photo_hash = base64.b64encode(
        hashlib.sha256(photo_bytes).digest(),
    ).decode()
    ext = _detect_ext(photo_url)
    filename = f'photo_{index}'
    now = datetime.now(timezone.utc).strftime(
        '%Y-%m-%dT%H:%M:%S',
    )

    bd_payload = {
        'Размер': str(len(photo_bytes)),
        'Хеш': photo_hash,
        'ДвоичныеДанные_Base64Data': photo_b64,
        'ДвоичныеДанные_Type': (
            'application/octet-stream'
        ),
    }
    bd_result = client.post(
        'Catalog_ХранилищеДвоичныхДанных', bd_payload,
    )
    bd_key = bd_result['Ref_Key']

    file_payload = {
        'Description': filename,
        'ВладелецФайла_Key': nom_key,
        'ВладелецФайла_Type': (
            'StandardODATA.Catalog_Номенклатура'
        ),
        'Расширение': ext,
        'Размер': len(photo_bytes),
        'ДатаСоздания': now,
        'ДатаМодификацииУниверсальная': now,
        'ТипХраненияФайла': 'ВИнформационнойБазе',
        'СтатусИзвлеченияТекста': 'НеИзвлечен',
        'ИндексКартинки': 42,
    }
    file_result = client.post(
        'Catalog_НоменклатураПрисоединенныеФайлы',
        file_payload,
    )
    file_key = file_result['Ref_Key']

    storage_payload = {
        'Файл': file_key,
        'Файл_Type': (
            'StandardODATA.'
            'Catalog_НоменклатураПрисоединенныеФайлы'
        ),
        'ХранилищеДвоичныхДанных_Key': bd_key,
    }
    client.post(
        'InformationRegister_ХранилищеФайлов',
        storage_payload,
    )

    logger.info(
        'Фото "%s.%s" загружено (%d байт)',
        filename, ext, len(photo_bytes),
    )
    return file_result


def create_product(
    client: OData1C,
    data: ProductData,
    price_type_keys: list[str] | None = None,
) -> dict:
    """Полный цикл создания товара в 1С."""
    if not data.article:
        raise ODataValidationError(
            'Артикул не может быть пустым'
        )

    if article_exists(client, data.article):
        raise ProductExistsError(
            f'Артикул "{data.article}" уже существует'
        )

    category_key = _find_or_create_category(
        client, data.category,
    )
    group_key = _find_group_key(client, data.group)
    color_guid = _find_color_guid(client, data.color)

    nom = _create_nomenclature(
        client, data, category_key,
        group_key, color_guid,
    )
    nom_key = nom['Ref_Key']

    characteristics = []
    for size in data.sizes:
        char = _create_characteristic(
            client, nom_key, data.article, size,
        )
        char_key = char['Ref_Key']
        characteristics.append(char)

        _create_barcode(
            client, nom_key, char_key, size.barcode,
        )
        _set_price(
            client, nom_key, char_key,
            data.price, price_type_keys,
        )

    _set_price(
        client, nom_key, EMPTY_GUID,
        data.price, price_type_keys,
    )

    photos = []
    for i, url in enumerate(data.photos):
        photo = _upload_photo(client, nom_key, url, i)
        if photo:
            photos.append(photo)

    if photos:
        first_photo_key = photos[0]['Ref_Key']
        endpoint = (
            f"Catalog_Номенклатура(guid'{nom_key}')"
        )
        client.patch(
            endpoint,
            {'ФайлКартинки_Key': first_photo_key},
        )
        logger.info('Основное фото: %s', first_photo_key)

    logger.info(
        'Товар "%s" (%s) создан, '
        'характеристик: %d, фото: %d',
        data.name, data.article,
        len(characteristics), len(photos),
    )
    return {
        'nomenclature': nom,
        'characteristics': characteristics,
        'photos': photos,
    }


def get_product(
    client: OData1C,
    article: str,
) -> dict:
    """Собирает полный слепок товара по артикулу."""
    nom = get_nomenclature_by_article(client, article)
    nom_key = nom['Ref_Key']

    params = {
        '$filter': (
            f"Номенклатура_Key eq guid'{nom_key}'"
        ),
        '$format': 'json',
    }
    barcodes_result = client.get(
        'InformationRegister_ШтрихкодыНоменклатуры',
        params,
    )
    prices_result = client.get(
        'InformationRegister_ЦеныНоменклатуры', params,
    )

    barcodes = barcodes_result.get('value', [])
    char_keys = {
        b['Характеристика_Key']
        for b in barcodes
        if b.get('Характеристика_Key')
        and b['Характеристика_Key'] != EMPTY_GUID
    }

    characteristics = []
    for ck in char_keys:
        try:
            endpoint = (
                'Catalog_ХарактеристикиНоменклатуры'
                f"(guid'{ck}')"
            )
            char = client.get(
                endpoint, {'$format': 'json'},
            )
            characteristics.append(char)
        except ODataNotFoundError:
            logger.warning(
                'Характеристика %s пропущена', ck,
            )

    photos = list_product_photos(client, nom_key)
    return {
        'nomenclature': nom,
        'characteristics': characteristics,
        'barcodes': barcodes,
        'prices': prices_result.get('value', []),
        'photos': photos,
    }


def update_product(
    client: OData1C,
    article: str,
    update_data: dict,
    price_type_keys: list[str] | None = None,
) -> dict:
    """Обновляет товар по артикулу."""
    nom = get_nomenclature_by_article(client, article)
    nom_key = nom['Ref_Key']

    fields = {}
    if 'name' in update_data:
        fields['Description'] = update_data['name']
        fields['НаименованиеПолное'] = (
            update_data['name']
        )

    if fields:
        endpoint = (
            f"Catalog_Номенклатура(guid'{nom_key}')"
        )
        client.patch(endpoint, fields)
        logger.info(
            'Обновлена номенклатура "%s"', article,
        )

    if 'price' in update_data:
        new_price = float(update_data['price'])
        params = {
            '$filter': (
                f"Номенклатура_Key eq guid'{nom_key}'"
            ),
            '$format': 'json',
        }
        prices = client.get(
            'InformationRegister_ЦеныНоменклатуры',
            params,
        )
        seen: set = set()
        for p in prices.get('value', []):
            char_key = p.get(
                'Характеристика_Key', EMPTY_GUID,
            )
            if char_key in seen:
                continue
            seen.add(char_key)
            _set_price(
                client, nom_key, char_key,
                new_price, price_type_keys,
            )
        if EMPTY_GUID not in seen:
            _set_price(
                client, nom_key, EMPTY_GUID,
                new_price, price_type_keys,
            )

    new_sizes = update_data.get('sizes', [])
    for s in new_sizes:
        size = SizeData(
            global_size=s['global'],
            ru_size=s['ru'],
            barcode=s['barcode'],
        )
        char = _create_characteristic(
            client, nom_key, article, size,
        )
        char_key = char['Ref_Key']
        _create_barcode(
            client, nom_key, char_key, size.barcode,
        )
        if 'price' in update_data:
            _set_price(
                client, nom_key, char_key,
                float(update_data['price']),
                price_type_keys,
            )

    return get_product(client, article)


def delete_product(
    client: OData1C,
    article: str,
) -> bool:
    """Помечает товар на удаление (soft delete)."""
    nom = get_nomenclature_by_article(client, article)
    nom_key = nom['Ref_Key']
    endpoint = (
        f"Catalog_Номенклатура(guid'{nom_key}')"
    )
    client.patch(endpoint, {'DeletionMark': True})
    logger.info(
        'Товар "%s" помечен на удаление', article,
    )
    return True


def list_product_photos(
    client: OData1C,
    nom_key: str,
) -> list[dict]:
    """Возвращает присоединённые файлы товара."""
    params = {
        '$filter': (
            f"ВладелецФайла_Key eq guid'{nom_key}' and "
            f"DeletionMark eq false"
        ),
        '$select': (
            'Ref_Key,Description,Расширение,Размер'
        ),
        '$format': 'json',
    }
    try:
        result = client.get(
            'Catalog_НоменклатураПрисоединенныеФайлы',
            params,
        )
    except ODataNotFoundError:
        return []
    return result.get('value', [])


def get_photo_bytes(
    client: OData1C,
    file_key: str,
) -> tuple[bytes, str]:
    """Возвращает (содержимое, расширение) фото по file_key."""
    file_endpoint = (
        'Catalog_НоменклатураПрисоединенныеФайлы'
        f"(guid'{file_key}')"
    )
    file_meta = client.get(
        file_endpoint, {'$format': 'json'},
    )
    ext = (file_meta.get('Расширение') or 'jpg').lstrip('.')

    link_params = {
        '$filter': f"Файл eq guid'{file_key}'",
        '$select': 'ХранилищеДвоичныхДанных_Key',
        '$format': 'json',
    }
    link_result = client.get(
        'InformationRegister_ХранилищеФайлов',
        link_params,
    )
    link_rows = link_result.get('value', [])
    if not link_rows:
        raise ODataNotFoundError(
            f'Нет двоичных данных для файла {file_key}'
        )
    bd_key = link_rows[0]['ХранилищеДвоичныхДанных_Key']

    bd_endpoint = (
        f"Catalog_ХранилищеДвоичныхДанных(guid'{bd_key}')"
    )
    bd = client.get(bd_endpoint, {'$format': 'json'})
    payload = bd.get('ДвоичныеДанные_Base64Data') or ''
    return base64.b64decode(payload), ext


def _load_prices_and_chars(
    client: OData1C,
    nom_keys: list[str],
) -> tuple[dict[str, float], dict[str, list[str]]]:
    """Одним проходом: цены и Характеристика_Key per nom_key.

    Возвращает ({nom_key: цена}, {nom_key: [char_key, ...]}).
    Приоритет цены: сначала актуальная строка с ВидЦен_Key из
    ODATA_PRICE_TYPE_GUIDS (если задан), при её отсутствии —
    любая актуальная, при её отсутствии — любая. Внутри
    приоритета побеждает latest по Period.
    """
    prices: dict[str, float] = {}
    chars_map: dict[str, list[str]] = {}
    seen_chars: dict[str, set[str]] = {}
    if not nom_keys:
        return prices, chars_map
    preferred = set(ODATA_PRICE_TYPE_GUIDS)
    # {nom_key: (priority, period, price)}
    # priority: 2 — preferred+актуальная, 1 — актуальная,
    # 0 — любая
    best: dict[str, tuple[int, str, float]] = {}
    batch = 40
    unique = [k for k in set(nom_keys) if k]
    for i in range(0, len(unique), batch):
        chunk = unique[i:i + batch]
        flt = ' or '.join(
            f"Номенклатура_Key eq guid'{k}'"
            for k in chunk
        )
        params = {
            '$filter': flt,
            '$select': (
                'Номенклатура_Key,Характеристика_Key,'
                'ВидЦен_Key,Цена,Period,Актуальность'
            ),
            '$format': 'json',
        }
        try:
            data = client.get(
                'InformationRegister_ЦеныНоменклатуры',
                params,
            )
        except ODataNotFoundError:
            continue
        for row in data.get('value', []):
            nk = row.get('Номенклатура_Key') or ''
            if not nk:
                continue
            ck = row.get('Характеристика_Key') or ''
            if ck and ck != EMPTY_GUID:
                bucket = seen_chars.setdefault(nk, set())
                if ck not in bucket:
                    bucket.add(ck)
                    chars_map.setdefault(nk, []).append(ck)
            price = float(row.get('Цена') or 0)
            if price <= 0:
                continue
            actual = bool(row.get('Актуальность'))
            vid = row.get('ВидЦен_Key') or ''
            if actual and vid in preferred:
                prio = 2
            elif actual:
                prio = 1
            else:
                prio = 0
            period = row.get('Period') or ''
            prev = best.get(nk)
            if (prev is None or prio > prev[0] or
                    (prio == prev[0] and period > prev[1])):
                best[nk] = (prio, period, price)
    for nk, (_, _, price) in best.items():
        prices[nk] = price
    return prices, chars_map


_PHOTO_EXTS = {'jpg', 'jpeg', 'png', 'webp', 'gif'}


def _batch_names(
    client: OData1C,
    endpoint: str,
    keys: list[str],
) -> dict[str, str]:
    """Батч Description по Ref_Key. {ref_key: description}."""
    result: dict[str, str] = {}
    unique = [
        k for k in set(keys)
        if k and k != EMPTY_GUID
    ]
    if not unique:
        return result
    for i in range(0, len(unique), 40):
        chunk = unique[i:i + 40]
        flt = ' or '.join(
            f"Ref_Key eq guid'{k}'" for k in chunk
        )
        params = {
            '$filter': flt,
            '$select': 'Ref_Key,Description',
            '$format': 'json',
        }
        try:
            data = client.get(endpoint, params)
        except ODataNotFoundError:
            logger.warning('Справочник %s недоступен', endpoint)
            return result
        for row in data.get('value', []):
            result[row['Ref_Key']] = (
                row.get('Description') or ''
            )
    return result


def _batch_colors(
    client: OData1C,
    nom_keys: list[str],
) -> dict[str, str]:
    """{nom_key: цвет} через ТЧ ДополнительныеРеквизиты."""
    result: dict[str, str] = {}
    if not ODATA_COLOR_PROP_GUID or not nom_keys:
        return result
    unique = [k for k in set(nom_keys) if k]
    value_by_nom: dict[str, str] = {}
    for i in range(0, len(unique), 40):
        chunk = unique[i:i + 40]
        flt = ' or '.join(
            f"Ref_Key eq guid'{k}'" for k in chunk
        )
        params = {
            '$filter': (
                f'({flt}) and Свойство_Key eq '
                f"guid'{ODATA_COLOR_PROP_GUID}'"
            ),
            '$select': 'Ref_Key,Значение',
            '$format': 'json',
        }
        try:
            data = client.get(
                'Catalog_Номенклатура_ДополнительныеРеквизиты',
                params,
            )
        except ODataNotFoundError:
            return result
        for row in data.get('value', []):
            val = row.get('Значение') or ''
            if val and val != EMPTY_GUID:
                value_by_nom[row['Ref_Key']] = val
    if not value_by_nom:
        return result
    names = _batch_names(
        client,
        'Catalog_ЗначенияСвойствОбъектов',
        list(value_by_nom.values()),
    )
    for nom_key, val_key in value_by_nom.items():
        color = names.get(val_key, '')
        if color:
            result[nom_key] = color
    return result


def _batch_char_keys_by_nom(
    client: OData1C,
    nom_keys: list[str],
    seed: dict[str, list[str]] | None = None,
) -> dict[str, list[str]]:
    """{nom_key: [char_key, ...]} через штрихкоды и seed.

    Прямой фильтр по Owner в характеристиках 1С не поддерживает
    (500), поэтому ссылка nom→char берётся из ИнфРегистра
    ШтрихкодыНоменклатуры (где Номенклатура_Key фильтруется)
    объединённая с seed (обычно — характеристики из цен).
    """
    result: dict[str, list[str]] = {}
    seen: dict[str, set[str]] = {}
    if seed:
        for nk, cks in seed.items():
            bucket = seen.setdefault(nk, set())
            for ck in cks:
                if ck and ck != EMPTY_GUID and ck not in bucket:
                    bucket.add(ck)
                    result.setdefault(nk, []).append(ck)
    unique = [k for k in set(nom_keys) if k]
    if not unique:
        return result
    for i in range(0, len(unique), 40):
        chunk = unique[i:i + 40]
        flt = ' or '.join(
            f"Номенклатура_Key eq guid'{k}'" for k in chunk
        )
        params = {
            '$filter': flt,
            '$select': (
                'Номенклатура_Key,Характеристика_Key'
            ),
            '$format': 'json',
        }
        try:
            data = client.get(
                'InformationRegister_ШтрихкодыНоменклатуры',
                params,
            )
        except ODataNotFoundError:
            continue
        for row in data.get('value', []):
            nk = row.get('Номенклатура_Key') or ''
            ck = row.get('Характеристика_Key') or ''
            if not nk or not ck or ck == EMPTY_GUID:
                continue
            bucket = seen.setdefault(nk, set())
            if ck in bucket:
                continue
            bucket.add(ck)
            result.setdefault(nk, []).append(ck)
    return result


def _batch_char_descriptions(
    client: OData1C,
    char_keys: list[str],
) -> dict[str, str]:
    """{char_key: Description} батчем по Ref_Key."""
    result: dict[str, str] = {}
    unique = [k for k in set(char_keys) if k and k != EMPTY_GUID]
    if not unique:
        return result
    for i in range(0, len(unique), 40):
        chunk = unique[i:i + 40]
        flt = ' or '.join(
            f"Ref_Key eq guid'{k}'" for k in chunk
        )
        params = {
            '$filter': flt,
            '$select': 'Ref_Key,Description,DeletionMark',
            '$format': 'json',
        }
        try:
            data = client.get(
                'Catalog_ХарактеристикиНоменклатуры',
                params,
            )
        except ODataNotFoundError:
            return result
        for row in data.get('value', []):
            if row.get('DeletionMark'):
                continue
            result[row['Ref_Key']] = (
                row.get('Description') or ''
            )
    return result


def _batch_sizes(
    client: OData1C,
    nom_articles: dict[str, str],
    seed_chars: dict[str, list[str]] | None = None,
) -> dict[str, list[dict]]:
    """{nom_key: [{global, ru}, ...]} из характеристик.

    Порядок: как отдал 1С. Дубли по (global, ru) убираются.
    seed_chars — предварительно собранные char_keys (например,
    из регистра цен) объединяются со штрихкодами.
    """
    result: dict[str, list[dict]] = {}
    if not nom_articles:
        return result
    char_map = _batch_char_keys_by_nom(
        client, list(nom_articles.keys()), seed=seed_chars,
    )
    all_chars = [
        ck for cks in char_map.values() for ck in cks
    ]
    descriptions = _batch_char_descriptions(client, all_chars)
    for nom_key, chars in char_map.items():
        article = nom_articles.get(nom_key, '')
        seen: set[tuple[str, str]] = set()
        bucket: list[dict] = []
        for ck in chars:
            desc = descriptions.get(ck, '')
            if not desc:
                continue
            g, ru = _parse_size_lenient(desc, article)
            if not (g or ru):
                continue
            pair = (g, ru)
            if pair in seen:
                continue
            seen.add(pair)
            bucket.append({'global': g, 'ru': ru})
        if bucket:
            result[nom_key] = bucket
    return result


def _batch_first_photos(
    client: OData1C,
    nom_keys: list[str],
) -> dict[str, str]:
    """{nom_key: file_key} — первый присоединённый файл."""
    result: dict[str, str] = {}
    unique = [k for k in set(nom_keys) if k]
    if not unique:
        return result
    for i in range(0, len(unique), 40):
        chunk = unique[i:i + 40]
        flt = ' or '.join(
            f"ВладелецФайла_Key eq guid'{k}'" for k in chunk
        )
        params = {
            '$filter': (
                f'({flt}) and DeletionMark eq false'
            ),
            '$select': (
                'Ref_Key,ВладелецФайла_Key,Расширение,'
                'Description'
            ),
            '$orderby': 'ВладелецФайла_Key,Description',
            '$format': 'json',
        }
        try:
            data = client.get(
                'Catalog_НоменклатураПрисоединенныеФайлы',
                params,
            )
        except ODataNotFoundError:
            continue
        for row in data.get('value', []):
            owner = row.get('ВладелецФайла_Key') or ''
            if not owner or owner in result:
                continue
            ext = (
                row.get('Расширение') or ''
            ).lower().lstrip('.')
            if ext and ext not in _PHOTO_EXTS:
                continue
            result[owner] = row['Ref_Key']
    return result


def get_all_products(
    client: OData1C,
    limit: int = 500,
    offset: int = 0,
    only_active: bool = True,
    prefix: str = '',
) -> list[dict]:
    """Список товаров с базовыми данными.

    Батчами обогащается: название категории и группы, цвет из
    ТЧ ДополнительныеРеквизиты, фолбэк фото на первый файл, если
    основной ФайлКартинки_Key пуст. Характеристики и штрихкоды
    не тянет — для деталей вызывать get_product(article).
    """
    conds = ['IsFolder eq false']
    if only_active:
        conds.append('DeletionMark eq false')
    if prefix:
        conds.append(
            f"startswith(Артикул, '{_esc(prefix)}')"
        )
    params = {
        '$filter': ' and '.join(conds),
        '$select': (
            'Ref_Key,Артикул,Description,'
            'НаименованиеПолное,Parent_Key,'
            'КатегорияНоменклатуры_Key,ФайлКартинки_Key,'
            'DeletionMark'
        ),
        '$orderby': 'Description',
        '$top': str(min(limit, _PAGE_SIZE)),
        '$skip': str(offset),
        '$format': 'json',
    }
    result = client.get('Catalog_Номенклатура', params)
    rows = result.get('value', [])
    nom_keys = [r['Ref_Key'] for r in rows]

    cat_keys = [
        r.get('КатегорияНоменклатуры_Key') or '' for r in rows
    ]
    grp_keys = [r.get('Parent_Key') or '' for r in rows]

    nom_articles = {
        r['Ref_Key']: (r.get('Артикул') or '')
        for r in rows
    }

    prices, price_chars = _load_prices_and_chars(
        client, nom_keys,
    )
    categories = _batch_names(
        client, 'Catalog_КатегорииНоменклатуры', cat_keys,
    )
    groups = _batch_names(
        client, 'Catalog_Номенклатура', grp_keys,
    )
    colors = _batch_colors(client, nom_keys)
    sizes = _batch_sizes(
        client, nom_articles, seed_chars=price_chars,
    )

    need_photo = [
        r['Ref_Key'] for r in rows
        if not (r.get('ФайлКартинки_Key') or '').strip()
        or (r.get('ФайлКартинки_Key') or '') == EMPTY_GUID
    ]
    fallback_photos = _batch_first_photos(
        client, need_photo,
    )

    out: list[dict] = []
    for r in rows:
        key = r['Ref_Key']
        photo_key = r.get('ФайлКартинки_Key') or ''
        if not photo_key or photo_key == EMPTY_GUID:
            photo_key = fallback_photos.get(key, '')
        short = r.get('Description') or ''
        full = r.get('НаименованиеПолное') or ''
        article = r.get('Артикул') or ''
        name = short or full or article
        cat_key = r.get('КатегорияНоменклатуры_Key') or ''
        grp_key = r.get('Parent_Key') or ''
        out.append({
            'ref_key': key,
            'article': article,
            'name': name,
            'full_name': full,
            'group_key': grp_key,
            'group_name': (
                groups.get(grp_key, '')
                if grp_key and grp_key != EMPTY_GUID
                else ''
            ),
            'category_key': cat_key,
            'category_name': (
                categories.get(cat_key, '')
                if cat_key and cat_key != EMPTY_GUID
                else ''
            ),
            'color': colors.get(key, ''),
            'sizes': sizes.get(key, []),
            'photo_key': photo_key,
            'price': prices.get(key, 0.0),
            'deletion_mark': bool(r.get('DeletionMark')),
        })
    return out
