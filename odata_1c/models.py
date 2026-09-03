from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class MovementRecord:
    """Одна нормализованная запись товародвижения."""
    period: datetime | None
    name: str
    article: str
    barcode: str
    size: str
    size_global: str
    size_ru: str
    quantity: float
    operation_type: str
    warehouse_from: str
    warehouse_to: str
    organization_from: str
    organization_to: str
    document_kind: str
    document_number: str
    document_date: datetime | None
    recorder: str


@dataclass
class StockRecord:
    """Текущий остаток товара по складу."""
    name: str
    article: str
    barcode: str
    size: str
    size_global: str
    size_ru: str
    warehouse: str
    organization: str
    quantity: float


@dataclass
class TurnoverRecord:
    """Одна строка регистра Продажи/Turnovers за период.

    Гранулярность — (номенклатура, характеристика, склад,
    организация, контрагент, месяц). Все суммы — с НДС в
    основных полях; поля *_no_vat — без НДС.
    """
    article: str
    name: str
    size: str
    nomenclature_key: str
    characteristic_key: str
    warehouse: str
    warehouse_ref: str
    organization: str
    organization_ref: str
    contractor: str
    contractor_ref: str
    month: datetime
    quantity: float
    revenue: float
    revenue_no_vat: float
    cost: float
    cost_no_vat: float


@dataclass
class SaleRecord:
    """Одна строка продажи (или возврата) по каналу."""
    nomenclature_key: str
    characteristic_key: str | None
    article: str | None
    size: str | None
    channel: str
    quantity: float
    amount: float
    date: datetime | None
    type: str
    warehouse: str | None = None
    organization: str | None = None


@dataclass
class SizeData:
    """Один размер: глобальный, российский, штрихкод."""
    global_size: str
    ru_size: str
    barcode: str


@dataclass
class ProductData:
    """Товар для создания/обновления в 1С."""
    article: str
    name: str
    description: str
    price: float
    category: str
    color: str
    group: str = ''
    sizes: list[SizeData] = field(default_factory=list)
    photos: list[str] = field(default_factory=list)

    @classmethod
    def from_json(cls, data: dict) -> 'ProductData':
        """Создаёт ProductData из dict сервиса."""
        sizes = [
            SizeData(
                global_size=s['global'],
                ru_size=s['ru'],
                barcode=s['barcode'],
            )
            for s in data.get('sizes', [])
        ]
        return cls(
            article=data['article'],
            name=data['name'],
            description=data.get('description', ''),
            price=float(data['price']),
            category=data.get('category', ''),
            color=data.get('color', ''),
            group=data.get('group', ''),
            sizes=sizes,
            photos=data.get('photos', []),
        )
