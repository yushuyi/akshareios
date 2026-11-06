#!/usr/bin/env python3
"""业绩预告 / 业绩快报单测（无需联网，monkeypatch 报表层）"""

import pytest

import akshareios.stock_forecast as sf
import akshareios.stock_finance as finance

_FC_ROW = {
    "SECUCODE": "688235.SH",
    "SECURITY_CODE": "688235",
    "SECURITY_NAME_ABBR": "百济神州",
    "NOTICE_DATE": "2026-11-06 00:00:00",
    "REPORT_DATE": "2026-12-31 00:00:00",
    "PREDICT_FINANCE_CODE": "006",
    "PREDICT_FINANCE": "营业收入",
    "PREDICT_AMT_LOWER": 46300000000,
    "PREDICT_AMT_UPPER": 47000000000,
    "ADD_AMP_LOWER": 21.12,
    "ADD_AMP_UPPER": 22.96,
    "PREDICT_CONTENT": "预计2026年1-12月营业收入:4,630,000万元至4,700,000万元。",
    "CHANGE_REASON_EXPLAIN": "主要得益于公司截至第三季度的业绩表现。",
    "PREDICT_TYPE": "略增",
    "PREYEAR_SAME_PERIOD": 38224999000,
    "TRADE_MARKET": "上交所科创板",
    "INCREASE_JZ": 22.04,
    "FORECAST_JZ": 46650000000,
    "IS_LATEST": "T",
}

_FC_ROW_NP = {
    **_FC_ROW,
    "PREDICT_FINANCE": "归属于上市公司股东的净利润",
    "IS_LATEST": "F",
}

_KB_ROW = {
    "SECURITY_CODE": "688235",
    "SECURITY_NAME_ABBR": "百济神州",
    "UPDATE_DATE": "2026-11-06 00:00:00",
    "REPORT_DATE": "2026-09-30 00:00:00",
    "BASIC_EPS": 4.16,
    "TOTAL_OPERATE_INCOME": 34993317000,
    "TOTAL_OPERATE_INCOME_SQ": 27595233000,
    "PARENT_NETPROFIT": 6055116000,
    "PARENT_NETPROFIT_SQ": 1138596000,
    "PARENT_BVPS": 26.62,
    "WEIGHTAVG_ROE": 17.27,
    "YSTZ": 26.809282603267,
    "JLRTBZCL": 431.805486757375,
    "DJDYSHZ": 9.406843687661,
    "DJDJLHZ": 67.4587791397,
    "PUBLISHNAME": "化学制药",
    "NOTICE_DATE": "2026-11-06 00:00:00",
    "QDATE": "2026Q3",
    "DATATYPE": "2026年 三季报",
}


def test_forecast_fields_not_scaled(monkeypatch):
    """业绩预告金额原始单位就是元，不做任何换算"""
    monkeypatch.setattr(sf, "get_report_page", lambda *a, **k: ([_FC_ROW], 49))
    it = sf.stock_yjyg_em(date="20261231")["items"][0]
    assert it["代码"] == "688235"
    assert it["报告期"] == "2026-12-31"
    assert it["公告日期"] == "2026-11-06"
    assert it["预测指标"] == "营业收入"
    assert it["预测金额下限(元)"] == 46300000000.0
    assert it["预测金额上限(元)"] == 47000000000.0
    assert it["同比变动下限(%)"] == 21.12
    assert it["上年同期值(元)"] == 38224999000.0
    assert it["是否最新"] == "是"
    assert it["预告类型"] == "略增"


