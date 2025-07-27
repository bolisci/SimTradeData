"""
多市场支持模块

提供港股、美股等多市场的数据适配和统一查询功能。
"""

from .currency import CurrencyConverter
from .hk_market import HKMarketAdapter
from .multi_market import MultiMarketManager
from .timezone_handler import TimezoneHandler
from .us_market import USMarketAdapter

__all__ = [
    "HKMarketAdapter",
    "USMarketAdapter",
    "MultiMarketManager",
    "CurrencyConverter",
    "TimezoneHandler",
]
