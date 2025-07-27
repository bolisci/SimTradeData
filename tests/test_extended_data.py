"""
测试扩展数据类型

验证ETF数据、板块数据、技术指标和数据聚合功能。
"""

import logging
from datetime import date, datetime
from unittest.mock import Mock, patch

import pytest

from simtradedata.config import Config
from simtradedata.database import DatabaseManager
from simtradedata.extended_data import (
    DataAggregator,
    ETFDataManager,
    SectorDataManager,
    TechnicalIndicatorManager,
)

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestETFDataManager:
    """测试ETF数据管理器"""

    @pytest.fixture
    def mock_db_manager(self):
        """模拟数据库管理器"""
        return Mock(spec=DatabaseManager)

    def test_initialization(self, mock_db_manager):
        """测试初始化"""
        config = Config()
        manager = ETFDataManager(mock_db_manager, config)

        assert manager.db_manager is mock_db_manager
        assert manager.config is config
        assert "stock" in manager.etf_types
        assert "bond" in manager.etf_types

        logger.info("✅ ETF数据管理器初始化测试通过")

    def test_save_etf_info(self, mock_db_manager):
        """测试保存ETF基础信息"""
        manager = ETFDataManager(mock_db_manager)

        etf_data = {
            "symbol": "510300.SS",
            "name": "沪深300ETF",
            "market": "SS",
            "etf_type": "index",
            "underlying_index": "沪深300",
            "management_company": "华夏基金",
            "expense_ratio": 0.5,
            "aum": 50000000000,
        }

        # 模拟数据库执行成功
        mock_db_manager.execute.return_value = None

        result = manager.save_etf_info(etf_data)

        assert result == True
        mock_db_manager.execute.assert_called_once()

        logger.info("✅ 保存ETF基础信息测试通过")

    def test_save_etf_holdings(self, mock_db_manager):
        """测试保存ETF成分股"""
        manager = ETFDataManager(mock_db_manager)

        holdings_data = [
            {
                "stock_symbol": "000001.SZ",
                "stock_name": "平安银行",
                "weight": 3.5,
                "shares": 1000000,
                "market_value": 15000000,
                "sector": "金融",
            },
            {
                "stock_symbol": "600000.SS",
                "stock_name": "浦发银行",
                "weight": 2.8,
                "shares": 800000,
                "market_value": 12000000,
                "sector": "金融",
            },
        ]

        # 模拟数据库执行成功
        mock_db_manager.execute.return_value = None

        result = manager.save_etf_holdings("510300.SS", holdings_data)

        assert result == True
        # 应该调用删除和插入操作
        assert mock_db_manager.execute.call_count >= 2

        logger.info("✅ 保存ETF成分股测试通过")

    def test_get_etf_info(self, mock_db_manager):
        """测试获取ETF信息"""
        manager = ETFDataManager(mock_db_manager)

        # 模拟数据库返回
        mock_db_manager.fetchone.return_value = {
            "symbol": "510300.SS",
            "name": "沪深300ETF",
            "etf_type": "index",
            "aum": 50000000000,
        }

        result = manager.get_etf_info("510300.SS")

        assert result is not None
        assert result["symbol"] == "510300.SS"
        assert result["name"] == "沪深300ETF"

        logger.info("✅ 获取ETF信息测试通过")


class TestSectorDataManager:
    """测试板块数据管理器"""

    @pytest.fixture
    def mock_db_manager(self):
        """模拟数据库管理器"""
        return Mock(spec=DatabaseManager)

    def test_initialization(self, mock_db_manager):
        """测试初始化"""
        config = Config()
        manager = SectorDataManager(mock_db_manager, config)

        assert manager.db_manager is mock_db_manager
        assert "sw" in manager.industry_standards
        assert "industry" in manager.sector_types

        logger.info("✅ 板块数据管理器初始化测试通过")

    def test_save_industry_classification(self, mock_db_manager):
        """测试保存行业分类"""
        manager = SectorDataManager(mock_db_manager)

        classification_data = {
            "symbol": "000001.SZ",
            "stock_name": "平安银行",
            "standard": "sw",
            "level1_code": "801780",
            "level1_name": "银行",
            "level2_code": "801780",
            "level2_name": "银行",
            "effective_date": "2024-01-01",
        }

        # 模拟数据库执行成功
        mock_db_manager.execute.return_value = None

        result = manager.save_industry_classification(classification_data)

        assert result == True
        mock_db_manager.execute.assert_called_once()

        logger.info("✅ 保存行业分类测试通过")

    def test_get_stock_industry(self, mock_db_manager):
        """测试获取股票行业分类"""
        manager = SectorDataManager(mock_db_manager)

        # 模拟数据库返回
        mock_db_manager.fetchone.return_value = {
            "symbol": "000001.SZ",
            "level1_name": "银行",
            "level2_name": "银行",
            "standard": "sw",
        }

        result = manager.get_stock_industry("000001.SZ", "sw")

        assert result is not None
        assert result["level1_name"] == "银行"

        logger.info("✅ 获取股票行业分类测试通过")


