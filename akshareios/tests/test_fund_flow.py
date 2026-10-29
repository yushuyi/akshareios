#!/usr/bin/env python3
"""个股资金流主源/新浪降级单元测试（无需联网）"""

import pytest

import akshareios.stock_fund_flow as sff
from akshareios import _fallback_sina


EM_KLINES = [
    "2026-10-28,3000000.00,1000000.00,500000.00,-2000000.00,-500000.00,"
    "15.00,5.00,2.50,-10.00,-2.50,10.53,4.78",
    "2026-10-29,4000000.00,1500000.00,600000.00,-2500000.00,-100000.00,"
    "20.00,7.50,3.00,-12.50,-0.50,10.92,3.70",
]


def _em_boom(*args, **kwargs):
    raise ConnectionError("push2his 不可用")


# 新浪真实返回的字段形状（截取自 2026-10-29 真机数据，数值为构造值）
SINA_ROWS = [
    {
        "opendate": "2026-10-29", "trade": "10.9200", "changeratio": "0.037037",
        "r0": "1000000.00", "r1": "3000000.00", "r2": "2000000.00", "r3": "1000000.00",
        "r0_net": "400000.00", "r1_net": "200000.00", "r2_net": "-300000.00", "r3_net": "-100000.00",
    },
    {
        "opendate": "2026-10-28", "trade": "10.5300", "changeratio": "0.0477612",
        "r0": "800000.00", "r1": "2500000.00", "r2": "2200000.00", "r3": "1500000.00",
        "r0_net": "300000.00", "r1_net": "100000.00", "r2_net": "-200000.00", "r3_net": "-50000.00",
    },
]


class FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_em_primary_succeeds_sina_not_called(monkeypatch) -> None:
    called = []
    monkeypatch.setattr(sff, "get_push2his_json", lambda path, params, timeout: {"data": {"klines": EM_KLINES}})
    monkeypatch.setattr(sff, "sina_fund_flow", lambda *a, **kw: called.append(1))
    rows = sff.stock_individual_fund_flow("603517", limit=2)
    assert called == []
    assert [r["日期"] for r in rows] == ["2026-10-28", "2026-10-29"]  # 正序
    assert rows[-1]["主力净流入额"] == 4000000.00


def test_em_fails_falls_back_to_sina(monkeypatch) -> None:
    captured = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        return FakeResp(SINA_ROWS)

    monkeypatch.setattr(sff, "get_push2his_json", _em_boom)
    monkeypatch.setattr(_fallback_sina.requests, "get", fake_get)
    rows = sff.stock_individual_fund_flow("603517", limit=5)

    assert "MoneyFlow.ssl_qsfx_lscjfb" in captured["url"]
    assert captured["params"]["daima"] == "sh603517"
    assert captured["params"]["num"] == "5"
    # 新浪倒序返回 → 转正序
    assert [r["日期"] for r in rows] == ["2026-10-28", "2026-10-29"]
    latest = rows[-1]
    assert latest["超大单净流入额"] == 400000.00
    assert latest["大单净流入额"] == 200000.00
    assert latest["主力净流入额"] == 600000.00  # 主力 = 超大单 + 大单
    assert latest["中单净流入额"] == -300000.00
    assert latest["小单净流入额"] == -100000.00
    # 四档买入合计 = 成交额 7000000；占比 = 净额/成交额×100
    assert latest["主力净占比"] == round(600000 / 7000000 * 100, 2)
    assert latest["超大单净占比"] == round(400000 / 7000000 * 100, 2)
    assert latest["收盘价"] == 10.92
    assert latest["涨跌幅"] == round(0.037037 * 100, 2)  # 比值 → %


def test_fallback_limit_none_requests_250(monkeypatch) -> None:
    """limit=None/≤0 归一化后，降级 num 请求 250 全量。"""
    captured = {}
    monkeypatch.setattr(sff, "get_push2his_json", _em_boom)
    monkeypatch.setattr(
        _fallback_sina.requests, "get",
        lambda url, params=None, headers=None, timeout=None: (
            captured.update(params=params), FakeResp(SINA_ROWS)
        )[1],
    )
    sff.stock_individual_fund_flow("000001", limit=None)
    assert captured["params"]["num"] == "250"


def test_both_fail_raise_from_em_root_cause(monkeypatch) -> None:
    """主源与降级均失败时，带出主源根因（call_with_fallback 承诺）。"""
    monkeypatch.setattr(sff, "get_push2his_json", _em_boom)
    monkeypatch.setattr(
        sff, "sina_fund_flow",
        lambda *a, **kw: (_ for _ in ()).throw(ValueError("新浪也不可用")),
    )
    with pytest.raises(ValueError, match="新浪也不可用") as exc_info:
        sff.stock_individual_fund_flow("000001", limit=3)
    assert isinstance(exc_info.value.__cause__, ConnectionError)


def test_sina_non_list_returns_empty(monkeypatch) -> None:
    monkeypatch.setattr(sff, "get_push2his_json", _em_boom)
    monkeypatch.setattr(_fallback_sina.requests, "get", lambda *a, **kw: FakeResp({"errno": 1}))
    assert sff.stock_individual_fund_flow("000001", limit=3) == []


def test_sina_zero_turnover_and_missing_nets(monkeypatch) -> None:
    rows = [{"opendate": "2026-10-29", "trade": "10.92", "changeratio": "0.0",
             "r0": "0", "r1": "0", "r2": "0", "r3": "0",
             "r0_net": None, "r1_net": None, "r2_net": None, "r3_net": None}]
    monkeypatch.setattr(sff, "get_push2his_json", _em_boom)
    monkeypatch.setattr(_fallback_sina.requests, "get", lambda *a, **kw: FakeResp(rows))
    out = sff.stock_individual_fund_flow("000001", limit=1)
    # 四档净额均缺失 → 主力净额为 None（非 0），占比无成交额也为 None
    assert out[0]["主力净流入额"] is None
    assert out[0]["超大单净流入额"] is None
    assert out[0]["主力净占比"] is None
