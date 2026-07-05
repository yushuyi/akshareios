"""
新浪财经备用数据源

参考：akshare/stock/stock_zh_a_sina.py、stock_zh_a_minute
"""

import json
import re

import requests

from akshareios._convert import apply_row_limit, to_float, to_int
from akshareios._http import _EM_HEADERS
from akshareios._pagination import make_page_result
from akshareios._symbols import to_market_symbol

_SINA_HEADERS = {
    **_EM_HEADERS,
    "Referer": "https://finance.sina.com.cn/",
}

_HQ_URL = "https://hq.sinajs.cn/list={symbols}"
_MINUTE_URL = "https://quotes.sina.cn/cn/api/jsonp_v2.php/=/CN_MarketDataService.getKLineData"
_SPOT_URL = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
_COUNT_URL = (
    "http://vip.stock.finance.sina.com.cn/quotes_service/api/"
    "json_v2.php/Market_Center.getHQNodeStockCount?node=hs_a"
)


def sina_individual_quote(symbol: str, *, timeout: float) -> dict:
    """新浪实时报价，字段少于东财个股详情。"""
    sina_sym = to_market_symbol(symbol)
    r = requests.get(
        _HQ_URL.format(symbols=sina_sym),
        timeout=timeout,
        headers=_SINA_HEADERS,
    )
    r.raise_for_status()
    text = r.text
    m = re.search(r'="([^"]*)"', text)
    if not m:
        return {}
    parts = m.group(1).split(",")
    if len(parts) < 10 or not parts[0]:
        return {}

    prev_close = to_float(parts[2])
    latest = to_float(parts[3])
    change = None
    pct = None
    if prev_close and latest is not None:
        change = round(latest - prev_close, 4)
        if prev_close:
            pct = round(change / prev_close * 100, 4)

    plain = sina_sym.removeprefix("sh").removeprefix("sz").removeprefix("bj")
    return {
        "股票代码": plain,
        "股票简称": parts[0],
        "最新价": latest,
        "今开": to_float(parts[1]),
        "昨收": prev_close,
        "最高": to_float(parts[4]),
        "最低": to_float(parts[5]),
        "成交量": to_int(parts[8]) if len(parts) > 8 else None,
        "成交额": to_float(parts[9]) if len(parts) > 9 else None,
        "涨跌额": change,
        "涨跌幅": pct,
    }


def sina_minute_klines(
    symbol: str,
    *,
    period: str,
    limit: int | None,
    timeout: float,
) -> list[dict]:
    """新浪分钟 K 线（period 为 1/5/15/30/60）。"""
    sina_sym = to_market_symbol(symbol)
    datalen = min(limit if limit and limit > 0 else 120, 250)
    params = {
        "symbol": sina_sym,
        "scale": period if period != "1" else "1",
        "ma": "no",
        "datalen": str(datalen),
    }
    r = requests.get(_MINUTE_URL, params=params, timeout=timeout, headers=_SINA_HEADERS)
    r.raise_for_status()
    text = r.text
    if "=(" not in text:
        return []
    payload = text.split("=(", 1)[1].rsplit(");", 1)[0]
    data = json.loads(payload)
    if not isinstance(data, list):
        return []

    rows = []
    for item in data:
        day = item.get("day") or ""
        rows.append({
            "时间": day,
            "开盘": to_float(item.get("open")),
            "收盘": to_float(item.get("close")),
            "最高": to_float(item.get("high")),
            "最低": to_float(item.get("low")),
            "成交量": to_int(item.get("volume")),
            "成交额": to_float(item.get("amount")) if item.get("amount") else None,
            "振幅": None,
            "涨跌幅": None,
            "涨跌额": None,
            "换手率": None,
        })
    return apply_row_limit(rows, limit)


def sina_code_name_page(
    *,
    page: int,
    page_size: int,
    timeout: float,
) -> dict:
    """新浪 A 股列表分页（code + name）。"""
    try:
        cr = requests.get(_COUNT_URL, timeout=timeout, headers=_SINA_HEADERS)
        cr.raise_for_status()
        total = int(re.findall(r"\d+", cr.text)[0])
    except Exception:
        total = 5000

    params = {
        "page": str(page),
        "num": str(page_size),
        "sort": "symbol",
        "asc": "1",
        "node": "hs_a",
        "symbol": "",
        "_s_r_a": "page",
    }
    r = requests.get(_SPOT_URL, params=params, timeout=timeout, headers=_SINA_HEADERS)
    r.raise_for_status()
    # 新浪返回 JSON 数组，可能非严格 JSON
    text = r.text.strip()
    data = json.loads(text)
    items = []
    for row in data:
        code = str(row.get("code", "")).zfill(6)
        items.append({"code": code, "name": row.get("name")})

    return make_page_result(items, page=page, page_size=page_size, total=total)
