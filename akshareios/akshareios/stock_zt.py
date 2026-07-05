"""
涨停板行情 - 涨停股池

数据源：东方财富 push2ex API
原版参考：akshare/stock_feature/stock_ztb_em.py → stock_zt_pool_em()
"""

from datetime import datetime

from akshareios._convert import to_float, to_int
from akshareios._http import get
from akshareios._pagination import (
    DEFAULT_PAGE_SIZE,
    clamp_page,
    clamp_page_size,
    make_page_result,
)


def stock_zt_pool_em(
    date: str | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    timeout: float = 15,
) -> dict:
    """
    东方财富-涨停股池（分页）

    :param date: 交易日 YYYYMMDD，默认当天
    :param page: 页码，从 1 开始
    :param page_size: 每页条数，默认 20，最大 100
    :return: 分页 dict；非交易日或收盘前可能为空列表
    """
    page = clamp_page(page)
    page_size = clamp_page_size(page_size)
    trade_date = date or datetime.now().strftime("%Y%m%d")

    url = "https://push2ex.eastmoney.com/getTopicZTPool"
    params = {
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
        "dpt": "wz.ztzt",
        "Pageindex": str(page - 1),
        "pagesize": str(page_size),
        "sort": "fbt:asc",
        "date": trade_date,
    }
    r = get(url, params=params, timeout=timeout)
    r.raise_for_status()
    data = r.json().get("data")
    if not data:
        return make_page_result([], page=page, page_size=page_size, total=0)

    pool = data.get("pool") or []
    total = int(data.get("tc") or len(pool))

    items = []
    base_rank = (page - 1) * page_size
    for idx, row in enumerate(pool):
        items.append(_parse_zt_row(row, rank=base_rank + idx + 1))

    return make_page_result(items, page=page, page_size=page_size, total=total)


def _parse_zt_row(row: dict, *, rank: int) -> dict:
    zttj = row.get("zttj") or {}
    if isinstance(zttj, dict):
        zttj_str = f"{zttj.get('days', '')}/{zttj.get('ct', '')}"
    else:
        zttj_str = str(zttj)

    price = row.get("p")
    latest = to_float(price) / 1000 if price is not None else None

    fbt = str(row.get("fbt") or "").zfill(6)
    lbt = str(row.get("lbt") or "").zfill(6)

    return {
        "序号": rank,
        "代码": row.get("c"),
        "名称": row.get("n"),
        "最新价": latest,
        "涨跌幅": to_float(row.get("zdp")),
        "成交额": to_float(row.get("amount")),
        "流通市值": to_float(row.get("ltsz")),
        "总市值": to_float(row.get("tshare")),
        "换手率": to_float(row.get("hs")),
        "连板数": to_int(row.get("lbc")),
        "首次封板时间": fbt,
        "最后封板时间": lbt,
        "封板资金": to_float(row.get("fund")),
        "炸板次数": to_int(row.get("zbc")),
        "所属行业": row.get("hybk"),
        "涨停统计": zttj_str,
    }
