"""
沪深京 A 股代码名称列表

主数据源：东方财富 push2 clist；失败时降级新浪分页列表。
"""

from akshareios._fallback import call_with_fallback
from akshareios._fallback_sina import sina_code_name_page
from akshareios._http import get_push2_clist
from akshareios._pagination import (
    DEFAULT_PAGE_SIZE,
    clamp_page,
    clamp_page_size,
    make_page_result,
)


def stock_info_a_code_name(
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    timeout: float = 15,
) -> dict:
    """股票代码名称分页；东财失败时降级新浪。"""
    page = clamp_page(page)
    page_size = clamp_page_size(page_size)

    return call_with_fallback(
        lambda: _list_em(page=page, page_size=page_size, timeout=timeout),
        lambda: sina_code_name_page(page=page, page_size=page_size, timeout=timeout),
    )


def _list_em(
    *,
    page: int,
    page_size: int,
    timeout: float,
) -> dict:
    params = {
        "pn": str(page),
        "pz": str(page_size),
        "po": "1",
        "np": "1",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2",
        "invt": "2",
        "fid": "f12",
        "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048",
        "fields": "f12,f14",
    }
    data = get_push2_clist(params, timeout=timeout)
    data_body = data.get("data", {})
    diff = data_body.get("diff", [])
    if not diff:
        return make_page_result([], page=page, page_size=page_size, total=0)

    total = int(data_body.get("total", 0) or 0)
    items = []
    for item in diff:
        if "f12" in item:
            items.append({"code": item["f12"], "name": item["f14"]})

    return make_page_result(items, page=page, page_size=page_size, total=total)
