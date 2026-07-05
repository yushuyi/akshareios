"""
腾讯证券备用数据源

参考：akshare/stock_feature/stock_hist_tx.py、akshare/stock/stock_zh_a_tx.py
"""

import json
from datetime import datetime

import requests

from akshareios._convert import apply_row_limit, to_float, to_int
from akshareios._http import _EM_HEADERS
from akshareios._pagination import make_page_result
from akshareios._symbols import is_index_code, to_market_symbol

_TX_HEADERS = {
    **_EM_HEADERS,
    "Referer": "https://gu.qq.com/",
}

_KLINE_URL = "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get"
_RANK_URL = "https://proxy.finance.qq.com/cgi/cgi-bin/rank/hs/getBoardRankList"


def tx_daily_hist(
    symbol: str,
    *,
    start_date: str,
    end_date: str,
    adjust: str = "",
    limit: int | None,
    timeout: float,
    is_index: bool = False,
) -> list[dict]:
    """腾讯日 K 线，仅支持日线。"""
    tx_sym = to_market_symbol(symbol, is_index=is_index or is_index_code(symbol))
    adj = {"qfq": "qfq", "hfq": "hfq"}.get(adjust, "")

    beg = _fmt_date(start_date)
    end = _fmt_date(end_date)
    start_year = int(beg[:4])
    end_year = min(int(end[:4]), datetime.now().year)

    rows: list[dict] = []
    for year in range(start_year, end_year + 1):
        params = {
            "_var": f"kline_day{adj}{year}",
            "param": f"{tx_sym},day,{year}-01-01,{year + 1}-12-31,640,{adj}",
            "r": "0.8205512681390605",
        }
        r = requests.get(_KLINE_URL, params=params, timeout=timeout, headers=_TX_HEADERS)
        r.raise_for_status()
        body = _parse_tx_json(r.text)
        sym_data = (body.get("data") or {}).get(tx_sym) or {}
        key = "day"
        if adj == "qfq" and "qfqday" in sym_data:
            key = "qfqday"
        elif adj == "hfq" and "hfqday" in sym_data:
            key = "hfqday"
        bars = sym_data.get(key) or []
        for bar in bars:
            if len(bar) < 6:
                continue
            d = str(bar[0])
            if d < beg or d > end:
                continue
            rows.append({
                "日期": d,
                "开盘": to_float(bar[1]),
                "收盘": to_float(bar[2]),
                "最高": to_float(bar[3]),
                "最低": to_float(bar[4]),
                "成交量": to_int(bar[5]),
                "成交额": to_float(bar[6]) if len(bar) > 6 and isinstance(bar[6], (int, float, str)) else None,
                "振幅": None,
                "涨跌幅": None,
                "涨跌额": None,
                "换手率": to_float(bar[7]) if len(bar) > 7 else None,
            })

    rows.sort(key=lambda x: x["日期"])
    return apply_row_limit(rows, limit)


def tx_spot_page(
    *,
    page: int,
    page_size: int,
    timeout: float,
) -> dict:
    """腾讯沪深京涨幅榜分页。"""
    params = {
        "_appver": "11.17.0",
        "board_code": "aStock",
        "sort_type": "price",
        "direct": "down",
        "offset": str((page - 1) * page_size),
        "count": str(page_size),
    }
    r = requests.get(_RANK_URL, params=params, timeout=timeout, headers=_TX_HEADERS)
    r.raise_for_status()
    data = (r.json().get("data") or {})
    rank_list = data.get("rank_list") or []
    total = int(data.get("total") or len(rank_list) or page_size * 10)

    items = []
    for row in rank_list:
        code = str(row.get("code", ""))
        plain = code.removeprefix("sh").removeprefix("sz").removeprefix("bj")
        items.append({
            "代码": plain or code,
            "名称": row.get("name"),
            "最新价": to_float(row.get("pn")),
            "涨跌幅": to_float(row.get("speed")),
            "涨跌额": None,
            "成交量": None,
            "成交额": None,
            "换手率": to_float(row.get("hsl")),
            "流通市值": to_float(row.get("ltsz")),
        })

    return make_page_result(items, page=page, page_size=page_size, total=total)


def _fmt_date(s: str) -> str:
    s = s.replace("-", "")
    if len(s) >= 8:
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return s


def _parse_tx_json(text: str) -> dict:
    """解析腾讯 JSONP 响应：kline_day2025={...}"""
    if not text:
        return {}
    idx = text.find("={")
    if idx < 0:
        return json.loads(text)
    return json.loads(text[idx + 1 :])
