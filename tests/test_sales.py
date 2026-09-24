from datetime import datetime

import pytest

from odata_1c.exceptions import ODataNotFoundError
from odata_1c.movements import (
    CHARACTERISTICS,
    EMPTY_GUID,
    NOMENCLATURE,
    ORGS_CATALOG,
    WAREHOUSES_CATALOG,
)
from odata_1c.sales import (
    CHANNEL_UNKNOWN,
    CONTRACTS,
    DOC_COMMISSION,
    DOC_COMMISSION_RETURNS,
    DOC_COMMISSION_SALES,
    SALES_REG,
    TYPE_RETURN,
    TYPE_SALE,
    _resolve_channel,
    dims_by_recorder,
    get_marketplace_sales,
)


@pytest.mark.parametrize(
    ('description', 'expected'),
    [
        ('Договор WB 2024', 'WB'),
        ('РВБ комиссия', 'WB'),
        ('Вайлдберриз', 'WB'),
        ('ООО Интернет Решения (OZON)', 'Ozon'),
        ('Купишуз / Lamoda', 'Lamoda'),
        ('Прочий договор', CHANNEL_UNKNOWN),
        ('', CHANNEL_UNKNOWN),
    ],
)
def test_resolve_channel(description, expected):
    assert _resolve_channel(description) == expected


def test_dims_by_recorder_takes_first_non_empty():
    rows = [
        {
            'Recorder': 'd1',
            'Склад_Key': EMPTY_GUID,
            'Организация_Key': 'o1',
        },
        {'Recorder': 'd1', 'Склад_Key': 'w1', 'Организация_Key': 'o2'},
        {'Recorder': 'd1', 'Склад_Key': 'w2', 'Организация_Key': ''},
        {'Recorder': '', 'Склад_Key': 'w3', 'Организация_Key': 'o3'},
    ]
    assert dims_by_recorder(rows) == {'d1': ('w1', 'o1')}


class FakeClient:

    def __init__(self, data: dict):
        self.data = data
        self.calls: list[str] = []

    def get(self, endpoint, params=None):
        self.calls.append(endpoint)
        if endpoint not in self.data:
            raise ODataNotFoundError(endpoint)
        return {'value': self.data[endpoint]}


def _marketplace_data():
    return {
        DOC_COMMISSION: [
            {
                'Ref_Key': 'd1',
                'Date': '2025-08-10T12:00:00',
                'Договор_Key': 'c1',
                'Организация_Key': EMPTY_GUID,
            },
        ],
        CONTRACTS: [{'Ref_Key': 'c1', 'Description': 'WB договор'}],
        DOC_COMMISSION_SALES: [
            {
                'Ref_Key': 'd1',
                'Номенклатура_Key': 'n1',
                'Характеристика_Key': 'ch1',
                'Количество': 2,
                'Сумма': 1000,
            },
        ],
        DOC_COMMISSION_RETURNS: [
            {
                'Ref_Key': 'd1',
                'Номенклатура_Key': 'n1',
                'Характеристика_Key': 'ch1',
                'Количество': 1,
                'Сумма': 500,
            },
        ],
        NOMENCLATURE: [
            {'Ref_Key': 'n1', 'Description': 'Футболка',
             'Артикул': 'A100'},
        ],
        CHARACTERISTICS: [
            {'Ref_Key': 'ch1', 'Description': 'A100-M, 46'},
        ],
        SALES_REG: [
            {
                'Recorder': 'd1',
                'Склад_Key': 'w1',
                'Организация_Key': 'o1',
            },
        ],
        WAREHOUSES_CATALOG: [
            {'Ref_Key': 'w1', 'Description': 'Склад WB'},
        ],
        ORGS_CATALOG: [
            {'Ref_Key': 'o1', 'Description': 'ИП Иванов'},
        ],
    }


def test_marketplace_sales_dims_from_sales_register():
    client = FakeClient(_marketplace_data())
    records = get_marketplace_sales(
        client, datetime(2025, 8, 1), datetime(2025, 8, 31),
    )
    assert SALES_REG in client.calls
    assert len(records) == 2

    sale, ret = records
    assert sale.type == TYPE_SALE
    assert sale.channel == 'WB'
    assert sale.article == 'A100'
    assert sale.size == 'M, 46'
    assert sale.quantity == 2
    assert sale.amount == 1000
    assert sale.warehouse == 'Склад WB'
    assert sale.organization == 'ИП Иванов'

    assert ret.type == TYPE_RETURN
    assert ret.quantity == -1
    assert ret.amount == -500


def test_marketplace_sales_channel_filter():
    client = FakeClient(_marketplace_data())
    records = get_marketplace_sales(
        client, datetime(2025, 8, 1), datetime(2025, 8, 31),
        channel='Ozon',
    )
    assert records == []
