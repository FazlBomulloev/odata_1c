from datetime import datetime

from pydantic import BaseModel, Field


class DateRange(BaseModel):
    date_from: datetime
    date_to: datetime


class MarketplaceSalesRequest(DateRange):
    channel: str | None = Field(default=None)


class RetailSalesRequest(DateRange):
    pass


class AllSalesRequest(DateRange):
    pass


class MovementsRequest(DateRange):
    kind: str = 'all'
    organization: str = ''
    warehouse: str = ''


class GrossProfitRequest(DateRange):
    article: str | None = None
    warehouse: str = ''
    organization: str = ''
    contractor: str = ''
    # Гранулярность по умолчанию — по размеру. Поддерживаемые ключи:
    # article, size, warehouse, organization, contractor, month.
    group_by: list[str] = Field(
        default_factory=lambda: ['article', 'size'],
    )


class StockRequest(BaseModel):
    warehouse: str = ''
    organization: str = ''
    nomenclature: str = ''
    only_positive: bool = True


class StockByArticleRequest(BaseModel):
    article: str


class RunSummary(BaseModel):
    id: int
    method: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    duration_ms: int | None
    record_count: int | None
    error: str | None
    params: dict


class RunDetail(RunSummary):
    payload: list | None
