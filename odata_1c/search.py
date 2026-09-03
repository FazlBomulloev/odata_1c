import logging

from .client import OData1C
from .exceptions import ArticleNotFoundError

logger = logging.getLogger(__name__)


def _esc(value: str) -> str:
    """Экранирует одинарную кавычку для OData $filter."""
    return value.replace("'", "''")


def search_by_article(
    client: OData1C,
    prefix: str,
) -> list[str]:
    """Возвращает все артикулы номенклатуры по префиксу."""
    params = {
        '$filter': (
            f"startswith(Артикул, '{_esc(prefix)}')"
        ),
        '$select': 'Артикул',
        '$format': 'json',
    }
    result = client.get('Catalog_Номенклатура', params)
    articles = [
        item['Артикул']
        for item in result.get('value', [])
        if item.get('Артикул')
    ]
    logger.info(
        'Найдено %d артикулов по префиксу "%s"',
        len(articles), prefix,
    )
    return sorted(articles)


def find_free_article(
    client: OData1C,
    prefix: str,
) -> str:
    """Находит следующий свободный артикул с этим префиксом."""
    articles = search_by_article(client, prefix)
    if not articles:
        return f'{prefix}01'

    suffixes = []
    for art in articles:
        suffix = art[len(prefix):]
        if suffix.isdigit():
            suffixes.append(int(suffix))

    if not suffixes:
        return f'{prefix}01'

    next_num = max(suffixes) + 1
    suffix_len = max(2, len(articles[0]) - len(prefix))
    return f'{prefix}{next_num:0{suffix_len}d}'


def article_exists(
    client: OData1C,
    article: str,
) -> bool:
    """Проверяет, занят ли артикул."""
    params = {
        '$filter': f"Артикул eq '{_esc(article)}'",
        '$select': 'Ref_Key',
        '$format': 'json',
    }
    result = client.get('Catalog_Номенклатура', params)
    return len(result.get('value', [])) > 0


def get_nomenclature_by_article(
    client: OData1C,
    article: str,
) -> dict:
    """Возвращает номенклатуру по артикулу."""
    params = {
        '$filter': f"Артикул eq '{_esc(article)}'",
        '$format': 'json',
    }
    result = client.get('Catalog_Номенклатура', params)
    items = result.get('value', [])
    if not items:
        raise ArticleNotFoundError(
            f'Артикул "{article}" не найден в 1С'
        )
    return items[0]
