#!/usr/bin/env python3
"""分笔成交明细的单元测试（monkeypatch 网络，无需联网）"""

import csv

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
    if p == 1:
        # seq 1 与上一页重复，seq 2 为新记录，验证跨页按序号去重
        return _Resp(
            'v_detail_data_sh603517=[0,"1/09:30:02/11.23/0.03/10/11230/B'
            '|2/09:30:05/11.24/0.01/5/5620/B"]'
        )
    return _Resp('v_detail_data_sh603517=[0,""]')


def test_tick_tx_parse(monkeypatch) -> None:
    monkeypatch.setattr(
        st, "get",
        lambda url, params=None, timeout=None, headers=None: _tx_page(params["p"]),
    )
    rows = st.stock_zh_a_tick_tx("603517")
    assert len(rows) == 3  # seq 0/1/2，重复的 seq 1 被去掉
    assert rows[0]["成交时间"] == "09:25:00"
    assert rows[0]["性质"] == "卖盘"
    assert rows[1]["性质"] == "买盘" and rows[2]["性质"] == "买盘"
    assert rows[0]["成交量"] == 471 and rows[0]["成交金额"] == 527520
    assert rows[1]["成交价格"] == 11.23 and rows[1]["价格变动"] == 0.03


# ---------------------------------------------------------------- 东财源

def test_tick_em_parse(monkeypatch) -> None:
    calls = []

    def fake_json(path, params, timeout=15):
        calls.append(params)
        # 注意形状：details 在 data 层内
        return {"data": {"details": [
            "09:15:15,11.18,36,0,4",
            "09:30:00,11.21,1498,0,2",
            "09:30:03,11.20,10,0,1",
        ]}}

    monkeypatch.setattr(st, "get_push2_json", fake_json)
    rows = st.stock_zh_a_tick_em("603517")
    assert len(rows) == 3
    # 方向对齐上游：4 中性、2 买盘、1 卖盘
    assert rows[0]["性质"] == "中性盘"
    assert rows[1]["性质"] == "买盘"
    assert rows[2]["性质"] == "卖盘"
    # 东财无金额，按 价×量×100 估算
    assert rows[0]["成交金额"] == 40248
    assert rows[1]["成交金额"] == 1679258
    assert rows[2]["成交金额"] == 11200
    assert rows[0]["价格变动"] is None
    # 本页最早 09:15，拉取一次即终止
    assert len(calls) == 1
    assert calls[0]["ut"]  # 请求必须带 ut


def test_tick_em_paging(monkeypatch) -> None:
    calls = []

    def fake_json(path, params, timeout=15):
        calls.append(params["pos"])
        if params["pos"] == "-0":
            # 行序故意倒置：details[0] 是 09:16，min 才是 09:15——
            # 若实现回退成取首行，会误判未到集合竞价而多翻一页
            return {"data": {"details": [
                "09:16:00,11.21,100,0,2",
                "09:15:00,11.20,50,0,1",
            ]}}
        return {"data": {"details": []}}  # 空页，防御性终止

    monkeypatch.setattr(st, "get_push2_json", fake_json)
    rows = st.stock_zh_a_tick_em("603517")
    assert len(calls) == 1   # 本页 min 已到 09:15，单页即终止
    assert len(rows) == 2                       # 两笔切片
    assert [r["成交时间"] for r in rows] == ["09:15:00", "09:16:00"]
    assert sum(r["成交量"] for r in rows) == 150  # 100 + 50


def test_tick_em_secid_market(monkeypatch) -> None:
    seen_secid = []

    def fake_json(path, params, timeout=15):
        seen_secid.append(params["secid"])
        return {"data": {"details": ["09:15:00,11.00,1,0,4"]}}

    monkeypatch.setattr(st, "get_push2_json", fake_json)
    for code, expected in [
        ("603517", "1.603517"),  # 沪
        ("000001", "0.000001"),  # 深
        ("920001", "0.920001"),  # 北交所 920 段，不得挂沪
        ("830799", "0.830799"),  # 北交所 8 段
        ("430047", "0.430047"),  # 北交所 4 段
    ]:
        st.stock_zh_a_tick_em(code)
        assert seen_secid[-1] == expected


# ---------------------------------------------------------------- 网易源

