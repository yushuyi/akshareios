"""
资金流向 - 个股资金流历史（主力/超大单/大单/中单/小单净流入）

数据源：东方财富 push2his fflow 接口
原版参考：akshare/stock/stock_fund_em.py → stock_individual_fund_flow()
"""

from akshareios._convert import apply_row_limit, ensure_symbol, to_float
from akshareios._http import get_push2his_json

_FFLOW_PATH = "/api/qt/stock/fflow/daykline/get"

_FIELDS = [
    "日期", "主力净流入额", "小单净流入额", "中单净流入额", "大单净流入额", "超大单净流入额",
    "主力净占比", "小单净占比", "中单净占比", "大单净占比", "超大单净占比", "收盘价", "涨跌幅",
]


def stock_individual_fund_flow(
    symbol: str = "000001",
    limit: int | None = 120,
    timeout: float = 15,
) -> list[dict]:
    """
    个股资金流历史（日线，按时间正序）

    :param symbol: 6 位代码
    :param limit: 最多返回条数，默认 120，上限 250；None 或 ≤0 视为全量后截断至 250
    :return: list[dict]，金额单位元、占比单位 %；最新一天为最近已收盘交易日（当日盘中不刷新，收盘后更新）
    """
    symbol = ensure_symbol(symbol)
    if limit is not None and limit <= 0:
        limit = None  # 归一化 ≤0 为全量语义，统一走 250 截断，避免 lmt 负数下发
    market_code = 1 if symbol.startswith("6") else 0
    params = {
        "lmt": str(limit or 0),
        "klt": "101",
        "secid": f"{market_code}.{symbol}",
        "fields1": "f1,f2,f3,f7",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
    }
    data = get_push2his_json(_FFLOW_PATH, params, timeout=timeout)
    klines = (data.get("data") or {}).get("klines") or []

    results = []
    for line in klines:
        fields = line.split(",")
        if len(fields) < len(_FIELDS):
            continue
        row = {}
        for idx, name in enumerate(_FIELDS):
            row[name] = fields[idx] if name == "日期" else to_float(fields[idx])
        results.append(row)
    return apply_row_limit(results, limit)
