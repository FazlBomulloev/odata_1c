import base64
import json
import logging
import time
from urllib.parse import quote

import requests

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
    ODataTimeoutError,
    ODataValidationError,
)

logger = logging.getLogger(__name__)

_IDEMPOTENT = frozenset({'GET', 'HEAD'})

def _make_basic_auth(login: str, password: str) -> str:
    creds = f'{login}:{password}'.encode('utf-8')
    return 'Basic ' + base64.b64encode(creds).decode()

def _extract_odata_error(resp: 'requests.Response') -> str:
    text = ''
    try:
        text = resp.text or ''
    except (UnicodeDecodeError, AttributeError):
        text = ''
    if not text:
        return ''
    try:
        body = resp.json()
    except (ValueError, json.JSONDecodeError):
        return text[:500]
    err = body.get('odata.error') if isinstance(body, dict) else None
    if not isinstance(err, dict):
        return text[:500]
    code = err.get('code', '') or ''
    msg = err.get('message', '')
    if isinstance(msg, dict):
        msg = msg.get('value', '') or ''
    msg = str(msg or '').strip()
    if code and msg:
        return f'{code}: {msg}'
    return msg or code or text[:500]

def _parse_json_body(resp: 'requests.Response') -> dict:
    if resp.status_code == 204:
        return {}
    body = resp.content or b''
    if not body.strip():
        return {}
    try:
        return resp.json()
    except (ValueError, json.JSONDecodeError) as exc:
        snippet = ''
        try:
            snippet = (resp.text or '')[:300]
        except (UnicodeDecodeError, AttributeError):
            snippet = ''
        raise ODataValidationError(
            f'Не JSON в ответе 1С ({exc}): {snippet!r}'
        )

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
        self.max_retries = max(1, int(max_retries))
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
        path = quote(endpoint, safe=_PATH_SAFE)
        url = f'{self.base_url}/{path}'
        if params:
            qs = '&'.join(
                f'{k}={quote(str(v), safe=_QUERY_SAFE)}'
                for k, v in params.items()
            )
            url = f'{url}?{qs}'
        return url

    def _send_once(
        self,
        method: str,
        url: str,
        json_data: dict | None,
    ) -> requests.Response:
        req = requests.Request(
            method=method,
            url=url,
            json=json_data,
            headers=self.session.headers,
        )
        prepared = req.prepare()
        prepared.url = url
        return self.session.send(
            prepared,
            timeout=self.timeout,
        )

    def _request(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
        json_data: dict | None = None,
    ) -> requests.Response:
        method = method.upper()
        url = self._build_url(endpoint, params)
        idempotent = method in _IDEMPOTENT
        attempts = self.max_retries if idempotent else 1
        last_exc: Exception | None = None

        for attempt in range(1, attempts + 1):
            try:
                logger.debug(
                    'Запрос %s %s (попытка %d/%d)',
                    method, endpoint, attempt, attempts,
                )
                resp = self._send_once(method, url, json_data)
            except requests.Timeout as exc:
                if not idempotent:
                    raise ODataTimeoutError(
                        f'Таймаут {method} {endpoint} — '
                        f'состояние в 1С неизвестно, '
                        f'ретрай запрещён: {exc}'
                    )
                last_exc = exc
                self._sleep_backoff(attempt, attempts, exc)
                continue
            except requests.ConnectionError as exc:
                if not idempotent:
                    raise ODataConnectionError(
                        f'Обрыв соединения {method} {endpoint}: '
                        f'{exc}'
                    )
                last_exc = exc
                self._sleep_backoff(attempt, attempts, exc)
                continue
            except requests.RequestException as exc:

                raise ODataConnectionError(
                    f'Ошибка запроса {method} {endpoint}: {exc}'
                )

            status = resp.status_code
            if 500 <= status < 600 and idempotent \
                    and attempt < attempts:
                detail = _extract_odata_error(resp) or (
                    f'HTTP {status}'
                )
                logger.warning(
                    '5xx от 1С (%s), повтор', detail,
                )
                self._sleep_backoff(attempt, attempts, None)
                continue

            self._check_response(resp, endpoint)
            return resp

        raise ODataConnectionError(
            f'Не удалось выполнить {method} {endpoint} '
            f'за {attempts} попыт(ки): {last_exc}'
        )

    def _sleep_backoff(
        self,
        attempt: int,
        attempts: int,
        exc: Exception | None,
    ) -> None:
        if attempt >= attempts:
            return
        wait = 2 ** attempt
        if exc is not None:
            logger.warning(
                'Сетевая ошибка (%s), повтор через %d сек',
                exc, wait,
            )
        time.sleep(wait)

    def _check_response(
        self,
        resp: requests.Response,
        endpoint: str,
    ) -> None:
        status = resp.status_code
        if status < 400:
            return
        detail = _extract_odata_error(resp)
        if status == 401:
            raise ODataAuthError(
                f'Ошибка авторизации в 1С: {detail}'
                if detail else 'Ошибка авторизации в 1С'
            )
        if status == 403:
            raise ODataAuthError(
                f'Доступ запрещён: {detail}'
                if detail else 'Доступ запрещён'
            )
        if status == 404:
            raise ODataNotFoundError(
                f'Не найдено: {endpoint}'
                + (f' — {detail}' if detail else '')
            )
        if 400 <= status < 500:
            raise ODataValidationError(
                f'HTTP {status} на {endpoint}'
                + (f': {detail}' if detail else '')
            )
        raise ODataConnectionError(
            f'HTTP {status} на {endpoint}'
            + (f': {detail}' if detail else '')
        )

    def get(
        self,
        endpoint: str,
        params: dict | None = None,
    ) -> dict:
        resp = self._request('GET', endpoint, params=params)
        return _parse_json_body(resp)

    def post(
        self,
        endpoint: str,
        data: dict,
    ) -> dict:
        resp = self._request(
            'POST', endpoint, json_data=data,
        )
        logger.info('Создано: %s', endpoint)
        return _parse_json_body(resp)

    def patch(
        self,
        endpoint: str,
        data: dict,
    ) -> dict:
        resp = self._request(
            'PATCH', endpoint, json_data=data,
        )
        logger.info('Обновлено: %s', endpoint)
        return _parse_json_body(resp)

    def delete(self, endpoint: str) -> bool:
        self._request('DELETE', endpoint)
        logger.info('Удалено: %s', endpoint)
        return True
