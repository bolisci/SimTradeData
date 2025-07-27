"""
数据库模块

全新的数据库架构，提供高效的数据存储和查询功能。
"""

from .manager import DatabaseManager
from .schema import create_database_schema, get_table_list, validate_schema

__all__ = [
    "DatabaseManager",
    "create_database_schema",
    "get_table_list",
    "validate_schema",
]
