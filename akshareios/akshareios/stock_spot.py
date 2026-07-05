"""
沪深京 A 股实时行情快照

主数据源：东方财富 push2 clist；失败时降级腾讯涨幅榜。
"""

from akshareios._fallback import call_with_fallback
from akshareios._fallback_tx import tx_spot_page
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

_SORT_FIELDS = frozenset({"f3", "f12", "f14", "f6", "f20"})


def stock_zh_a_spot_em(
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    sort_by: str = "f3",
    timeout: float = 20,
) -> dict:
    """实时行情分页；东财 clist 失败时降级腾讯排行榜。"""
    page = clamp_page(page)
    page_size = clamp_page_size(page_size)

    return call_with_fallback(
        lambda: _spot_em(page=page, page_size=page_size, sort_by=sort_by, timeout=timeout),
        lambda: tx_spot_page(page=page, page_size=page_size, timeout=timeout),
    )


def _spot_em(
    *,
    page: int,
    page_size: int,
    sort_by: str,
    timeout: float,
) -> dict:
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
    if not diff:
        return make_page_result([], page=page, page_size=page_size, total=0)

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
