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
