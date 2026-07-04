# akshareios

AKShare 轻量 iOS 版 —— 纯 Python 实现的 A 股数据接口，**零 C 扩展依赖**。

专为 iOS 内嵌 Python 运行时设计，仅依赖 `requests`，可在任何无法编译 C 扩展的环境（iOS / WebAssembly / 受限容器）中运行。

## 安装

```bash
pip install akshareios
```

或从 GitHub 安装最新版：

```bash
pip install https://github.com/yushuyi/akshareios/archive/refs/heads/main.zip
```

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

# 获取个股详细信息（单只股票，无需分页）
info = ak.stock_individual_info_em(symbol="600519")
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

- 东方财富（EastMoney）：股票列表、K 线、实时行情、个股信息

## License

MIT（基于 AKShare 改造）
