#!/usr/bin/env python3
"""
测试智能补充功能
验证增量同步器的智能补充是否能正确工作
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


def test_smart_backfill():
    """测试智能补充功能"""
    print("🚀 测试智能补充功能...")

    # 初始化组件
    config = Config()
    db_manager = DatabaseManager()
    data_source_manager = DataSourceManager(config)
    processing_engine = DataProcessingEngine(db_manager, data_source_manager, config)
    incremental_sync = IncrementalSync(
        db_manager, data_source_manager, processing_engine, config
    )

    # 测试参数 - 使用几只有问题的股票
    test_symbols = ["600519.SS", "000858.SZ"]  # 使用还没有补充过的股票
    target_date = date(2025, 1, 24)

    print(f"测试股票: {test_symbols}")
    print(f"目标日期: {target_date}")
    print(
        f"智能补充功能: {'启用' if incremental_sync.enable_smart_backfill else '禁用'}"
    )

    # 1. 检查测试股票的数据质量
    print("\n📊 检查测试股票的数据质量...")
    for symbol in test_symbols:
        quality_check = incremental_sync.check_data_quality(symbol, "1d")
        print(f"{symbol}:")
        print(f"  总记录数: {quality_check.get('total_records', 0)}")
        print(f"  NULL字段数: {quality_check.get('null_change_percent', 0)}")
        print(
            f"  需要补充: {'是' if quality_check.get('needs_backfill', False) else '否'}"
        )
        print(f"  补充比例: {quality_check.get('backfill_ratio', 0)*100:.1f}%")

    # 2. 运行带智能补充的增量同步
    print(f"\n🔄 运行带智能补充的增量同步...")
    try:
        sync_result = incremental_sync.sync_all_symbols(
            target_date=target_date, symbols=test_symbols, frequencies=["1d"]
        )

        print("✅ 同步完成!")

        # 解析结果
        if isinstance(sync_result, dict):
            print(f"总股票数: {sync_result.get('total_symbols', 0)}")
            print(f"成功同步: {sync_result.get('success_count', 0)}")
            print(f"同步错误: {sync_result.get('error_count', 0)}")

            # 智能补充统计
            backfill_stats = sync_result.get("smart_backfill", {})
            if backfill_stats:
                print(f"\n📈 智能补充统计:")
                print(
                    f"  功能启用: {'是' if backfill_stats.get('enabled', False) else '否'}"
                )
                print(f"  检查股票数: {backfill_stats.get('checked_symbols', 0)}")
                print(
                    f"  需要补充股票数: {backfill_stats.get('needs_backfill_symbols', 0)}"
                )
                print(
                    f"  实际补充股票数: {backfill_stats.get('backfilled_symbols', 0)}"
                )
                print(f"  补充记录数: {backfill_stats.get('backfilled_records', 0)}")
                print(f"  补充错误数: {backfill_stats.get('backfill_errors', 0)}")

    except Exception as e:
        print(f"❌ 同步失败: {e}")
        return False

    # 3. 验证补充结果
    print(f"\n✅ 验证补充结果...")

    total_before_null = 0
    total_after_null = 0
    total_enhanced = 0

    for symbol in test_symbols:
        print(f"\n--- 验证股票 {symbol} ---")

        # 检查补充后的数据质量
        after_quality = incremental_sync.check_data_quality(symbol, "1d")
        total_records = after_quality.get("total_records", 0)
        null_fields = after_quality.get("null_change_percent", 0)
        enhanced_records = after_quality.get("enhanced_records", 0)

        total_before_null += null_fields  # 这里应该是0了
        total_after_null += null_fields
        total_enhanced += enhanced_records

        print(f"  总记录数: {total_records}")
        print(
            f"  NULL字段数: {null_fields} ({null_fields/total_records*100:.1f}%)"
            if total_records > 0
            else ""
        )
        print(
            f"  增强记录数: {enhanced_records} ({enhanced_records/total_records*100:.1f}%)"
            if total_records > 0
            else ""
        )

        # 显示几个示例记录
        sample_sql = """
        SELECT date, close, change_percent, prev_close, amplitude, source
        FROM market_data 
        WHERE symbol = ? AND change_percent IS NOT NULL AND change_percent != 0
        ORDER BY date DESC 
        LIMIT 3
        """

        samples = db_manager.fetchall(sample_sql, (symbol,))

        if samples:
            print(f"  最新数据示例:")
            for sample in samples:
                print(
                    f"    {sample['date']}: 收盘{sample['close']}, 涨跌幅{sample['change_percent']}%, 振幅{sample['amplitude']}%, 数据源:{sample['source']}"
                )
        else:
            print(f"  ⚠️  没有找到有效的衍生字段数据")

    # 4. 总结
    print(f"\n🎯 测试总结:")
    print(f"  测试股票数: {len(test_symbols)}")
    print(f"  补充后NULL字段总数: {total_after_null}")
    print(f"  增强记录总数: {total_enhanced}")

    success = total_after_null == 0 and total_enhanced > 0

    if success:
        print(f"🎉 智能补充功能测试成功!")
        print(f"✅ 所有历史数据的衍生字段都已补充完成")
        print(f"✅ 数据源已标记为增强处理")
    else:
        print(f"❌ 智能补充功能测试失败")
        print(f"⚠️  仍有部分数据未正确补充")

    db_manager.close()
    return success


def main():
    """主函数"""
    print("🧪 开始智能补充功能测试...")

    success = test_smart_backfill()

    if success:
        print(f"\n✅ 智能补充功能已验证可用!")
        print(f"📋 下次运行全量同步时，系统将自动:")
        print(f"   1. 检测历史数据的衍生字段质量")
        print(f"   2. 自动补充缺失的change_percent、amplitude等字段")
        print(f"   3. 将数据源标记为增强处理")
        print(f"   4. 无需手动干预即可解决历史数据质量问题")
    else:
        print(f"\n❌ 智能补充功能测试未通过")
        print(f"需要进一步调试和修复")


if __name__ == "__main__":
    main()
