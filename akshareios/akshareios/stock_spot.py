"""
沪深京 A 股实时行情快照

数据源：东方财富 push2 API
原版参考：akshare/stock_feature/stock_hist_em.py → stock_zh_a_spot_em()
"""

from akshareios._http import get_push2_clist
from akshareios._pagination import (
    DEFAULT_PAGE_SIZE,
    clamp_page,
    clamp_page_size,
    make_page_result,
)

_FIELD_MAP = {
    "f2": "最新价",
    "f3": "涨跌幅",
    "f4": "涨跌额",
    "f5": "成交量",
    "f6": "成交额",
    "f7": "振幅",
    "f8": "换手率",
    "f9": "市盈率-动态",
    "f10": "量比",
    "f12": "代码",
    "f14": "名称",
    "f15": "最高",
    "f16": "最低",
    "f17": "今开",
    "f18": "昨收",
    "f20": "总市值",
    "f21": "流通市值",
    "f23": "市净率",
}

# 常用排序字段：f3=涨跌幅, f12=代码, f14=名称, f6=成交额
_SORT_FIELDS = frozenset({"f3", "f12", "f14", "f6", "f20"})


def stock_zh_a_spot_em(
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    sort_by: str = "f3",
    timeout: float = 20,
) -> dict:
    """
    东方财富网-沪深京 A 股-实时行情（分页快照）

    :param page: 页码，从 1 开始
    :param page_size: 每页条数，默认 20，最大 100
    :param sort_by: 排序字段，常用 f3（涨跌幅）、f12（代码）、f6（成交额）
    :param timeout: 请求超时时间（秒）
    :return: {"items": [...], "page": 1, "page_size": 20, "total": 5123, "total_pages": 257, "has_more": true}
    """
    page = clamp_page(page)
    page_size = clamp_page_size(page_size)
    fid = sort_by if sort_by in _SORT_FIELDS else "f3"

    params = {
        "pn": str(page),
        "pz": str(page_size),
        "po": "1",
        "np": "1",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2",
        "invt": "2",
        "fid": fid,
        "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048",
        "fields": ",".join(_FIELD_MAP.keys()),
    }
    data_json = get_push2_clist(params, timeout=timeout)
    data_body = data_json.get("data", {})
    diff = data_body.get("diff", [])
    total = int(data_body.get("total", 0) or 0)

    items = []
    for item in diff:
        record = {}
        for field_key, field_name in _FIELD_MAP.items():
            val = item.get(field_key)
            if val == "-":
                val = None
            record[field_name] = val
        items.append(record)

    return make_page_result(items, page=page, page_size=page_size, total=total)
