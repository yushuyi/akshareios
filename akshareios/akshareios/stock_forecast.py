"""
业绩预告 / 业绩快报（东方财富数据中心 datacenter 报表）

真机会话（2026-11-05）里模型在推演「业绩」时，把预告中的「预增 50%」
当成了已实现业绩。同一个报告期实际存在三个披露阶段，数字不同、可靠度递增：

    业绩预告（预测区间，未经审计）
        → 业绩快报（初步核算，未经审计）
            → 正式业绩报表（已披露；本库已有 stock_yjbb_em，list 返回、不带 _meta）

因此这里每个接口都在 `_meta` 里显式声明「披露阶段」，并在「相关接口」里
指明另两个阶段该调谁；否则裸数值进上下文后，模型无从判断这是预测还是事实。

原版参考：akshare/stock_feature/stock_yjyg_em.py（stock_yjyg_em / stock_yjkb_em）
上游是按列位置硬映射字段，这里一律按报表真实 key 名取值。

三个报表在 datacenter-web 域均可查（实测 2026-11-06），统一走 get_report_page，
无需引入 securities 域。金额字段原始单位就是元，不做换算。
"""

import re

from akshareios._convert import ensure_symbol, to_float
from akshareios._datacenter import get_report_page
from akshareios._pagination import clamp_page, clamp_page_size, make_page_result
from akshareios._provenance import Provenance, attach_meta

_FORECAST_REPORT = "RPT_PUBLIC_OP_NEWPREDICT"
_EXPRESS_REPORT = "RPT_FCI_PERFORMANCEE"

_FORECAST_PROVENANCE = Provenance(
    primary_source="东方财富 datacenter（业绩预告 RPT_PUBLIC_OP_NEWPREDICT）",
    fallback_source="无（该报表无可用降级源，失败即抛错）",
    freshness="按公告日期披露，报告期结束前后均可能发布；盘中不刷新",
    primary_note="业绩预告是**预测区间**，未经审计，不是已实现业绩。"
                 "「预测金额」随「预测指标」变化（可能是归母净利润、扣非净利润或营业收入），"
                 "读数值前必须先看该行的「预测指标」，不能一律当净利润；"
                 "金额单位元，变动幅度单位 %，上下限为区间而非确定值。"
                 "同期同股可能有多条修订预告，用「是否最新」区分。"
                 "同一公司同一报告期常同时存在营业收入、归母净利润、扣非净利润等"
                 "多条不同指标的记录，不可相加、也不可当作同一口径比较。",
)

_EXPRESS_PROVENANCE = Provenance(
    primary_source="东方财富 datacenter（业绩快报 RPT_FCI_PERFORMANCEE）",
    fallback_source="无（该报表无可用降级源，失败即抛错）",
    freshness="按公告 / 更新日期披露，通常在正式财报之前；盘中不刷新",
    primary_note="业绩快报是公司**初步核算**结果，未经审计，与后续正式财报可能有差异。"
                 "金额单位元，每股收益 / 每股净资产单位元，比率与同比环比单位 %。"
                 "「净利润」为归母净利润，去年同期值用于核对同比口径。",
)

_RELATED = {
    "预测阶段": "stock_yjyg_em（业绩预告：预测区间，未经审计）",
    "初步核算阶段": "stock_yjkb_em（业绩快报：初步核算，未经审计）",
    "正式披露阶段": "stock_yjbb_em（个股业绩报表：已披露；list 返回、不带 _meta）",
}


def _iso_date(date: str | None) -> str | None:
    """20261231 / 2026-12-31 → 2026-12-31；None 表示不按报告期过滤。"""
    if date is None or str(date).strip() == "":
        return None
    text = str(date).strip()
    if re.fullmatch(r"\d{8}", text):
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text
    raise ValueError(f"无效报告期: {date!r}，需 20261231 或 2026-12-31")


def _short_date(value) -> str:
    return str(value or "")[:10]


def _build_filter(report_date: str | None, symbol: str | None) -> str:
    clauses = []
    if report_date:
        clauses.append(f"(REPORT_DATE='{report_date}')")
    if symbol:
        clauses.append(f'(SECURITY_CODE="{ensure_symbol(symbol)}")')
    return "".join(clauses)


def _empty_reason(report_date: str | None, symbol: str | None, stage: str) -> str:
    if report_date and symbol:
        return f"该股票在 {report_date} 报告期无{stage}披露记录"
    if report_date:
        return f"{report_date} 报告期暂无{stage}披露（可能尚未到披露期，或该期无公司发布）"
    if symbol:
        return f"该股票暂无{stage}披露记录"
    return f"接口未返回{stage}数据"


def _paging_hint(total: int) -> str:
    return (
        f"未指定报告期，total={total} 为全历史累计条数；"
        "请传 date 精确查某报告期，不要逐页翻全历史"
    )


def _parse_forecast_row(row: dict) -> dict:
    latest = row.get("IS_LATEST")
    return {
        "代码": row.get("SECURITY_CODE"),
        "名称": row.get("SECURITY_NAME_ABBR"),
        "报告期": _short_date(row.get("REPORT_DATE")),
        "公告日期": _short_date(row.get("NOTICE_DATE")),
        "预测指标": row.get("PREDICT_FINANCE"),
        "预告类型": row.get("PREDICT_TYPE"),
        "预测金额下限(元)": to_float(row.get("PREDICT_AMT_LOWER")),
        "预测金额上限(元)": to_float(row.get("PREDICT_AMT_UPPER")),
        "预测金额均值(元)": to_float(row.get("FORECAST_JZ")),
        "同比变动下限(%)": to_float(row.get("ADD_AMP_LOWER")),
        "同比变动上限(%)": to_float(row.get("ADD_AMP_UPPER")),
        "同比变动均值(%)": to_float(row.get("INCREASE_JZ")),
        "上年同期值(元)": to_float(row.get("PREYEAR_SAME_PERIOD")),
        "预告内容": row.get("PREDICT_CONTENT"),
        "变动原因": row.get("CHANGE_REASON_EXPLAIN"),
        "是否最新": "是" if latest == "T" else ("否" if latest == "F" else None),
        "市场板块": row.get("TRADE_MARKET"),
    }


