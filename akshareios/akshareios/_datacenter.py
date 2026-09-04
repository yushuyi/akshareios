"""东财数据中心 datacenter 报表接口（纯 JSON 直连）。"""

from akshareios._http import get

DC_WEB_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
DC_F10_URL = "https://datacenter.eastmoney.com/securities/api/data/v1/get"


def get_report(
    report_name: str,
    *,
    filter: str = "",
    columns: str = "ALL",
    sort_columns: str = "",
    sort_types: str = "",
    page_size: int = 50,
    page_number: int = 1,
    url: str = DC_WEB_URL,
    source: str = "WEB",
    timeout: float = 15,
) -> list[dict]:
    """查询 datacenter 报表，返回数据行列表；无数据时返回空列表。"""
    params = {
        "reportName": report_name,
        "columns": columns,
        "pageSize": str(page_size),
        "pageNumber": str(page_number),
        "source": source,
        "client": "WEB",
    }
    if filter:
        params["filter"] = filter
    if sort_columns:
        params["sortColumns"] = sort_columns
        params["sortTypes"] = sort_types
    r = get(url, params=params, timeout=timeout)
    r.raise_for_status()
    result = r.json().get("result") or {}
    return result.get("data") or []


def to_secucode(symbol: str) -> str:
    """6 位代码 → 交易所后缀代码（603517 → 603517.SH）。"""
    if symbol.startswith("6"):
        return f"{symbol}.SH"
    if symbol.startswith(("4", "8", "9")):
        return f"{symbol}.BJ"
    return f"{symbol}.SZ"
