"""
测试API路由器

验证查询构建器、结果格式化器、缓存和路由器功能。
"""

import logging
from datetime import date
from unittest.mock import Mock

import pandas as pd
import pytest

from simtradedata.api import (
    APIRouter,
    FundamentalsQueryBuilder,
    HistoryQueryBuilder,
    QueryCache,
    ResultFormatter,
    SnapshotQueryBuilder,
    StockInfoQueryBuilder,
)
from simtradedata.config import Config
from simtradedata.database import DatabaseManager

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestQueryBuilders:
    """测试查询构建器"""

    def test_history_query_builder(self):
        """测试历史数据查询构建器"""
        builder = HistoryQueryBuilder()

        # 测试单个股票查询
        sql, params = builder.build_query(
            symbols="000001.SZ",
            start_date="2024-01-01",
            end_date="2024-01-31",
            frequency="1d",
        )

        assert "SELECT" in sql
        assert "FROM market_data" in sql
        assert "WHERE" in sql
        assert "symbol = ?" in sql
        assert "frequency = ?" in sql
        assert "000001.SZ" in params
        assert "1d" in params

        logger.info("✅ 历史数据查询构建器测试通过")

    def test_symbol_normalization(self):
        """测试股票代码标准化"""
        builder = HistoryQueryBuilder()

        # 测试不同格式的股票代码
        assert builder.normalize_symbol("000001") == "000001.SZ"
        assert builder.normalize_symbol("600000") == "600000.SS"
        assert builder.normalize_symbol("000001.SZ") == "000001.SZ"
        assert builder.normalize_symbol("AAPL") == "AAPL.US"

        # 测试批量标准化
        symbols = builder.normalize_symbols(["000001", "600000", "AAPL"])
        assert symbols == ["000001.SZ", "600000.SS", "AAPL.US"]

        logger.info("✅ 股票代码标准化测试通过")

    def test_date_range_parsing(self):
        """测试日期范围解析"""
        builder = HistoryQueryBuilder()

        # 测试字符串日期
        start, end = builder.parse_date_range("2024-01-01", "2024-01-31")
        assert start == "2024-01-01"
        assert end == "2024-01-31"

        # 测试date对象
        start, end = builder.parse_date_range(date(2024, 1, 1), date(2024, 1, 31))
        assert start == "2024-01-01"
        assert end == "2024-01-31"

        # 测试无效日期范围
        with pytest.raises(ValueError):
            builder.parse_date_range("2024-01-31", "2024-01-01")

        logger.info("✅ 日期范围解析测试通过")

    def test_snapshot_query_builder(self):
        """测试快照数据查询构建器"""
        builder = SnapshotQueryBuilder()

        # 测试最新快照查询
        sql, params = builder.build_query(
            symbols=["000001.SZ", "600000.SS"], market="SZ"
        )

        assert "SELECT" in sql
        assert "FROM market_data" in sql
        assert "frequency = '1d'" in sql
        assert "MAX(trade_date)" in sql

        logger.info("✅ 快照数据查询构建器测试通过")

    def test_fundamentals_query_builder(self):
        """测试财务数据查询构建器"""
        builder = FundamentalsQueryBuilder()

        sql, params = builder.build_query(
            symbols=["000001.SZ"], report_date="2023-12-31", report_type="Q4"
        )

        assert "SELECT" in sql
        assert "FROM ptrade_fundamentals" in sql
        assert "report_date = ?" in sql
        assert "report_type = ?" in sql
        assert "2023-12-31" in params
        assert "Q4" in params

        logger.info("✅ 财务数据查询构建器测试通过")

    def test_stock_info_query_builder(self):
        """测试股票信息查询构建器"""
        builder = StockInfoQueryBuilder()

        sql, params = builder.build_query(market="SZ", industry="银行", status="active")

        assert "SELECT" in sql
        assert "FROM stocks" in sql
        assert "market = ?" in sql
        assert "industry LIKE ?" in sql
        assert "status = ?" in sql

        logger.info("✅ 股票信息查询构建器测试通过")


