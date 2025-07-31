#!/usr/bin/env python3
"""
测试增量同步器的增强流程
验证增量同步是否使用了增强的数据处理引擎
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


def test_incremental_sync_with_derived_fields():
    """测试增量同步器的衍生字段计算"""
    print("开始测试增量同步器的衍生字段计算...")

    # 初始化组件
    config = Config()
    db_manager = DatabaseManager()
    data_source_manager = DataSourceManager(config)
    processing_engine = DataProcessingEngine(db_manager, data_source_manager, config)
    incremental_sync = IncrementalSync(
        db_manager, data_source_manager, processing_engine, config
    )

    # 测试参数
    test_symbols = ["000001.SZ", "000002.SZ"]
    target_date = date(2025, 1, 24)

    print(f"测试股票: {test_symbols}")
    print(f"目标日期: {target_date}")

    # 清理测试数据
    print("清理旧的测试数据...")
    for symbol in test_symbols:
        db_manager.execute(
            "DELETE FROM market_data WHERE symbol = ? AND date >= ?",
            (symbol, "2025-01-20"),
        )

    # 使用增量同步器同步数据
    print("使用增量同步器同步数据...")
    sync_result = incremental_sync.sync_all_symbols(
        target_date=target_date, symbols=test_symbols, frequencies=["1d"]
    )

    print(f"同步结果: {sync_result}")

    # 检查数据库中的结果
    print("\n检查数据库中的增强数据...")
    for symbol in test_symbols:
        print(f"\n--- 检查股票 {symbol} ---")

        sql = """
        SELECT date, close, change_percent, prev_close, amplitude, source
        FROM market_data 
        WHERE symbol = ? AND date >= '2025-01-20'
        ORDER BY date DESC
        LIMIT 3
        """

        records = db_manager.fetchall(sql, (symbol,))

        if records:
            print(f"找到 {len(records)} 条记录:")
            enhanced_count = 0
            derived_field_count = 0

            for record in records:
                print(f"  日期: {record['date']}")
                print(f"  收盘: {record['close']}")
                print(f"  涨跌幅: {record['change_percent']}%")
                print(f"  前收盘: {record['prev_close']}")
                print(f"  振幅: {record['amplitude']}%")
                print(f"  数据源: {record['source']}")

                if record["source"] == "processed_enhanced":
                    enhanced_count += 1

                if (
                    record["change_percent"] is not None
                    and record["change_percent"] != 0
                ):
                    derived_field_count += 1

                print("  ---")

            print(f"✅ 增强处理记录: {enhanced_count}/{len(records)}")
            print(f"✅ 衍生字段计算记录: {derived_field_count}/{len(records)}")

        else:
            print("❌ 没有找到任何记录")

    # 统计整体数据质量
    print("\n=== 整体数据质量统计 ===")
    quality_sql = """
    SELECT 
        COUNT(*) as total_records,
        COUNT(CASE WHEN source = 'processed_enhanced' THEN 1 END) as enhanced_records,
        COUNT(CASE WHEN change_percent IS NOT NULL AND change_percent != 0 THEN 1 END) as derived_field_records,
        AVG(CASE WHEN change_percent IS NOT NULL THEN change_percent ELSE 0 END) as avg_change_percent
    FROM market_data 
    WHERE symbol IN (?, ?) AND date >= '2025-01-20'
    """

    quality_result = db_manager.fetchone(quality_sql, tuple(test_symbols))

    if quality_result:
        total = quality_result["total_records"]
        enhanced = quality_result["enhanced_records"]
        derived = quality_result["derived_field_records"]
        avg_change = quality_result["avg_change_percent"]

        print(f"总记录数: {total}")
        print(
            f"增强处理记录: {enhanced} ({enhanced/total*100:.1f}%)" if total > 0 else ""
        )
        print(
            f"衍生字段记录: {derived} ({derived/total*100:.1f}%)" if total > 0 else ""
        )
        print(f"平均涨跌幅: {avg_change:.4f}%")

        if enhanced == total and derived > 0:
            print("🎉 增量同步成功使用了增强的数据处理引擎！")
        else:
            print("⚠️  增量同步未完全使用增强处理引擎")

    # 关闭连接
    db_manager.close()
    print("\n测试完成")


if __name__ == "__main__":
    test_incremental_sync_with_derived_fields()