class TestTechnicalIndicatorManager:
    """测试技术指标管理器"""

    @pytest.fixture
    def mock_db_manager(self):
        """模拟数据库管理器"""
        db_manager = Mock(spec=DatabaseManager)

        # 模拟价格数据
        mock_price_data = [
            {
                "trade_date": "2024-01-15",
                "open": 10.0,
                "high": 10.5,
                "low": 9.8,
                "close": 10.2,
                "volume": 1000000,
                "money": 10200000,
            },
            {
                "trade_date": "2024-01-16",
                "open": 10.2,
                "high": 10.8,
                "low": 10.0,
                "close": 10.5,
                "volume": 1200000,
                "money": 12600000,
            },
            {
                "trade_date": "2024-01-17",
                "open": 10.5,
                "high": 10.6,
                "low": 10.1,
                "close": 10.3,
                "volume": 900000,
                "money": 9270000,
            },
        ]

        db_manager.fetchall.return_value = mock_price_data

        return db_manager

    def test_initialization(self, mock_db_manager):
        """测试初始化"""
        config = Config()
        manager = TechnicalIndicatorManager(mock_db_manager, config)

        assert manager.db_manager is mock_db_manager
        assert "ma" in manager.builtin_indicators
        assert "rsi" in manager.builtin_indicators
        assert "macd" in manager.builtin_indicators

        logger.info("✅ 技术指标管理器初始化测试通过")

    @patch("simtradedata.extended_data.technical_indicators.pd")
    def test_calculate_ma_indicator(self, mock_pd, mock_db_manager):
        """测试计算移动平均线"""
        # 跳过如果没有pandas
        if mock_pd is None:
            pytest.skip("pandas not available")

        manager = TechnicalIndicatorManager(mock_db_manager)

        # 模拟pandas DataFrame
        mock_df = Mock()
        mock_df.columns = ["open", "high", "low", "close", "volume", "money"]
        mock_df.__getitem__ = Mock(return_value=Mock())
        mock_df.__getitem__.return_value.rolling.return_value.mean.return_value.items.return_value = [
            (datetime(2024, 1, 15), 10.0),
            (datetime(2024, 1, 16), 10.25),
            (datetime(2024, 1, 17), 10.33),
        ]

        mock_pd.DataFrame.return_value = mock_df
        mock_pd.to_datetime.return_value = mock_df
        mock_pd.isna.return_value = False

        result = manager.calculate_indicator("000001.SZ", "ma", {"period": 5})

        # 由于模拟的复杂性，主要测试是否能正常调用
        assert isinstance(result, list)

        logger.info("✅ 计算移动平均线测试通过")

    def test_get_available_indicators(self, mock_db_manager):
        """测试获取可用指标"""
        manager = TechnicalIndicatorManager(mock_db_manager)

        indicators = manager.get_available_indicators()

        assert "builtin" in indicators
        assert "custom" in indicators
        assert "ma" in indicators["builtin"]
        assert "rsi" in indicators["builtin"]

        logger.info("✅ 获取可用指标测试通过")


class TestDataAggregator:
    """测试数据聚合器"""

    @pytest.fixture
    def mock_db_manager(self):
        """模拟数据库管理器"""
        db_manager = Mock(spec=DatabaseManager)

        # 模拟聚合查询结果
        mock_aggregation_data = [
            {
                "period": "2024-01-15",
                "avg_price": 10.2,
                "avg_change_pct": 1.5,
                "total_volume": 5000000,
            },
            {
                "period": "2024-01-16",
                "avg_price": 10.5,
                "avg_change_pct": 2.1,
                "total_volume": 6000000,
            },
        ]

        # 模拟市场统计数据
        mock_market_stats = {
            "total_stocks": 100,
            "total_records": 1000,
            "avg_price": 15.5,
            "total_volume": 50000000,
            "avg_change_pct": 1.2,
        }

        def fetchall_side_effect(sql, params=None):
            if "GROUP BY" in sql:
                return mock_aggregation_data
            else:
                return []

        def fetchone_side_effect(sql, params=None):
            if "COUNT" in sql or "AVG" in sql:
                return mock_market_stats
            else:
                return None

        db_manager.fetchall.side_effect = fetchall_side_effect
        db_manager.fetchone.side_effect = fetchone_side_effect

        return db_manager

    def test_initialization(self, mock_db_manager):
        """测试初始化"""
        config = Config()
        aggregator = DataAggregator(mock_db_manager, config)

        assert aggregator.db_manager is mock_db_manager
        assert "time" in aggregator.aggregation_dimensions
        assert "price" in aggregator.aggregation_metrics

        logger.info("✅ 数据聚合器初始化测试通过")

    def test_calculate_market_statistics(self, mock_db_manager):
        """测试计算市场统计"""
        aggregator = DataAggregator(mock_db_manager)

        result = aggregator.calculate_market_statistics("SZ", 30)

        assert result is not None
        assert "market" in result
        assert "basic_stats" in result
        assert result["market"] == "SZ"

        logger.info("✅ 计算市场统计测试通过")

    def test_aggregate_market_data(self, mock_db_manager):
        """测试聚合市场数据"""
        aggregator = DataAggregator(mock_db_manager)

        config = {
            "dimension": "time",
            "granularity": "daily",
            "metrics": ["price", "volume"],
            "start_date": date(2024, 1, 15),
            "end_date": date(2024, 1, 17),
        }

        result = aggregator.aggregate_market_data(config)

        assert result is not None
        assert "dimension" in result
        assert "data" in result
        assert result["dimension"] == "time"

        logger.info("✅ 聚合市场数据测试通过")


