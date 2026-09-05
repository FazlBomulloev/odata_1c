import asyncio
import base64
import json
import logging
from typing import Any
from urllib.parse import quote

import httpx

_QUERY_SAFE = "'()*!,=/:$"
_PATH_SAFE = '/'

from .config import (
    ODATA_BASE_URL,
    ODATA_CONCURRENCY,
    ODATA_LOGIN,
    ODATA_MAX_RETRIES,
    ODATA_PASSWORD,
    ODATA_TIMEOUT,
)

logger = logging.getLogger(__name__)

def _extract_odata_error(resp: httpx.Response) -> str:
    text = resp.text or ''
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

def _parse_json_body(resp: httpx.Response) -> dict:
    if resp.status_code == 204:
        return {}
    body = resp.content or b''
    if not body.strip():
        return {}
    return resp.json()

class AsyncOData1C:

    def __init__(
        self,
        base_url: str = ODATA_BASE_URL,
        login: str = ODATA_LOGIN,
        password: str = ODATA_PASSWORD,
        timeout: int = ODATA_TIMEOUT,
        max_retries: int = ODATA_MAX_RETRIES,
        concurrency: int = ODATA_CONCURRENCY,
    ):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries
        creds = f'{login}:{password}'.encode('utf-8')
        auth = base64.b64encode(creds).decode()
        self._headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': f'Basic {auth}',
        }
        self._client: httpx.AsyncClient | None = None
        self._sem = asyncio.Semaphore(concurrency)

    async def __aenter__(self) -> 'AsyncOData1C':
        self._client = httpx.AsyncClient(
            timeout=self.timeout,
            headers=self._headers,
        )
        return self

    async def __aexit__(self, *exc) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

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

    async def get(
        self,
        endpoint: str,
        params: dict | None = None,
    ) -> dict:
        assert self._client is not None, (
            'Использовать через async with'
        )
        url = self._build_url(endpoint, params)
        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                async with self._sem:
                    resp = await self._client.get(url)
                if resp.status_code == 401:
                    detail = _extract_odata_error(resp)
                    raise PermissionError(
                        'Ошибка авторизации в 1С'
                        + (f': {detail}' if detail else ''),
                    )
                if resp.status_code == 403:
                    detail = _extract_odata_error(resp)
                    raise PermissionError(
                        'Доступ запрещён'
                        + (f': {detail}' if detail else ''),
                    )
                if resp.status_code == 404:
                    raise LookupError(
                        f'Не найдено: {endpoint}',
                    )
                if 400 <= resp.status_code < 500:
                    detail = _extract_odata_error(resp) or (
                        f'HTTP {resp.status_code}'
                    )
                    raise ValueError(
                        f'{endpoint}: {detail}'
                    )
                resp.raise_for_status()
                try:
                    return _parse_json_body(resp)
                except (ValueError, json.JSONDecodeError) as exc:
                    snippet = (resp.text or '')[:300]
                    raise ValueError(
                        f'Не JSON от 1С на {endpoint} '
                        f'({exc}): {snippet!r}'
                    )
            except (PermissionError, LookupError, ValueError):
                raise
            except (
                httpx.ConnectError,
                httpx.ReadTimeout,
                httpx.HTTPStatusError,
            ) as exc:
                last_exc = exc
                if attempt >= self.max_retries:
                    break
                wait = 2 ** attempt
                logger.warning(
                    'Ошибка запроса %s (%s), '
                    'повтор через %d сек',
                    endpoint, exc, wait,
                )
                await asyncio.sleep(wait)
        raise ConnectionError(
            f'Не удалось выполнить запрос {endpoint}: '
            f'{last_exc}'
        )

    async def gather(self, coros) -> list[Any]:
        return await asyncio.gather(*coros)
