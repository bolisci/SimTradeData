"""
扩展数据类型模块

提供ETF数据、板块数据和技术指标扩展功能。
"""

from .data_aggregator import DataAggregator
from .etf_data import ETFDataManager
from .sector_data import SectorDataManager
from .technical_indicators import TechnicalIndicatorManager

__all__ = [
    "ETFDataManager",
    "SectorDataManager",
    "TechnicalIndicatorManager",
    "DataAggregator",
]
