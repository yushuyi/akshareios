"""
东方财富-行业板块列表

数据源：东方财富 push2 clist API
原版参考：akshare/stock/stock_board_industry_em.py → stock_board_industry_name_em()
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
    "f8": "换手率",
    "f12": "板块代码",
    "f14": "板块名称",
    "f20": "总市值",
    "f104": "上涨家数",
    "f105": "下跌家数",
    "f128": "领涨股票",
    "f136": "领涨股票-涨跌幅",
}


def stock_board_industry_name_em(
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    timeout: float = 20,
) -> dict:
    """
    东方财富-沪深行业板块列表（分页）

    :param page: 页码，从 1 开始
    :param page_size: 每页条数，默认 20，最大 100
    :return: 分页 dict，items 含板块名称、涨跌幅、领涨股等
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
        "fid": "f3",
        "fs": "m:90 t:2 f:!50",
        "fields": ",".join(_FIELD_MAP.keys()),
    }
    data_json = get_push2_clist(params, timeout=timeout)
    data_body = data_json.get("data", {})
    diff = data_body.get("diff", [])
    total = int(data_body.get("total", 0) or 0)

    items = []
    base_rank = (page - 1) * page_size
    for idx, item in enumerate(diff):
        record = {"排名": base_rank + idx + 1}
        for field_key, field_name in _FIELD_MAP.items():
            val = item.get(field_key)
            if val == "-":
                val = None
            record[field_name] = val
        items.append(record)

    return make_page_result(items, page=page, page_size=page_size, total=total)
