#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""个股公告模块的单元测试（monkeypatch 网络，无需联网）"""

import pytest

import akshareios.stock_ann as sa


class _Resp:
    """requests.Response 最小替身：返回预置 JSON。"""

    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._payload


def _item(art: str, title: str, date: str, *cols: str) -> dict:
    return {
        "art_code": art,
        "title_ch": title,
        "notice_date": date,
        "columns": [{"column_name": c} for c in cols],
    }


# --------------------------------------------------------------- 列表解析

def test_list_parse(monkeypatch) -> None:
    payload = {"data": {"total_hits": 1, "list": [
        _item("AN001", "ST绝味:关于公司股票申请撤销其他风险警示的公告",
              "2026-10-13 00:00:00", "申请撤销风险警示及特别处理", "董事会决议公告"),
    ]}}
    seen = {}

    def fake_get(url, params=None, timeout=None, headers=None):
        seen.update(url=url, params=params, headers=headers)
        return _Resp(payload)

    monkeypatch.setattr(sa, "get", fake_get)
    rows = sa.stock_ann_em("603517")
    assert len(rows) == 1
    row = rows[0]
    assert row["公告日期"] == "2026-10-13"
    assert row["公告类型"] == "申请撤销风险警示及特别处理、董事会决议公告"
    assert row["公告编码"] == "AN001"
    assert row["网址"].endswith("/603517/AN001.html")
    # 必须带东财来源 Referer，且列表走 ann 接口
    assert "np-anotice-stock" in seen["url"]
    assert seen["headers"]["Referer"] == "https://data.eastmoney.com/"
    assert seen["params"]["stock_list"] == "603517"
    assert seen["params"]["f_node"] == "0"  # 默认全部


def test_list_title_fallback_and_empty(monkeypatch) -> None:
    # 无 title_ch 时回退 title；空列也安全返回 []
    payload = {"data": {"list": [
        {"art_code": "AN002", "title": "仅 title 字段", "notice_date": "2026-01-01",
         "columns": []},
    ]}}
    monkeypatch.setattr(sa, "get", lambda *a, **k: _Resp(payload))
    rows = sa.stock_ann_em("000001")
    assert rows[0]["公告标题"] == "仅 title 字段"
    assert rows[0]["公告类型"] == ""

    monkeypatch.setattr(sa, "get", lambda *a, **k: _Resp({"data": {}}))
    assert sa.stock_ann_em("000001") == []


# --------------------------------------------------------------- 关键词与翻页

def test_keyword_filters_and_paginates(monkeypatch) -> None:
    pages = {
        1: [_item("A1", "回购进展公告", "2026-10-08"),
            _item("A2", "董事会决议公告", "2026-10-08")],
        2: [_item("A3", "关于公司股票申请撤销其他风险警示的公告", "2026-10-13")],
    }
    calls = []

    def fake_get(url, params=None, timeout=None, headers=None):
        p = int(params["page_index"])
        calls.append(p)
        return _Resp({"data": {"total_hits": 3, "list": pages.get(p, [])}})

    monkeypatch.setattr(sa, "get", fake_get)
    monkeypatch.setattr(sa, "_PAGE_SIZE", 2)  # 缩小页长，便于构造翻页
    rows = sa.stock_ann_em("603517", size=5, keyword="撤销")
    assert calls == [1, 2]  # 首页满页且无匹配，继续翻第二页
    assert len(rows) == 1
    assert rows[0]["公告编码"] == "A3"


def test_stops_at_full_count(monkeypatch) -> None:
    # 无关键词：第一页满页但已到 total_hits，不翻第二页
    def fake_get(url, params=None, timeout=None, headers=None):
        p = int(params["page_index"])
        if p == 1:
            return _Resp({"data": {"total_hits": 2, "list": [
                _item("A1", "公告一", "2026-10-01"),
                _item("A2", "公告二", "2026-10-02"),
            ]}})
        return _Resp({"data": {"total_hits": 2, "list": []}})

    monkeypatch.setattr(sa, "get", fake_get)
    monkeypatch.setattr(sa, "_PAGE_SIZE", 2)
    rows = sa.stock_ann_em("603517", size=10)
    assert len(rows) == 2


# --------------------------------------------------------------- 类别 / 日期

def test_category_mapping(monkeypatch) -> None:
    seen = {}
    monkeypatch.setattr(
        sa, "get",
        lambda url, params=None, timeout=None, headers=None:
            (seen.update(params=params), _Resp({"data": {"list": []}}))[1],
    )
    sa.stock_ann_em("603517", category="财务报告")
    assert seen["params"]["f_node"] == "1"
    with pytest.raises(ValueError):
        sa.stock_ann_em("603517", category="不存在的类别")


def test_date_range_params(monkeypatch) -> None:
    seen = {}
    monkeypatch.setattr(
        sa, "get",
        lambda url, params=None, timeout=None, headers=None:
            (seen.update(params=params), _Resp({"data": {"list": []}}))[1],
    )
    sa.stock_ann_em("603517", begin_date="20260101", end_date="2026-06-30")
    assert seen["params"]["begin_time"] == "2026-01-01"
    assert seen["params"]["end_time"] == "2026-06-30"
    with pytest.raises(ValueError):
        sa.stock_ann_em("603517", begin_date="2026/01/01")


def test_norm_period_date() -> None:
    assert sa._norm_period_date("20261013") == "2026-10-13"
    assert sa._norm_period_date("2026-1-2") == "2026-01-02"
    assert sa._norm_period_date("") == ""


# --------------------------------------------------------------- 正文

