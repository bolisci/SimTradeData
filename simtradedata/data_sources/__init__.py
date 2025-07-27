"""
数据源模块

提供多个数据源的统一接口，包括AkShare、BaoStock、QStock等。
"""

from .akshare_adapter import AkShareAdapter
from .baostock_adapter import BaoStockAdapter
from .base import BaseDataSource
from .manager import DataSourceManager
from .qstock_adapter import QStockAdapter

__all__ = [
    "BaseDataSource",
    "DataSourceManager",
    "AkShareAdapter",
    "BaoStockAdapter",
    "QStockAdapter",
]
