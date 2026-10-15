"""
个股公告查询 —— 公告列表 / 公告正文

数据源：东方财富公告中心
- 列表：https://np-anotice-stock.eastmoney.com/api/security/ann
- 正文：https://np-cnotice-stock.eastmoney.com/api/content/ann

原版参考：akshare/stock_fundamental/stock_notice.py、scripts/stock_ann.py
纯 Python 实现，仅依赖 requests，适用于 iOS 内嵌 Python。
"""

from akshareios._convert import ensure_symbol
from akshareios._http import get

LIST_API = "https://np-anotice-stock.eastmoney.com/api/security/ann"
CONTENT_API = "https://np-cnotice-stock.eastmoney.com/api/content/ann"

# 公告中心页面 Referer，东财对该域接口有来源校验
_ANN_HEADERS = {"Referer": "https://data.eastmoney.com/"}

# 公告大类 → 东财 f_node 编码（对齐上游 stock_notice_report）
CATEGORY_MAP = {
    "全部": "0",
    "财务报告": "1",
    "融资公告": "2",
    "风险提示": "3",
    "信息变更": "4",
    "重大事项": "5",
    "资产重组": "6",
    "持股变动": "7",
}

# 东财单页最多返回 100 条
_PAGE_SIZE = 100
# 翻页防御上限：单只个股公告极少超过 2000 条，避免异常响应下无限翻页
_MAX_PAGES = 20
# 单次列表返回条数上限，防止 size 误传成超大值导致长时间拉取
MAX_ANN_ROWS = 500

_DETAIL_URL = "https://data.eastmoney.com/notices/detail/{symbol}/{art_code}.html"


def _norm_period_date(value) -> str:
    """接受 YYYYMMDD 或 YYYY-MM-DD，统一为东财要求的 YYYY-MM-DD。"""
    s = str(value or "").strip()
    if not s:
        return ""
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    parts = s.split("-")
    if len(parts) == 3 and all(p.isdigit() for p in parts):
        return f"{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2]):02d}"
    raise ValueError(f"无效日期: {value!r}，需 YYYYMMDD 或 YYYY-MM-DD")


def _clean_text(text) -> str:
    """规整公告正文：逐行去空白、压缩连续空行，保留换行以维持可读性。"""
    if not text:
        return ""
    out: list[str] = []
    prev_blank = False
    for raw in str(text).splitlines():
        line = raw.strip()
        if line:
            out.append(line)
            prev_blank = False
        elif not prev_blank:
            out.append("")
            prev_blank = True
    return "\n".join(out).strip()


def _category_node(category) -> str:
    """中文大类名 → f_node 编码，非法类别抛 ValueError。"""
    if category is None:
        return CATEGORY_MAP["全部"]
    key = str(category).strip()
    if key not in CATEGORY_MAP:
        raise ValueError(f"无效公告类别: {category!r}，可选: {'、'.join(CATEGORY_MAP)}")
    return CATEGORY_MAP[key]


def stock_ann_em(
    symbol: str,
    size: int = 10,
    *,
    keyword: str | None = None,
    category: str = "全部",
    begin_date: str | None = None,
    end_date: str | None = None,
    timeout: float = 15,
) -> list[dict]:
    """
    个股公告列表（按公告日期倒序）。

    :param symbol: 6 位股票代码
    :param size: 返回条数，默认 10，上限 500
    :param keyword: 标题关键词（如"半年度报告""撤销风险警示"），仅返回标题含该词的公告；
                    关键词在服务端返回结果内过滤，必要时自动翻页
    :param category: 公告大类，可选：全部/财务报告/融资公告/风险提示/信息变更/
                     重大事项/资产重组/持股变动
    :param begin_date: 起始日期，YYYYMMDD 或 YYYY-MM-DD
    :param end_date: 结束日期，YYYYMMDD 或 YYYY-MM-DD
    :return: list[dict]，字段 公告日期/公告类型/公告标题/公告编码/网址
    """
    symbol = ensure_symbol(symbol)
    if not isinstance(size, int) or size <= 0:
        raise ValueError(f"条数 size 需为正整数，收到: {size!r}")
    size = min(size, MAX_ANN_ROWS)
    f_node = _category_node(category)
    keyword = keyword.strip() if isinstance(keyword, str) and keyword.strip() else None

    base_params = {
        "sr": "-1",
        "page_size": str(_PAGE_SIZE),
        "ann_type": "A",
        "client_source": "web",
        "f_node": f_node,
        "s_node": "0",
        "stock_list": symbol,
    }
    if begin_date:
        base_params["begin_time"] = _norm_period_date(begin_date)
    if end_date:
        base_params["end_time"] = _norm_period_date(end_date)

    results: list[dict] = []
    for page in range(1, _MAX_PAGES + 1):
        params = dict(base_params, page_index=str(page))
        resp = get(LIST_API, params=params, timeout=timeout, headers=_ANN_HEADERS)
        resp.raise_for_status()
        data = resp.json().get("data") or {}
        items = data.get("list") or []
        if not items:
            break
        for it in items:
            title = it.get("title_ch") or it.get("title") or ""
            if keyword and keyword not in title:
                continue
            col_names = [
                c.get("column_name")
                for c in (it.get("columns") or [])
                if c.get("column_name")
            ]
            art_code = it.get("art_code") or ""
            results.append({
                "公告日期": (it.get("notice_date") or "")[:10],
                "公告类型": "、".join(col_names),
                "公告标题": title,
                "公告编码": art_code,
                "网址": _DETAIL_URL.format(symbol=symbol, art_code=art_code)
                if art_code
                else "",
            })
            if len(results) >= size:
                return results
        # 本页不足整页即末页；或已翻到服务端总量页
        if len(items) < _PAGE_SIZE:
            break
        total_hits = data.get("total_hits")
        if isinstance(total_hits, int) and page * _PAGE_SIZE >= total_hits:
            break
    return results


def stock_ann_content_em(symbol: str, art_code: str, *, timeout: float = 15) -> dict:
    """
    读取单条公告正文（纯文本）。

    :param symbol: 6 位股票代码（接口要求同时传入）
    :param art_code: 公告编码，取自 stock_ann_em 返回的"公告编码"
    :return: dict，字段 公告标题/公告日期/证券简称/正文/附件网址；
             原文为 PDF 附件型公告时正文可能为空，以附件网址为准
    """
    symbol = ensure_symbol(symbol)
    art_code = str(art_code or "").strip()
    if not art_code:
        raise ValueError("缺少公告编码 art_code，请先用 stock_ann_em 获取")
    params = {
        "art_code": art_code,
        "page_size": "50",
        "page_index": "1",
        "ann_type": "A",
        "stock_list": symbol,
        "client_source": "web",
        "f_node": "0",
        "s_node": "0",
    }
    resp = get(CONTENT_API, params=params, timeout=timeout, headers=_ANN_HEADERS)
    resp.raise_for_status()
    data = resp.json().get("data") or {}
    return {
        "公告标题": data.get("notice_title") or data.get("title") or "",
        "公告日期": (data.get("notice_date") or "")[:10],
        "证券简称": data.get("short_name") or "",
        "正文": _clean_text(data.get("notice_content")),
        "附件网址": data.get("attach_url_web") or data.get("attach_url") or "",
    }
