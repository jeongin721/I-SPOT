# 성공 응답 Contract 구현.
# docs/02_ARCHITECTURE.md: 성공 응답은 항상 {"data": {}} 형태를 유지한다.

from typing import Generic, List, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class DataResponse(BaseModel, Generic[T]):
    """모든 성공 응답의 공통 Envelope."""

    data: T


class PageMeta(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int


class PagedItems(BaseModel, Generic[T]):
    """목록 응답 본문. data.items / data.meta 구조를 유지한다."""

    items: List[T]
    meta: PageMeta


def paged(items: List[T], total: int, page: int, page_size: int) -> PagedItems[T]:
    total_pages = (total + page_size - 1) // page_size if page_size else 0

    return PagedItems[T](
        items=items,
        meta=PageMeta(
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        ),
    )