def test_content_parse(monkeypatch) -> None:
    payload = {"data": {
        "notice_title": "ST绝味:关于公司股票申请撤销其他风险警示的公告",
        "notice_date": "2026-10-13 00:00:00",
        "short_name": "ST绝味",
        "notice_content": "\n  第一段正文  \n\n\n  第二段正文\n",
        "attach_url_web": "https://pdf.example.com/a.pdf",
    }}
    seen = {}
    monkeypatch.setattr(
        sa, "get",
        lambda url, params=None, timeout=None, headers=None:
            (seen.update(url=url, params=params), _Resp(payload))[1],
    )
    info = sa.stock_ann_content_em("603517", "AN001")
    assert info["公告标题"].startswith("ST绝味")
    assert info["公告日期"] == "2026-10-13"
    assert info["证券简称"] == "ST绝味"
    assert info["附件网址"] == "https://pdf.example.com/a.pdf"
    # 连续空行压缩、逐行去空白
    assert info["正文"] == "第一段正文\n\n第二段正文"
    assert "np-cnotice-stock" in seen["url"]
    assert seen["params"]["art_code"] == "AN001"
    assert seen["params"]["stock_list"] == "603517"


def test_content_attach_fallback(monkeypatch) -> None:
    # 无 web 附件时回退 attach_url
    monkeypatch.setattr(sa, "get", lambda *a, **k: _Resp({"data": {
        "attach_url": "https://pdf.example.com/b.pdf",
        "notice_content": None,
    }}))
    info = sa.stock_ann_content_em("603517", "AN002")
    assert info["附件网址"] == "https://pdf.example.com/b.pdf"
    assert info["正文"] == ""


# --------------------------------------------------------------- 正文翻页拼接

def test_content_paginates_full_text(monkeypatch) -> None:
    # 长公告：3 页，前两页满 5000 字符、末页短；按 page_index 逐页拼接全文
    pages = {1: "甲" * 5000, 2: "乙" * 5000, 3: "丙" * 2878}
    calls = []

    def fake_get(url, params=None, timeout=None, headers=None):
        p = int(params["page_index"])
        calls.append(p)
        return _Resp({"data": {
            "notice_title": "长期激励计划草案",
            "notice_date": "2026-06-27 00:00:00",
            "short_name": "ST绝味",
            "page_size": 3,
            "notice_content": pages[p],
        }})

    monkeypatch.setattr(sa, "get", fake_get)
    info = sa.stock_ann_content_em("603517", "AN202606261824606440")
    assert calls == [1, 2, 3]  # 总页数 3，翻满即止
    assert info["正文"] == "甲" * 5000 + "乙" * 5000 + "丙" * 2878
    assert len(info["正文"]) == 12878
    assert info["公告标题"] == "长期激励计划草案"


def test_content_stops_on_clamp(monkeypatch) -> None:
    # 末页恰好 5000 字符且无 page_size：越界页被服务端钳制返回末页，
    # 与上页内容重复即停止拼接，不会把末页反复并入
    calls = []

    def fake_get(url, params=None, timeout=None, headers=None):
        p = int(params["page_index"])
        calls.append(p)
        content = "甲" * 5000 if p == 1 else "乙" * 5000
        return _Resp({"data": {"notice_content": content}})

    monkeypatch.setattr(sa, "get", fake_get)
    info = sa.stock_ann_content_em("603517", "AN003")
    assert calls == [1, 2, 3]  # 第 3 页钳制返回第 2 页内容，探到重复即止
    assert info["正文"] == "甲" * 5000 + "乙" * 5000


def test_content_stops_on_short_page_without_total(monkeypatch) -> None:
    # 无 page_size 字段时靠短页（不足 5000 字符）终止
    calls = []

    def fake_get(url, params=None, timeout=None, headers=None):
        p = int(params["page_index"])
        calls.append(p)
        content = "戊" * 5000 if p == 1 else "己" * 100
        return _Resp({"data": {"notice_content": content}})

    monkeypatch.setattr(sa, "get", fake_get)
    info = sa.stock_ann_content_em("603517", "AN004")
    assert calls == [1, 2]
    assert info["正文"] == "戊" * 5000 + "己" * 100


def test_content_page_size_as_string(monkeypatch) -> None:
    # page_size 为字符串总页数时也能正确终止（容错解析）
    calls = []

    def fake_get(url, params=None, timeout=None, headers=None):
        p = int(params["page_index"])
        calls.append(p)
        content = "庚" * 5000 if p == 1 else "辛" * 5000
        return _Resp({"data": {"page_size": "2", "notice_content": content}})

    monkeypatch.setattr(sa, "get", fake_get)
    info = sa.stock_ann_content_em("603517", "AN005")
    assert calls == [1, 2]
    assert info["正文"] == "庚" * 5000 + "辛" * 5000


def test_clean_text() -> None:
    assert sa._clean_text(None) == ""
    assert sa._clean_text("  只有一行  ") == "只有一行"
    assert sa._clean_text("a\n\n\n\nb") == "a\n\nb"


# --------------------------------------------------------------- 参数校验

def test_invalid_args() -> None:
    with pytest.raises(ValueError):
        sa.stock_ann_em("abc")
    with pytest.raises(ValueError):
        sa.stock_ann_em("603517", size=0)
    with pytest.raises(ValueError):
        sa.stock_ann_em("603517", size=-3)
    with pytest.raises(ValueError):
        sa.stock_ann_content_em("603517", "")
    with pytest.raises(ValueError):
        sa.stock_ann_content_em("603517", None)
