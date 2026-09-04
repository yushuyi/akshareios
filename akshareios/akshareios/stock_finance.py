"""
财务业绩 - 个股业绩报表（营收/净利/同比/毛利率/ROE）

数据源：东方财富数据中心 datacenter API
原版参考：akshare/stock_feature/stock_yjbb_em.py → stock_yjbb_em()
"""

from akshareios._convert import to_float
from akshareios._datacenter import get_report

_FIELDS = {
    "报告期": "REPORTDATE",
    "公告日期": "NOTICE_DATE",
    "营收": "TOTAL_OPERATE_INCOME",
    "营收同比": "YSTZ",
    "净利润": "PARENT_NETPROFIT",
    "净利同比": "SJLTZ",
    "毛利率": "XSMLL",
    "每股收益": "BASIC_EPS",
    "每股净资产": "BPS",
    "净资产收益率": "WEIGHTAVG_ROE",
}


def stock_yjbb_em(symbol: str = "000001", timeout: float = 15) -> list[dict]:
    """
    个股业绩报表历史（按报告期倒序，涵盖年报/中报/季报）

    :param symbol: 6 位代码
    :return: list[dict]，首条即最近报告期；报告单位：元
    """
    rows = get_report(
        "RPT_LICO_FN_CPD",
        filter=f'(SECURITY_CODE="{symbol}")',
        sort_columns="REPORTDATE",
        sort_types="-1",
        page_size=12,
        timeout=timeout,
    )
    results = []
    for row in rows:
        item = {}
        for cn, field in _FIELDS.items():
            value = row.get(field)
            item[cn] = str(value)[:10] if cn in ("报告期", "公告日期") and value else to_float(value)
        results.append(item)
    return results
