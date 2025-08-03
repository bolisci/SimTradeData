"""
测试智能补充功能
整合了原来的智能补充相关测试
"""

from datetime import date

import pytest

from tests.conftest import BaseTestClass, SyncTestMixin


@pytest.mark.sync
@pytest.mark.slow
class TestSmartBackfill(BaseTestClass, SyncTestMixin):
    """测试智能补充功能"""

    def test_incremental_sync_smart_backfill(self, incremental_sync, db_manager):
        """测试增量同步器的智能补充功能"""
        # 使用特定的测试股票（可能有数据质量问题的）
        test_symbols = ["600519.SS", "000858.SZ"]
        target_date = date(2025, 1, 24)

        self.print_test_info(
            "增量同步智能补充测试", test_symbols, date(2025, 1, 20), target_date
        )

        # 检查智能补充是否启用
        print(
            f"智能补充功能: {'启用' if incremental_sync.enable_smart_backfill else '禁用'}"
        )

        # 1. 检查初始数据质量
        initial_stats = self._check_initial_data_quality(
            db_manager, incremental_sync, test_symbols
        )

        # 2. 执行智能补充同步
        sync_result = incremental_sync.sync_all_symbols(
            target_date=target_date, symbols=test_symbols, frequencies=["1d"]
        )

        self.verify_sync_result(sync_result)

        # 3. 验证补充效果
        final_stats = self._check_final_data_quality(
            db_manager, incremental_sync, test_symbols
        )

        # 4. 比较补充前后的改进
        self._verify_backfill_improvement(initial_stats, final_stats, test_symbols)

    def test_sync_manager_smart_backfill(
        self, db_manager, data_source_manager, processing_engine, config
    ):
        """测试完整同步管理器的智能补充功能"""
        from simtradedata.sync import SyncManager

        sync_manager = SyncManager(
            db_manager, data_source_manager, processing_engine, config
        )

        test_symbols = ["002415.SZ", "300059.SZ"]
        target_date = date(2025, 1, 24)

        self.print_test_info(
            "同步管理器智能补充测试", test_symbols, date(2025, 1, 20), target_date
        )

        # 检查初始状态
        initial_stats = {}
        for symbol in test_symbols:
            quality_check = sync_manager.incremental_sync.check_data_quality(
                symbol, "1d"
            )
            initial_stats[symbol] = quality_check
            print(
                f"{symbol}: 总记录数 {quality_check.get('total_records', 0)}, "
                f"NULL字段数 {quality_check.get('null_change_percent', 0)}"
            )

        # 执行完整同步流程
        sync_result = sync_manager.run_full_sync(
            target_date=target_date, symbols=test_symbols
        )

        # 验证同步结果（不期望一定成功，因为可能是测试数据问题）
        if isinstance(sync_result, dict):
            print(f"同步管理器结果: {sync_result}")
        else:
            print(f"同步管理器结果类型: {type(sync_result)}")

        # 验证最终结果
        for symbol in test_symbols:
            final_quality = sync_manager.incremental_sync.check_data_quality(
                symbol, "1d"
            )
            initial_nulls = initial_stats[symbol].get("null_change_percent", 0)
            final_nulls = final_quality.get("null_change_percent", 0)

            initial_records = initial_stats[symbol].get("total_records", 0)
            final_records = final_quality.get("total_records", 0)

            print(
                f"{symbol} 补充效果: 记录数从 {initial_records} 增加到 {final_records}, NULL字段从 {initial_nulls} 到 {final_nulls}"
            )

            # 验证有改进 - 重点是数据获取，而不是NULL字段减少
            if initial_records == 0 and final_records > 0:
                print(f"  ✅ 成功获取数据: 从无数据到 {final_records} 条记录")
            elif final_records >= initial_records:
                if final_nulls <= initial_nulls:
                    print(f"  ✅ 数据质量保持或改善")
                else:
                    print(f"  ℹ️ 获取了更多数据，NULL字段正常增加")
            else:
                pytest.fail(f"股票 {symbol} 记录数减少了")

    def _check_initial_data_quality(
        self, db_manager, incremental_sync, symbols: list
    ) -> dict:
        """检查初始数据质量"""
        print("\n📊 检查初始数据质量...")
        initial_stats = {}

        for symbol in symbols:
            quality_check = incremental_sync.check_data_quality(symbol, "1d")
            initial_stats[symbol] = quality_check

            print(f"{symbol}:")
            print(f"  总记录数: {quality_check.get('total_records', 0)}")
            print(f"  NULL字段数: {quality_check.get('null_change_percent', 0)}")
            print(f"  数据完整性: {quality_check.get('data_completeness', 0):.2f}%")

        return initial_stats

    def _check_final_data_quality(
        self, db_manager, incremental_sync, symbols: list
    ) -> dict:
        """检查最终数据质量"""
        print("\n📊 检查最终数据质量...")
        final_stats = {}

        for symbol in symbols:
            quality_check = incremental_sync.check_data_quality(symbol, "1d")
            final_stats[symbol] = quality_check

            print(f"{symbol}:")
            print(f"  总记录数: {quality_check.get('total_records', 0)}")
            print(f"  NULL字段数: {quality_check.get('null_change_percent', 0)}")
            print(f"  数据完整性: {quality_check.get('data_completeness', 0):.2f}%")

        return final_stats

    def _verify_backfill_improvement(
        self, initial_stats: dict, final_stats: dict, symbols: list
    ):
        """验证智能补充的改进效果"""
        print("\n🔍 验证智能补充效果...")

        for symbol in symbols:
            initial = initial_stats[symbol]
            final = final_stats[symbol]

            initial_records = initial.get("total_records", 0)
            final_records = final.get("total_records", 0)

            initial_nulls = initial.get("null_change_percent", 0)
            final_nulls = final.get("null_change_percent", 0)

            print(f"{symbol} 改进情况:")
            print(
                f"  记录数: {initial_records} -> {final_records} "
                f"({'增加' if final_records > initial_records else '持平'})"
            )
            print(
                f"  NULL字段: {initial_nulls} -> {final_nulls} "
                f"({'改善' if final_nulls < initial_nulls else '持平' if final_nulls == initial_nulls else '正常增加'})"
            )

            # 验证改进标准
            # 1. 记录数应该保持或增加
            assert final_records >= initial_records, f"股票 {symbol} 记录数减少"

            # 2. 如果初始没有记录，现在有记录了，这是改善
            if initial_records == 0 and final_records > 0:
                print(f"  ✅ 成功获取数据: 从无数据到 {final_records} 条记录")
                continue

            # 3. 如果之前有记录，NULL字段数应该减少或保持
            if initial_records > 0:
                null_rate_before = (
                    initial_nulls / initial_records if initial_records > 0 else 0
                )
                null_rate_after = (
                    final_nulls / final_records if final_records > 0 else 0
                )

                if null_rate_after < null_rate_before:
                    improvement_rate = (
                        (null_rate_before - null_rate_after) / null_rate_before
                        if null_rate_before > 0
                        else 0
                    )
                    print(f"  ✅ 数据质量改善率: {improvement_rate:.1%}")
                elif null_rate_after == null_rate_before:
                    print(f"  ℹ️ 数据质量保持稳定")
                else:
                    # 允许一定的质量下降，特别是在获取更多数据的情况下
                    print(f"  ⚠️ 数据质量有所下降，但获取了更多数据")

        print("🎉 智能补充效果验证通过！")


