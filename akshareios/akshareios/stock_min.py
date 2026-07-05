"""
沪深京 A 股分时 / 分钟 K 线

主数据源：东方财富 push2his；失败时降级新浪分钟 K 线。
"""

from datetime import datetime, timedelta

from akshareios._convert import apply_row_limit, to_float, to_int
from akshareios._fallback import call_with_fallback
from akshareios._fallback_sina import sina_minute_klines
from akshareios._http import get

_DEFAULT_START = "1979-09-01 09:32:00"
_DEFAULT_END = "2222-01-01 09:32:00"


def stock_zh_a_hist_min_em(
    symbol: str = "000001",
    start_date: str = _DEFAULT_START,
    end_date: str = _DEFAULT_END,
    period: str = "5",
    adjust: str = "",
    limit: int | None = 120,
    timeout: float = 15,
) -> list[dict]:
    """
    分时 / 分钟行情；东财失败时降级新浪（不复权，字段略少）。
    """
    rows = call_with_fallback(
        lambda: _min_em(
            symbol,
            start_date=start_date,
            end_date=end_date,
            period=period,
            adjust=adjust,
            limit=limit,
            timeout=timeout,
        ),
        lambda: _min_sina_fallback(
            symbol,
            start_date=start_date,
            end_date=end_date,
            period=period,
            limit=limit,
            timeout=timeout,
        ),
        retry_on_empty=True,
    )
    rows = [r for r in rows if start_date <= r["时间"] <= end_date]
    return apply_row_limit(rows, limit)


def _min_em(
    symbol: str,
    *,
    start_date: str,
    end_date: str,
    period: str,
    adjust: str,
    limit: int | None,
    timeout: float,
) -> list[dict]:
    market_code = 1 if symbol.startswith("6") else 0
    secid = f"{market_code}.{symbol}"

    if period == "1":
        return _fetch_trends(secid, timeout=timeout)
    return _fetch_minute_klines(
        secid,
        period=period,
        adjust=adjust,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        timeout=timeout,
    )


def _min_sina_fallback(
    symbol: str,
    *,
    start_date: str,
    end_date: str,
    period: str,
    limit: int | None,
    timeout: float,
) -> list[dict]:
    scale = period if period in {"1", "5", "15", "30", "60"} else "5"
    return sina_minute_klines(symbol, period=scale, limit=limit, timeout=timeout)


def _fetch_trends(secid: str, *, timeout: float) -> list[dict]:
    url = "https://push2his.eastmoney.com/api/qt/stock/trends2/get"
    params = {
        "fields1": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58",
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
        "ndays": "1",
        "iscr": "0",
        "secid": secid,
    }
    r = get(url, params=params, timeout=timeout)
    r.raise_for_status()
    trends = (r.json().get("data") or {}).get("trends") or []

    rows = []
    for line in trends:
        fields = line.split(",")
        if len(fields) < 8:
            continue
        rows.append({
            "时间": fields[0],
            "开盘": to_float(fields[1]),
            "收盘": to_float(fields[2]),
            "最高": to_float(fields[3]),
            "最低": to_float(fields[4]),
            "成交量": to_int(fields[5]),
            "成交额": to_float(fields[6]),
            "均价": to_float(fields[7]),
        })
    return rows


def _fetch_minute_klines(
    secid: str,
    *,
    period: str,
    adjust: str,
    start_date: str,
    end_date: str,
    limit: int | None,
    timeout: float,
) -> list[dict]:
    adjust_map = {"qfq": "1", "hfq": "2", "": "0"}
    beg, end = _minute_beg_end(start_date, end_date, period=period, limit=limit)
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
        "klt": period,
        "fqt": adjust_map.get(adjust, "0"),
        "secid": secid,
        "beg": beg,
        "end": end,
    }
    r = get(url, params=params, timeout=timeout)
    r.raise_for_status()
    klines = (r.json().get("data") or {}).get("klines") or []

    rows = []
    for line in klines:
        fields = line.split(",")
        if len(fields) < 11:
            continue
        rows.append({
            "时间": fields[0],
            "开盘": to_float(fields[1]),
            "收盘": to_float(fields[2]),
            "最高": to_float(fields[3]),
            "最低": to_float(fields[4]),
            "成交量": to_int(fields[5]),
            "成交额": to_float(fields[6]),
            "振幅": to_float(fields[7]),
            "涨跌幅": to_float(fields[8]),
            "涨跌额": to_float(fields[9]),
            "换手率": to_float(fields[10]),
        })
    return rows


def _minute_beg_end(
    start_date: str,
    end_date: str,
    *,
    period: str,
    limit: int | None,
) -> tuple[str, str]:
    if end_date != _DEFAULT_END:
        end = end_date[:10].replace("-", "")
    else:
        end = datetime.now().strftime("%Y%m%d")

    if start_date != _DEFAULT_START:
        beg = start_date[:10].replace("-", "")
        return beg, end

    bars_per_day = {"5": 48, "15": 16, "30": 8, "60": 4}.get(period, 48)
    cap = limit if limit and limit > 0 else 120
    days = max(3, cap // bars_per_day + 2)
    beg = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
    return beg, end
