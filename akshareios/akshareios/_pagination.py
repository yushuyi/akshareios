"""
分页工具 —— 限制单次拉取条数，避免 Agent 终端输出爆炸。
"""

MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 20


def clamp_page(page: int) -> int:
    return max(1, page)


def clamp_page_size(page_size: int) -> int:
    return max(1, min(page_size, MAX_PAGE_SIZE))


def make_page_result(
    items: list,
    *,
    page: int,
    page_size: int,
    total: int,
) -> dict:
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
        "has_more": page < total_pages,
    }
