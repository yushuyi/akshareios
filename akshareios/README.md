# akshareios

AKShare 轻量 iOS 版 —— 纯 Python 实现的 A 股数据接口，**零 C 扩展依赖**。

专为 iOS 内嵌 Python 运行时设计，仅依赖 `requests`，可在任何无法编译 C 扩展的环境（iOS / WebAssembly / 受限容器）中运行。

## 安装

包位于本仓库的 `akshareios/` 子目录，从 GitHub 安装：

```bash
pip install "git+https://github.com/yushuyi/akshareios.git#subdirectory=akshareios"
```

或下载 wheel 后本地安装：

```bash
pip install ./akshareios-0.6.8-py3-none-any.whl
```

> **注意**：请勿使用 `pip install https://github.com/yushuyi/akshareios/archive/refs/heads/main.zip`。
> 仓库根目录是 AKShare 上游工程，该命令会安装完整版 AKShare（依赖 pandas/numpy/lxml），
> 而不是本轻量版；本项目也未发布到 PyPI，`pip install akshareios` 同样无效。

## 快速开始

```python
import akshareios as ak

# 分页获取 A 股代码和名称（默认每页 20 条，最大 100 条）
page1 = ak.stock_info_a_code_name(page=1, page_size=20)
# {"items": [{"code": "000001", "name": "平安银行"}, ...], "page": 1, "total": 5123, "has_more": true}

# 获取个股历史 K 线（默认最多 120 根）
klines = ak.stock_zh_a_hist(symbol="600519", period="daily", limit=60)

# 分页获取实时行情（默认按涨跌幅排序）
spot = ak.stock_zh_a_spot_em(page=1, page_size=20, sort_by="f3")

# 分钟 K 线 / 分时（默认最多 120 根）
mins = ak.stock_zh_a_hist_min_em(symbol="600519", period="5", limit=60)

# 指数 K 线
idx = ak.index_zh_a_hist(symbol="000001", start_date="20250101", end_date="20250701", limit=60)

# 行业板块（分页）
boards = ak.stock_board_industry_name_em(page=1, page_size=20)

# 涨停股池（分页；非交易日可能为空）
zt = ak.stock_zt_pool_em(page=1, page_size=20)

# 获取个股详细信息（单只股票，无需分页）
info = ak.stock_individual_info_em(symbol="600519")

# 股东户数趋势（首条即最新一期）
gdhs = ak.stock_holder_num_em(symbol="600519")

# 十大流通股东（最新一期）
gdfx = ak.stock_gdfx_free_top_10_em(symbol="600519")

# 业绩报表（营收/净利/同比/毛利率/ROE，按报告期倒序）
yjbb = ak.stock_yjbb_em(symbol="600519")

# 个股资金流历史（主力/超大单净流入，默认 120 天）
fund = ak.stock_individual_fund_flow(symbol="600519", limit=60)
```

## 分页约定

列表类接口（`stock_info_a_code_name`、`stock_zh_a_spot_em`）**不再一次性拉全市场**，统一返回：

```python
{
    "items": [...],       # 当前页数据
    "page": 1,            # 当前页码（从 1 开始）
    "page_size": 20,      # 本页条数
    "total": 5123,        # 全市场总数
    "total_pages": 257,   # 总页数
    "has_more": True      # 是否还有下一页
}
```

- `page_size` 默认 **20**，硬上限 **100**
- 需要下一页时传 `page=2, page_size=20`，依此类推

## 与 AKShare 的区别

| 特性 | AKShare | akshareios |
|------|---------|------------|
| 返回类型 | pandas.DataFrame | list[dict] / 分页 dict |
| 依赖 | pandas + numpy + lxml + ... | 仅 requests |
| iOS 兼容 | ❌ | ✅ |
| 接口数量 | 1000+ | 核心精选 |
| API 兼容 | - | 函数名保持一致 |

## 数据源

- 东方财富（EastMoney）：股票列表、K 线、实时行情、个股信息、股东数据、业绩报表、资金流向

## License

MIT（基于 AKShare 改造）
