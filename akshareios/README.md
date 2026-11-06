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
pip install ./akshareios-0.6.15-py3-none-any.whl
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

# 板块成分股（分页；total 即成分股总数）
cons = ak.stock_board_industry_cons_em(symbol="软件开发", page=1, page_size=20)

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

# 名称 → 代码（同名可能是 A 股 / 指数 / 板块 / ETF，看「代码体系」挑）
match = ak.stock_name_to_code("茅台")
code = match["推荐代码"]  # "600519"

# 全市场两融余额 / 个股两融明细（T-1 收盘后，金额单位元）
mkt = ak.stock_margin_balance_em(limit=10)
detail = ak.stock_margin_detail_em(symbol="600519", limit=10)

# 龙虎榜（近 7 天）与买卖席位明细
lhb = ak.stock_lhb_detail_em(start_date="20261101", end_date="20261106")
seats = ak.stock_lhb_stock_detail_em(symbol="000525", date="20261106")
```

> **涨停池空列表不等于「今天 0 只涨停」**：非交易日 / 盘前 / 历史日期，东财都返回
> `tc=0 / pool=[]`。读 `_meta.空结果原因` 与 `_meta.交易日判定` 再下结论（见下）。


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

## 数据源与口径

主源东方财富（股票列表、K 线、实时行情、个股信息、股东、业绩、资金流、板块），不可用时自动降级：

| 降级源 | 覆盖接口 |
|---|---|
| 腾讯证券 | 日 K 线（仅 daily）、实时行情榜、最近交易日分笔 |
| 新浪财经 | 分钟 K 线、个股详情、A 股列表、行业板块与成分股、资金流 |
| 网易财经 | 任意已收盘交易日分笔成交 |

**dict 类返回值**（个股详情、实时榜、板块列表 / 成分股、股票列表、两融、龙虎榜、
涨停池、名称解析）带 `_meta` 信封：

```json
{"数据源": "...", "状态": "主源|降级", "数据时间": "...", "口径说明": "...", "缺失字段": [...]}
```

接口特有的判定也放在同一个信封里，模型只需读一处：`最新数据日期`、`上榜日`、
`请求日期` / `服务端最新池日期` / `交易日判定` / `空结果原因`、`精确匹配` / `推荐代码`。

降级时字段会变少、单位与排序可能与主源不同：`stock_zh_a_spot_em` 降级后 `成交量` / `成交额` 恒为 `null`（该源不提供，**不是**「无成交」）；`stock_individual_info_em` 降级后不含股本 / 市值 / 估值字段；板块列表降级后代码是新浪 `new_xxx`，可直接传给 `stock_board_industry_cons_em` 走新浪成分股。调用方应先读 `_meta` 再决定该数值能否用于当前判断。list 类返回值（K 线、资金流、分笔等）保持原有结构，不带 `_meta`。

资金流无论主源还是降级都是 **T-1 收盘后**数据，当日盘中不刷新。

### 「空结果」不是一个意思

| 接口 | 空 items 的可能含义 | 判据 |
|---|---|---|
| `stock_zt_pool_em` | 非交易日 / 盘前未生成 / 历史日期不支持 / 当日确无涨停 / 页码越界 | `_meta.空结果原因`、`交易日判定`；`服务端最新池日期 ≠ 请求日期` 即「没有该日数据」，**不是** 0 只涨停 |
| `stock_lhb_detail_em` / `stock_lhb_stock_detail_em` | 区间内无上榜 / 该股当日未上榜 / 尚未收盘披露 | `_meta.空结果原因`；盘中没有当日龙虎榜 |
| 两融 / 龙虎榜 datacenter 报表 | `success=false, code=9201 返回数据为空` 是合法空结果 | 报表层已区分：`9501 报表配置不存在 / 列不存在` 才抛错，不会把参数写错伪装成「无记录」 |

### 0.6.15 新增接口的口径

| 接口 | 主源 | 数据时间 | 单位 / 注意 |
|---|---|---|---|
| `stock_margin_balance_em` | 东财 datacenter 全市场两融账户统计 | **T-1 收盘后**，盘中不刷新 | 报表原始单位是**亿元**，已换算为元；占比 / 维持担保比例 / 指数涨跌幅仍是 % |
| `stock_margin_detail_em` | 东财 datacenter 个股两融明细 | **T-1 收盘后**，盘中不刷新 | 金额本来就是元（不再换算）；融券余量 / 卖出量为股 |
| `stock_lhb_detail_em` | 东财 datacenter 龙虎榜详情 | 当日收盘后披露，盘中无当日数据 | 金额元、比率 %；「上榜后 N 日」未到天数为 `null`，不是 0 |
| `stock_lhb_stock_detail_em` | 东财 datacenter 买卖席位 | 当日收盘后披露 | `flag="全部"` 合并买卖两榜，用「方向」区分，不要相加去重 |
| `stock_name_to_code` | 东财搜索建议 | 静态代码表，不含价格 | 同名结果分 A 股 / 指数 / 东财板块 BK / 基金，按「代码体系」挑选；`推荐代码` 需核对简称 |

两融与龙虎榜报表**没有可用降级源**：接口失败时抛错，而不是返回一份看起来正常的空数据。


## License

MIT（基于 AKShare 改造）
