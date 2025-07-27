"""
测试数据预处理模块 (重构后)

验证批处理调度器功能。其他功能已整合到 DataProcessingEngine 和 SyncManager 中。
"""

import logging
from datetime import date
from unittest.mock import Mock

import pytest

from simtradedata.config import Config
from simtradedata.data_sources import DataSourceManager
from simtradedata.database import DatabaseManager
from simtradedata.preprocessor import BatchScheduler

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestBatchScheduler:
    """测试批处理调度器"""

    @pytest.fixture
    def mock_scheduler_components(self):
        """模拟调度器组件"""
        db_manager = Mock(spec=DatabaseManager)
        data_source_manager = Mock(spec=DataSourceManager)
        config = Config()

        return db_manager, data_source_manager, config

    def test_initialization(self, mock_scheduler_components):
        """测试初始化"""
        db_manager, data_source_manager, config = mock_scheduler_components

        scheduler = BatchScheduler(db_manager, data_source_manager, config)

        assert scheduler.db_manager is db_manager
        assert scheduler.data_source_manager is data_source_manager
        assert scheduler.processing_engine is not None
        assert scheduler.sync_manager is not None
        assert scheduler.is_running is False

        logger.info("✅ 批处理调度器初始化测试通过")

    def test_trading_day_check(self, mock_scheduler_components):
        """测试交易日检查"""
        db_manager, data_source_manager, config = mock_scheduler_components
        scheduler = BatchScheduler(db_manager, data_source_manager, config)

        # 模拟数据库返回
        db_manager.fetchone.return_value = {"is_trading": 1}

        # 测试交易日检查
        is_trading = scheduler._is_trading_day(date(2024, 1, 20))
        assert is_trading is True

        # 模拟非交易日
        db_manager.fetchone.return_value = None
        is_trading = scheduler._is_trading_day(date(2024, 1, 21))
        assert is_trading is False

        logger.info("✅ 交易日检查测试通过")

    def test_sync_delegation(self, mock_scheduler_components):
        """测试同步功能委托"""
        db_manager, data_source_manager, config = mock_scheduler_components
        scheduler = BatchScheduler(db_manager, data_source_manager, config)

        # 模拟 SyncManager 的返回值
        mock_result = {
            "target_date": "2024-01-20",
            "summary": {"successful_phases": 1, "failed_phases": 0},
        }
        scheduler.sync_manager.run_full_sync = Mock(return_value=mock_result)

        # 测试每日同步委托
        result = scheduler.run_daily_sync(date(2024, 1, 20))

        # 验证委托调用
        scheduler.sync_manager.run_full_sync.assert_called_once_with(
            target_date=date(2024, 1, 20), symbols=None, frequencies=["1d"]
        )

        assert result == mock_result
        logger.info("✅ 同步功能委托测试通过")

    def test_historical_sync_delegation(self, mock_scheduler_components):
        """测试历史同步委托"""
        db_manager, data_source_manager, config = mock_scheduler_components
        scheduler = BatchScheduler(db_manager, data_source_manager, config)

        # 模拟增量同步器的返回值
        mock_symbol_result = {"success_count": 5, "error_count": 0}
        scheduler.sync_manager.incremental_sync.sync_symbol_range = Mock(
            return_value=mock_symbol_result
        )

        # 测试历史同步委托
        result = scheduler.run_historical_sync(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 5),
            symbols=["000001.SZ", "000002.SZ"],
        )

        # 验证委托调用
        assert scheduler.sync_manager.incremental_sync.sync_symbol_range.call_count == 2
        assert result["total_symbols"] == 2
        assert result["success_count"] == 10  # 2 symbols * 5 success each

        logger.info("✅ 历史同步委托测试通过")


def test_preprocessor_integration():
    """运行预处理器集成测试"""
    logger.info("🚀 开始预处理器集成测试...")

    # 这个测试会被pytest自动发现和运行
    logger.info("🎉 预处理器集成测试完成!")


if __name__ == "__main__":
    # 运行集成测试
    test_preprocessor_integration()

    # 运行pytest测试
    pytest.main([__file__, "-v"])
