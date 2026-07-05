"""
中国股票指数历史 K 线

主数据源：东方财富 push2his；失败时降级腾讯日 K。
"""

from akshareios._convert import apply_row_limit, to_float, to_int
from akshareios._fallback import call_with_fallback
from akshareios._fallback_tx import tx_daily_hist
from akshareios._http import get

_COMMON_INDEX_SECID = {
    "000001": "1.000001",
    "399001": "0.399001",
    "399006": "0.399006",
    "000300": "1.000300",
    "000016": "1.000016",
    "399005": "0.399005",
    "000688": "1.000688",
    "000852": "1.000852",
}


def index_zh_a_hist(
    symbol: str = "000001",
    period: str = "daily",
    start_date: str = "19700101",
    end_date: str = "20500101",
    limit: int | None = 120,
    timeout: float = 15,
) -> list[dict]:
    """指数日/周/月 K 线；日线在东财失败时降级腾讯。"""
    return call_with_fallback(
        lambda: _index_em(
            symbol,
            period=period,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            timeout=timeout,
        ),
        lambda: _index_tx_fallback(
            symbol,
            period=period,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            timeout=timeout,
        ),
        retry_on_empty=True,
    )


def _index_em(
    symbol: str,
    *,
    period: str,
    start_date: str,
    end_date: str,
    limit: int | None,
    timeout: float,
) -> list[dict]:
    period_dict = {"daily": "101", "weekly": "102", "monthly": "103"}
    secid = _resolve_index_secid(symbol, timeout=timeout)

    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "secid": secid,
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": period_dict.get(period, "101"),
        "fqt": "0",
        "beg": start_date,
        "end": end_date,
    }
    r = get(url, params=params, timeout=timeout)
    r.raise_for_status()
    klines = (r.json().get("data") or {}).get("klines") or []
    if not klines:
        return []

    rows = []
    for line in klines:
        fields = line.split(",")
        if len(fields) < 7:
            continue
        rows.append({
            "日期": fields[0],
            "开盘": to_float(fields[1]),
            "收盘": to_float(fields[2]),
            "最高": to_float(fields[3]),
            "最低": to_float(fields[4]),
            "成交量": to_int(fields[5]),
            "成交额": to_float(fields[6]),
            "振幅": to_float(fields[7]) if len(fields) > 7 else None,
            "涨跌幅": to_float(fields[8]) if len(fields) > 8 else None,
            "涨跌额": to_float(fields[9]) if len(fields) > 9 else None,
            "换手率": to_float(fields[10]) if len(fields) > 10 else None,
        })
    return apply_row_limit(rows, limit)


def _index_tx_fallback(
    symbol: str,
    *,
    period: str,
    start_date: str,
    end_date: str,
    limit: int | None,
    timeout: float,
) -> list[dict]:
    if period != "daily":
        raise ValueError("非日线周期仅东财支持")
    return tx_daily_hist(
        symbol,
        start_date=start_date,
        end_date=end_date,
        adjust="",
        limit=limit,
        timeout=timeout,
        is_index=True,
    )


def _resolve_index_secid(symbol: str, *, timeout: float) -> str:
    if symbol in _COMMON_INDEX_SECID:
        return _COMMON_INDEX_SECID[symbol]
    for market in ("1", "0", "2", "47"):
        secid = f"{market}.{symbol}"
        if _probe_index_secid(secid, timeout=timeout):
            _COMMON_INDEX_SECID[symbol] = secid
            return secid
    return f"1.{symbol}"


def _probe_index_secid(secid: str, *, timeout: float) -> bool:
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "secid": secid,
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51",
        "klt": "101",
        "fqt": "0",
        "beg": "0",
        "end": "20500000",
    }
    try:
        r = get(url, params=params, timeout=timeout)
        r.raise_for_status()
        return len((r.json().get("data") or {}).get("klines") or []) > 0
    except Exception:
        return False
