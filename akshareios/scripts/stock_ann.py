#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A 股公告查询（akshareios 包模块的命令行入口）—— 数据源：东方财富
用法:
  python3 scripts/stock_ann.py <代码> [条数] [--kw 关键词] [--cat 类别]  # 列出最近公告
  python3 scripts/stock_ann.py <代码> --read <公告编码>                  # 读取公告正文
示例:
  python3 scripts/stock_ann.py 603517 10
  python3 scripts/stock_ann.py 603517 20 --kw 半年度报告
  python3 scripts/stock_ann.py 603517 --cat 财务报告
  python3 scripts/stock_ann.py 603517 --read AN202610121830364073
"""
import json
import os
import sys

# 脚本位于 akshareios/scripts/，包根是上一级目录
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from akshareios.stock_ann import stock_ann_content_em, stock_ann_em


def _opt(name: str) -> str | None:
    if name in sys.argv and sys.argv.index(name) + 1 < len(sys.argv):
        return sys.argv[sys.argv.index(name) + 1]
    return None


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    code = args[0] if args else "600519"
    if "--read" in sys.argv:
        art = _opt("--read")
        print(json.dumps(stock_ann_content_em(code, art), ensure_ascii=False, indent=2))
    else:
        size = int(args[1]) if len(args) > 1 else 10
        rows = stock_ann_em(
            code,
            size,
            keyword=_opt("--kw"),
            category=_opt("--cat") or "全部",
        )
        print(json.dumps(
            {"stock": code, "count": len(rows), "items": rows},
            ensure_ascii=False, indent=2,
        ))
