"""
akshareios - AKShare 轻量 iOS 版

纯 Python 实现的 A 股数据接口，无 pandas/numpy/lxml 依赖。
仅依赖 requests，适用于 iOS 内嵌 Python 等无法编译 C 扩展的环境。
"""

__version__ = "0.1.0"

from akshareios.stock_list import stock_info_a_code_name
from akshareios.stock_hist import stock_zh_a_hist
from akshareios.stock_spot import stock_zh_a_spot_em
from akshareios.stock_info import stock_individual_info_em

__all__ = [
    "stock_info_a_code_name",
    "stock_zh_a_hist",
    "stock_zh_a_spot_em",
    "stock_individual_info_em",
]