class TestResultFormatter:
    """测试结果格式化器"""

    def test_dataframe_formatting(self):
        """测试DataFrame格式化"""
        formatter = ResultFormatter()

        # 模拟查询结果
        data = [
            {
                "symbol": "000001.SZ",
                "trade_date": "2024-01-20",
                "open": 10.0,
                "high": 10.5,
                "low": 9.8,
                "close": 10.2,
                "volume": 1000000,
            },
            {
                "symbol": "600000.SS",
                "trade_date": "2024-01-20",
                "open": 8.0,
                "high": 8.3,
                "low": 7.9,
                "close": 8.1,
                "volume": 800000,
            },
        ]

        # 转换为DataFrame
        df = formatter.format_result(data, "dataframe")

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert "open" in df.columns
        assert "close" in df.columns

        logger.info("✅ DataFrame格式化测试通过")

    def test_json_formatting(self):
        """测试JSON格式化"""
        formatter = ResultFormatter()

        data = [{"symbol": "000001.SZ", "close": 10.2, "volume": 1000000}]

        metadata = {"query_type": "history", "symbol_count": 1}

        json_result = formatter.format_result(data, "json", metadata)

        assert isinstance(json_result, str)
        assert '"data"' in json_result
        assert '"metadata"' in json_result
        assert '"timestamp"' in json_result

        logger.info("✅ JSON格式化测试通过")

    def test_error_formatting(self):
        """测试错误格式化"""
        formatter = ResultFormatter()

        error_result = formatter.format_error_result("测试错误", "TEST_ERROR", "json")

        assert isinstance(error_result, str)
        assert '"error"' in error_result
        assert '"error_message"' in error_result

        logger.info("✅ 错误格式化测试通过")


class TestQueryCache:
    """测试查询缓存"""

    def test_cache_operations(self):
        """测试缓存基本操作"""
        cache = QueryCache()

        # 测试设置和获取
        test_data = {"symbol": "000001.SZ", "close": 10.2}
        cache_key = "test_key"

        success = cache.set(cache_key, test_data)
        assert success is True

        cached_data = cache.get(cache_key)
        assert cached_data == test_data

        # 测试删除
        success = cache.remove(cache_key)
        assert success is True

        cached_data = cache.get(cache_key)
        assert cached_data is None

        logger.info("✅ 缓存基本操作测试通过")

    def test_cache_key_generation(self):
        """测试缓存键生成"""
        cache = QueryCache()

        # 测试相同参数生成相同键
        key1 = cache.generate_cache_key(
            "history", symbols=["000001.SZ"], frequency="1d"
        )
        key2 = cache.generate_cache_key(
            "history", symbols=["000001.SZ"], frequency="1d"
        )
        assert key1 == key2

        # 测试不同参数生成不同键
        key3 = cache.generate_cache_key(
            "history", symbols=["600000.SS"], frequency="1d"
        )
        assert key1 != key3

        logger.info("✅ 缓存键生成测试通过")

    def test_cache_stats(self):
        """测试缓存统计"""
        cache = QueryCache()

        # 添加一些测试数据
        cache.set("key1", {"data": "test1"})
        cache.set("key2", {"data": "test2"})

        stats = cache.get_cache_stats()

        assert "total_entries" in stats
        assert "active_entries" in stats
        assert stats["total_entries"] >= 2

        logger.info("✅ 缓存统计测试通过")


