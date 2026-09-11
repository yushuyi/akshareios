#!/usr/bin/env python3
"""代码转换与新浪板块解析的单元测试（无需联网）"""

from akshareios._datacenter import to_secucode
from akshareios._fallback_sina import _parse_sina_boards
from akshareios._symbols import to_market_symbol


def test_to_market_symbol_stock_index_explicit() -> None:
    # 000001 双身份：股票降级必须得 sz000001（平安银行），指数须显式传 is_index
    assert to_market_symbol("000001", is_index=False) == "sz000001"
    assert to_market_symbol("000001", is_index=True) == "sh000001"
    assert to_market_symbol("600519", is_index=False) == "sh600519"
    assert to_market_symbol("399001", is_index=True) == "sz399001"
    assert to_market_symbol("830799", is_index=False) == "bj830799"
    assert to_market_symbol("sh600519") == "sh600519"  # 已带前缀原样返回


def test_to_secucode_bj_vs_sh_b() -> None:
    # 920 北交所新代码段归 BJ；900 沪 B 归 SH（曾一刀切归 BJ 的回归）
    assert to_secucode("920002") == "920002.BJ"
    assert to_secucode("900901") == "900901.SH"
    assert to_secucode("600519") == "600519.SH"
    assert to_secucode("000001") == "000001.SZ"
    assert to_secucode("830799") == "830799.BJ"


_SAMPLE = (
    'var S_Finance_bankuai_sinaindustry = {"new_blhy":"new_blhy,玻璃行业,19,17.44,'
    "-0.05,-0.31,1026385049,22316435075,sh600184,10.022,19.980,1.820,光电股份\","
    '"bad_row":"only,few,fields"};'
)


def test_parse_sina_boards() -> None:
    items = _parse_sina_boards(_SAMPLE)
    assert len(items) == 1  # 字段不足 13 段的坏行被跳过
    row = items[0]
    assert row["板块代码"] == "new_blhy"
    assert row["板块名称"] == "玻璃行业"
    assert row["公司家数"] == 19
    assert row["涨跌幅"] == -0.31
    assert row["领涨股代码"] == "600184"
    assert row["领涨股票"] == "光电股份"
    assert row["数据源"] == "新浪行业"


def test_parse_sina_boards_empty() -> None:
    assert _parse_sina_boards("") == []
    assert _parse_sina_boards("var x = not json") == []
