"""
PTrade SQLite数据缓存系统

高性能的PTrade API数据缓存解决方案，支持多市场、多频率的历史数据查询。
"""

__version__ = "0.1.0"
__author__ = "SimTradeData Team"

from .config import Config
from .database import DatabaseManager

__all__ = [
    "DatabaseManager",
    "Config",
]
