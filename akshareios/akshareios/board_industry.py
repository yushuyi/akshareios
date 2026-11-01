"""
东方财富-行业板块列表与成分股

数据源：东方财富 push2 clist API；板块列表不可用时降级新浪行业板块
原版参考：akshare/stock/stock_board_industry_em.py
→ stock_board_industry_name_em() / stock_board_industry_cons_em()
"""

import re

import requests

from akshareios._fallback import call_with_fallback
from akshareios._fallback_sina import sina_board_industry_page
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

    东财 push2 不可用时自动降级新浪行业板块；降级结果带「数据源: 新浪行业」，
    板块代码为新浪体系（new_xxx），不可用于东财成分股接口。

    :param page: 页码，从 1 开始
    :param page_size: 每页条数，默认 20，最大 100
    :return: 分页 dict，items 含板块名称、涨跌幅、领涨股等
    """
    # 先 clamp 再进降级链：page_size=0 会让降级源的分页运算 ZeroDivisionError
    page = clamp_page(page)
    page_size = clamp_page_size(page_size)
    return call_with_fallback(
        lambda: _industry_em(page, page_size, timeout=timeout),
        lambda: sina_board_industry_page(page, page_size, timeout=timeout),
        retry_on_empty=True,
    )


def _industry_em(page: int, page_size: int, *, timeout: float) -> dict:
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


_CONS_FIELD_MAP = {
    "f12": "代码",
    "f14": "名称",
    "f2": "最新价",
    "f3": "涨跌幅",
    "f4": "涨跌额",
    "f5": "成交量",
    "f6": "成交额",
    "f8": "换手率",
    "f9": "市盈率-动态",
    "f10": "量比",
    "f15": "最高",
    "f16": "最低",
    "f17": "今开",
    "f18": "昨收",
    "f20": "总市值",
    "f21": "流通市值",
}


def stock_board_industry_cons_em(
    symbol: str,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    timeout: float = 20,
) -> dict:
    """
    东方财富-行业板块成分股（分页）

    「板块有多少只成分股」看返回的 total 即可，无需翻页。
    仅东财主源、无降级：东财 push2 不可用时报错请稍后重试；
    板块列表的新浪降级源（new_xxx 代码）与本接口不兼容。

    :param symbol: 板块代码（如 BK0737）或板块名称（如 软件开发）
    :param page: 页码，从 1 开始
    :param page_size: 每页条数，默认 20，最大 100
    :return: 分页 dict，items 含代码、名称、最新价、涨跌幅等；total = 成分股总数
    """
    if not symbol or not symbol.strip():
        raise ValueError("symbol 不能为空：传板块代码（BK0737）或板块名称（软件开发）")
    symbol = symbol.strip()
    page = clamp_page(page)
    page_size = clamp_page_size(page_size)

    board_code = _resolve_board_code(symbol, timeout=timeout)

    params = {
        "pn": str(page),
        "pz": str(page_size),
        "po": "1",
        "np": "1",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2",
        "invt": "2",
        "fid": "f3",
        "fs": f"b:{board_code} f:!50",
        "fields": ",".join(_CONS_FIELD_MAP.keys()),
    }
    try:
        data_json = get_push2_clist(params, timeout=timeout)
    except requests.ConnectionError as exc:
        # 网络 outage 与「BK 代码传错」（data 为空）在 get_push2_clist 里不可区分，
        # 报错里同时给出两条出路，避免传错代码被引导无效重试
        raise ValueError(
            f"成分股查询失败（东财 push2 不可用或 BK 代码无效）：{exc}；"
            "可先用 stock_board_industry_name_em 确认板块代码，或稍后重试"
        ) from exc
    data_body = data_json.get("data", {})
    diff = data_body.get("diff", [])
    total = int(data_body.get("total", 0) or 0)

    items = []
    base_rank = (page - 1) * page_size
    for idx, item in enumerate(diff):
        record = {"排名": base_rank + idx + 1}
        for field_key, field_name in _CONS_FIELD_MAP.items():
            val = item.get(field_key)
            if val == "-":
                val = None
            record[field_name] = val
        items.append(record)

    return make_page_result(items, page=page, page_size=page_size, total=total)


def _resolve_board_code(symbol: str, *, timeout: float) -> str:
    """板块代码直接返回；板块名称翻板块列表精确匹配（列表最多 ~500 条，5 页内）"""
    if re.fullmatch(r"BK\d+", symbol, re.IGNORECASE):
        return symbol.upper()

    page = 1
    while True:
        result = stock_board_industry_name_em(page=page, page_size=100, timeout=timeout)
        items = result.get("items", [])
        # 新浪降级源的板块体系与东财成分股不兼容，立刻明示，避免误报「未找到板块」
        if any("数据源" in item for item in items):
            raise ValueError(
                "东财 push2 暂不可用（板块列表已降级新浪），无法按名称解析板块："
                "请直接传东财 BK 代码，或稍后重试"
            )
        if not items and page == 1:
            raise ValueError("东财与新浪板块列表均暂不可用，无法解析板块，请稍后重试")
        for item in items:
            if item.get("板块名称") == symbol:
                return str(item.get("板块代码") or "")
        if not result.get("has_more"):
            break
        page += 1
    raise ValueError(
        f"未找到板块「{symbol}」：请确认名称（可用 stock_board_industry_name_em 查列表）"
        "或直接传 BK 代码"
    )
