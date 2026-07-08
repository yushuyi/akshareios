"""
akshareios - AKShare 轻量 iOS 版

纯 Python 实现的 A 股数据接口，无 pandas/numpy/lxml 依赖。
仅依赖 requests，适用于 iOS 内嵌 Python 等无法编译 C 扩展的环境。
"""

__version__ = "0.4.1"

from akshareios.stock_list import stock_info_a_code_name
from akshareios.stock_hist import stock_zh_a_hist
from akshareios.stock_min import stock_zh_a_hist_min_em
from akshareios.index_hist import index_zh_a_hist
from akshareios.stock_spot import stock_zh_a_spot_em
from akshareios.stock_info import stock_individual_info_em
from akshareios.board_industry import stock_board_industry_name_em
from akshareios.stock_zt import stock_zt_pool_em

__all__ = [
    "stock_info_a_code_name",
    "stock_zh_a_hist",
    "stock_zh_a_hist_min_em",
    "index_zh_a_hist",
    "stock_zh_a_spot_em",
    "stock_individual_info_em",
    "stock_board_industry_name_em",
    "stock_zt_pool_em",
]
