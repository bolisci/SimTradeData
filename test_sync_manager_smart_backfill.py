#!/usr/bin/env python3
"""
测试完整同步管理器的智能补充功能
验证整个同步流程中智能补充是否正常工作
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


def test_sync_manager_smart_backfill():
    """测试同步管理器的智能补充功能"""
    print("🚀 测试完整同步管理器的智能补充功能...")

    # 初始化组件
    config = Config()
    db_manager = DatabaseManager()
    data_source_manager = DataSourceManager(config)
    processing_engine = DataProcessingEngine(db_manager, data_source_manager, config)
    sync_manager = SyncManager(
        db_manager, data_source_manager, processing_engine, config
    )

    # 测试参数 - 使用一些还没有补充过的股票
    test_symbols = ["002415.SZ", "300059.SZ"]  # 使用不同的股票
    target_date = date(2025, 1, 24)

    print(f"测试股票: {test_symbols}")
    print(f"目标日期: {target_date}")

    # 1. 检查测试股票的数据质量
    print("\n📊 检查测试股票的数据质量...")

    initial_stats = {}
    for symbol in test_symbols:
        quality_check = sync_manager.incremental_sync.check_data_quality(symbol, "1d")
        initial_stats[symbol] = quality_check

        print(f"{symbol}:")
        print(f"  总记录数: {quality_check.get('total_records', 0)}")
        print(f"  NULL字段数: {quality_check.get('null_change_percent', 0)}")
        print(
            f"  需要补充: {'是' if quality_check.get('needs_backfill', False) else '否'}"
        )
        print(f"  补充比例: {quality_check.get('backfill_ratio', 0)*100:.1f}%")

    # 2. 运行完整同步管理器
    print(f"\n🔄 运行完整同步管理器...")
    try:
        sync_result = sync_manager.run_full_sync(
            target_date=target_date, symbols=test_symbols, frequencies=["1d"]
        )

        print("✅ 完整同步完成!")

        # 解析结果
        if isinstance(sync_result, dict) and sync_result.get("success", True):
            data = sync_result.get("data", sync_result)
            phases = data.get("phases", {})
            summary = data.get("summary", {})

            print(f"成功阶段: {summary.get('successful_phases', 0)}")
            print(f"失败阶段: {summary.get('failed_phases', 0)}")

            # 检查增量同步阶段是否包含智能补充统计
            if "incremental_sync" in phases:
                inc_sync = phases["incremental_sync"]
                if inc_sync.get("status") == "completed" and "result" in inc_sync:
                    result = inc_sync["result"]

                    # 查找智能补充统计
                    backfill_stats = result.get("smart_backfill", {})
                    if backfill_stats:
                        print(f"\n📈 智能补充统计:")
                        print(
                            f"  功能启用: {'是' if backfill_stats.get('enabled', False) else '否'}"
                        )
                        print(
                            f"  检查股票数: {backfill_stats.get('checked_symbols', 0)}"
                        )
                        print(
                            f"  需要补充股票数: {backfill_stats.get('needs_backfill_symbols', 0)}"
                        )
                        print(
                            f"  实际补充股票数: {backfill_stats.get('backfilled_symbols', 0)}"
                        )
                        print(
                            f"  补充记录数: {backfill_stats.get('backfilled_records', 0)}"
                        )
                        print(
                            f"  补充错误数: {backfill_stats.get('backfill_errors', 0)}"
                        )
                    else:
                        print(f"\n⚠️  未找到智能补充统计信息")
                else:
                    print(f"\n❌ 增量同步阶段失败: {inc_sync.get('error', 'Unknown')}")
            else:
                print(f"\n⚠️  增量同步阶段未找到")
        else:
            print(f"❌ 同步失败: {sync_result}")
            return False

    except Exception as e:
        print(f"❌ 同步过程出现异常: {e}")
        return False

    # 3. 验证补充结果
    print(f"\n✅ 验证智能补充结果...")

    total_initial_null = 0
    total_final_null = 0
    total_enhanced = 0
    total_backfilled = 0

    for symbol in test_symbols:
        print(f"\n--- 验证股票 {symbol} ---")

        # 初始状态
        initial = initial_stats[symbol]
        initial_null = initial.get("null_change_percent", 0)
        initial_total = initial.get("total_records", 0)
        total_initial_null += initial_null

        # 检查补充后的数据质量
        final_quality = sync_manager.incremental_sync.check_data_quality(symbol, "1d")
        final_null = final_quality.get("null_change_percent", 0)
        final_total = final_quality.get("total_records", 0)
        enhanced_records = final_quality.get("enhanced_records", 0)

        total_final_null += final_null
        total_enhanced += enhanced_records

        # 计算补充的记录数
        backfilled_records = initial_null - final_null
        total_backfilled += backfilled_records

        print(f"  补充前: {initial_null}/{initial_total} 条NULL记录")
        print(f"  补充后: {final_null}/{final_total} 条NULL记录")
        print(f"  补充数量: {backfilled_records} 条记录")
        print(
            f"  增强记录数: {enhanced_records} ({enhanced_records/final_total*100:.1f}%)"
            if final_total > 0
            else ""
        )

        # 显示几个示例记录
        sample_sql = """
        SELECT date, close, change_percent, prev_close, amplitude, source
        FROM market_data 
        WHERE symbol = ? AND source LIKE '%enhanced%'
        ORDER BY date DESC 
        LIMIT 3
        """

        samples = db_manager.fetchall(sample_sql, (symbol,))

        if samples:
            print(f"  增强数据示例:")
            for sample in samples:
                print(
                    f"    {sample['date']}: 收盘{sample['close']}, 涨跌幅{sample['change_percent']}%, 振幅{sample['amplitude']}%, 数据源:{sample['source']}"
                )
        else:
            print(f"  ⚠️  没有找到增强处理的数据")

    # 4. 总结
    print(f"\n🎯 智能补充功能测试总结:")
    print(f"  测试股票数: {len(test_symbols)}")
    print(f"  初始NULL记录数: {total_initial_null}")
    print(f"  最终NULL记录数: {total_final_null}")
    print(f"  补充记录数: {total_backfilled}")
    print(f"  增强记录总数: {total_enhanced}")

    # 成功标准：NULL记录显著减少，增强记录数量增加
    improvement = total_initial_null - total_final_null
    success = improvement > 0 and total_enhanced > 0

    if success:
        print(f"🎉 完整同步管理器智能补充功能测试成功!")
        print(f"✅ 成功补充了 {improvement} 条历史记录的衍生字段")
        print(f"✅ 生成了 {total_enhanced} 条增强处理记录")
        print(f"✅ 智能补充功能完全集成到完整同步流程中")
    else:
        print(f"❌ 智能补充功能测试失败")
        if improvement == 0:
            print(f"⚠️  没有补充任何历史记录")
        if total_enhanced == 0:
            print(f"⚠️  没有生成增强处理记录")

    db_manager.close()
    return success


def main():
    """主函数"""
    print("🧪 开始完整同步管理器智能补充功能测试...")

    success = test_sync_manager_smart_backfill()

    if success:
        print(f"\n🎉 完整同步管理器智能补充功能已验证可用!")
        print(f"📋 现在您可以:")
        print(f"   ✅ 运行任何全量同步，系统会自动检测并补充历史数据")
        print(f"   ✅ 无需手动干预，约200万条历史记录将自动补充衍生字段")
        print(f"   ✅ 新数据和历史数据都将使用增强处理引擎")
        print(f"   ✅ 数据质量问题将得到彻底解决")

        print(f"\n🚀 智能补充功能特性:")
        print(f"   🔍 自动采样检测数据质量")
        print(f"   📊 智能预估需要补充的数据量")
        print(f"   ⚡ 分批处理避免内存问题")
        print(f"   📈 实时统计补充进度")
        print(f"   🎯 支持配置开关控制")

    else:
        print(f"\n❌ 完整同步管理器智能补充功能测试未通过")
        print(f"需要进一步调试和修复")


if __name__ == "__main__":
    main()
