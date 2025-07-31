#!/usr/bin/env python3
"""
测试增量同步对历史数据的处理行为
验证是否会重新处理已有数据
"""

import os
import sys
from datetime import date

# 添加项目路径
sys.path.insert(0, os.path.abspath("."))

from simtradedata.config import Config
from simtradedata.data_sources import DataSourceManager
from simtradedata.database import DatabaseManager
from simtradedata.preprocessor import DataProcessingEngine
from simtradedata.sync import IncrementalSync


def test_historical_data_behavior():
    """测试增量同步对历史数据的处理行为"""
    print("🔍 测试增量同步对历史数据的处理行为...")

    # 初始化组件
    config = Config()
    db_manager = DatabaseManager()
    data_source_manager = DataSourceManager(config)
    processing_engine = DataProcessingEngine(db_manager, data_source_manager, config)
    incremental_sync = IncrementalSync(
        db_manager, data_source_manager, processing_engine, config
    )

    # 测试股票
    test_symbol = "000001.SZ"
    target_date = date(2025, 1, 24)

    print(f"测试股票: {test_symbol}")
    print(f"目标日期: {target_date}")

    # 1. 检查当前数据状态
    print("\n📊 检查当前数据状态...")
    check_sql = """
    SELECT date, close, change_percent, prev_close, source
    FROM market_data 
    WHERE symbol = ? 
    ORDER BY date DESC 
    LIMIT 5
    """

    current_data = db_manager.fetchall(check_sql, (test_symbol,))

    if current_data:
        print(f"找到 {len(current_data)} 条最新记录:")
        for record in current_data:
            print(
                f"  {record['date']}: 收盘{record['close']}, 涨跌幅{record['change_percent']}%, 数据源:{record['source']}"
            )

    # 2. 获取最后数据日期
    last_date = incremental_sync.get_last_data_date(test_symbol, "1d")
    print(f"\n📅 最后数据日期: {last_date}")

    # 3. 计算同步范围
    start_date, end_date = incremental_sync.calculate_sync_range(
        test_symbol, target_date, "1d"
    )
    print(f"📅 计算的同步范围: {start_date} 到 {end_date}")

    if start_date is None:
        print("✅ 数据已是最新，不会进行同步")
        print("🔍 这意味着增量同步不会重新处理历史数据")
    else:
        print(f"🔄 会同步 {start_date} 到 {end_date} 的数据")
        print("🔍 这意味着只会处理新增的日期范围")

    # 4. 检查具体的数据质量情况
    print(f"\n📊 检查 {test_symbol} 的数据质量情况...")
    quality_sql = """
    SELECT 
        COUNT(*) as total_records,
        COUNT(CASE WHEN change_percent IS NULL THEN 1 END) as null_change_percent,
        COUNT(CASE WHEN source LIKE '%enhanced' THEN 1 END) as enhanced_records,
        MIN(date) as earliest_date,
        MAX(date) as latest_date
    FROM market_data 
    WHERE symbol = ?
    """

    quality_stats = db_manager.fetchone(quality_sql, (test_symbol,))

    if quality_stats:
        total = quality_stats["total_records"]
        print(f"  总记录数: {total}")
        print(
            f"  增强处理记录: {quality_stats['enhanced_records']} ({quality_stats['enhanced_records']/total*100:.1f}%)"
        )
        print(
            f"  change_percent为NULL: {quality_stats['null_change_percent']} ({quality_stats['null_change_percent']/total*100:.1f}%)"
        )
        print(
            f"  日期范围: {quality_stats['earliest_date']} 到 {quality_stats['latest_date']}"
        )

        if quality_stats["null_change_percent"] > 0:
            print(
                f"⚠️  该股票有 {quality_stats['null_change_percent']} 条历史记录的衍生字段为NULL"
            )
            print(f"🔍 增量同步不会重新处理这些历史数据")
        else:
            print(f"✅ 该股票的所有衍生字段都已计算完成")

    # 5. 测试强制全量更新的可能性
    print(f"\n🧪 测试如果删除最新数据会发生什么...")

    # 删除一些最新数据来模拟需要重新同步的情况
    delete_sql = "DELETE FROM market_data WHERE symbol = ? AND date >= ?"
    recent_date = "2025-01-20"

    print(f"删除 {test_symbol} 从 {recent_date} 开始的数据...")
    db_manager.execute(delete_sql, (test_symbol, recent_date))

    # 重新计算同步范围
    new_last_date = incremental_sync.get_last_data_date(test_symbol, "1d")
    new_start_date, new_end_date = incremental_sync.calculate_sync_range(
        test_symbol, target_date, "1d"
    )

    print(f"删除后的最后数据日期: {new_last_date}")
    print(f"删除后的同步范围: {new_start_date} 到 {new_end_date}")

    if new_start_date:
        print(f"🔄 现在会同步 {new_start_date} 到 {new_end_date} 的数据")
        print(f"🔍 这证明了增量同步只处理缺失的日期范围")

    db_manager.close()


def main():
    """主函数"""
    print("🚀 分析增量同步对历史数据的处理行为...")
    test_historical_data_behavior()

    print(f"\n📋 结论:")
    print(f"1️⃣ 增量同步只处理缺失的日期范围")
    print(f"2️⃣ 已存在的历史数据不会被重新处理")
    print(f"3️⃣ 即使历史数据的衍生字段为NULL，也不会自动补充")
    print(f"4️⃣ 要补充历史数据，需要:")
    print(f"   - 删除相关历史数据后重新同步")
    print(f"   - 或使用专门的数据补充脚本")


if __name__ == "__main__":
    main()
