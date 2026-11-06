"""
东方财富-行业板块列表与成分股

数据源：东方财富 push2 clist API；板块列表不可用时降级新浪行业板块
原版参考：akshare/stock/stock_board_industry_em.py
→ stock_board_industry_name_em() / stock_board_industry_cons_em()
"""

import re

import requests

from akshareios._fallback import call_with_fallback
from akshareios._fallback_sina import (
    sina_board_industry_cons_page,
    sina_board_industry_page,
)
from akshareios._http import get_push2_clist
from akshareios._pagination import (
    DEFAULT_PAGE_SIZE,
    clamp_page,
    clamp_page_size,
    make_page_result,
)
from akshareios._provenance import Provenance, attach_meta

_BOARD_NAME_PROVENANCE = Provenance(
    primary_source="东方财富 push2 clist",
    fallback_source="新浪行业板块",
    freshness="盘中实时（收盘后为最近收盘价）",
    fallback_note="新浪板块代码是 new_xxx 体系，与东财 BK 代码不通用；"
                  "新浪不提供上涨/下跌家数与板块总市值，改给公司家数/平均价格/总成交量/总成交额。"
                  "成分股查询请传本结果里的板块代码（new_xxx）。",
    missing_fields=("排名", "上涨家数", "下跌家数", "领涨股票-涨跌幅", "总市值"),
    primary_note="板块代码为东财 BK 体系，可直接用于成分股接口。",
)

_BOARD_CONS_PROVENANCE = Provenance(
    primary_source="东方财富 push2 clist",
    fallback_source="新浪行业成分股",
    freshness="盘中实时（收盘后为最近收盘价）",
    fallback_note="新浪按代码升序（主源按涨跌幅降序）；成交量已由股换算为手、"
                  "总市值/流通市值已由万元换算为元，与主源同单位；量比新浪不提供，恒为 null。"
                  "新浪行业分类与东财行业分类不完全一致，成分股名单可能有差异。",
    missing_fields=("量比",),
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
        provenance=_BOARD_NAME_PROVENANCE,
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
    东财 push2 不可用时，若板块列表已降级新浪，用新浪 new_xxx 代码查新浪
    成分股（字段对齐主源，单位已换算），不再直接抛「稍后重试」。
    直接传 BK 代码时仍只走东财主源：BK 与新浪 node 无对应关系，不能混用。

    :param symbol: 东财板块代码（BK0737）、新浪板块代码（new_xxx）或板块名称（软件开发）
    :param page: 页码，从 1 开始
    :param page_size: 每页条数，默认 20，最大 100
    :return: 分页 dict，items 含代码、名称、最新价、涨跌幅等；total = 成分股总数
    """
    if not symbol or not symbol.strip():
        raise ValueError("symbol 不能为空：传板块代码（BK0737 / new_xxx）或板块名称（软件开发）")
    symbol = symbol.strip()
    page = clamp_page(page)
    page_size = clamp_page_size(page_size)

    board_code = _resolve_board_code(symbol, timeout=timeout)
    if board_code.startswith("new_"):
        result = sina_board_industry_cons_page(
            board_code, page=page, page_size=page_size, timeout=timeout
        )
        return attach_meta(result, _BOARD_CONS_PROVENANCE.meta(degraded=True))

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

    return attach_meta(
        make_page_result(items, page=page, page_size=page_size, total=total),
        _BOARD_CONS_PROVENANCE.meta(degraded=False),
    )


def _resolve_board_code(symbol: str, *, timeout: float) -> str:
    """板块代码直接返回；板块名称翻板块列表精确匹配（列表最多 ~500 条，5 页内）。

    板块列表降级新浪时返回 new_xxx 而非抛错——调用方据此走新浪成分股降级源。
    """
    if re.fullmatch(r"BK\d+", symbol, re.IGNORECASE):
        return symbol.upper()
    if symbol.startswith("new_"):
        return symbol

    page = 1
    while True:
        result = stock_board_industry_name_em(page=page, page_size=100, timeout=timeout)
        items = result.get("items", [])
        degraded = any("数据源" in item for item in items)
        if not items and page == 1:
            raise ValueError("东财与新浪板块列表均暂不可用，无法解析板块，请稍后重试")
        for item in items:
            if item.get("板块名称") == symbol:
                code = str(item.get("板块代码") or "")
                if degraded and not code.startswith("new_"):
                    raise ValueError(
                        "板块列表已降级新浪但代码体系异常，无法解析板块，请稍后重试"
                    )
                return code
        if not result.get("has_more"):
            break
        page += 1
    if degraded:
        raise ValueError(
            f"板块列表此刻已降级新浪（new_xxx 体系），新浪行业分类里没有「{symbol}」："
            "请改传 stock_board_industry_name_em 返回的板块代码，或稍后东财恢复后重试名称"
        )
    raise ValueError(
        f"未找到板块「{symbol}」：请确认名称（可用 stock_board_industry_name_em 查列表）"
        "或直接传 BK 代码 / new_xxx 代码"
    )
