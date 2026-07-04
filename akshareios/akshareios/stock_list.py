"""
沪深京 A 股代码名称列表

数据源：东方财富 push2 API
原版参考：akshare/stock_feature/stock_hist_em.py → stock_zh_a_spot_em() 的股票列表部分
"""

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
    """
    获取沪深京 A 股代码和名称列表（分页）。

    :param page: 页码，从 1 开始
    :param page_size: 每页条数，默认 20，最大 100
    :param timeout: 请求超时时间（秒）
    :return: {"items": [{"code": "000001", "name": "平安银行"}, ...], "page": 1, ...}
    """
    page = clamp_page(page)
    page_size = clamp_page_size(page_size)

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
    total = int(data_body.get("total", 0) or 0)

    items = []
    for item in diff:
        if "f12" in item:
            items.append({"code": item["f12"], "name": item["f14"]})

    return make_page_result(items, page=page, page_size=page_size, total=total)
