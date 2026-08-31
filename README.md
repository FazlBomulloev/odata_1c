# odata_1c

Python-клиент для чтения товародвижения из 1С УНФ 3.0 через
стандартный интерфейс OData. Возвращает плоские нормализованные
записи `MovementRecord`, готовые к загрузке в БД, отчёт или
интеграционный поток.

Модуль ничего не пишет в 1С, ничего не сохраняет на диск и
не поднимает HTTP-сервисов. Это библиотека: подключил, вызвал,
получил `list[MovementRecord]` — что делать дальше решает
вызывающий код.

---

## Установка

```bash
pip install -r requirements.txt
```

Зависимости минимальные: `requests`, `python-dotenv`.

Заведите `.env` рядом с пакетом:

```
ODATA_BASE_URL=http://<host>/<база>/odata/standard.odata
ODATA_LOGIN=<логин>
ODATA_PASSWORD=<пароль>
ODATA_TIMEOUT=120
ODATA_MAX_RETRIES=3
```

Логин с кириллицей поддерживается (`OData1C` кодирует Basic Auth
в UTF-8, а не в cp1251, как это делает `requests` по умолчанию).

---

## Быстрый старт

```python
from datetime import datetime
from odata_1c import OData1C, get_all_movements

client = OData1C()
movements = get_all_movements(
    client,
    datetime(2025, 8, 1),
    datetime(2025, 8, 31),
)

for m in movements:
    print(m.period, m.operation_type, m.article,
          m.size, m.quantity,
          m.warehouse_from, '->', m.warehouse_to)
```

Полный набор примеров с фильтрами, агрегациями и разбором
видов документов — в `examples.py`.

---

## Публичное API

Все функции возвращают `list[MovementRecord]` и принимают:

- `client: OData1C` — экземпляр клиента.
- `date_from`, `date_to` — `datetime` или ISO-строка
  `YYYY-MM-DDTHH:MM:SS`. Обязательные, границы включительно.
- `organization=''` — GUID организации (`Catalog_Организации.Ref_Key`).
- `warehouse=''` — GUID склада (`Catalog_СтруктурныеЕдиницы.Ref_Key`).

| Функция | Что возвращает |
|---|---|
| `get_transfers`   | Перемещения между складами и межфирменные передачи. |
| `get_write_offs`  | Списания запасов. |
| `get_receipts`    | Оприходования, приходные ордера, приходные накладные, ввод начальных остатков, принятие к учёту. |
| `get_expenses`    | Расходные ордера и расходные накладные. |
| `get_all_movements` | Все виды разом; тип операции проставляется по виду документа. |
| `list_recorder_types` | Уникальные `Recorder_Type` за период. Утилита: если в базе появился новый вид документа, пишущий в регистр движений — здесь его будет видно. |

Пример фильтра по складу:

```python
from odata_1c import OData1C, get_all_movements

client = OData1C()

# Получить GUID нужного склада
data = client.get('Catalog_СтруктурныеЕдиницы', {
    "$filter": "Description eq 'Основной склад'",
    "$select": 'Ref_Key',
    "$format": 'json',
})
wh_guid = data['value'][0]['Ref_Key']

recs = get_all_movements(
    client, '2025-08-01T00:00:00', '2025-09-01T00:00:00',
    warehouse=wh_guid,
)
```

Фильтр по складу или организации сохраняет пары перемещения:
если совпала хотя бы одна сторона (например, склад-приёмник),
пара с несовпадающим складом-источником всё равно попадёт в
результат целиком. Это сделано специально — иначе межфирменные
передачи и обычные перемещения между складами разрывались бы
на половинки.

---

## Модель `MovementRecord`

```python
@dataclass
class MovementRecord:
    period: datetime | None
    name: str
    article: str
    barcode: str
    size: str          # '2XL, 54' — global + ru через запятую
    size_global: str   # '2XL'
    size_ru: str       # '54'
    quantity: float
    operation_type: str
    warehouse_from: str
    warehouse_to: str
    organization_from: str
    organization_to: str
    document_kind: str          # 'ПеремещениеЗапасов' и т.п.
    document_number: str
    document_date: datetime | None
    recorder: str               # GUID документа-регистратора
```

