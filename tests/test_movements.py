from datetime import datetime

import pytest

from odata_1c.movements import (
    _iso_to,
    _pair_transfers,
    _parse_dt,
    _parse_size,
)


@pytest.mark.parametrize(
    ('description', 'article', 'expected'),
    [
        ('A100-2XL, 54', 'A100', ('2XL', '54', '2XL, 54')),
        ('M, 46', '', ('M', '46', 'M, 46')),
        ('B200-M, 46', 'A100', ('B200-M', '46', 'B200-M, 46')),
        ('Единый', 'A100', ('', '', 'Единый')),
        ('', 'A100', ('', '', '')),
    ],
)
def test_parse_size(description, article, expected):
    assert _parse_size(description, article) == expected


@pytest.mark.parametrize(
    ('value', 'expected'),
    [
        (datetime(2025, 8, 31), '2025-08-31T23:59:59'),
        (
            datetime(2025, 8, 31, 12, 30, 5),
            '2025-08-31T12:30:05',
        ),
        ('2025-08-31', '2025-08-31T23:59:59'),
        ('2025-08-31T00:00:00', '2025-08-31T23:59:59'),
        ('2025-08-31T10:00:00', '2025-08-31T10:00:00'),
    ],
)
def test_iso_to_extends_day(value, expected):
    assert _iso_to(value) == expected


def test_parse_dt():
    assert _parse_dt('2025-08-01T10:20:30.123') == datetime(
        2025, 8, 1, 10, 20, 30,
    )
    assert _parse_dt('') is None
    assert _parse_dt('мусор') is None


def _row(rec, rtype, nom, qty, char='c1'):
    return {
        'Recorder': rec,
        'RecordType': rtype,
        'Номенклатура_Key': nom,
        'Характеристика_Key': char,
        'Количество': qty,
    }


def test_pair_transfers_matches_by_nom_char_qty():
    exp = _row('r1', 'Expense', 'n1', 2)
    rec = _row('r1', 'Receipt', 'n1', 2)
    pairs, orphans = _pair_transfers([exp, rec])
    assert pairs == [(exp, rec)]
    assert orphans == []


def test_pair_transfers_does_not_reuse_receipt():
    e1 = _row('r1', 'Expense', 'n1', 1)
    e2 = _row('r1', 'Expense', 'n1', 1)
    r1 = _row('r1', 'Receipt', 'n1', 1)
    pairs, orphans = _pair_transfers([e1, e2, r1])
    assert pairs == [(e1, r1)]
    assert orphans == [e2]


def test_pair_transfers_one_side_only_is_orphan():
    exp = _row('r1', 'Expense', 'n1', 3)
    other = _row('r2', 'Receipt', 'n1', 3)
    pairs, orphans = _pair_transfers([exp, other])
    assert pairs == []
    assert orphans == [exp, other]


def test_pair_transfers_qty_mismatch_is_orphan():
    exp = _row('r1', 'Expense', 'n1', 3)
    rec = _row('r1', 'Receipt', 'n1', 2)
    pairs, orphans = _pair_transfers([exp, rec])
    assert pairs == []
    assert orphans == [exp, rec]