def test_forecast_meta_declares_stage_and_related(monkeypatch):
    """_meta 必须写明「预测、未经审计」，并指路另外两个披露阶段"""
    monkeypatch.setattr(sf, "get_report_page", lambda *a, **k: ([_FC_ROW], 49))
    meta = sf.stock_yjyg_em(date="20261231")["_meta"]
    assert "预测区间" in meta["披露阶段"]
    assert "未经审计" in meta["披露阶段"]
    assert "预测指标" in meta["口径说明"]
    assert "不可相加" in meta["口径说明"]
    assert meta["报告期"] == "2026-12-31"
    assert meta["最新公告日期"] == "2026-11-06"
    assert set(meta["相关接口"]) == {"预测阶段", "初步核算阶段", "正式披露阶段"}
    assert "stock_yjbb_em" in meta["相关接口"]["正式披露阶段"]


def test_related_interfaces_have_no_wrong_self_reference(monkeypatch):
    """快报调用时不能出现「本接口=业绩预告」这种自指错误"""
    monkeypatch.setattr(sf, "get_report_page", lambda *a, **k: ([_KB_ROW], 13))
    related = sf.stock_yjkb_em()["_meta"]["相关接口"]
    assert all("本接口" not in v for v in related.values())


def test_forecast_metrics_deduplicated_in_meta(monkeypatch):
    """同一公司同期有多条不同指标时，_meta 要列出全部，防止模型相加"""
    monkeypatch.setattr(
        sf, "get_report_page", lambda *a, **k: ([_FC_ROW, _FC_ROW_NP], 49)
    )
    meta = sf.stock_yjyg_em(date="20261231")["_meta"]
    assert len(meta["本页预测指标"]) == 2
    assert "营业收入" in meta["本页预测指标"]
    assert "归属于上市公司股东的净利润" in meta["本页预测指标"]


@pytest.mark.parametrize("date", ["20261231", "2026-12-31"])
def test_date_formats_build_report_date_filter(monkeypatch, date):
    captured = {}

    def fake(*args, **kwargs):
        captured.update(kwargs)
        return [_FC_ROW], 49

    monkeypatch.setattr(sf, "get_report_page", fake)
    sf.stock_yjyg_em(date=date)
    assert captured["filter"] == "(REPORT_DATE='2026-12-31')"
    assert captured["sort_columns"] == "NOTICE_DATE,SECURITY_CODE"


def test_symbol_and_date_filter_combined(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        sf, "get_report_page", lambda *a, **k: (captured.update(k) or [], 0)
    )
    sf.stock_yjyg_em(date="20261231", symbol="600519")
    assert captured["filter"] == "(REPORT_DATE='2026-12-31')(SECURITY_CODE=\"600519\")"


def test_invalid_date_raises():
    with pytest.raises(ValueError, match="无效报告期"):
        sf.stock_yjyg_em(date="2026/12/31")


def test_invalid_symbol_raises():
    with pytest.raises(ValueError, match="无效的股票代码"):
        sf.stock_yjkb_em(symbol="茅台")


def test_no_date_adds_paging_hint(monkeypatch):
    """未指定报告期时 total 是全历史 19 万+，必须提示别翻页"""
    monkeypatch.setattr(sf, "get_report_page", lambda *a, **k: ([_FC_ROW], 191440))
    r = sf.stock_yjyg_em()
    assert r["total"] == 191440
    assert "不要逐页翻全历史" in r["_meta"]["查询提示"]
    assert "跨报告期" in r["_meta"]["报告期"]


def test_with_date_has_no_paging_hint(monkeypatch):
    monkeypatch.setattr(sf, "get_report_page", lambda *a, **k: ([_FC_ROW], 49))
    assert "查询提示" not in sf.stock_yjyg_em(date="20261231")["_meta"]


@pytest.mark.parametrize(
    "kwargs,expected",
    [
        ({"date": "20271231"}, "报告期暂无"),
        ({"symbol": "600519"}, "该股票暂无"),
        ({"date": "20271231", "symbol": "600519"}, "该股票在"),
        ({}, "接口未返回"),
    ],
)
def test_empty_reason_varies_by_query(monkeypatch, kwargs, expected):
    monkeypatch.setattr(sf, "get_report_page", lambda *a, **k: ([], 0))
    meta = sf.stock_yjyg_em(**kwargs)["_meta"]
    assert expected in meta["空结果原因"]
    assert meta["最新公告日期"] is None
    assert meta["本页预测指标"] == []


