#!/usr/bin/env python3
"""涨停池空列表歧义单测（无需联网）"""

import pytest

import akshareios.stock_zt as zt

_ROW = {
    "c": "002578", "n": "闽发铝业", "p": 5010, "zdp": 10.1099,
    "amount": 538747056, "ltsz": 4314424430.61, "tshare": 4702537181.76,
    "hs": 12.5048, "lbc": 5, "fbt": 92500, "lbt": 93009,
    "fund": 220341804, "zbc": 1, "hybk": "工业金属",
    "zttj": {"days": 10, "ct": 6},
}


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def mock_response(monkeypatch, payload):
    monkeypatch.setattr(zt, "get", lambda *a, **k: _Resp(payload))


def test_trading_day_pool_has_no_empty_reason(monkeypatch):
    mock_response(monkeypatch, {"data": {"qdate": 20261106, "tc": 32, "pool": [_ROW]}})
    r = zt.stock_zt_pool_em(date="20261106")
    assert r["total"] == 32
    assert r["items"][0]["最新价"] == pytest.approx(5.01)
    assert r["items"][0]["连板数"] == 5
    assert "空结果原因" not in r["_meta"]
    assert r["_meta"]["交易日判定"] == "请求日与服务端池日期一致"


def test_non_trading_day_empty_is_not_zero_limit_up(monkeypatch):
    """周日请求：tc=0/pool=[] 与「当日 0 只涨停」同形，靠 qdate 拆开"""
    mock_response(monkeypatch, {"data": {"qdate": 20261106, "tc": 0, "pool": []}})
    r = zt.stock_zt_pool_em(date="20261101")
    assert r["items"] == [] and r["total"] == 0
    assert r["_meta"]["交易日判定"] == "未返回该日池数据"
    assert "不等于" in r["_meta"]["空结果原因"]
    assert r["_meta"]["请求日期"] == "20261101"
    assert r["_meta"]["服务端最新池日期"] == "20261106"


def test_same_day_zero_is_real_no_limit_up(monkeypatch):
    """qdate 与请求日一致且 tc=0，才是「当日确无涨停」"""
    mock_response(monkeypatch, {"data": {"qdate": 20261106, "tc": 0, "pool": []}})
    r = zt.stock_zt_pool_em(date="20261106")
    assert r["_meta"]["交易日判定"] == "交易日且已有当日池数据"
    assert "当日确无涨停股" in r["_meta"]["空结果原因"]


def test_page_out_of_range(monkeypatch):
    mock_response(monkeypatch, {"data": {"qdate": 20261106, "tc": 32, "pool": []}})
    r = zt.stock_zt_pool_em(date="20261106", page=9)
    assert "页码越界" in r["_meta"]["空结果原因"]


def test_no_data_body_is_explained(monkeypatch):
    for payload in ({"data": None}, {"rc": 0}):
        mock_response(monkeypatch, payload)
        r = zt.stock_zt_pool_em(date="20261101")
        assert r["items"] == []
        assert r["_meta"]["交易日判定"] == "未知"
        assert "不可解读" in r["_meta"]["空结果原因"]


def test_meta_declares_source_and_freshness(monkeypatch):
    mock_response(monkeypatch, {"data": {"qdate": 20261106, "tc": 1, "pool": [_ROW]}})
    meta = zt.stock_zt_pool_em(date="20261106")["_meta"]
    assert meta["状态"] == "主源"
    assert "push2ex" in meta["数据源"]
    assert "空结果原因" in meta["口径说明"]


def test_date_normalization_and_validation(monkeypatch):
    captured = {}

    def fake_get(url, params=None, timeout=None, **kwargs):
        captured.update(params)
        return _Resp({"data": {"qdate": 20261106, "tc": 0, "pool": []}})

    monkeypatch.setattr(zt, "get", fake_get)
    zt.stock_zt_pool_em(date="2026-11-01")
    assert captured["date"] == "20261101"
    with pytest.raises(ValueError, match="date 格式"):
        zt.stock_zt_pool_em(date="上周日")
