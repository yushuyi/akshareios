"""
个股详细信息

主数据源：东方财富 push2；失败时降级新浪 hq.sinajs.cn 实时报价。
"""

from akshareios._fallback import call_with_fallback
from akshareios._fallback_sina import sina_individual_quote
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
    """个股信息；东财失败时返回新浪实时报价（字段较少）。"""
    return call_with_fallback(
        lambda: _info_em(symbol, timeout=timeout),
        lambda: sina_individual_quote(symbol, timeout=timeout),
        retry_on_empty=True,
    )


def _info_em(symbol: str, *, timeout: float) -> dict:
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
    data = r.json().get("data")
    if not data:
        return {}

    result = {}
    for field_key, field_name in _FIELD_MAP.items():
        val = data.get(field_key)
        if val == "-":
            val = None
        result[field_name] = val
    return result
