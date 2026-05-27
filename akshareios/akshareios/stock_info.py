"""
个股详细信息

数据源：东方财富 push2 API
原版参考：akshare/stock/stock_info_em.py → stock_individual_info_em()
"""

from akshareios._http import get

_FIELD_MAP = {
    "f57": "股票代码",
    "f58": "股票简称",
    "f84": "总股本",
    "f85": "流通股",
    "f127": "行业",
    "f116": "总市值",
    "f117": "流通市值",
    "f189": "上市时间",
    "f43": "最新价",
    "f44": "最高",
    "f45": "最低",
    "f46": "今开",
    "f60": "昨收",
    "f47": "成交量",
    "f48": "成交额",
    "f50": "量比",
    "f55": "市盈率",
    "f162": "市净率",
    "f168": "换手率",
    "f169": "涨跌额",
    "f170": "涨跌幅",
}


def stock_individual_info_em(
    symbol: str = "603777",
    timeout: float = 15,
) -> dict:
    """
    东方财富-个股-股票信息

    :param symbol: 股票代码，如 "600519"
    :param timeout: 请求超时时间（秒）
    :return: {"股票代码": "600519", "股票简称": "贵州茅台", "总市值": ..., ...}
    """
    market_code = 1 if symbol.startswith("6") else 0
    url = "https://push2.eastmoney.com/api/qt/stock/get"
    params = {
        "fltt": "2",
        "invt": "2",
        "fields": ",".join(_FIELD_MAP.keys()),
        "secid": f"{market_code}.{symbol}",
    }
    r = get(url, params=params, timeout=timeout)
    r.raise_for_status()
    data_json = r.json()

    data = data_json.get("data")
    if not data:
        return {}

    result = {}
    for field_key, field_name in _FIELD_MAP.items():
        val = data.get(field_key)
        if val == "-":
            val = None
        result[field_name] = val

    return result
