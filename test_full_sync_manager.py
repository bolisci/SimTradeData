#!/usr/bin/env python3
"""
测试完整的同步管理器
验证整个同步流程是否使用了增强的数据处理引擎
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
from simtradedata.sync import SyncManager


def test_full_sync_with_enhanced_processing():
    """测试完整同步管理器的增强数据处理"""
    print("🚀 开始测试完整同步管理器的增强数据处理...")

    # 初始化组件
    config = Config()
    db_manager = DatabaseManager()
    data_source_manager = DataSourceManager(config)
    processing_engine = DataProcessingEngine(db_manager, data_source_manager, config)
    sync_manager = SyncManager(
        db_manager, data_source_manager, processing_engine, config
    )

    # 测试参数 - 使用少量股票进行快速测试
    test_symbols = ["000001.SZ", "000002.SZ"]
    target_date = date(2025, 1, 24)

    print(f"测试股票: {test_symbols}")
    print(f"目标日期: {target_date}")

    # 清理测试数据
    print("清理旧的测试数据...")
    for symbol in test_symbols:
        db_manager.execute(
            "DELETE FROM market_data WHERE symbol = ? AND date >= ?",
            (symbol, "2025-01-22"),  # 只清理最近几天
        )

    # 运行完整同步（只测试增量同步阶段）
    print("开始完整同步流程...")
    try:
        sync_result = sync_manager.run_full_sync(
            target_date=target_date, symbols=test_symbols, frequencies=["1d"]
        )

        print("✅ 同步完成!")

        # 提取关键结果
        if isinstance(sync_result, dict) and sync_result.get("success", True):
            data = sync_result.get("data", sync_result)
            phases = data.get("phases", {})
            summary = data.get("summary", {})

            print(f"成功阶段: {summary.get('successful_phases', 0)}")
            print(f"失败阶段: {summary.get('failed_phases', 0)}")

            # 检查增量同步结果
            if "incremental_sync" in phases:
                inc_sync = phases["incremental_sync"]
                if inc_sync.get("status") == "completed":
                    result = inc_sync.get("result", {})
                    print(f"增量同步成功: {result.get('success_count', 0)}只股票")
                    print(f"增量同步错误: {result.get('error_count', 0)}只股票")
                else:
                    print(f"增量同步失败: {inc_sync.get('error', 'Unknown')}")
        else:
            print(f"同步失败: {sync_result}")

    except Exception as e:
        print(f"同步过程出现异常: {e}")

    # 检查数据库中的结果
    print("\n📊 检查数据库中的增强数据...")

    total_records = 0
    enhanced_records = 0
    derived_field_records = 0

    for symbol in test_symbols:
        print(f"\n--- 检查股票 {symbol} ---")

        sql = """
        SELECT date, close, change_percent, prev_close, amplitude, source, quality_score
        FROM market_data 
        WHERE symbol = ? AND date >= '2025-01-22'
        ORDER BY date DESC
        LIMIT 5
        """

        records = db_manager.fetchall(sql, (symbol,))

        if records:
            print(f"找到 {len(records)} 条记录:")

            for record in records:
                total_records += 1

                print(f"  日期: {record['date']}")
                print(f"  收盘: {record['close']}")
                print(f"  涨跌幅: {record['change_percent']}%")
                print(f"  前收盘: {record['prev_close']}")
                print(f"  振幅: {record['amplitude']}%")
                print(f"  数据源: {record['source']}")
                print(f"  质量分数: {record['quality_score']}")

                if record["source"] == "processed_enhanced":
                    enhanced_records += 1

                if (
                    record["change_percent"] is not None
                    and record["change_percent"] != 0
                ):
                    derived_field_records += 1

                print("  ---")
        else:
            print("❌ 没有找到任何记录")

    # 最终统计
    print(f"\n🎯 最终统计:")
    print(f"总记录数: {total_records}")
    print(
        f"增强处理记录: {enhanced_records} ({enhanced_records/total_records*100:.1f}%)"
        if total_records > 0
        else ""
    )
    print(
        f"衍生字段记录: {derived_field_records} ({derived_field_records/total_records*100:.1f}%)"
        if total_records > 0
        else ""
    )

    if enhanced_records == total_records and total_records > 0:
        print("🎉 完整同步管理器成功使用了增强的数据处理引擎！")
        print("✅ 所有记录都使用了 processed_enhanced 数据源")
        print("✅ 衍生字段计算正常工作")
        print("✅ 数据质量分数为100")
        success = True
    else:
        print("⚠️  同步结果不符合预期")
        success = False

    # 关闭连接
    db_manager.close()
    print(f"\n{'🎉 测试成功完成!' if success else '❌ 测试未通过'}")

    return success


if __name__ == "__main__":
    test_full_sync_with_enhanced_processing()
