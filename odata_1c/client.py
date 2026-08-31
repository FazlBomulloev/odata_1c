import base64
import logging
import time
from urllib.parse import quote

import requests

# safe-набор для OData: пробелы и кириллица в query кодируются,
# кавычки/скобки/двоеточие/запятая — валидны.
_QUERY_SAFE = "'()*!,=/:$"
_PATH_SAFE = '/'

from .config import (
    ODATA_BASE_URL,
    ODATA_LOGIN,
    ODATA_MAX_RETRIES,
    ODATA_PASSWORD,
    ODATA_TIMEOUT,
)
from .exceptions import (
    ODataAuthError,
    ODataConnectionError,
    ODataNotFoundError,
)

logger = logging.getLogger(__name__)


def _make_basic_auth(login: str, password: str) -> str:
    """Basic Auth с поддержкой кириллицы."""
    creds = f'{login}:{password}'.encode('utf-8')
    return 'Basic ' + base64.b64encode(creds).decode()


class OData1C:

    def __init__(
        self,
        base_url: str = ODATA_BASE_URL,
        login: str = ODATA_LOGIN,
        password: str = ODATA_PASSWORD,
        timeout: int = ODATA_TIMEOUT,
        max_retries: int = ODATA_MAX_RETRIES,
    ):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries
        self._auth_header = _make_basic_auth(
            login, password,
        )
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': self._auth_header,
        })

    def _build_url(
        self,
        endpoint: str,
        params: dict | None = None,
    ) -> str:
        """URL с процентным кодированием пробелов и кириллицы."""
        path = quote(endpoint, safe=_PATH_SAFE)
        url = f'{self.base_url}/{path}'
        if params:
            qs = '&'.join(
                f'{k}={quote(str(v), safe=_QUERY_SAFE)}'
                for k, v in params.items()
            )
            url = f'{url}?{qs}'
        return url

    def _request(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
        json_data: dict | None = None,
    ) -> requests.Response:
        """Выполняет запрос с retry и backoff."""
        url = self._build_url(endpoint, params)
        last_exc = None

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.debug(
                    'Запрос %s %s (попытка %d)',
                    method, endpoint, attempt,
                )
                req = requests.Request(
                    method=method,
                    url=url,
                    json=json_data,
                    headers=self.session.headers,
                )
                prepared = req.prepare()
                prepared.url = url
                resp = self.session.send(
                    prepared,
                    timeout=self.timeout,
                )
                self._check_response(resp, endpoint)
                return resp

            except ODataAuthError:
                raise
            except ODataNotFoundError:
                raise
            except (
                requests.ConnectionError,
                requests.Timeout,
            ) as exc:
                last_exc = exc
                wait = 2 ** attempt
                logger.warning(
                    'Ошибка соединения с 1С (%s), '
                    'повтор через %d сек',
                    exc, wait,
                )
                time.sleep(wait)
            except requests.RequestException as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    wait = 2 ** attempt
                    logger.warning(
                        'Ошибка запроса (%s), '
                        'повтор через %d сек',
                        exc, wait,
                    )
                    time.sleep(wait)

        raise ODataConnectionError(
            f'Не удалось выполнить запрос после '
            f'{self.max_retries} попыток: {last_exc}'
        )

    def _check_response(
        self,
        resp: requests.Response,
        endpoint: str,
    ) -> None:
        """Проверяет HTTP-ответ."""
        if resp.status_code == 401:
            raise ODataAuthError(
                'Ошибка авторизации в 1С'
            )
        if resp.status_code == 403:
            raise ODataAuthError(
                'Доступ запрещён'
            )
        if resp.status_code == 404:
            raise ODataNotFoundError(
                f'Не найдено: {endpoint}'
            )
        resp.raise_for_status()

    def get(
        self,
        endpoint: str,
        params: dict | None = None,
    ) -> dict:
        """GET-запрос, возвращает JSON."""
        resp = self._request('GET', endpoint, params=params)
        return resp.json()

    def post(
        self,
        endpoint: str,
        data: dict,
    ) -> dict:
        """POST-запрос, создание сущности."""
        resp = self._request(
            'POST', endpoint, json_data=data,
        )
        logger.info('Создано: %s', endpoint)
        return resp.json()

    def patch(
        self,
        endpoint: str,
        data: dict,
    ) -> dict:
        """PATCH-запрос, обновление сущности."""
        resp = self._request(
            'PATCH', endpoint, json_data=data,
        )
        logger.info('Обновлено: %s', endpoint)
        return resp.json()

    def delete(self, endpoint: str) -> bool:
        """DELETE-запрос."""
        self._request('DELETE', endpoint)
        logger.info('Удалено: %s', endpoint)
        return True