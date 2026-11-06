"""
龙虎榜（榜单 / 买卖席位明细）

数据源：东方财富数据中心 datacenter 报表，单一主源、无可用降级源。
原版参考：akshare/stock_feature/stock_lhb_em.py
→ stock_lhb_detail_em() / stock_lhb_stock_detail_em()

真机会话（2026-11-05）里模型在推演「席位资金 / 游资」时说「接口我没有」，
这里补榜单与席位。数据由交易所收盘后披露，**盘中没有当日龙虎榜**；
查不到时返回合法空结果并在 `_meta` 说明原因，不伪装成异常、也不写成 0 条成交。
"""

from datetime import datetime, timedelta

from akshareios._convert import ensure_symbol, to_float
from akshareios._datacenter import get_report_page
from akshareios._pagination import (
    DEFAULT_PAGE_SIZE,
    clamp_page,
    clamp_page_size,
    make_page_result,
)
from akshareios._provenance import Provenance, attach_meta

_DETAIL_REPORT = "RPT_DAILYBILLBOARD_DETAILSNEW"
_SEAT_REPORTS = {
    "买入": ("RPT_BILLBOARD_DAILYDETAILSBUY", "BUY"),
    "卖出": ("RPT_BILLBOARD_DAILYDETAILSSELL", "SELL"),
}

_DETAIL_PROVENANCE = Provenance(
    primary_source="东方财富 datacenter（龙虎榜详情）",
    fallback_source="无（该报表无可用降级源，失败即抛错）",
    freshness="当日收盘后披露，盘中无当日数据",
    primary_note="按上榜日倒序；金额单位元、价格单位元、比率与涨跌幅单位 %。"
                 "同一只股票同一天可能因多个上榜原因出现多行；"
                 "「上榜后 N 日」为历史复盘涨跌幅，未到天数时为 null，不是 0。",
)

_SEAT_PROVENANCE = Provenance(
    primary_source="东方财富 datacenter（龙虎榜买卖席位）",
    fallback_source="无（该报表无可用降级源，失败即抛错）",
    freshness="当日收盘后披露，盘中无当日数据",
    primary_note="买入榜 / 卖出榜各最多 5 个营业部席位，金额单位元；"
                 "净额为负表示净卖出；占总成交比单位 %。"
                 "「全部」模式把两榜合在一个 items 里，用「方向」区分，不要相加去重。",
)


def _iso_date(value) -> str:
    """YYYYMMDD / YYYY-MM-DD → YYYY-MM-DD（datacenter filter 需要带横杠）。"""
    if value is None:
        return datetime.now().strftime("%Y-%m-%d")
    text = str(value).strip().replace("-", "").replace("/", "")
    if len(text) != 8 or not text.isdigit():
        raise ValueError(f"日期格式应为 YYYYMMDD 或 YYYY-MM-DD: {value!r}")
    return f"{text[:4]}-{text[4:6]}-{text[6:8]}"


def _parse_detail_row(row: dict, *, rank: int) -> dict:
    return {
        "序号": rank,
        "代码": row.get("SECURITY_CODE"),
        "名称": row.get("SECURITY_NAME_ABBR"),
        "上榜日": str(row.get("TRADE_DATE") or "")[:10],
        "解读": row.get("EXPLAIN"),
        "上榜原因": row.get("EXPLANATION"),
        "收盘价": to_float(row.get("CLOSE_PRICE")),
        "涨跌幅": to_float(row.get("CHANGE_RATE")),
        "龙虎榜净买额": to_float(row.get("BILLBOARD_NET_AMT")),
        "龙虎榜买入额": to_float(row.get("BILLBOARD_BUY_AMT")),
        "龙虎榜卖出额": to_float(row.get("BILLBOARD_SELL_AMT")),
        "龙虎榜成交额": to_float(row.get("BILLBOARD_DEAL_AMT")),
        "市场总成交额": to_float(row.get("ACCUM_AMOUNT")),
        "净买额占总成交比": to_float(row.get("DEAL_NET_RATIO")),
        "成交额占总成交比": to_float(row.get("DEAL_AMOUNT_RATIO")),
        "换手率": to_float(row.get("TURNOVERRATE")),
        "流通市值": to_float(row.get("FREE_MARKET_CAP")),
        "上榜后1日": to_float(row.get("D1_CLOSE_ADJCHRATE")),
        "上榜后2日": to_float(row.get("D2_CLOSE_ADJCHRATE")),
        "上榜后5日": to_float(row.get("D5_CLOSE_ADJCHRATE")),
        "上榜后10日": to_float(row.get("D10_CLOSE_ADJCHRATE")),
    }


