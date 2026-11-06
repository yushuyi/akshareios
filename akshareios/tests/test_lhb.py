#!/usr/bin/env python3
"""龙虎榜 / datacenter 报表层单测（无需联网）"""

import pytest

import akshareios._datacenter as dc
import akshareios.stock_lhb as lhb

_DETAIL_ROW = {
    "SECURITY_CODE": "000525",
    "SECURITY_NAME_ABBR": "红太阳",
    "TRADE_DATE": "2026-11-06 00:00:00",
    "EXPLAIN": "普通席位买入",
    "EXPLANATION": "日涨幅偏离值达到7%的前5只证券",
    "CLOSE_PRICE": 5.02,
    "CHANGE_RATE": 10.0877,
    "BILLBOARD_NET_AMT": 98694262.06,
    "BILLBOARD_BUY_AMT": 148944265.27,
    "BILLBOARD_SELL_AMT": 50250003.21,
    "BILLBOARD_DEAL_AMT": 199194268.48,
    "ACCUM_AMOUNT": 593597267.0,
    "DEAL_NET_RATIO": 16.626468406567,
    "DEAL_AMOUNT_RATIO": 33.557140430702,
    "TURNOVERRATE": 11.3403,
    "FREE_MARKET_CAP": 5581035225.1,
    "D1_CLOSE_ADJCHRATE": None,
    "D2_CLOSE_ADJCHRATE": None,
    "D5_CLOSE_ADJCHRATE": None,
    "D10_CLOSE_ADJCHRATE": None,
}

_SEAT_ROW = {
    "OPERATEDEPT_NAME": "国泰海通证券上海江苏路营业部",
    "OPERATEDEPT_CODE": "10025080",
    "BUY": 49883529,
    "SELL": 274743,
    "NET": 49608786,
    "TOTAL_BUYRIO": 0.084035981587,
    "TOTAL_SELLRIO": 0.000462844112,
    "EXPLANATION": "日涨幅偏离值达到7%的前5只证券",
}


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_datacenter_empty_is_legal(monkeypatch):
    """9201「返回数据为空」是合法空结果，不能当异常"""
    payload = {"success": False, "code": "9201", "message": "返回数据为空", "result": None}
    monkeypatch.setattr(dc, "get", lambda *a, **k: _Resp(payload))
    assert dc.get_report_page("X") == ([], 0)


def test_datacenter_bad_column_raises(monkeypatch):
    """9501「列不存在 / 报表配置不存在」必须抛，不能静默变空列表"""
    payload = {
        "success": False,
        "code": "9501",
        "message": "SECURITY_CODE列不存在",
        "result": None,
    }
    monkeypatch.setattr(dc, "get", lambda *a, **k: _Resp(payload))
    with pytest.raises(ValueError, match="SECURITY_CODE列不存在"):
        dc.get_report_page("X")


def test_datacenter_returns_real_total(monkeypatch):
    payload = {"success": True, "result": {"data": [{"a": 1}], "count": 404}}
    monkeypatch.setattr(dc, "get", lambda *a, **k: _Resp(payload))
    rows, total = dc.get_report_page("X")
    assert rows == [{"a": 1}] and total == 404


def test_lhb_detail_fields_and_meta(monkeypatch):
    monkeypatch.setattr(lhb, "get_report_page", lambda *a, **k: ([_DETAIL_ROW], 404))
    r = lhb.stock_lhb_detail_em(start_date="20261101", end_date="20261106")
    it = r["items"][0]
    assert it["序号"] == 1
    assert it["代码"] == "000525"
    assert it["上榜日"] == "2026-11-06"
    assert it["龙虎榜净买额"] == 98694262.06
    assert it["上榜后1日"] is None          # 未到天数 ≠ 0
    assert r["total"] == 404
    assert "收盘后" in r["_meta"]["数据时间"]


def test_lhb_default_window_is_relative_to_end_date(monkeypatch):
    """只传 end_date 时默认起点要相对它回溯 7 天，不能退化成单日"""
    captured = {}
    monkeypatch.setattr(
        lhb,
        "get_report_page",
        lambda *a, **k: (captured.update(k) or [], 0),
    )
    lhb.stock_lhb_detail_em(end_date="20261106")
    assert "2026-10-30" in captured["filter"]
    assert "2026-11-06" in captured["filter"]


def test_lhb_empty_explains_reason(monkeypatch):
    monkeypatch.setattr(lhb, "get_report_page", lambda *a, **k: ([], 0))
    r = lhb.stock_lhb_detail_em(start_date="20261101", end_date="20261101")
    assert r["items"] == []
    assert "不可当作" in r["_meta"]["空结果原因"]


def test_seat_all_mode_merges_two_reports(monkeypatch):
    calls = []

    def fake(report, **kwargs):
        calls.append(report)
        return [_SEAT_ROW], 5

    monkeypatch.setattr(lhb, "get_report_page", fake)
    r = lhb.stock_lhb_stock_detail_em("000525", "20261106")
    assert calls == ["RPT_BILLBOARD_DAILYDETAILSBUY", "RPT_BILLBOARD_DAILYDETAILSSELL"]
    assert len(r["items"]) == 2
    assert r["items"][0]["方向"] == "买入"
    assert r["items"][1]["方向"] == "卖出"
    assert r["items"][0]["净额"] == 49608786.0
    assert r["_meta"]["查询方向"] == "全部"


def test_seat_single_flag_and_bad_flag(monkeypatch):
    monkeypatch.setattr(lhb, "get_report_page", lambda *a, **k: ([_SEAT_ROW], 5))
    r = lhb.stock_lhb_stock_detail_em("000525", "2026-11-06", flag="卖出")
    assert len(r["items"]) == 1
    assert r["items"][0]["方向"] == "卖出"
    with pytest.raises(ValueError, match="flag"):
        lhb.stock_lhb_stock_detail_em("000525", flag="买盘")


def test_seat_empty_not_zero_amount(monkeypatch):
    monkeypatch.setattr(lhb, "get_report_page", lambda *a, **k: ([], 0))
    r = lhb.stock_lhb_stock_detail_em("600519", "20261105")
    assert r["items"] == []
    assert "未上榜" in r["_meta"]["空结果原因"]


def test_bad_date_raises():
    with pytest.raises(ValueError, match="日期格式"):
        lhb.stock_lhb_stock_detail_em("000525", "2026-1-6")
