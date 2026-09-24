import asyncio
from dataclasses import asdict
from datetime import datetime

from app.backend.services import fetch_marketplace_sales
from odata_1c.sales import get_marketplace_sales

from .test_sales import FakeClient, _marketplace_data


class FakeAsyncClient:

    def __init__(self, data: dict):
        self.data = data

    async def get(self, endpoint, params=None):
        if endpoint not in self.data:
            raise LookupError(endpoint)
        return {'value': self.data[endpoint]}


def test_marketplace_sales_package_matches_backend():
    date_from = datetime(2025, 8, 1)
    date_to = datetime(2025, 8, 31)
    data = _marketplace_data()

    sync_records = [
        asdict(r)
        for r in get_marketplace_sales(
            FakeClient(data), date_from, date_to,
        )
    ]
    async_records = asyncio.run(
        fetch_marketplace_sales(
            FakeAsyncClient(data), date_from, date_to,
        ),
    )
    assert sync_records == async_records