def stock_lhb_detail_em(
    start_date: str | None = None,
    end_date: str | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    timeout: float = 15,
) -> dict:
    """
    东方财富-龙虎榜详情（分页，按上榜日倒序）

    :param start_date: 开始日期 YYYYMMDD / YYYY-MM-DD，默认最近 7 天
    :param end_date: 结束日期，默认今天
    :param page: 页码，从 1 开始
    :param page_size: 每页条数，默认 20，最大 100
    :return: 分页 dict（items / total / _meta）
    """
    page = clamp_page(page)
    page_size = clamp_page_size(page_size)
    end = _iso_date(end_date)
    if start_date is not None:
        start = _iso_date(start_date)
    else:
        # 传了 end_date 时也要相对它回溯 7 天，不能让默认区间退化成单日。
        start = (datetime.strptime(end, "%Y-%m-%d") - timedelta(days=7)).strftime(
            "%Y-%m-%d"
        )
    rows, total = get_report_page(
        _DETAIL_REPORT,
        filter=f"(TRADE_DATE>='{start}')(TRADE_DATE<='{end}')",
        sort_columns="TRADE_DATE,SECURITY_CODE",
        sort_types="-1,1",
        page_size=page_size,
        page_number=page,
        timeout=timeout,
    )
    base_rank = (page - 1) * page_size
    items = [
        _parse_detail_row(row, rank=base_rank + idx + 1)
        for idx, row in enumerate(rows)
    ]
    extra = {"查询区间": f"{start} ~ {end}"}
    if not items:
        extra["空结果原因"] = (
            f"{start} ~ {end} 内无龙虎榜记录：可能是非交易日 / 当日尚未收盘披露 / "
            "该区间确实无个股上榜，不可当作「上榜但成交为 0」"
        )
    result = make_page_result(items, page=page, page_size=page_size, total=total)
    return attach_meta(result, _DETAIL_PROVENANCE.meta(degraded=False, extra=extra))


def _parse_seat_row(row: dict, *, rank: int, direction: str) -> dict:
    return {
        "序号": rank,
        "方向": direction,
        "营业部": row.get("OPERATEDEPT_NAME"),
        "营业部代码": row.get("OPERATEDEPT_CODE"),
        "买入金额": to_float(row.get("BUY")),
        "卖出金额": to_float(row.get("SELL")),
        "净额": to_float(row.get("NET")),
        "买入金额占总成交比": to_float(row.get("TOTAL_BUYRIO")),
        "卖出金额占总成交比": to_float(row.get("TOTAL_SELLRIO")),
        "上榜原因": row.get("EXPLANATION"),
    }


def stock_lhb_stock_detail_em(
    symbol: str = "000525",
    date: str | None = None,
    flag: str = "全部",
    timeout: float = 15,
) -> dict:
    """
    东方财富-个股龙虎榜买卖席位明细

    :param symbol: 6 位股票代码
    :param date: 上榜日 YYYYMMDD / YYYY-MM-DD，默认今天；可先用
                 stock_lhb_detail_em 查该股实际的上榜日
    :param flag: 买入 / 卖出 / 全部（默认，两榜合并、每行带「方向」）
    :return: 分页 dict（items / total / _meta）
    """
    if flag not in ("买入", "卖出", "全部"):
        raise ValueError(f"flag 只能是 买入 / 卖出 / 全部，收到: {flag!r}")
    symbol = ensure_symbol(symbol)
    trade_date = _iso_date(date)
    directions = ("买入", "卖出") if flag == "全部" else (flag,)

    items: list[dict] = []
    for direction in directions:
        report, sort_column = _SEAT_REPORTS[direction]
        rows, _ = get_report_page(
            report,
            filter=f"(TRADE_DATE='{trade_date}')(SECURITY_CODE=\"{symbol}\")",
            sort_columns=sort_column,
            sort_types="-1",
            page_size=50,
            timeout=timeout,
        )
        for idx, row in enumerate(rows):
            items.append(_parse_seat_row(row, rank=idx + 1, direction=direction))

    extra = {"代码": symbol, "上榜日": trade_date, "查询方向": flag}
    if not items:
        extra["空结果原因"] = (
            f"{symbol} 在 {trade_date} 无龙虎榜席位数据：通常是该股当日未上榜，"
            "也可能是非交易日 / 当日尚未收盘披露；不是「上榜但买卖金额为 0」"
        )
    result = make_page_result(
        items, page=1, page_size=max(len(items), 1), total=len(items)
    )
    return attach_meta(result, _SEAT_PROVENANCE.meta(degraded=False, extra=extra))
