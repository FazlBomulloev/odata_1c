import asyncio
import base64
import logging
from typing import Any
from urllib.parse import quote

import httpx

# safe-набор для OData: буквы/цифры/`_` кодировать не надо,
# кавычки/скобки/двоеточие/запятая/знак равно/косая — валидны в
# query по RFC 3986 sub-delims. Пробелы и кириллица уйдут в %HH.
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


class AsyncOData1C:
    """Асинхронный HTTP-клиент к OData 1С c семафором и retry."""

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
        # endpoint содержит кириллицу (`Catalog_Номенклатура`
        # и т.п.), значения $filter — пробелы и кавычки.
        # Без URL-энкодинга 1С отвечает 400/500, а FastAPI —
        # ловит это как 502.
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
                    raise PermissionError(
                        'Ошибка авторизации в 1С',
                    )
                if resp.status_code == 403:
                    raise PermissionError('Доступ запрещён')
                if resp.status_code == 404:
                    raise LookupError(
                        f'Не найдено: {endpoint}',
                    )
                resp.raise_for_status()
                return resp.json()
            except (PermissionError, LookupError):
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
        """asyncio.gather с общим семафором клиента."""
        return await asyncio.gather(*coros)
