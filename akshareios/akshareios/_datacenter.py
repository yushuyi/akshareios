"""东财数据中心 datacenter 报表接口（纯 JSON 直连）。"""

from akshareios._http import get

DC_WEB_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
DC_F10_URL = "https://datacenter.eastmoney.com/securities/api/data/v1/get"


def _build_params(
    report_name: str,
    *,
    filter: str,
    columns: str,
    sort_columns: str,
    sort_types: str,
    page_size: int,
    page_number: int,
    source: str,
) -> dict:
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
    return params


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
    params = _build_params(
        report_name,
        filter=filter,
        columns=columns,
        sort_columns=sort_columns,
        sort_types=sort_types,
        page_size=page_size,
        page_number=page_number,
        source=source,
    )
    r = get(url, params=params, timeout=timeout)
    r.raise_for_status()
    result = r.json().get("result") or {}
    return result.get("data") or []


def get_report_page(
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
) -> tuple[list[dict], int]:
    """查询 datacenter 报表，返回 (数据行, 总条数)。

    与 get_report 的区别（新增接口一律用这个）：
    1. 区分「报表参数错误」与「确实没有数据」。success=false 有两义：
       code 9201「返回数据为空」是合法空结果，code 9501「报表配置不存在 /
       列不存在」才是真错误，直接抛 ValueError。旧实现一律静默返回 []，
       会把写错的列名伪装成「今日无记录」，也会被误读成当日 0 条。
    2. 带出 result.count，让分页 dict 的 total 是真实总数而非本页条数。
    """
    params = _build_params(
        report_name,
        filter=filter,
        columns=columns,
        sort_columns=sort_columns,
        sort_types=sort_types,
        page_size=page_size,
        page_number=page_number,
        source=source,
    )
    r = get(url, params=params, timeout=timeout)
    r.raise_for_status()
    payload = r.json()
    if payload.get("success") is False:
        # 东财把「报表参数错误」和「查不到数据」都标 success=false，靠 code 区分：
        #   9201 / 返回数据为空 → 合法空结果（如个股当日未上龙虎榜）
        #   9501 / 报表配置不存在、xxx列不存在 → 真错误，必须抛，否则静默变空列表
        # 全当错误会把「没有数据」变成异常，全当空会把写错的列名藏起来。
        code = str(payload.get("code") or "")
        message = payload.get("message") or "未知错误"
        if code == "9201" or "返回数据为空" in str(message):
            return [], 0
        raise ValueError(f"东财报表 {report_name} 查询失败: {message} (code={code})")
    result = payload.get("result") or {}
    rows = result.get("data") or []
    try:
        total = int(result.get("count") or 0)
    except (TypeError, ValueError):
        total = 0
    return rows, total


def to_secucode(symbol: str) -> str:
    """6 位代码 → 交易所后缀代码（603517 → 603517.SH）。"""
    # 920 开头是北交所新代码段，须先于 9 判断；900 开头是沪 B，归 SH。
    if symbol.startswith(("4", "8", "920")):
        return f"{symbol}.BJ"
    if symbol.startswith(("5", "6", "9")):
        return f"{symbol}.SH"
    return f"{symbol}.SZ"
