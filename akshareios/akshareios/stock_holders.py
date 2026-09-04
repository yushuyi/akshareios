"""
股东数据 - 股东户数趋势 / 十大流通股东

数据源：东方财富数据中心 datacenter API
原版参考：akshare/stock_feature/stock_gdhs.py、akshare/stock_feature/stock_gdfx_em.py
"""

from akshareios._convert import ensure_symbol, to_float, to_int
from akshareios._datacenter import DC_F10_URL, get_report, to_secucode


def stock_holder_num_em(symbol: str = "000001", timeout: float = 15) -> list[dict]:
    """
    个股股东户数趋势（按期末日期倒序）

    :param symbol: 6 位代码
    :return: list[dict]，首条即最新一期
    """
    symbol = ensure_symbol(symbol)
    rows = get_report(
        "RPT_HOLDERNUM_DET",
        filter=f'(SECURITY_CODE="{symbol}")',
        sort_columns="END_DATE",
        sort_types="-1",
        page_size=50,
        timeout=timeout,
    )
    results = []
    for row in rows:
        results.append({
            "日期": str(row.get("END_DATE") or "")[:10],
            "股东户数": to_int(row.get("HOLDER_NUM")),
            "较上期变化比例": to_float(row.get("HOLDER_NUM_RATIO")),
            "户均持股市值": to_float(row.get("AVG_MARKET_CAP")),
            "户均持股数量": to_float(row.get("AVG_HOLD_NUM")),
            "总市值": to_float(row.get("TOTAL_MARKET_CAP")),
            "公告日期": str(row.get("HOLD_NOTICE_DATE") or "")[:10],
        })
    return results


def stock_gdfx_free_top_10_em(symbol: str = "000001", timeout: float = 15) -> list[dict]:
    """
    个股十大流通股东（最新一期）

    :param symbol: 6 位代码
    :return: list[dict]，按持股排名 1-10
    """
    symbol = ensure_symbol(symbol)
    rows = get_report(
        "RPT_F10_EH_FREEHOLDERS",
        filter=f'(SECUCODE="{to_secucode(symbol)}")',
        sort_columns="END_DATE,FREE_HOLDNUM_RATIO",
        sort_types="-1,-1",
        page_size=10,
        url=DC_F10_URL,
        source="HSF10",
        timeout=timeout,
    )
    results = []
    for row in rows:
        results.append({
            "期末日期": str(row.get("END_DATE") or "")[:10],
            "排名": to_int(row.get("HOLDER_RANK")),
            "股东名称": row.get("HOLDER_NAME"),
            "持股数量": to_int(row.get("HOLD_NUM")),
            "持股市值": to_float(row.get("HOLDER_MARKET_CAP")),
            "持股比例": to_float(row.get("FREE_HOLDNUM_RATIO")),
            "增减": row.get("HOLD_CHANGE"),
            "增减比例": to_float(row.get("HOLD_CHANGE_RATIOTB")),
            "股东性质": row.get("HOLDER_TYPE"),
        })
    if results:
        # 服务端在最新一期不足 10 名时会用上一期行补满，按最大期末日期过滤
        latest = max(r["期末日期"] for r in results)
        results = [r for r in results if r["期末日期"] == latest]
    return results
