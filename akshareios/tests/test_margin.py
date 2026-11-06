#!/usr/bin/env python3
"""两融余额接口单测（无需联网，monkeypatch 报表层）"""

import pytest

import akshareios.stock_margin as sm

_MARKET_ROW = {
    "STATISTICS_DATE": "2026-11-05 00:00:00",
    "FIN_BALANCE": 22785.1390914,
    "LOAN_BALANCE": 288.19109676,
    "MARGIN_BALANCE": 23073.33018816,
    "FIN_BUY_AMT": 1870.75746231,
    "LOAN_SELL_AMT": 11.15900279,
    "MARGIN_TRADE_AMT": 1881.91646511,
    "TOTAL_GUARANTEE": 71450.94162551,
    "BALANCE_RATIO": 2.4546,
    "TRADE_AMT_RATIO": 8.8142,
    "AVG_GUARANTEE_RATIO": 262.6319,
    "SCI_CLOSE_PRICE": 3689.9109,
    "SCI_CHANGE_RATE": 1.188483320774,
    "INVESTOR_NUM": 422427,
    "MARGINLIAB_INVESTOR_NUM": 1974858,
}

_DETAIL_ROW = {
    "DATE": "2026-11-05 00:00:00",
    "SCODE": "600519",
    "SECNAME": "贵州茅台",
    "RZYE": 15199205505,
    "RQYE": 310510200,
    "RZRQYE": 15509715705,
    "RZMRE": 408291828,
    "RZCHE": 369027030,
    "RZJME": 39264798,
    "RQYL": 213850,
    "RQMCL": 7700,
    "RZYEZB": 0.83736713,
    "SPJ": 1452,
    "ZDF": 0.3844,
}


def test_market_amount_yi_to_yuan(monkeypatch):
    """市场报表金额单位是亿元，必须换算成元（否则量级差 1 亿倍）"""
    monkeypatch.setattr(sm, "get_report_page", lambda *a, **k: ([_MARKET_ROW], 3422))
    r = sm.stock_margin_balance_em(limit=2)
    it = r["items"][0]
    assert it["融资余额"] == pytest.approx(22785.1390914 * 1e8)
    assert it["两融余额"] == pytest.approx(23073.33018816 * 1e8)
    assert it["融资买入额"] == pytest.approx(1870.75746231 * 1e8)


def test_market_percent_fields_not_scaled(monkeypatch):
    """百分比 / 指数点位不是金额，不能被亿元换算误伤"""
    monkeypatch.setattr(sm, "get_report_page", lambda *a, **k: ([_MARKET_ROW], 3422))
    it = sm.stock_margin_balance_em()["items"][0]
    assert it["两融余额占流通市值比"] == 2.4546
    assert it["平均维持担保比例"] == 262.6319
    assert it["上证指数收盘"] == 3689.9109
    assert it["参与交易投资者数"] == 422427


def test_total_is_returned_rows_not_history_count(monkeypatch):
    """取最近 N 条时 total 不能是全历史条数，否则 has_more 诱导翻上千页"""
    monkeypatch.setattr(sm, "get_report_page", lambda *a, **k: ([_MARKET_ROW], 3422))
    r = sm.stock_margin_balance_em(limit=2)
    assert r["total"] == 1
    assert r["has_more"] is False
    assert r["_meta"]["历史总条数"] == 3422


def test_market_meta_declares_t_minus_1(monkeypatch):
    monkeypatch.setattr(sm, "get_report_page", lambda *a, **k: ([_MARKET_ROW], 3422))
    meta = sm.stock_margin_balance_em()["_meta"]
    assert meta["状态"] == "主源"
    assert "T-1" in meta["数据时间"]
    assert "亿元" in meta["口径说明"]
    assert meta["最新数据日期"] == "2026-11-05"


def test_detail_amount_already_yuan(monkeypatch):
    """个股报表金额本来就是元，不能再乘 1e8"""
    monkeypatch.setattr(sm, "get_report_page", lambda *a, **k: ([_DETAIL_ROW], 4013))
    r = sm.stock_margin_detail_em("600519")
    it = r["items"][0]
    assert it["融资余额"] == 15199205505.0
    assert it["融资净买入"] == 39264798.0
    assert it["名称"] == "贵州茅台"
    assert r["_meta"]["代码"] == "600519"


def test_detail_filter_uses_scode(monkeypatch):
    """实测报表列是 SCODE / DATE，写成 SECURITY_CODE 会被东财报 9501"""
    captured = {}

    def fake(*args, **kwargs):
        captured.update(kwargs)
        return [_DETAIL_ROW], 4013

    monkeypatch.setattr(sm, "get_report_page", fake)
    sm.stock_margin_detail_em("600519", limit=3)
    assert captured["filter"] == '(SCODE="600519")'
    assert captured["sort_columns"] == "DATE"
    assert captured["page_size"] == 3


def test_invalid_symbol_raises():
    with pytest.raises(ValueError, match="无效的股票代码"):
        sm.stock_margin_detail_em("茅台")


def test_empty_rows_meta_has_no_latest_date(monkeypatch):
    monkeypatch.setattr(sm, "get_report_page", lambda *a, **k: ([], 0))
    r = sm.stock_margin_balance_em()
    assert r["items"] == []
    assert r["_meta"]["最新数据日期"] is None
