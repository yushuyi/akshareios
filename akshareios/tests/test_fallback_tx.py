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


def _gen_bars(start_day: str, count: int) -> list:
    """从 start_day 起按工作日生成 count 根标准布局 bar。"""
    from datetime import date, timedelta

    bars = []
    d = date.fromisoformat(start_day)
    while len(bars) < count:
        if d.weekday() < 5:
            bars.append([
                d.isoformat(), "10.00", "10.00", "10.10", "9.90",
                "100.00", {}, "0.10", "1000.00", "",
            ])
        d += timedelta(days=1)
    return bars


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
        limit=2,
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

    # 首个年度区间已拿够 limit=2 根，立即停止，不向更早年份回溯
    assert requested == ["2026-01-01"]


def test_tx_daily_hist_active_stops_immediately(monkeypatch) -> None:
    """活跃标的近窗口数据充足，1 次请求即停，不做全历史回溯。"""
    bars = _gen_bars("2026-01-05", 260)  # 2026 区间即给足 250+ 根
    requested = _patch_tx(monkeypatch, "", "sh603517", {2026: bars})
    rows = ftx.tx_daily_hist(
        "603517",
        start_date="19700101",
        end_date="20500101",
        adjust="",
        limit=250,
        timeout=10,
    )
    assert len(rows) == 250
    assert requested == ["2026-01-01"]


def test_tx_daily_hist_delisted_returns_tail_from_recent_window(monkeypatch) -> None:
    """退市股：腾讯按结束日返回尾部 640 根（忽略起始日），最近区间即
    返回退市前数据，不得零 bar，也不需向前回溯。"""
    # 600432 吉恩镍业 2018-07 退市，请求 2026 区间真实返回 2014-2018 的数据
    bars = _gen_bars("2018-01-01", 260)
    requested = _patch_tx(monkeypatch, "", "sh600432", {2026: bars})
    rows = ftx.tx_daily_hist(
        "600432",
        start_date="19700101",
        end_date="20500101",
        adjust="",
        limit=250,
        timeout=10,
    )
    assert requested == ["2026-01-01"]
    assert len(rows) == 250
    assert rows[0]["日期"] >= "2018-01-01"
    assert rows[-1]["日期"] <= "2019-12-31"


def test_tx_daily_hist_nonexistent_code_stops_after_first_empty(monkeypatch) -> None:
    """无效代码首区间即零，不向 1970 年方向做 29 次无意义空请求。"""
    requested = _patch_tx(monkeypatch, "", "sh999999", {})
    rows = ftx.tx_daily_hist(
        "999999",
        start_date="19700101",
        end_date="20500101",
        adjust="",
        limit=250,
        timeout=10,
    )
    assert rows == []
    assert requested == ["2026-01-01"]


def test_tx_daily_hist_sparse_history_walks_back_to_floor(monkeypatch) -> None:
    """每个区间数据稀疏、不足 need_bars 时，自近向远回溯到显式
    start_date 硬下界为止，不被静默抬升，也不越过它继续请求。"""
    bars_by_year = {year: _gen_bars(f"{year}-01-01", 5)
                    for year in range(2000, 2027, 2)}
    requested = _patch_tx(monkeypatch, "", "sh603517", bars_by_year)
    rows = ftx.tx_daily_hist(
        "603517",
        start_date="20000101",
        end_date="20500101",
        adjust="",
        limit=250,
        timeout=10,
    )
    years = [p[:4] for p in requested]
    # 从 2026 步长 2 回溯，最后一个区间对必须覆盖 2000 年（2000 覆盖 2000-2001）
    assert years[0] == "2026"
    assert years[-1] == "2000"
    assert "1998" not in years
    assert len(rows) == 70  # 14 个区间 × 5 根


def test_tx_amount_wan_to_yuan() -> None:
    assert ftx._tx_amount_yuan("3430.84") == 34308400.00
    assert ftx._tx_amount_yuan({}) is None
    assert ftx._tx_amount_yuan("") is None


if __name__ == "__main__":
    import sys
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
