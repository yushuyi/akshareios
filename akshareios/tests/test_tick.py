#!/usr/bin/env python3
"""分笔成交明细的单元测试（monkeypatch 网络，无需联网）"""

import pytest
import requests

import akshareios.stock_tick as st


class _Resp:
    """构造 requests.Response 的最小替身。"""

    def __init__(self, text: str = "", status_code: int = 200) -> None:
        self.text = text
        self.status_code = status_code
        self.encoding = None

    def raise_for_status(self) -> None:
        pass


# ---------------------------------------------------------------- 腾讯源

def _tx_page(p: int) -> _Resp:
    if p == 0:
        return _Resp(
            'v_detail_data_sh603517=[0,"0/09:25:00/11.20/0.00/471/527520/S'
            '|1/09:30:02/11.23/0.03/10/11230/B"]'
        )
    return _Resp('v_detail_data_sh603517=[0,""]')


def test_tick_tx_parse(monkeypatch) -> None:
    monkeypatch.setattr(
        st, "get",
        lambda url, params=None, timeout=None, headers=None: _tx_page(params["p"]),
    )
    rows = st.stock_zh_a_tick_tx("603517")
    assert len(rows) == 2
    assert rows[0]["成交时间"] == "09:25:00"
    assert rows[0]["性质"] == "卖盘" and rows[1]["性质"] == "买盘"
    assert rows[0]["成交量"] == 471 and rows[0]["成交金额"] == 527520
    assert rows[1]["成交价格"] == 11.23 and rows[1]["价格变动"] == 0.03


# ---------------------------------------------------------------- 东财源

def test_tick_em_parse(monkeypatch) -> None:
    def fake_json(path, params, timeout=15):
        return {"details": [
            "09:15:15,11.18,36,0,4",
            "09:30:00,11.21,1498,45,1",
            "09:30:03,11.20,10,2,2",
        ]}

    monkeypatch.setattr(st, "get_push2_json", fake_json)
    rows = st.stock_zh_a_tick_em("603517")
    assert len(rows) == 3
    assert rows[0]["性质"] == "中性盘"   # 标记 4
    assert rows[1]["性质"] == "买盘"   # 标记 1
    assert rows[2]["性质"] == "卖盘"   # 标记 2
    assert rows[1]["成交笔数"] == 45
    assert rows[0]["成交时间"] == "09:15:15"


# ---------------------------------------------------------------- 网易源

_HTML = (
    "<table>"
    "<tr><td>09:25:00</td><td>11.20</td><td>0.00</td>"
    "<td>471</td><td>527,520</td><td>卖盘</td></tr>"
    "<tr><td>15:00:00</td><td>11.21</td><td>0.01</td>"
    "<td>1498</td><td>1,679,258</td><td>中性盘</td></tr>"
    "</table>"
)


def test_tick_163_parse(monkeypatch) -> None:
    monkeypatch.setattr(
        st, "get",
        lambda url, params=None, timeout=None, headers=None: _Resp(_HTML),
    )
    rows = st.stock_zh_a_tick_163("603517", "20261009")
    assert len(rows) == 2
    assert rows[0]["成交金额"] == 527520 and rows[0]["性质"] == "卖盘"
    assert rows[1]["成交金额"] == 1679258


def test_tick_163_502(monkeypatch) -> None:
    monkeypatch.setattr(
        st, "get",
        lambda url, params=None, timeout=None, headers=None: _Resp("", 502),
    )
    with pytest.raises(requests.ConnectionError):
        st.stock_zh_a_tick_163("603517", "20261009")


def test_tick_163_empty_table(monkeypatch) -> None:
    monkeypatch.setattr(
        st, "get",
        lambda url, params=None, timeout=None, headers=None: _Resp("<table></table>"),
    )
    with pytest.raises(ValueError):
        st.stock_zh_a_tick_163("603517", "20261009")


def test_build_163_url() -> None:
    assert st._build_163_url("603517", "20261009").endswith(
        "/cjmx/2026/20261009/0603517.html"
    )
    # 深市市场前缀为 1
    assert st._build_163_url("000001", "20261009").endswith(
        "/cjmx/2026/20261009/1000001.html"
    )


# ---------------------------------------------------------------- 日期工具

def test_normalize_date() -> None:
    assert st._normalize_date("2026-10-09") == "20261009"
    assert st._normalize_date("20261009") == "20261009"
    with pytest.raises(ValueError):
        st._normalize_date("2026-10")
    with pytest.raises(ValueError):
        st._normalize_date("abcdefgh")


def test_latest_trade_date() -> None:
    from datetime import datetime

    assert st.latest_trade_date(datetime(2026, 10, 10)) == "20261009"  # 周六
    assert st.latest_trade_date(datetime(2026, 10, 12)) == "20261009"  # 周一
    assert st.latest_trade_date(datetime(2026, 10, 11)) == "20261009"  # 周日
    assert st.latest_trade_date(datetime(2026, 10, 9)) == "20261008"   # 周五→周四


# ---------------------------------------------------------------- 统一入口路由

def test_auto_latest_uses_tx(monkeypatch) -> None:
    monkeypatch.setattr(st, "stock_zh_a_tick_tx", lambda c, timeout=None: [{"src": "tx"}])
    monkeypatch.setattr(st, "stock_zh_a_tick_em", lambda c, timeout=None: [{"src": "em"}])
    assert st.stock_zh_a_tick("603517") == [{"src": "tx"}]


def test_auto_latest_fallback_on_exception(monkeypatch) -> None:
    def boom(c, timeout=None):
        raise requests.ConnectionError("腾讯不可用")

    monkeypatch.setattr(st, "stock_zh_a_tick_tx", boom)
    monkeypatch.setattr(st, "stock_zh_a_tick_em", lambda c, timeout=None: [{"src": "em"}])
    assert st.stock_zh_a_tick("603517") == [{"src": "em"}]


def test_auto_latest_fallback_on_empty(monkeypatch) -> None:
    monkeypatch.setattr(st, "stock_zh_a_tick_tx", lambda c, timeout=None: [])
    monkeypatch.setattr(st, "stock_zh_a_tick_em", lambda c, timeout=None: [{"src": "em"}])
    assert st.stock_zh_a_tick("603517") == [{"src": "em"}]


def test_auto_history_uses_163(monkeypatch) -> None:
    monkeypatch.setattr(
        st, "stock_zh_a_tick_163",
        lambda c, d, timeout=None: [{"src": "163", "date": d}],
    )
    assert st.stock_zh_a_tick("603517", "20260925") == [
        {"src": "163", "date": "20260925"}
    ]


def test_forced_source(monkeypatch) -> None:
    monkeypatch.setattr(st, "stock_zh_a_tick_em", lambda c, timeout=None: [{"src": "em"}])
    assert st.stock_zh_a_tick("603517", source="em") == [{"src": "em"}]


def test_invalid_symbol() -> None:
    with pytest.raises(ValueError):
        st.stock_zh_a_tick("abc")