Возможные значения `operation_type`:

`перемещение`, `межфирменное`, `списание`, `оприходование`,
`приход`, `расход`, `пересортица`, `сборка`, `переработка`.

Полный маппинг «вид документа → тип операции» лежит в
`odata_1c.movements.DOCUMENT_OPERATION` — его можно править
на месте, если в вашей базе есть свои виды документов.

Логика заполнения `warehouse_from` / `warehouse_to`:

- Перемещение и межфирменная передача — обе стороны заполнены.
- Списание, расход — заполнен только `warehouse_from`,
  `warehouse_to = ''`.
- Оприходование, приход — заполнен только `warehouse_to`.

Если справочник `Catalog_СтруктурныеЕдиницы` не опубликован,
в поле придёт GUID склада. Аналогично для организаций.

---

## Как это устроено

1. Один запрос к регистру `ЗапасыНаСкладах_RecordType` за период,
   с фильтром по `Recorder_Type` (если в вызове задан набор видов
   документов). Пагинация `$top` + `$skip`, страница 1000.
2. Пре-фильтр строк по `Организация_Key` / `СтруктурнаяЕдиница_Key`
   (Python-фильтр, см. ниже почему не в `$filter`). Для парных
   типов сохраняются все строки Recorder-а, если хотя бы одна
   удовлетворяет фильтру — иначе разорвались бы пары.
3. Пакетный резолв справочников по всем нужным GUID:
   `Catalog_Номенклатура`, `Catalog_ХарактеристикиНоменклатуры`,
   `InformationRegister_ШтрихкодыНоменклатуры`, документы-регистраторы,
   `Catalog_Организации`, `Catalog_СтруктурныеЕдиницы`.
   Батч по 40 ключей через `$filter Ref_Key eq guid'...' or ...`.
4. Парение Expense / Receipt для видов из `PAIRED_KINDS`
   (перемещение + межфирменная передача) — жадный матч по
   `(Номенклатура_Key, Характеристика_Key, Количество)` внутри
   Recorder-а. Непарные строки (граничный эффект периода)
   отдаются как одиночные записи.
5. Нормализация в `MovementRecord`.

Никакого N+1: на строку регистра в 1С отдельный запрос не идёт.
Число HTTP-вызовов за один `get_all_movements` — порядка
`страницы_регистра + 6..10 батчей справочников`, не тысячи.

---

## Логирование

Все модули пишут через стандартный `logging`:

```python
import logging
logging.basicConfig(level=logging.INFO)
```

`INFO` — сколько строк регистра выгружено за период.
`WARNING` — недоступные справочники, битые даты,
непарные строки перемещения, отсутствующая номенклатура.
`DEBUG` — детали HTTP-запросов.

---

## Ошибки

Всё, что выходит наружу, — потомки `ODataError`:

- `ODataConnectionError` — сетевые проблемы, 5xx после повторов.
- `ODataAuthError` — 401 / 403.
- `ODataNotFoundError` — 404 на конкретный ресурс.
- `ODataValidationError` — ошибка валидации данных на стороне модуля.

Клиент делает до `ODATA_MAX_RETRIES` повторов с экспоненциальным
backoff (2, 4, 8 секунд) на сетевых ошибках и `RequestException`.
`AuthError` и `NotFoundError` пробрасываются без ретраев.

---

## Структура пакета

```
odata_1c/
    __init__.py       # публичные экспорты
    client.py         # HTTP-клиент OData1C (Basic Auth + retry)
    config.py         # чтение .env
    exceptions.py     # исключения
    models.py         # dataclass MovementRecord
    movements.py      # вся логика чтения движений
```

Единственный класс — `OData1C`. Единственная модель наружу —
`MovementRecord`. Всё остальное — функции.
