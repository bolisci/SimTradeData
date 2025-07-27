"""
API路由器演示

展示查询构建器、结果格式化器、缓存和路由器功能。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from datetime import datetime
from unittest.mock import Mock

from simtradedata.api import (
    APIRouter,
    FundamentalsQueryBuilder,
    HistoryQueryBuilder,
    QueryCache,
    ResultFormatter,
    SnapshotQueryBuilder,
)
from simtradedata.config import Config
from simtradedata.database import DatabaseManager

# 设置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def demo_query_builders():
    """演示查询构建器功能"""
    print("\n🔧 查询构建器演示")
    print("=" * 50)

    # 历史数据查询构建器
    print("📈 历史数据查询构建器:")
    history_builder = HistoryQueryBuilder()

    sql, params = history_builder.build_query(
        symbols=["000001.SZ", "600000.SS"],
        start_date="2024-01-01",
        end_date="2024-01-31",
        frequency="1d",
    )

    print(f"  SQL: {sql[:100]}...")
    print(f"  参数: {params}")

    # 股票代码标准化
    print(f"\n🏷️  股票代码标准化:")
    test_symbols = ["000001", "600000", "AAPL", "00700"]
    for symbol in test_symbols:
        normalized = history_builder.normalize_symbol(symbol)
        print(f"  {symbol} -> {normalized}")

    # 快照数据查询构建器
    print(f"\n📊 快照数据查询构建器:")
    snapshot_builder = SnapshotQueryBuilder()

    sql, params = snapshot_builder.build_query(symbols=["000001.SZ"], market="SZ")

    print(f"  SQL: {sql[:100]}...")
    print(f"  参数: {params}")

    # 财务数据查询构建器
    print(f"\n💰 财务数据查询构建器:")
    fundamentals_builder = FundamentalsQueryBuilder()

    sql, params = fundamentals_builder.build_query(
        symbols=["000001.SZ"], report_date="2023-12-31", report_type="Q4"
    )

    print(f"  SQL: {sql[:100]}...")
    print(f"  参数: {params}")


def demo_result_formatter():
    """演示结果格式化器功能"""
    print("\n📋 结果格式化器演示")
    print("=" * 50)

    formatter = ResultFormatter()

    # 模拟查询结果
    mock_data = [
        {
            "symbol": "000001.SZ",
            "trade_date": "2024-01-20",
            "open": 10.0,
            "high": 10.5,
            "low": 9.8,
            "close": 10.2,
            "volume": 1000000,
            "money": 10200000.0,
            "pe_ratio": 15.5,
            "pb_ratio": 1.2,
        },
        {
            "symbol": "600000.SS",
            "trade_date": "2024-01-20",
            "open": 8.0,
            "high": 8.3,
            "low": 7.9,
            "close": 8.1,
            "volume": 800000,
            "money": 6480000.0,
            "pe_ratio": 12.3,
            "pb_ratio": 0.9,
        },
    ]

    print(f"📥 原始数据 ({len(mock_data)} 条记录):")
    for i, record in enumerate(mock_data):
        print(
            f"  {i+1}. {record['symbol']}: 收盘价={record['close']}, 成交量={record['volume']:,}"
        )

    # DataFrame格式
    print(f"\n📊 DataFrame格式:")
    df_result = formatter.format_result(mock_data, "dataframe")
    print(f"  类型: {type(df_result)}")
    print(f"  形状: {df_result.shape}")
    print(f"  列名: {list(df_result.columns)}")
    print(f"  索引: {df_result.index.names}")

    # JSON格式
    print(f"\n📄 JSON格式:")
    json_result = formatter.format_result(mock_data, "json")
    print(f"  类型: {type(json_result)}")
    print(f"  长度: {len(json_result)} 字符")
    print(f"  包含字段: data, count, timestamp")

    # 字典格式
    print(f"\n📝 字典格式:")
    dict_result = formatter.format_result(mock_data, "dict")
    print(f"  类型: {type(dict_result)}")
    print(f"  键: {list(dict_result.keys())}")
    print(f"  数据条数: {dict_result['count']}")

    # 历史数据专用格式化
    print(f"\n📈 历史数据专用格式化:")
    history_result = formatter.format_history_result(
        mock_data,
        symbols=["000001.SZ", "600000.SS"],
        start_date="2024-01-01",
        end_date="2024-01-31",
        frequency="1d",
        format_type="dict",
    )

    metadata = history_result["metadata"]
    print(f"  查询类型: {metadata['query_type']}")
    print(f"  股票数量: {metadata['symbol_count']}")
    print(f"  记录数量: {metadata['record_count']}")
    print(f"  日期范围: {metadata['start_date']} 到 {metadata['end_date']}")


def demo_query_cache():
    """演示查询缓存功能"""
    print("\n💾 查询缓存演示")
    print("=" * 50)

    cache = QueryCache()

    # 缓存配置信息
    print(f"🔧 缓存配置:")
    print(f"  启用状态: {cache.enable_cache}")
    print(f"  TTL: {cache.cache_ttl} 秒")
    print(f"  最大大小: {cache.max_cache_size}")
    print(f"  压缩: {cache.cache_compression}")

    # 生成缓存键
    print(f"\n🔑 缓存键生成:")
    cache_key1 = cache.generate_cache_key(
        "history", symbols=["000001.SZ"], start_date="2024-01-01", frequency="1d"
    )
    print(f"  历史数据查询键: {cache_key1}")

    cache_key2 = cache.generate_cache_key(
        "snapshot", market="SZ", trade_date="2024-01-20"
    )
    print(f"  快照数据查询键: {cache_key2}")

    # 缓存操作
    print(f"\n💾 缓存操作:")
    test_data = {
        "symbol": "000001.SZ",
        "close": 10.2,
        "volume": 1000000,
        "timestamp": datetime.now().isoformat(),
    }

    # 设置缓存
    success = cache.set(cache_key1, test_data)
    print(f"  设置缓存: {success}")

    # 获取缓存
    cached_data = cache.get(cache_key1)
    print(f"  获取缓存: {'成功' if cached_data else '失败'}")
    print(f"  缓存数据: {cached_data}")

    # 缓存统计
    print(f"\n📊 缓存统计:")
    stats = cache.get_cache_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")


def demo_api_router():
    """演示API路由器功能"""
    print("\n🚀 API路由器演示")
    print("=" * 50)

    # 创建模拟数据库管理器
    db_manager = Mock(spec=DatabaseManager)

    # 模拟历史数据
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
            "pe_ratio": 15.5,
            "pb_ratio": 1.2,
            "ma5": 10.1,
            "ma10": 10.0,
            "ma20": 9.9,
        }
    ]

    # 模拟股票信息
    mock_stock_info = [
        {
            "symbol": "000001.SZ",
            "name": "平安银行",
            "market": "SZ",
            "industry": "银行",
            "list_date": "1991-04-03",
            "status": "active",
            "total_share": 19405918198,
            "float_share": 19405918198,
        }
    ]

    db_manager.fetchall.return_value = mock_history_data

    # 创建API路由器
    config = Config()
    router = APIRouter(db_manager, config)

    print(f"🔧 路由器配置:")
    print(f"  缓存启用: {router.enable_cache}")
    print(f"  查询日志: {router.enable_query_log}")
    print(f"  查询超时: {router.query_timeout} 秒")

    # 历史数据查询
    print(f"\n📈 历史数据查询:")
    history_result = router.get_history(
        symbols="000001.SZ",
        start_date="2024-01-01",
        end_date="2024-01-31",
        frequency="1d",
        format_type="dict",
    )

    print(f"  查询类型: {history_result['metadata']['query_type']}")
    print(f"  股票数量: {history_result['metadata']['symbol_count']}")
    print(f"  记录数量: {history_result['metadata']['record_count']}")
    print(
        f"  数据示例: {history_result['data'][0] if history_result['data'] else '无数据'}"
    )

    # 快照数据查询
    print(f"\n📊 快照数据查询:")
    snapshot_result = router.get_snapshot(
        symbols=["000001.SZ"], market="SZ", format_type="dict"
    )

    print(f"  查询类型: {snapshot_result['metadata']['query_type']}")
    print(f"  记录数量: {snapshot_result['metadata']['record_count']}")

    # 股票信息查询
    db_manager.fetchall.return_value = mock_stock_info

    print(f"\n🏢 股票信息查询:")
    stock_info_result = router.get_stock_info(
        market="SZ", industry="银行", format_type="dict"
    )

    print(f"  查询类型: {stock_info_result['metadata']['query_type']}")
    print(f"  记录数量: {stock_info_result['metadata']['record_count']}")
    if stock_info_result["data"]:
        stock = stock_info_result["data"][0]
        print(f"  示例股票: {stock['symbol']} - {stock['name']}")

    # API统计信息
    print(f"\n📊 API统计信息:")
    stats = router.get_api_stats()

    print(f"  缓存统计:")
    cache_stats = stats["cache"]
    print(f"    启用状态: {cache_stats['enabled']}")
    print(f"    缓存条目: {cache_stats['total_entries']}")
    print(f"    活跃条目: {cache_stats['active_entries']}")

    print(f"  格式化器:")
    formatter_info = stats["formatter"]
    print(f"    默认格式: {formatter_info['default_format']}")
    print(f"    支持格式: {formatter_info['supported_formats']}")

    print(f"  查询构建器:")
    builders = stats["builders"]
    print(f"    最大股票数: {builders['history']['max_symbols_per_query']}")
    print(f"    最大日期范围: {builders['history']['max_date_range_days']} 天")
    print(f"    支持频率: {builders['history']['supported_frequencies']}")
    print(f"    支持市场: {builders['supported_markets']}")


def main():
    """主演示函数"""
    print("🚀 SimTradeData API路由器演示")
    print("=" * 60)

    try:
        # 演示各个组件
        demo_query_builders()
        demo_result_formatter()
        demo_query_cache()
        demo_api_router()

        print("\n🎉 API路由器演示完成!")
        print("\n📝 总结:")
        print("✅ 查询构建器: 支持历史、快照、财务、股票信息查询")
        print("✅ 结果格式化器: DataFrame、JSON、字典多种格式")
        print("✅ 查询缓存: 智能缓存、LRU淘汰、压缩存储")
        print("✅ API路由器: 统一接口、错误处理、性能监控")
        print("✅ 高性能特性: SQL优化、缓存加速、并发支持")

    except Exception as e:
        logger.error(f"演示过程中出现错误: {e}")
        raise


if __name__ == "__main__":
    main()
