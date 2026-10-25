"""通用分页处理。

封装 Django Paginator，输出对模板友好的分页结果（含页码窗口）。
视图侧可直接把 PageResult 传入模板，配合 templates/includes/pagination.html 使用。
"""

from dataclasses import dataclass, field
from typing import Any

from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http import HttpRequest

from .constants import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    PAGE_QUERY_PARAM,
    PAGE_SIZE_QUERY_PARAM,
)


@dataclass
class PageResult:
    """分页结果，供模板与视图复用。"""

    items: list
    total: int
    page: int
    page_size: int
    total_pages: int
    page_range: list[int] = field(default_factory=list)

    @property
    def has_previous(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def previous_page(self) -> int:
        return max(1, self.page - 1)

    @property
    def next_page(self) -> int:
        return min(self.total_pages, self.page + 1)


def compute_page_range(current: int, total_pages: int, window: int = 2) -> list[int]:
    """计算以当前页为中心、半径为 window 的页码窗口（始终包含首页与末页）。"""
    if total_pages <= 0:
        return []
    start = max(1, current - window)
    end = min(total_pages, current + window)
    pages = set(range(start, end + 1))
    pages.update({1, total_pages})
    return sorted(pages)


def paginate(
    queryset: Any,
    page: Any = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    window: int = 2,
) -> PageResult:
    """对 queryset / 列表分页。page 非法时回退到首页或末页，永不抛异常。"""
    try:
        page_size = int(page_size)
    except (TypeError, ValueError):
        page_size = DEFAULT_PAGE_SIZE
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))

    paginator = Paginator(queryset, page_size)
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    current = page_obj.number
    total_pages = paginator.num_pages
    return PageResult(
        items=list(page_obj.object_list),
        total=paginator.count,
        page=current,
        page_size=page_size,
        total_pages=total_pages,
        page_range=compute_page_range(current, total_pages, window),
    )


def paginate_from_request(queryset: Any, request: HttpRequest, window: int = 2) -> PageResult:
    """从请求查询参数（page / page_size）中提取并分页。"""
    page = request.GET.get(PAGE_QUERY_PARAM, 1)
    page_size = request.GET.get(PAGE_SIZE_QUERY_PARAM, DEFAULT_PAGE_SIZE)
    return paginate(queryset, page=page, page_size=page_size, window=window)
