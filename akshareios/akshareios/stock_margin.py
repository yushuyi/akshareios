"""
融资融券余额（全市场 / 个股明细）

数据源：东方财富数据中心 datacenter 报表，均只有单一主源、无可用降级源。
原版参考：akshare/stock_feature/stock_margin_em.py（账户统计）

真机会话（2026-11-05）里模型反复推演「杠杆资金」却说「接口我没有」，
这里补齐两融余额与个股两融明细。两个报表都是 **T-1 收盘后**由交易所
披露，盘中不刷新，必须在 `_meta` 里写明，否则会被当成当日实时杠杆数据。
"""

from akshareios._convert import ensure_symbol, to_float, to_int
from akshareios._datacenter import get_report_page
from akshareios._pagination import clamp_page_size, make_page_result
from akshareios._provenance import Provenance, attach_meta

_MARKET_REPORT = "RPTA_WEB_MARGIN_DAILYTRADE"
_DETAIL_REPORT = "RPTA_WEB_RZRQ_GGMX"

_MARKET_PROVENANCE = Provenance(
    primary_source="东方财富 datacenter（全市场两融账户统计）",
    fallback_source="无（该报表无可用降级源，失败即抛错）",
    freshness="T-1 收盘后披露，当日盘中不刷新",
    primary_note="全市场口径；金额字段原始单位为亿元，已换算为元，与库内其他金额字段统一。"
                 "占比 / 维持担保比例 / 指数涨跌幅保持百分比原值；"
                 "投资者数量为人数，融券相关口径为全市场汇总。",
)

_DETAIL_PROVENANCE = Provenance(
    primary_source="东方财富 datacenter（个股融资融券明细）",
    fallback_source="无（该报表无可用降级源，失败即抛错）",
    freshness="T-1 收盘后披露，当日盘中不刷新",
    primary_note="个股口径，按日期倒序（首条最新）；金额单位元、融券余量/卖出量单位股、"
                 "占比与涨跌幅单位 %。融资净买入 = 融资买入额 - 融资偿还额（直接取报表 RZJME）。",
)

# 市场报表金额单位：亿元。不换算时 22785 会被读成 2.28 万元，量级差 1 亿倍
# （与 2026-11 修过的腾讯 ltsz 单位是同一类坑）。
_YI_TO_YUAN = 1e8


def _yi_to_yuan(value) -> float | None:
    number = to_float(value)
    return round(number * _YI_TO_YUAN, 2) if number is not None else None


def _date(value) -> str:
    return str(value or "")[:10]


def _parse_market_row(row: dict) -> dict:
    return {
        "日期": _date(row.get("STATISTICS_DATE")),
        "融资余额": _yi_to_yuan(row.get("FIN_BALANCE")),
        "融券余额": _yi_to_yuan(row.get("LOAN_BALANCE")),
        "两融余额": _yi_to_yuan(row.get("MARGIN_BALANCE")),
        "融资买入额": _yi_to_yuan(row.get("FIN_BUY_AMT")),
        "融券卖出额": _yi_to_yuan(row.get("LOAN_SELL_AMT")),
        "两融交易额": _yi_to_yuan(row.get("MARGIN_TRADE_AMT")),
        "担保物总价值": _yi_to_yuan(row.get("TOTAL_GUARANTEE")),
        "两融余额占流通市值比": to_float(row.get("BALANCE_RATIO")),
        "两融交易额占成交额比": to_float(row.get("TRADE_AMT_RATIO")),
        "平均维持担保比例": to_float(row.get("AVG_GUARANTEE_RATIO")),
        "上证指数收盘": to_float(row.get("SCI_CLOSE_PRICE")),
        "上证指数涨跌幅": to_float(row.get("SCI_CHANGE_RATE")),
        "参与交易投资者数": to_int(row.get("INVESTOR_NUM")),
        "有负债投资者数": to_int(row.get("MARGINLIAB_INVESTOR_NUM")),
    }


def stock_margin_balance_em(limit: int = 20, timeout: float = 15) -> dict:
    """
    东方财富-全市场融资融券余额（按日期倒序，首条最新）

    :param limit: 返回最近多少个交易日，默认 20，上限 100
    :return: 分页 dict（items / total / _meta）；金额单位元
    """
    limit = clamp_page_size(limit)
    rows, total = get_report_page(
        _MARKET_REPORT,
        sort_columns="STATISTICS_DATE",
        sort_types="-1",
        page_size=limit,
        timeout=timeout,
    )
    items = [_parse_market_row(row) for row in rows]
    # limit 语义是「取最近 N 个交易日」，不是翻全历史。total 若直接用报表
    # count（全历史 3400+ 天）会让 has_more 恒为 true，诱导模型翻上千页；
    # 历史条数放进 _meta 供参考即可。
    result = make_page_result(items, page=1, page_size=limit, total=len(items))
    return attach_meta(
        result,
        _MARKET_PROVENANCE.meta(
            degraded=False,
            extra={
                "最新数据日期": items[0]["日期"] if items else None,
                "历史总条数": total,
            },
        ),
    )


def _parse_detail_row(row: dict) -> dict:
    return {
        "日期": _date(row.get("DATE")),
        "代码": row.get("SCODE"),
        "名称": row.get("SECNAME"),
        "融资余额": to_float(row.get("RZYE")),
        "融券余额": to_float(row.get("RQYE")),
        "两融余额": to_float(row.get("RZRQYE")),
        "融资买入额": to_float(row.get("RZMRE")),
        "融资偿还额": to_float(row.get("RZCHE")),
        "融资净买入": to_float(row.get("RZJME")),
        "融券余量": to_float(row.get("RQYL")),
        "融券卖出量": to_float(row.get("RQMCL")),
        "融资余额占流通市值比": to_float(row.get("RZYEZB")),
        "收盘价": to_float(row.get("SPJ")),
        "涨跌幅": to_float(row.get("ZDF")),
    }


def stock_margin_detail_em(
    symbol: str = "600519",
    limit: int = 20,
    timeout: float = 15,
) -> dict:
    """
    东方财富-个股融资融券明细（按日期倒序，首条最新）

    :param symbol: 6 位股票代码
    :param limit: 返回最近多少个交易日，默认 20，上限 100
    :return: 分页 dict（items / total / _meta）；金额单位元
    """
    symbol = ensure_symbol(symbol)
    limit = clamp_page_size(limit)
    rows, total = get_report_page(
        _DETAIL_REPORT,
        filter=f'(SCODE="{symbol}")',
        sort_columns="DATE",
        sort_types="-1",
        page_size=limit,
        timeout=timeout,
    )
    items = [_parse_detail_row(row) for row in rows]
    result = make_page_result(items, page=1, page_size=limit, total=len(items))
    return attach_meta(
        result,
        _DETAIL_PROVENANCE.meta(
            degraded=False,
            extra={
                "代码": symbol,
                "最新数据日期": items[0]["日期"] if items else None,
                "历史总条数": total,
            },
        ),
    )
