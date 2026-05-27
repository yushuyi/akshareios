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

# 获取全部 A 股代码和名称
stocks = ak.stock_info_a_code_name()
# [{"code": "000001", "name": "平安银行"}, {"code": "000002", "name": "万科A"}, ...]

# 获取个股历史 K 线
klines = ak.stock_zh_a_hist(symbol="600519", period="daily")
# [{"日期": "2024-01-02", "开盘": 1688.0, "收盘": 1700.0, ...}, ...]

# 获取全市场实时行情
spot = ak.stock_zh_a_spot_em()
# [{"代码": "000001", "名称": "平安银行", "最新价": 12.5, ...}, ...]

# 获取个股详细信息
info = ak.stock_individual_info_em(symbol="600519")
# {"股票代码": "600519", "股票简称": "贵州茅台", "总市值": ..., ...}
```

## 与 AKShare 的区别

| 特性 | AKShare | akshareios |
|------|---------|------------|
| 返回类型 | pandas.DataFrame | list[dict] |
| 依赖 | pandas + numpy + lxml + ... | 仅 requests |
| iOS 兼容 | ❌ | ✅ |
| 接口数量 | 1000+ | 核心精选 |
| API 兼容 | - | 函数名保持一致 |

## 数据源

- 东方财富（EastMoney）：股票列表、K 线、实时行情、个股信息
- 后续扩展：基金、期货、宏观经济等

## License

MIT（基于 AKShare 改造）