def stock_yjyg_em(
    date: str | None = None,
    symbol: str | None = None,
    page: int = 1,
    page_size: int = 20,
    timeout: float = 15,
) -> dict:
    """
    东方财富-业绩预告（按公告日期倒序，首条最新）

    :param date: 报告期，如 "20261231" / "2026-12-31"；None 表示跨报告期取最新披露
    :param symbol: 6 位股票代码；None 表示全市场
    :param page: 页码，从 1 开始
    :param page_size: 每页条数，默认 20，上限 100
    :return: 分页 dict（items / total / has_more / _meta）
    """
    report_date = _iso_date(date)
    page = clamp_page(page)
    page_size = clamp_page_size(page_size)
    rows, total = get_report_page(
        _FORECAST_REPORT,
        filter=_build_filter(report_date, symbol),
        sort_columns="NOTICE_DATE,SECURITY_CODE",
        sort_types="-1,-1",
        page_size=page_size,
        page_number=page,
        timeout=timeout,
    )
    items = [_parse_forecast_row(row) for row in rows]
    result = make_page_result(items, page=page, page_size=page_size, total=total)

    extra = {
        "披露阶段": "业绩预告（预测区间，未经审计，非已实现业绩）",
        "报告期": report_date or "未指定（跨报告期，按公告日期倒序）",
        "最新公告日期": items[0]["公告日期"] if items else None,
        "本页预测指标": sorted({it["预测指标"] for it in items if it["预测指标"]}),
        "相关接口": _RELATED,
        "查询代码": ensure_symbol(symbol) if symbol else None,
    }
    if not items:
        extra["空结果原因"] = _empty_reason(report_date, symbol, "业绩预告")
    if report_date is None:
        # 无报告期时 count 是全历史 19 万+ 条，has_more 恒为 true；
        # 明确告诉模型别翻页，传 date 精确查（两融接口同类问题的处理）。
        extra["查询提示"] = _paging_hint(total)
    return attach_meta(result, _FORECAST_PROVENANCE.meta(degraded=False, extra=extra))


def _parse_express_row(row: dict) -> dict:
    return {
        "代码": row.get("SECURITY_CODE"),
        "名称": row.get("SECURITY_NAME_ABBR"),
        "报告期": _short_date(row.get("REPORT_DATE")),
        "季度": row.get("QDATE"),
        "报告类型": row.get("DATATYPE"),
        "公告日期": _short_date(row.get("NOTICE_DATE")),
        "更新日期": _short_date(row.get("UPDATE_DATE")),
        "每股收益(元)": to_float(row.get("BASIC_EPS")),
        "营业总收入(元)": to_float(row.get("TOTAL_OPERATE_INCOME")),
        "营业总收入去年同期(元)": to_float(row.get("TOTAL_OPERATE_INCOME_SQ")),
        "营业总收入同比(%)": to_float(row.get("YSTZ")),
        "净利润(元)": to_float(row.get("PARENT_NETPROFIT")),
        "净利润去年同期(元)": to_float(row.get("PARENT_NETPROFIT_SQ")),
        "净利润同比(%)": to_float(row.get("JLRTBZCL")),
        "每股净资产(元)": to_float(row.get("PARENT_BVPS")),
        "净资产收益率(%)": to_float(row.get("WEIGHTAVG_ROE")),
        "营业总收入季度环比(%)": to_float(row.get("DJDYSHZ")),
        "净利润季度环比(%)": to_float(row.get("DJDJLHZ")),
        "所属行业": row.get("PUBLISHNAME"),
    }


def stock_yjkb_em(
    date: str | None = None,
    symbol: str | None = None,
    page: int = 1,
    page_size: int = 20,
    timeout: float = 15,
) -> dict:
    """
    东方财富-业绩快报（初步核算，按更新日期倒序，首条最新）

    :param date: 报告期，如 "20260930"；None 表示跨报告期取最新披露
    :param symbol: 6 位股票代码；None 表示全市场
    :param page: 页码，从 1 开始
    :param page_size: 每页条数，默认 20，上限 100
    :return: 分页 dict（items / total / has_more / _meta）
    """
    report_date = _iso_date(date)
    page = clamp_page(page)
    page_size = clamp_page_size(page_size)
    rows, total = get_report_page(
        _EXPRESS_REPORT,
        filter=_build_filter(report_date, symbol),
        sort_columns="UPDATE_DATE,SECURITY_CODE",
        sort_types="-1,-1",
        page_size=page_size,
        page_number=page,
        timeout=timeout,
    )
    items = [_parse_express_row(row) for row in rows]
    result = make_page_result(items, page=page, page_size=page_size, total=total)

    extra = {
        "披露阶段": "业绩快报（初步核算，未经审计，可能与正式财报有差异）",
        "报告期": report_date or "未指定（跨报告期，按更新日期倒序）",
        "最新公告日期": items[0]["公告日期"] if items else None,
        "相关接口": _RELATED,
        "查询代码": ensure_symbol(symbol) if symbol else None,
    }
    if not items:
        extra["空结果原因"] = _empty_reason(report_date, symbol, "业绩快报")
    if report_date is None:
        extra["查询提示"] = _paging_hint(total)
    return attach_meta(result, _EXPRESS_PROVENANCE.meta(degraded=False, extra=extra))
