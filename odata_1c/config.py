import os

from dotenv import load_dotenv

load_dotenv()

ODATA_BASE_URL = os.getenv(
    'ODATA_BASE_URL',
    'http://localhost/Intreid_UNF_Copy4/odata/standard.odata',
)
ODATA_LOGIN = os.getenv('ODATA_LOGIN', '')
ODATA_PASSWORD = os.getenv('ODATA_PASSWORD', '')
ODATA_TIMEOUT = int(os.getenv('ODATA_TIMEOUT', '30'))
ODATA_MAX_RETRIES = int(os.getenv('ODATA_MAX_RETRIES', '3'))
_price_types_raw = (
    os.getenv('ODATA_PRICE_TYPE_GUIDS', '')
    or os.getenv('ODATA_PRICE_TYPE_GUID', '')
)
ODATA_PRICE_TYPE_GUIDS = [
    g.strip() for g in _price_types_raw.split(',') if g.strip()
]
ODATA_PRICE_TYPE_GUID = (
    ODATA_PRICE_TYPE_GUIDS[0] if ODATA_PRICE_TYPE_GUIDS else ''
)
ODATA_COLOR_PROP_GUID = os.getenv(
    'ODATA_COLOR_PROP_GUID',
    '09aaacc4-32e5-11ef-9698-000c297d6e66',
)
