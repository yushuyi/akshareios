"""
沪深京 A 股历史 K 线数据

主数据源：东方财富 push2his；失败时降级腾讯日 K。
"""

from akshareios._convert import apply_row_limit, deduplicate_rows_by_date, to_float, to_int
from akshareios._fallback import call_with_fallback
from akshareios._fallback_tx import tx_daily_hist
from akshareios._http import get


def stock_zh_a_hist(
    symbol: str = "000001",
    period: str = "daily",
    start_date: str = "19700101",
    end_date: str = "20500101",
    adjust: str = "",
    limit: int | None = 120,
    timeout: float = 15,
) -> list[dict]:
    """
    沪深京 A 股历史行情（日/周/月 K 线）

    东财不可用时，日线自动降级腾讯证券（仅 daily）。
    """
    return call_with_fallback(
        lambda: _hist_em(
            symbol,
            period=period,
            start_date=start_date,
            end_date=end_date,
            adjust=adjust,
            limit=limit,
            timeout=timeout,
        ),
        lambda: _hist_tx_fallback(
            symbol,
            period=period,
            start_date=start_date,
            end_date=end_date,
            adjust=adjust,
            limit=limit,
            timeout=timeout,
        ),
        retry_on_empty=True,
    )


def _hist_em(
    symbol: str,
    *,
    period: str,
    start_date: str,
    end_date: str,
    adjust: str,
    limit: int | None,
    timeout: float,
) -> list[dict]:
    market_code = 1 if symbol.startswith("6") else 0
    adjust_dict = {"qfq": "1", "hfq": "2", "": "0"}
    period_dict = {"daily": "101", "weekly": "102", "monthly": "103"}

    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f116",
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
        "klt": period_dict.get(period, "101"),
        "fqt": adjust_dict.get(adjust, "0"),
        "secid": f"{market_code}.{symbol}",
        "beg": start_date,
        "end": end_date,
    }
    r = get(url, params=params, timeout=timeout)
    r.raise_for_status()
    klines = (r.json().get("data") or {}).get("klines") or []
    if not klines:
        return []

    results = []
    for line in klines:
        fields = line.split(",")
        if len(fields) < 11:
            continue
        results.append({
            "日期": fields[0],
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
    results = deduplicate_rows_by_date(results)
    return apply_row_limit(results, limit)


def _hist_tx_fallback(
    symbol: str,
    *,
    period: str,
    start_date: str,
    end_date: str,
    adjust: str,
    limit: int | None,
    timeout: float,
) -> list[dict]:
    if period != "daily":
        raise ValueError("非日线周期仅东财支持")
    return tx_daily_hist(
        symbol,
        start_date=start_date,
        end_date=end_date,
        adjust=adjust,
        limit=limit,
        timeout=timeout,
        is_index=False,
    )
