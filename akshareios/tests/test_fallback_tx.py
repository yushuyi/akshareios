#!/usr/bin/env python3
"""腾讯日 K 降级数据源单元测试（monkeypatch 网络，无需联网）

回归两个真机实录缺陷：
1. 腾讯 bar 成交量为 '31420.00' 小数字符串、成交额在 bar[8] 且单位万元，
   旧实现量/额/涨跌幅静默全 None（绝味会话 2026-10-10 实录）；
2. start_date 默认 19700101 时旧实现串行请求 50+ 个年度接口，
   东财断连降级时实测 14s+、设备 120s 超时。
"""

import json

import akshareios._fallback_tx as ftx


class _Resp:
    def __init__(self, text: str) -> None:
        self.text = text

    def raise_for_status(self) -> None:
        return None


def _jsonp(year: int, adj: str, tx_sym: str, bars: list) -> str:
    key = "qfqday" if adj == "qfq" else ("hfqday" if adj == "hfq" else "day")
    body = {"data": {tx_sym: {key: bars}}}
    return f"kline_day{adj}{year}={json.dumps(body, ensure_ascii=False)}"


def _patch_tx(monkeypatch, adj: str, tx_sym: str, bars_by_year: dict) -> list[str]:
    """返回记录到的请求年份列表，bars_by_year 缺年份的返回空数据。"""
    requested: list[str] = []

    def fake_get(url, params=None, timeout=None, headers=None):
        # param 形如 sh603517,day,2026-01-01,2027-12-31,640,qfq
        requested.append(params["param"].split(",")[2])
        # _var 形如 kline_dayqfq2026
        year = int(params["_var"][-4:])
        bars = bars_by_year.get(year, [])
        return _Resp(_jsonp(year, adj, tx_sym, bars))

    monkeypatch.setattr(ftx.requests, "get", fake_get)
    return requested


def test_tx_daily_hist_field_mapping(monkeypatch) -> None:
    """成交量/成交额/换手率正确解析，振幅涨跌额按相邻 bar 推算。"""
    bars = [
        ["2026-10-15", "10.57", "10.82", "10.85", "10.51", "41350.00", {}, "0.68", "4421.52", ""],
        ["2026-10-16", "10.70", "10.87", "11.02", "10.70", "31420.00", {}, "0.52", "3430.84", ""],
    ]
    requested = _patch_tx(
        monkeypatch, "qfq", "sh603517",
        {2024: [], 2025: [], 2026: bars},
    )
    rows = ftx.tx_daily_hist(
        "603517",
        start_date="19700101",
        end_date="20500101",
        adjust="qfq",
        limit=120,
        timeout=10,
        is_index=False,
    )
    assert len(rows) == 2
    first, last = rows

    # 成交量：小数字符串也能解析
    assert first["成交量"] == 41350
    assert last["成交量"] == 31420
    # 成交额：bar[8] 单位万元 → 元
    assert first["成交额"] == 44215200.00
    assert last["成交额"] == 34308400.00
    # 换手率在 bar[7]
    assert first["换手率"] == 0.68
    assert last["换手率"] == 0.52
    # 首根无前收，衍生字段留空
    assert first["涨跌额"] is None
    assert first["涨跌幅"] is None
    assert first["振幅"] is None
    # 第二根按相邻 bar 推算（与东财口径对齐）
    assert last["涨跌额"] == round(10.87 - 10.82, 3)
    assert last["涨跌幅"] == round((10.87 - 10.82) / 10.82 * 100, 2)
    assert last["振幅"] == round((11.02 - 10.70) / 10.82 * 100, 2)

    # 跨年收窄：limit=120 只需近 3 年，不得再从 1970 年起逐个请求
    assert requested == ["2024-01-01", "2025-01-01", "2026-01-01"]


def test_tx_daily_hist_year_window_250(monkeypatch) -> None:
    """limit=250（硬上限）也只请求约 3 个年度。"""
    requested = _patch_tx(monkeypatch, "", "sh603517", {})
    ftx.tx_daily_hist(
        "603517",
        start_date="19700101",
        end_date="20500101",
        adjust="",
        limit=250,
        timeout=10,
    )
    years = [p[:4] for p in requested]
    # limit=250 → ceil(250/200)+1 = 3 年缓冲
    assert years == ["2023", "2024", "2025", "2026"]


def test_tx_daily_hist_explicit_early_start(monkeypatch) -> None:
    """显式传入早于窗口的 start_date 时，实际取数仍受 250 根上限保护，
    年度窗口按 limit 收窄，不做无意义的全历史请求。"""
    requested = _patch_tx(monkeypatch, "", "sh603517", {})
    ftx.tx_daily_hist(
        "603517",
        start_date="20000101",
        end_date="20500101",
        adjust="",
        limit=60,
        timeout=10,
    )
    years = [p[:4] for p in requested]
    # limit=60 → ceil(60/200)+1 = 2 年缓冲
    assert years == ["2024", "2025", "2026"]


def test_tx_amount_wan_to_yuan() -> None:
    assert ftx._tx_amount_yuan("3430.84") == 34308400.00
    assert ftx._tx_amount_yuan({}) is None
    assert ftx._tx_amount_yuan("") is None


if __name__ == "__main__":
    import sys
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