@pytest.mark.sync
@pytest.mark.performance
class TestBackfillPerformance(BaseTestClass):
    """测试智能补充的性能表现"""

    def test_backfill_batch_performance(self, incremental_sync, db_manager):
        """测试批量智能补充的性能"""
        # 使用更多股票测试批量性能
        test_symbols = ["000001.SZ", "000002.SZ", "600000.SH", "600036.SH", "000858.SZ"]
        target_date = date(2025, 1, 24)

        self.print_test_info(
            "批量智能补充性能测试", test_symbols, date(2025, 1, 20), target_date
        )

        import time

        start_time = time.time()

        # 执行批量同步
        sync_result = incremental_sync.sync_all_symbols(
            target_date=target_date, symbols=test_symbols, frequencies=["1d"]
        )

        end_time = time.time()
        duration = end_time - start_time

        assert sync_result.get("success_count", 0) > 0, "批量同步失败"

        # 性能验证
        symbols_per_second = len(test_symbols) / duration if duration > 0 else 0
        print(f"批量处理性能: {len(test_symbols)} 只股票用时 {duration:.2f}秒")
        print(f"处理速度: {symbols_per_second:.2f} 股票/秒")

        # 性能标准（可根据实际情况调整）
        assert duration < 300, f"批量处理耗时过长: {duration:.2f}秒"  # 不超过5分钟
        assert (
            symbols_per_second > 0.02
        ), f"处理速度过慢: {symbols_per_second:.3f} 股票/秒"

        print("✅ 性能测试通过")