def test_paging_uses_real_total(monkeypatch):
    monkeypatch.setattr(sf, "get_report_page", lambda *a, **k: ([_FC_ROW], 49))
    r = sf.stock_yjyg_em(date="20261231", page=1, page_size=2)
    assert r["total"] == 49
    assert r["total_pages"] == 25
    assert r["has_more"] is True


def test_page_size_clamped(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        sf, "get_report_page", lambda *a, **k: (captured.update(k) or [], 0)
    )
    sf.stock_yjyg_em(page=0, page_size=1000)
    assert captured["page_size"] == 100
    assert captured["page_number"] == 1


def test_express_fields_and_units(monkeypatch):
    monkeypatch.setattr(sf, "get_report_page", lambda *a, **k: ([_KB_ROW], 13))
    it = sf.stock_yjkb_em(date="20260930")["items"][0]
    assert it["季度"] == "2026Q3"
    assert it["报告期"] == "2026-09-30"
    assert it["每股收益(元)"] == 4.16
    assert it["营业总收入(元)"] == 34993317000.0
    assert it["营业总收入去年同期(元)"] == 27595233000.0
    assert it["净利润(元)"] == 6055116000.0
    assert it["净利润同比(%)"] == pytest.approx(431.805486757375)
    assert it["营业总收入季度环比(%)"] == pytest.approx(9.406843687661)
    assert it["所属行业"] == "化学制药"


def test_express_meta_stage_and_hint(monkeypatch):
    monkeypatch.setattr(sf, "get_report_page", lambda *a, **k: ([_KB_ROW], 13))
    meta = sf.stock_yjkb_em()["_meta"]
    assert "初步核算" in meta["披露阶段"]
    assert "未经审计" in meta["披露阶段"]
    assert meta["最新公告日期"] == "2026-11-06"
    assert "跨报告期" in meta["报告期"]
    assert "不要逐页翻全历史" in meta["查询提示"]


def test_express_sort_and_report_name(monkeypatch):
    captured = {}

    def fake(report, **kwargs):
        captured["report"] = report
        captured.update(kwargs)
        return [_KB_ROW], 13

    monkeypatch.setattr(sf, "get_report_page", fake)
    sf.stock_yjkb_em(date="20260930")
    assert captured["report"] == "RPT_FCI_PERFORMANCEE"
    assert captured["sort_columns"] == "UPDATE_DATE,SECURITY_CODE"
    assert captured["filter"] == "(REPORT_DATE='2026-09-30')"


def test_forecast_report_name(monkeypatch):
    captured = {}

    def fake(report, **kwargs):
        captured["report"] = report
        return [_FC_ROW], 49

    monkeypatch.setattr(sf, "get_report_page", fake)
    sf.stock_yjyg_em(date="20261231")
    assert captured["report"] == "RPT_PUBLIC_OP_NEWPREDICT"


def test_express_empty_reason(monkeypatch):
    monkeypatch.setattr(sf, "get_report_page", lambda *a, **k: ([], 0))
    meta = sf.stock_yjkb_em(date="20271231")["_meta"]
    assert "业绩快报" in meta["空结果原因"]


def test_existing_yjbb_contract_unchanged(monkeypatch):
    """正式业绩报表仍是 list 返回、不带 _meta，新接口不能破坏既有契约"""
    monkeypatch.setattr(
        finance, "get_report", lambda *a, **k: [{"REPORTDATE": "2026-09-30 00:00:00", "BASIC_EPS": 0.01}]
    )
    rows = finance.stock_yjbb_em("600519")
    assert isinstance(rows, list)
    assert "_meta" not in rows[0]
    assert rows[0]["报告期"] == "2026-09-30"