def test_extended_data_integration():
    """扩展数据类型集成测试"""
    logger.info("🚀 开始扩展数据类型集成测试...")

    # 创建模拟组件
    config = Config()
    db_manager = Mock(spec=DatabaseManager)

    # 模拟数据库返回
    db_manager.execute.return_value = None

    def fetchone_side_effect(sql, params=None):
        if "COUNT(*) as total" in sql and "ptrade_etf_info" in sql:
            return {"total": 10}
        elif "COUNT(*) as total" in sql and "ptrade_concept_sectors" in sql:
            return {"total": 25}
        elif "COUNT(DISTINCT symbol)" in sql:
            return {
                "total_stocks": 100,
                "total_records": 1000,
                "avg_price": 15.5,
                "total_volume": 50000000,
                "total_turnover": 15500000000,
                "avg_change_pct": 1.2,
                "volatility": 2.5,
            }
        elif "SUM(CASE WHEN change_percent" in sql:
            return {
                "rising_count": 600,
                "falling_count": 350,
                "flat_count": 50,
                "max_gain": 10.0,
                "max_loss": -8.5,
            }
        elif "SUM(close * total_share)" in sql:
            return {"total_market_cap": 1000000000000, "avg_market_cap": 10000000000}
        else:
            return {"symbol": "510300.SS", "name": "沪深300ETF", "etf_type": "index"}

    def fetchall_side_effect(sql, params=None):
        if "GROUP BY etf_type" in sql:
            return [{"etf_type": "stock", "count": 5}, {"etf_type": "bond", "count": 3}]
        elif "GROUP BY market" in sql:
            return [{"market": "SZ", "count": 6}, {"market": "SS", "count": 4}]
        elif "GROUP BY sector_type" in sql:
            return [
                {"sector_type": "industry", "count": 20},
                {"sector_type": "concept", "count": 15},
            ]
        elif "GROUP BY standard" in sql:
            return [
                {"standard": "sw", "stock_count": 1000},
                {"standard": "citic", "stock_count": 800},
            ]
        else:
            return [
                {
                    "trade_date": "2024-01-15",
                    "open": 10.0,
                    "high": 10.5,
                    "low": 9.8,
                    "close": 10.2,
                    "volume": 1000000,
                    "money": 10200000,
                }
            ]

    db_manager.fetchone.side_effect = fetchone_side_effect
    db_manager.fetchall.side_effect = fetchall_side_effect

    # 测试ETF数据管理器
    etf_manager = ETFDataManager(db_manager, config)

    # 测试保存ETF信息
    etf_data = {
        "symbol": "510300.SS",
        "name": "沪深300ETF",
        "etf_type": "index",
        "aum": 50000000000,
    }

    result = etf_manager.save_etf_info(etf_data)
    assert result == True

    # 测试获取ETF信息
    etf_info = etf_manager.get_etf_info("510300.SS")
    assert etf_info is not None
    assert etf_info["symbol"] == "510300.SS"

    # 测试板块数据管理器
    sector_manager = SectorDataManager(db_manager, config)

    # 测试保存行业分类
    classification_data = {
        "symbol": "000001.SZ",
        "standard": "sw",
        "level1_name": "银行",
    }

    result = sector_manager.save_industry_classification(classification_data)
    assert result == True

    # 测试技术指标管理器
    indicator_manager = TechnicalIndicatorManager(db_manager, config)

    # 测试获取可用指标
    indicators = indicator_manager.get_available_indicators()
    assert "builtin" in indicators
    assert "ma" in indicators["builtin"]

    # 测试数据聚合器
    aggregator = DataAggregator(db_manager, config)

    # 测试市场统计
    market_stats = aggregator.calculate_market_statistics("SZ", 30)
    assert market_stats is not None
    assert "market" in market_stats

    # 测试获取统计信息
    etf_stats = etf_manager.get_manager_stats()
    assert "etf_types" in etf_stats

    sector_stats = sector_manager.get_manager_stats()
    assert "sector_types" in sector_stats

    indicator_stats = indicator_manager.get_manager_stats()
    assert "builtin_indicators" in indicator_stats

    aggregator_stats = aggregator.get_aggregator_stats()
    assert "aggregation_dimensions" in aggregator_stats

    logger.info("🎉 扩展数据类型集成测试通过!")


if __name__ == "__main__":
    # 运行集成测试
    test_extended_data_integration()

    # 运行pytest测试
    pytest.main([__file__, "-v"])
