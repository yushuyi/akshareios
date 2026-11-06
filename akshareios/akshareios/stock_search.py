"""
证券名称 → 代码解析

数据源：东方财富搜索建议 API（searchapi.eastmoney.com），单一主源。

真机会话里用户往往只说名称（「茅台」「视频媒体」「软件开发」），模型只能
猜代码，或翻板块列表按名称匹配——东财 push2 一降级就解析失败。这里给一个
轻量、一次请求的名称解析，并**显式标注证券类型**：同名可能是 A 股、指数、
东财板块（BK）或 ETF，混用会把「软件开发」指数代码喂给个股接口。
"""

import requests

from akshareios._http import _EM_HEADERS
from akshareios._pagination import clamp_page_size
from akshareios._provenance import Provenance, attach_meta

_SUGGEST_URL = "https://searchapi.eastmoney.com/api/suggest/get"
_SUGGEST_TOKEN = "D43BF722C8E33BDC906FB84D85E326E8"
_HEADERS = {**_EM_HEADERS, "Referer": "https://www.eastmoney.com/"}

_SEARCH_PROVENANCE = Provenance(
    primary_source="东方财富搜索建议（searchapi）",
    fallback_source="无（该接口无可用降级源，失败即抛错）",
    freshness="静态代码表（不含行情价格）",
    primary_note="同名结果可能分属 A 股 / 指数 / 东财板块 BK / 基金，"
                 "务必按「代码体系」挑选：只有 A 股代码能传给个股接口，"
                 "板块代码（BKxxxx）应传给板块成分股接口。"
                 "搜索为前缀/拼音模糊匹配，items 不保证包含全市场所有同名标的。",
)

_A_STOCK_TYPES = {"沪A", "深A", "京A", "北A", "科创板", "创业板", "A股"}


def _code_system(row: dict) -> str:
    kind = str(row.get("SecurityTypeName") or "")
    classify = str(row.get("Classify") or "")
    if kind == "板块" or classify == "BK":
        return "东财板块BK"
    if kind in _A_STOCK_TYPES:
        return "A股"
    if kind == "指数" or "Index" in classify:
        return "指数"
    if kind == "基金" or classify == "Fund":
        return "基金"
    return "其他"


def _search_suggest(keyword: str, *, count: int, timeout: float) -> list[dict]:
    params = {
        "input": keyword,
        "type": "14",
        "token": _SUGGEST_TOKEN,
        "count": str(count),
    }
    r = requests.get(_SUGGEST_URL, params=params, timeout=timeout, headers=_HEADERS)
    r.raise_for_status()
    payload = r.json()
    table = payload.get("QuotationCodeTable") or {}
    if str(table.get("Status")) not in ("0", "None", ""):
        raise ValueError(
            f"东财名称搜索失败: {table.get('Message') or '未知错误'}"
        )
    return table.get("Data") or []


def _normalize(row: dict) -> dict:
    return {
        "代码": row.get("Code"),
        "名称": row.get("Name"),
        "类型": row.get("SecurityTypeName"),
        "代码体系": _code_system(row),
        "市场": row.get("MktNum"),
    }


def stock_name_to_code(
    name: str,
    count: int = 10,
    *,
    security_type: str | None = None,
    timeout: float = 8,
) -> dict:
    """
    证券名称 / 拼音前缀 → 候选代码列表

    :param name: 名称关键词，如「贵州茅台」「茅台」「软件开发」「RJKF」
    :param count: 最多返回多少条候选，默认 10，上限 100
    :param security_type: 按「代码体系」过滤：A股 / 东财板块BK / 指数 / 基金
    :param timeout: 请求超时秒数
    :return: dict（items / 精确匹配 / 查询词 / _meta）。
             「精确匹配」仅在存在同名且为 A 股的结果时给出 6 位代码，否则为 None。
    """
    keyword = str(name or "").strip()
    if not keyword:
        raise ValueError("name 不能为空：传证券名称或板块名称")
    count = clamp_page_size(count)

    rows = _search_suggest(keyword, count=count, timeout=timeout)
    items = [_normalize(row) for row in rows if isinstance(row, dict)]
    if security_type:
        items = [item for item in items if item["代码体系"] == security_type]

    exact = next(
        (
            item["代码"]
            for item in items
            if item["名称"] == keyword
            and item["代码体系"] == "A股"
            and str(item["代码"] or "").isdigit()
        ),
        None,
    )
    extra: dict = {"查询词": keyword, "候选数": len(items)}
    recommended = exact
    if recommended is None:
        a_stock = [
            item
            for item in items
            if item["代码体系"] == "A股" and str(item["代码"] or "").isdigit()
        ]
        # 「茅台」这类简称搜出来的正式名是「贵州茅台」，严格同名判定会落空。
        # 只有一个 A 股候选时给推荐代码（真实会话里用户几乎都只说简称），
        # 但仍提示核对简称，不假装这是精确匹配。
        if len(a_stock) == 1:
            recommended = a_stock[0]["代码"]
            extra["推荐说明"] = (
                "无完全同名结果，但候选里只有一个 A 股代码；"
                "建议用 stock_individual_info_em 核对简称后再用于决策"
            )
        same_name = [item for item in items if item["名称"] == keyword]
        if same_name:
            extra["精确匹配说明"] = (
                "存在同名结果，但都不是 A 股代码或已被 security_type 过滤；"
                "按 items 里的「代码体系」选择，别直接把第一个代码当股票代码"
            )
        elif "推荐说明" not in extra:
            extra["精确匹配说明"] = "无完全同名结果；items 为模糊匹配候选，需人工确认"
    return attach_meta(
        {
            "items": items,
            "total": len(items),
            "精确匹配": exact,
            "推荐代码": recommended,
        },
        _SEARCH_PROVENANCE.meta(degraded=False, extra=extra),
    )


def resolve_board_code_by_name(name: str, *, timeout: float = 8) -> str | None:
    """板块名称 → 东财 BK 代码；找不到返回 None（供上层按需使用）。"""
    try:
        rows = _search_suggest(str(name).strip(), count=10, timeout=timeout)
    except Exception:
        return None
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("Name") == str(name).strip() and _code_system(row) == "东财板块BK":
            return str(row.get("Code") or "") or None
    return None
