#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A 股公告查询 — 数据源：东方财富公开接口
用法:
  python3 scripts/stock_ann.py <代码> [条数] [--kw 关键词]   # 列出最近公告
  python3 scripts/stock_ann.py <代码> --read <art_code>     # 读取公告正文
示例:
  python3 scripts/stock_ann.py 600519 10
  python3 scripts/stock_ann.py 600519 20 --kw 半年度报告
  python3 scripts/stock_ann.py 600519 --read AN202608141827994407
"""
import sys, json, requests

LIST_API = "https://np-anotice-stock.eastmoney.com/api/security/ann"
CONT_API = "https://np-cnotice-stock.eastmoney.com/api/content/ann"

def list_ann(code, size=10, kw=None):
    r = requests.get(LIST_API, params={
        "sr": -1, "page_size": size, "page_index": 1,
        "ann_type": "A", "stock_list": code}, timeout=15)
    items = r.json().get("data", {}).get("list", [])
    out = []
    for it in items:
        title = it.get("title_ch") or it.get("title", "")
        if kw and kw not in title:
            continue
        out.append({"date": (it.get("notice_date") or "")[:10],
                    "art_code": it.get("art_code"), "title": title})
    return out

def read_ann(art_code, code):
    r = requests.get(CONT_API, params={
        "art_code": art_code, "page_size": 50, "page_index": 1,
        "ann_type": "A", "stock_list": code,
        "client_source": "web", "f_node": 0, "s_node": 0}, timeout=15)
    return (r.json().get("data", {}) or {}).get("notice_content", "")

if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    kw_i = sys.argv.index("--kw") if "--kw" in sys.argv else -1
    kw = sys.argv[kw_i + 1] if kw_i >= 0 else None
    code = args[0] if args else "600519"
    if "--read" in sys.argv:
        art = sys.argv[sys.argv.index("--read") + 1]
        print(read_ann(art, code))
    else:
        size = int(args[1]) if len(args) > 1 else 10
        rows = list_ann(code, size, kw)
        print(json.dumps({"stock": code, "count": len(rows), "items": rows},
                         ensure_ascii=False, indent=2))
