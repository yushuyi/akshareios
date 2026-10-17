"""
腾讯证券备用数据源

参考：akshare/stock_feature/stock_hist_tx.py、akshare/stock/stock_zh_a_tx.py
"""

import json
import math
from datetime import datetime

import requests

from akshareios._convert import apply_row_limit, deduplicate_rows_by_date, to_float, to_int
from akshareios._http import _EM_HEADERS
from akshareios._pagination import make_page_result
from akshareios._symbols import to_market_symbol

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
    """
    腾讯日 K 线，仅支持日线。

    腾讯 bar 布局（真机抓包核实，qfqday/hfqday/day 一致）：
    [日期, 开, 收, 高, 低, 成交量(手, 小数字符串 '31420.00'),
     {} 占位, 换手率, 成交额(万元), ...]
    注意成交额在 bar[8] 且单位为万元（bar[6] 是占位 dict，不是成交额），
    旧实现读错位置导致量额列静默为 None（绝味会话 2026-10-10 实录）。
    """
    # 调用方已显式声明股票/指数身份（stock_hist 传 False、index_hist 传 True），
    # 禁止按代码前缀猜测：000001 平安银行会被误判成上证指数，静默返回错误数据。
    tx_sym = to_market_symbol(symbol, is_index=is_index)
    adj = {"qfq": "qfq", "hfq": "hfq"}.get(adjust, "")

    beg = _fmt_date(start_date)
    end = _fmt_date(end_date)
    end_year = min(int(end[:4]), datetime.now().year)

    # K 线最终受 apply_row_limit 截断（硬上限 250，约 1.2 个交易年度），
    # 按 limit 回推所需年份即可；默认 start_date=19700101 时旧实现会
    # 串行请求 50+ 个年度接口（东财断连降级时实测 14s+，设备 120s 超时）。
    # 每年约 240 个交易日，多留 1 年缓冲停牌与跨年边界。
    need_bars = min(limit if limit and limit > 0 else 250, 250)
    earliest_year = end_year - math.ceil(need_bars / 200) - 1
    start_year = max(int(beg[:4]), earliest_year)

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
                # bar[6] 是占位 dict，成交额在 bar[8]，单位万元 → 元
                "成交额": _tx_amount_yuan(bar[8]) if len(bar) > 8 else None,
                "振幅": None,
                "涨跌幅": None,
                "涨跌额": None,
                "换手率": to_float(bar[7]) if len(bar) > 7 else None,
            })

    rows.sort(key=lambda x: x["日期"])
    rows = deduplicate_rows_by_date(rows)
    _fill_derived_quote_fields(rows)
    return apply_row_limit(rows, limit)


def _tx_amount_yuan(value) -> float | None:
    """腾讯成交额单位为万元，转换为元；空串/占位 dict 视为缺失。"""
    amount = to_float(value)
    if amount is None:
        return None
    return round(amount * 10000, 2)


def _fill_derived_quote_fields(rows: list[dict]) -> None:
    """
    按相邻 bar 推算腾讯不直接给的涨跌额/涨跌幅/振幅（与东财字段对齐）。

    口径：涨跌额=今收-昨收；涨跌幅=涨跌额/昨收×100；振幅=(高-低)/昨收×100。
    复权序列的相邻收盘价已同口径调整，除权日也成立。首根无前收，留 None。
    """
    for i, row in enumerate(rows):
        if i == 0:
            continue
        prev_close = rows[i - 1].get("收盘")
        close = row.get("收盘")
        high = row.get("最高")
        low = row.get("最低")
        if not prev_close or not close:
            continue
        change = round(close - prev_close, 3)
        row["涨跌额"] = change
        row["涨跌幅"] = round(change / prev_close * 100, 2)
        if high is not None and low is not None:
            row["振幅"] = round((high - low) / prev_close * 100, 2)


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
