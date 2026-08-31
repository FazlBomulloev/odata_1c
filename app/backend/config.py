import os

from dotenv import load_dotenv

load_dotenv()

ODATA_BASE_URL = os.getenv(
    'ODATA_BASE_URL',
    'http://95.213.212.125:8380/Intreid_UNF_Copy4/'
    'odata/standard.odata',
)
ODATA_LOGIN = os.getenv('ODATA_LOGIN', '')
ODATA_PASSWORD = os.getenv('ODATA_PASSWORD', '')
ODATA_TIMEOUT = int(os.getenv('ODATA_TIMEOUT', '60'))
ODATA_MAX_RETRIES = int(os.getenv('ODATA_MAX_RETRIES', '3'))
ODATA_CONCURRENCY = int(os.getenv('ODATA_CONCURRENCY', '8'))

DB_URL = os.getenv(
    'DB_URL',
    'sqlite+aiosqlite:///./app.db',
)

CORS_ORIGINS = os.getenv(
    'CORS_ORIGINS',
    'http://localhost:5173,http://localhost:8080',
).split(',')

SYNC_INTERVAL_HOURS = int(os.getenv('SYNC_INTERVAL_HOURS', '2'))
# Первый прогон грузит движения/продажи за столько дней (2 года).
SYNC_BACKFILL_DAYS = int(os.getenv('SYNC_BACKFILL_DAYS', '730'))
# Каждый последующий прогон грузит только это окно и replace-ит
# его в БД — покрывает свежие движения и задним числом
# переоформленные документы в пределах окна.
SYNC_REFRESH_DAYS = int(os.getenv('SYNC_REFRESH_DAYS', '14'))
# Бэкфилл нарезается на чанки такого размера, чтобы падение
# посреди бэкфилла не отбрасывало прогресс полностью.
SYNC_CHUNK_DAYS = int(os.getenv('SYNC_CHUNK_DAYS', '30'))
# Если с последнего full-ребилда прошло больше — sync_loop сам
# запустит full-цикл (ловит переоформления задним числом).
SYNC_FULL_REBUILD_DAYS = int(os.getenv('SYNC_FULL_REBUILD_DAYS', '7'))
SYNC_ENABLED = os.getenv('SYNC_ENABLED', 'true').lower() in (
    '1', 'true', 'yes', 'y',
)

# Секрет для подписи session-cookie. Обязателен в проде.
# В dev — фолбэк, но с предупреждением в логах.
SESSION_SECRET = os.getenv('SESSION_SECRET', '')
SESSION_MAX_AGE = int(os.getenv('SESSION_MAX_AGE', '2592000'))
# httpOnly cookie летает по HTTP в dev; secure=True в проде.
SESSION_COOKIE_SECURE = os.getenv(
    'SESSION_COOKIE_SECURE', 'false',
).lower() in ('1', 'true', 'yes', 'y')

# Учётка owner-а создаётся при первом запуске, если пуста таблица users.
OWNER_USERNAME = os.getenv('OWNER_USERNAME', 'admin')
OWNER_PASSWORD = os.getenv('OWNER_PASSWORD', '')
