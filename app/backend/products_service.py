import asyncio
import logging

from odata_1c import (
    OData1C,
    ProductData,
    SizeData,
    article_exists,
    create_product,
    delete_product,
    find_free_article,
    get_all_products,
    get_photo_bytes,
    get_product,
    search_by_article,
    update_product,
)

logger = logging.getLogger(__name__)


def _build_client() -> OData1C:
    return OData1C()


def _create_sync(data: dict) -> dict:
    client = _build_client()
    sizes = [
        SizeData(
            global_size=s['global_size'],
            ru_size=s['ru_size'],
            barcode=s['barcode'],
        )
        for s in data.get('sizes', [])
    ]
    product = ProductData(
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
    return create_product(client, product)


async def list_products_async(
    prefix: str,
    limit: int,
    offset: int,
    only_active: bool,
    include_service: bool = False,
) -> list[dict]:
    def _work() -> list[dict]:
        client = _build_client()
        return get_all_products(
            client,
            limit=limit,
            offset=offset,
            only_active=only_active,
            prefix=prefix,
            include_service=include_service,
        )
    return await asyncio.to_thread(_work)


async def next_article_async(prefix: str) -> str:
    def _work() -> str:
        client = _build_client()
        return find_free_article(client, prefix)
    return await asyncio.to_thread(_work)


async def article_exists_async(article: str) -> bool:
    def _work() -> bool:
        client = _build_client()
        return article_exists(client, article)
    return await asyncio.to_thread(_work)


async def search_articles_async(prefix: str) -> list[str]:
    def _work() -> list[str]:
        client = _build_client()
        return search_by_article(client, prefix)
    return await asyncio.to_thread(_work)


async def get_product_async(article: str) -> dict:
    def _work() -> dict:
        client = _build_client()
        return get_product(client, article)
    return await asyncio.to_thread(_work)


async def create_product_async(data: dict) -> dict:
    return await asyncio.to_thread(_create_sync, data)


async def update_product_async(
    article: str, data: dict,
) -> dict:
    def _work() -> dict:
        client = _build_client()
        return update_product(client, article, data)
    return await asyncio.to_thread(_work)


async def delete_product_async(article: str) -> bool:
    def _work() -> bool:
        client = _build_client()
        return delete_product(client, article)
    return await asyncio.to_thread(_work)


async def photo_bytes_async(
    file_key: str,
) -> tuple[bytes, str]:
    def _work() -> tuple[bytes, str]:
        client = _build_client()
        return get_photo_bytes(client, file_key)
    return await asyncio.to_thread(_work)
