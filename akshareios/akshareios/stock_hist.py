"""
沪深京 A 股历史 K 线数据

数据源：东方财富 push2his API
原版参考：akshare/stock_feature/stock_hist_em.py → stock_zh_a_hist()
"""

from akshareios._http import get


_MAX_KLINE_ROWS = 250


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
    东方财富网-沪深京 A 股-历史行情（日/周/月 K 线）

    :param symbol: 股票代码，如 "000001"、"600519"
    :param period: K 线周期，'daily' / 'weekly' / 'monthly'
    :param start_date: 开始日期，格式 "20240101"
    :param end_date: 结束日期，格式 "20241231"
    :param adjust: 复权类型，"qfq"=前复权, "hfq"=后复权, ""=不复权
    :param limit: 最多返回条数，默认 120；传 None 不限制（最大 250）；按时间正序截断尾部
    :param timeout: 请求超时时间（秒）
    :return: [{"日期": "2024-01-02", "开盘": 10.5, "收盘": 10.8, ...}, ...]
    """
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
    data_json = r.json()

    klines_data = data_json.get("data")
    if not klines_data or not klines_data.get("klines"):
        return []

    results = []
    for line in klines_data["klines"]:
        fields = line.split(",")
        if len(fields) < 11:
            continue
        results.append({
            "日期": fields[0],
            "开盘": _to_float(fields[1]),
            "收盘": _to_float(fields[2]),
            "最高": _to_float(fields[3]),
            "最低": _to_float(fields[4]),
            "成交量": _to_int(fields[5]),
            "成交额": _to_float(fields[6]),
            "振幅": _to_float(fields[7]),
            "涨跌幅": _to_float(fields[8]),
            "涨跌额": _to_float(fields[9]),
            "换手率": _to_float(fields[10]),
        })

    if limit is None:
        if len(results) > _MAX_KLINE_ROWS:
            results = results[-_MAX_KLINE_ROWS:]
    elif limit > 0 and len(results) > limit:
        cap = min(limit, _MAX_KLINE_ROWS)
        results = results[-cap:]

    return results


def _to_float(value: str) -> float | None:
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _to_int(value: str) -> int | None:
    try:
        return int(value)
    except (ValueError, TypeError):
        return None
