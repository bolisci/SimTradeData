"""
API路由器模块

提供高性能的数据查询接口，支持历史数据、股票信息、财务数据等查询。
"""

from .cache import QueryCache
from .formatters import ResultFormatter
from .query_builders import (
    FundamentalsQueryBuilder,
    HistoryQueryBuilder,
    SnapshotQueryBuilder,
    StockInfoQueryBuilder,
)
from .router import APIRouter

__all__ = [
    "APIRouter",
    "HistoryQueryBuilder",
    "SnapshotQueryBuilder",
    "FundamentalsQueryBuilder",
    "StockInfoQueryBuilder",
    "ResultFormatter",
    "QueryCache",
]