_HTML = (
    "<table>"
    "<tr><td>09:25:00</td><td>11.20</td><td>0.00</td>"
    "<td>471</td><td>527,520</td><td>卖盘</td></tr>"
    "<tr><td>15:00:00</td><td>11.21</td><td>0.01</td>"
    "<td>1,498</td><td>1,679,258</td><td>中性盘</td></tr>"
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
    assert rows[1]["成交量"] == 1498 and rows[1]["成交金额"] == 1679258


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
    assert st._build_163_url("000001", "20261009").endswith(
        "/cjmx/2026/20261009/1000001.html"
    )
    # 北交所与深市同前缀 1，不得挂沪
    assert st._build_163_url("920001", "20261009").endswith(
        "/cjmx/2026/20261009/1920001.html"
    )
    assert st._build_163_url("830799", "20261009").endswith(
        "/cjmx/2026/20261009/1830799.html"
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


# ---------------------------------------------------------------- 拉取即落盘

def test_tick_to_file_writes_and_returns_path(monkeypatch, tmp_path) -> None:
    fake_rows = [
        {"成交时间": "09:25:00", "成交价格": 11.2, "价格变动": 0.0,
         "成交量": 471, "成交金额": 527520, "性质": "卖盘"},
        {"成交时间": "15:00:00", "成交价格": 11.21, "价格变动": 0.01,
         "成交量": 1498, "成交金额": 1679258, "性质": "中性盘"},
    ]
    monkeypatch.setattr(st, "stock_zh_a_tick", lambda *a, **k: fake_rows)
    monkeypatch.setattr(st, "_safe_stock_name", lambda code: "ST绝味")

    path = st.stock_zh_a_tick_to_file("603517", "20261009", out_dir=str(tmp_path))
    assert path == str(tmp_path / "ST绝味_603517_20261009.csv")

    with open(path, encoding="utf-8-sig", newline="") as fh:
        table = list(csv.reader(fh))
    assert table[0] == [
        "成交时间", "成交价格(元)", "价格变动(元)",
        "成交量(手)", "成交金额(元)", "性质",
    ]
    assert len(table) == 3  # 表头 + 2 笔
    assert table[1] == ["09:25:00", "11.2", "0.0", "471", "527520", "卖盘"]


def test_tick_to_file_empty_raises(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(st, "stock_zh_a_tick", lambda *a, **k: [])
    with pytest.raises(ValueError):
        st.stock_zh_a_tick_to_file("603517", "20261009", out_dir=str(tmp_path))


def test_safe_stock_name_cleans_and_falls_back(monkeypatch) -> None:
    import akshareios.stock_info as info

    # 简称中的 * 等非法字符须清洗
    monkeypatch.setattr(
        info, "stock_individual_info_em",
        lambda symbol: {"股票简称": "*ST绝味"},
    )
    assert st._safe_stock_name("603517") == "_ST绝味"

    def boom(symbol):
        raise requests.ConnectionError("获取失败")

    monkeypatch.setattr(info, "stock_individual_info_em", boom)
    st._NAME_CACHE.clear()  # 清缓存，才能走到失败回退分支
    assert st._safe_stock_name("603517") == "603517"  # 失败回退代码


# ------------------------------------------------- 实时会话日（盘中归属当天）

def test_realtime_session_date() -> None:
    from datetime import datetime

    cases = [
        (datetime(2026, 10, 12, 10, 0), "20261012"),   # 周一盘中 → 当天
        (datetime(2026, 10, 12, 15, 30), "20261012"),  # 周一盘后 → 当天
        (datetime(2026, 10, 12, 8, 0), "20261009"),    # 周一盘前 → 上周五
        (datetime(2026, 10, 13, 8, 0), "20261012"),    # 周二盘前 → 周一
        (datetime(2026, 10, 13, 9, 15), "20261013"),   # 周二 09:15 → 当天
        (datetime(2026, 10, 10, 10, 0), "20261009"),   # 周六 → 周五
        (datetime(2026, 10, 11, 10, 0), "20261009"),   # 周日 → 周五
    ]
    for ref, expected in cases:
        assert st._realtime_session_date(ref) == expected, ref


# ------------------------------------------------- Documents 根定位

def test_documents_root_cwd(monkeypatch, tmp_path) -> None:
    docs = tmp_path / "Documents"
    docs.mkdir()
    monkeypatch.chdir(docs)
    assert st._documents_root() == docs  # cwd 名为 Documents → 直接用


def test_documents_root_home_fallback(monkeypatch, tmp_path) -> None:
    from pathlib import Path

    monkeypatch.chdir(tmp_path)  # cwd 不叫 Documents、无 js → 回退主目录
    assert st._documents_root() == Path.home() / "Documents"


def test_documents_root_ios(monkeypatch, tmp_path) -> None:
    import sys
    import types

    (tmp_path / "Documents").mkdir(parents=True)
    fake_js = types.SimpleNamespace(
        window=types.SimpleNamespace(__MS_DOCROOT__=str(tmp_path))
    )
    monkeypatch.setitem(sys.modules, "js", fake_js)  # 模拟 Pyodide 的 js
    assert st._documents_root() == tmp_path / "Documents"


# ------------------------------------------------- 落盘：默认目录/透传/原子写

def test_tick_to_file_default_dir(monkeypatch, tmp_path) -> None:
    fake_rows = [{"成交时间": "09:25:00", "成交价格": 11.2, "价格变动": 0.0,
                  "成交量": 1, "成交金额": 100, "性质": "中性盘"}]
    monkeypatch.setattr(st, "_documents_root", lambda: tmp_path)
    monkeypatch.setattr(st, "stock_zh_a_tick", lambda *a, **k: fake_rows)
    monkeypatch.setattr(st, "_safe_stock_name", lambda c: "ST绝味")

    path = st.stock_zh_a_tick_to_file("603517", "20261009")  # 不传 out_dir
    assert path == str(tmp_path / "data" / "成交明细" / "ST绝味_603517_20261009.csv")


def test_tick_to_file_passthrough_none_and_atomic(monkeypatch, tmp_path) -> None:
    captured = {}

    def fake_tick(code, date, source="auto", timeout=15):
        captured.update(code=code, date=date, source=source, timeout=timeout)
        # 价格变动、成交金额缺失 → CSV 对应单元格应为空字符串
        return [{"成交时间": "09:25:00", "成交价格": 11.2,
                 "成交量": 1, "性质": "中性盘"}]

    monkeypatch.setattr(st, "stock_zh_a_tick", fake_tick)
    monkeypatch.setattr(st, "_safe_stock_name", lambda c: "ST绝味")
    path = st.stock_zh_a_tick_to_file(
        "603517", "20261009", source="tx", timeout=5, out_dir=str(tmp_path)
    )

    assert captured == dict(code="603517", date="20261009", source="tx", timeout=5)
    with open(path, encoding="utf-8-sig", newline="") as fh:
        table = list(csv.reader(fh))
    assert table[1] == ["09:25:00", "11.2", "", "1", "", "中性盘"]  # None→空
    assert not (tmp_path / "ST绝味_603517_20261009.csv.tmp").exists()  # 临时文件不残留
