# odata_1c

Работа с 1С УНФ 3.0 через стандартный интерфейс OData:
товародвижение, остатки, продажи (маркетплейсы и розница),
валовая прибыль, CRUD товаров. Состоит из трёх частей:

- `odata_1c/` — синхронная Python-библиотека (`requests`);
- `app/backend/` — FastAPI: фоновая синхронизация в SQLite
  и REST `/api/*` для веб-интерфейса;
- `app/web/` — React + TypeScript + Vite, раздаётся nginx.

---

## Запуск в Docker

```bash
cp .env.example .env   # заполнить ODATA_*, SESSION_SECRET,
                       # OWNER_PASSWORD
docker compose up -d --build
```

Веб-интерфейс — `http://localhost:${WEB_PORT:-8080}`, бэкенд
доступен только внутри сети compose. SQLite-кэш лежит в
`./data/app.db`.

Все переменные окружения с пояснениями — в `.env.example`.

---

## Бэкенд

- **Синхронизация** (`sync.py`). Раз в `SYNC_INTERVAL_HOURS`:
  склады, организации, остатки, движения, продажи, обороты.
  Первый прогон — бэкфилл за `SYNC_BACKFILL_DAYS` чанками по
  `SYNC_CHUNK_DAYS`, дальше перезаписывается окно
  `SYNC_REFRESH_DAYS`. Раз в `SYNC_FULL_REBUILD_DAYS` —
  полный ребилд. Прогоны пишутся в `sync_runs`.
- **Чтение** — страницы продаж, движений, остатков и валовой
  прибыли отдаются из кэша с серверной пагинацией.
- **Товары** — идут в 1С напрямую через библиотеку
  (в отдельном потоке).
- **Авторизация** — session-cookie, роли owner / user.
  Owner создаётся при первом старте из `OWNER_USERNAME` /
  `OWNER_PASSWORD`. `AUTH_ENABLED=false` отключает проверку.

Асинхронный клиент бэкенда (`odata_async.py`, `services.py`)
переиспользует константы и чистые функции библиотеки.
Совпадение результатов продаж проверяет
`tests/test_sales_parity.py`.

---

## Библиотека

### Установка

```bash
pip install -r requirements.txt
```

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

### Быстрый старт

```python
from datetime import datetime
from odata_1c import OData1C, get_all_movements, get_all_sales

client = OData1C()
movements = get_all_movements(
    client, datetime(2025, 8, 1), datetime(2025, 8, 31),
)
sales = get_all_sales(
    client, datetime(2025, 8, 1), datetime(2025, 8, 31),
)
```

Даты — `datetime` или ISO-строка. Верхняя граница без времени
(`2025-08-31` или полночь) расширяется до `23:59:59`.

### Публичное API

Движения (`list[MovementRecord]`), параметры
`client, date_from, date_to, organization='', warehouse=''`:

| Функция | Что возвращает |
|---|---|
| `get_transfers`   | Перемещения между складами и межфирменные передачи. |
| `get_write_offs`  | Списания запасов. |
| `get_receipts`    | Оприходования, приходные ордера и накладные, ввод начальных остатков, принятие к учёту. |
| `get_expenses`    | Расходные ордера и расходные накладные. |
| `get_all_movements` | Все виды разом. |
| `list_recorder_types` | Уникальные `Recorder_Type` за период. |

Остатки, продажи, обороты:

| Функция | Что возвращает |
|---|---|
| `get_stock(client, warehouse, organization, nomenclature, only_positive)` | `list[StockRecord]` — текущие остатки. |
| `get_stock_by_article(client, article)` | Остатки по артикулу. |
| `get_marketplace_sales(client, date_from, date_to, channel=None)` | `list[SaleRecord]` из отчётов комиссионера. Канал (`WB`, `Ozon`, `Lamoda`) — по названию договора, склад и организация — из регистра `Продажи`. Возвраты с минусом. |
| `get_retail_sales(client, date_from, date_to)` | Розница из отчётов о розничных продажах. |
| `get_all_sales(client, date_from, date_to)` | Маркетплейсы + розница. |
| `get_sales_turnover(client, date_from, date_to)` | `list[TurnoverRecord]` — выручка и себестоимость для валовой прибыли. |

Товары и артикулы:

| Функция | Что делает |
|---|---|
| `create_product(client, ProductData)` | Номенклатура, размеры-характеристики, штрихкоды, цены, цвет, фото. |
| `get_product` / `update_product` / `delete_product` | Чтение, изменение, пометка на удаление по артикулу. |
| `get_all_products` / `count_products` | Список товаров с пагинацией. |
| `list_product_photos` / `get_photo_bytes` | Фото номенклатуры. |
| `search_by_article` / `find_free_article` / `article_exists` / `get_nomenclature_by_article` | Поиск и подбор артикула. |

Для записи цен нужен `ODATA_PRICE_TYPE_GUIDS`, для цвета —
`ODATA_COLOR_PROP_GUID`. Значение по умолчанию подходит
только для базы `Intreid_UNF_Copy4`.

### Движения: детали

Фильтр по складу:

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

### Модель `MovementRecord`

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

### Как это устроено

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
- `ODataTimeoutError` — таймаут записи (POST / PATCH / DELETE).
- `ODataAuthError` — 401 / 403.
- `ODataNotFoundError` — 404 на конкретный ресурс.
- `ODataValidationError` — прочие 4xx, не-JSON ответ, ошибка
  валидации данных на стороне модуля.
- `ArticleNotFoundError`, `ProductExistsError` — операции
  с товарами.

GET / HEAD повторяются до `ODATA_MAX_RETRIES` раз с
экспоненциальным backoff (2, 4, 8 секунд) на сетевых ошибках
и 5xx. Запись не повторяется никогда: после таймаута состояние
в 1С неизвестно, повтор мог бы задвоить документ.

---

## Тесты

```bash
pip install -r app/backend/requirements.txt pytest
python -m pytest
```

Тесты не ходят в 1С: чистые функции проверяются напрямую,
продажи — через фейковый клиент.

---

## Структура

```
odata_1c/
    client.py         # HTTP-клиент OData1C (Basic Auth + retry)
    config.py         # чтение .env
    exceptions.py     # исключения
    models.py         # dataclass-модели
    movements.py      # товародвижение
    stock.py          # остатки
    sales.py          # продажи
    turnover.py       # обороты для валовой прибыли
    products.py       # CRUD товаров
    search.py         # поиск по артикулу
app/backend/          # FastAPI, синхронизация, SQLite
app/web/              # React-интерфейс
tests/                # pytest
```