class TestAPIRouter:
    """测试API路由器"""

    @pytest.fixture
    def mock_db_manager(self):
        """模拟数据库管理器"""
        db_manager = Mock(spec=DatabaseManager)

        # 模拟历史数据查询结果
        mock_history_data = [
            {
                "symbol": "000001.SZ",
                "trade_date": "2024-01-20",
                "frequency": "1d",
                "open": 10.0,
                "high": 10.5,
                "low": 9.8,
                "close": 10.2,
                "volume": 1000000,
                "money": 10200000,
            }
        ]

        # 模拟股票信息查询结果
        mock_stock_info = [
            {
                "symbol": "000001.SZ",
                "name": "平安银行",
                "market": "SZ",
                "industry": "银行",
                "status": "active",
            }
        ]

        db_manager.fetchall.return_value = mock_history_data

        return db_manager

    def test_router_initialization(self, mock_db_manager):
        """测试路由器初始化"""
        config = Config()
        router = APIRouter(mock_db_manager, config)

        assert router.db_manager is mock_db_manager
        assert router.config is config
        assert router.history_builder is not None
        assert router.formatter is not None
        assert router.cache is not None

        logger.info("✅ API路由器初始化测试通过")

    def test_get_history(self, mock_db_manager):
        """测试历史数据查询"""
        router = APIRouter(mock_db_manager)

        # 测试查询
        result = router.get_history(
            symbols="000001.SZ",
            start_date="2024-01-01",
            end_date="2024-01-31",
            frequency="1d",
            format_type="dict",
        )

        assert isinstance(result, dict)
        assert "data" in result
        assert "metadata" in result
        assert len(result["data"]) >= 0

        # 验证数据库查询被调用
        mock_db_manager.fetchall.assert_called()

        logger.info("✅ 历史数据查询测试通过")

    def test_get_snapshot(self, mock_db_manager):
        """测试快照数据查询"""
        router = APIRouter(mock_db_manager)

        result = router.get_snapshot(
            symbols=["000001.SZ", "600000.SS"], market="SZ", format_type="dict"
        )

        assert isinstance(result, dict)
        assert "data" in result
        assert "metadata" in result

        logger.info("✅ 快照数据查询测试通过")

    def test_get_stock_info(self, mock_db_manager):
        """测试股票信息查询"""
        router = APIRouter(mock_db_manager)

        result = router.get_stock_info(market="SZ", industry="银行", format_type="dict")

        assert isinstance(result, dict)
        assert "data" in result

        logger.info("✅ 股票信息查询测试通过")

    def test_api_stats(self, mock_db_manager):
        """测试API统计"""
        router = APIRouter(mock_db_manager)

        stats = router.get_api_stats()

        assert "cache" in stats
        assert "formatter" in stats
        assert "config" in stats
        assert "builders" in stats

        logger.info("✅ API统计测试通过")


def test_api_router_integration():
    """API路由器集成测试"""
    logger.info("🚀 开始API路由器集成测试...")

    # 创建模拟组件
    config = Config()
    db_manager = Mock(spec=DatabaseManager)

    # 模拟数据库返回
    mock_data = [
        {
            "symbol": "000001.SZ",
            "trade_date": "2024-01-20",
            "frequency": "1d",
            "open": 10.0,
            "high": 10.5,
            "low": 9.8,
            "close": 10.2,
            "volume": 1000000,
            "money": 10200000,
            "pe_ratio": 15.5,
            "pb_ratio": 1.2,
        }
    ]

    db_manager.fetchall.return_value = mock_data

    # 创建API路由器
    router = APIRouter(db_manager, config)

    # 测试查询构建器
    builder = HistoryQueryBuilder(config)
    sql, params = builder.build_query(
        symbols="000001.SZ", start_date="2024-01-01", end_date="2024-01-31"
    )
    assert "SELECT" in sql
    assert "000001.SZ" in params

    # 测试结果格式化器
    formatter = ResultFormatter(config)
    df_result = formatter.format_result(mock_data, "dataframe")
    assert isinstance(df_result, pd.DataFrame)

    json_result = formatter.format_result(mock_data, "json")
    assert isinstance(json_result, str)

    # 测试查询缓存
    cache = QueryCache(config)
    cache_key = cache.generate_cache_key("test", symbol="000001.SZ")
    cache.set(cache_key, mock_data)
    cached_data = cache.get(cache_key)
    assert cached_data == mock_data

    # 测试API路由器查询
    result = router.get_history(
        symbols="000001.SZ",
        start_date="2024-01-01",
        end_date="2024-01-31",
        format_type="dict",
    )

    assert isinstance(result, dict)
    assert "data" in result
    assert "metadata" in result
    assert result["metadata"]["query_type"] == "history"

    # 测试API统计
    stats = router.get_api_stats()
    assert "cache" in stats
    assert "formatter" in stats

    logger.info("🎉 API路由器集成测试通过!")


if __name__ == "__main__":
    # 运行集成测试
    test_api_router_integration()

    # 运行pytest测试
    pytest.main([__file__, "-v"])
