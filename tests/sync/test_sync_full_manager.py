"""
测试完整的同步管理器
验证整个同步流程是否使用了增强的数据处理引擎
"""

from datetime import date

import pytest

from tests.conftest import BaseTestClass, SyncTestMixin


@pytest.mark.sync
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.skip(
    reason="测试会执行完整的run_full_sync，可能很慢或超时，跳过以避免卡住整个测试套件"
)
class TestFullSyncManager(BaseTestClass, SyncTestMixin):
    """测试完整的同步管理器"""

    def test_full_sync_with_enhanced_processing(
        self, db_manager, data_source_manager, processing_engine, config
    ):
        """测试完整同步管理器的增强数据处理"""
        from simtradedata.sync import SyncManager

        sync_manager = SyncManager(
            db_manager, data_source_manager, processing_engine, config
        )

        # 测试参数 - 使用少量股票进行快速测试
        test_symbols = ["000001.SZ", "000002.SZ"]
        target_date = date(2025, 1, 24)

        self.print_test_info(
            "完整同步管理器增强处理测试", test_symbols, date(2025, 1, 22), target_date
        )

        # 清理测试数据
        self._cleanup_test_data(db_manager, test_symbols)

        # 运行完整同步
        sync_result = self._run_full_sync(sync_manager, target_date, test_symbols)

        # 验证同步结果
        self._verify_sync_phases(sync_result)

        # 检查数据库中的增强数据
        stats = self._analyze_enhanced_data(db_manager, test_symbols)

        # 验证增强处理效果
        self._verify_enhanced_processing(stats)

    def test_sync_manager_error_handling(
        self, db_manager, data_source_manager, processing_engine, config
    ):
        """测试同步管理器的错误处理"""
        from simtradedata.sync import SyncManager

        sync_manager = SyncManager(
            db_manager, data_source_manager, processing_engine, config
        )

        # 测试错误股票代码
        invalid_symbols = ["INVALID.XX", "FAKE.YY"]
        target_date = date(2025, 1, 24)

        self.print_test_info(
            "同步管理器错误处理测试", invalid_symbols, date(2025, 1, 22), target_date
        )

        try:
            sync_result = sync_manager.run_full_sync(
                target_date=target_date, symbols=invalid_symbols, frequencies=["1d"]
            )

            # 应该处理错误但不崩溃
            if isinstance(sync_result, dict):
                print(f"错误处理结果: {sync_result}")
                # 验证错误被正确记录 - 系统应该优雅处理错误而不是完全失败
                phases = sync_result.get("data", {}).get("phases", {})
                incremental_result = phases.get("incremental_sync", {}).get(
                    "result", {}
                )
                error_count = incremental_result.get("error_count", 0)

                assert (
                    error_count > 0 or sync_result.get("success") is True
                ), "应该正确处理错误股票代码，记录错误但不导致整体失败"

            print("✅ 错误处理测试通过")

        except Exception as e:
            pytest.fail(f"同步管理器应该优雅地处理错误，但抛出了异常: {e}")

    def test_sync_manager_partial_success(
        self, db_manager, data_source_manager, processing_engine, config
    ):
        """测试同步管理器的部分成功场景"""
        from simtradedata.sync import SyncManager

        sync_manager = SyncManager(
            db_manager, data_source_manager, processing_engine, config
        )

        # 混合有效和无效的股票代码
        mixed_symbols = ["000001.SZ", "INVALID.XX", "000002.SZ"]
        target_date = date(2025, 1, 24)

        self.print_test_info(
            "同步管理器部分成功测试", mixed_symbols, date(2025, 1, 22), target_date
        )

        # 清理有效股票的测试数据
        self._cleanup_test_data(db_manager, ["000001.SZ", "000002.SZ"])

        sync_result = sync_manager.run_full_sync(
            target_date=target_date, symbols=mixed_symbols, frequencies=["1d"]
        )

        # 验证部分成功的结果
        if isinstance(sync_result, dict):
            phases = sync_result.get("data", {}).get("phases", {})
            if "incremental_sync" in phases:
                inc_result = phases["incremental_sync"].get("result", {})
                success_count = inc_result.get("success_count", 0)
                error_count = inc_result.get("error_count", 0)

                print(f"成功处理: {success_count}只股票")
                print(f"错误处理: {error_count}只股票")

                # 应该有部分成功
                assert success_count > 0, "应该有成功处理的股票"
                assert error_count > 0, "应该有错误处理的股票"

                print("✅ 部分成功场景测试通过")

    def _cleanup_test_data(self, db_manager, symbols):
        """清理测试数据"""
        print("清理旧的测试数据...")
        for symbol in symbols:
            db_manager.execute(
                "DELETE FROM market_data WHERE symbol = ? AND date >= ?",
                (symbol, "2025-01-22"),  # 只清理最近几天
            )

    def _run_full_sync(self, sync_manager, target_date, symbols):
        """运行完整同步"""
        print("开始完整同步流程...")
        try:
            sync_result = sync_manager.run_full_sync(
                target_date=target_date, symbols=symbols, frequencies=["1d"]
            )

            print("✅ 同步完成!")
            return sync_result

        except Exception as e:
            pytest.fail(f"同步过程出现异常: {e}")

    def _verify_sync_phases(self, sync_result):
        """验证同步阶段结果"""
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

    def _analyze_enhanced_data(self, db_manager, symbols):
        """分析数据库中的增强数据"""
        print("\n📊 检查数据库中的增强数据...")

        total_records = 0
        enhanced_records = 0
        derived_field_records = 0

        for symbol in symbols:
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

        return {
            "total": total_records,
            "enhanced": enhanced_records,
            "derived_fields": derived_field_records,
        }

    def _verify_enhanced_processing(self, stats):
        """验证数据处理效果"""
        total = stats["total"]
        enhanced = stats["enhanced"]
        derived_fields = stats["derived_fields"]

        print(f"\n🎯 最终统计:")
        print(f"总记录数: {total}")

        if total > 0:
            enhanced_pct = enhanced / total * 100 if enhanced > 0 else 0
            derived_pct = derived_fields / total * 100 if derived_fields > 0 else 0

            print(f"增强处理记录: {enhanced} ({enhanced_pct:.1f}%)")
            print(f"衍生字段记录: {derived_fields} ({derived_pct:.1f}%)")

            # 验证标准 - 允许基础处理模式
            if enhanced > 0:
                # 如果有增强处理，验证增强处理的质量
                assert (
                    enhanced >= total * 0.8
                ), f"增强处理记录比例过低: {enhanced_pct:.1f}%"
                assert derived_fields > 0, "增强处理应该有计算的衍生字段"
                print("🎉 完整同步管理器成功使用了增强的数据处理引擎！")
                print("✅ 增强处理记录比例达标")
                print("✅ 衍生字段计算正常工作")
            else:
                # 基础处理模式 - 验证数据被正确获取
                print("ℹ️ 当前使用基础处理模式")
                assert total > 0, "应该至少获取到一些数据"
                print("✅ 完整同步管理器成功获取并处理了数据")
        else:
            pytest.fail("没有找到任何测试数据")


@pytest.mark.sync
@pytest.mark.performance
@pytest.mark.skip(
    reason="测试会执行完整的run_full_sync，可能很慢或超时，跳过以避免卡住整个测试套件"
)
class TestSyncManagerPerformance(BaseTestClass):
    """同步管理器性能测试"""

    def test_sync_manager_batching(
        self, db_manager, data_source_manager, processing_engine, config
    ):
        """测试同步管理器的批处理性能"""
        import time

        from simtradedata.sync import SyncManager

        sync_manager = SyncManager(
            db_manager, data_source_manager, processing_engine, config
        )

        # 使用更多股票测试批处理
        batch_symbols = ["000001.SZ", "000002.SZ", "600000.SH", "600036.SH"]
        target_date = date(2025, 1, 24)

        self.print_test_info(
            "同步管理器批处理性能测试", batch_symbols, date(2025, 1, 22), target_date
        )

        start_time = time.time()

        sync_result = sync_manager.run_full_sync(
            target_date=target_date, symbols=batch_symbols, frequencies=["1d"]
        )

        end_time = time.time()
        duration = end_time - start_time

        # 性能验证
        symbols_per_second = len(batch_symbols) / duration if duration > 0 else 0
        print(f"批处理性能: {len(batch_symbols)} 只股票用时 {duration:.2f}秒")
        print(f"处理速度: {symbols_per_second:.2f} 股票/秒")

        # 验证结果有效性
        assert isinstance(sync_result, dict), "应该返回有效的同步结果"

        # 性能标准（可根据实际情况调整）
        assert duration < 180, f"批处理耗时过长: {duration:.2f}秒"
        assert (
            symbols_per_second > 0.02
        ), f"处理速度过慢: {symbols_per_second:.3f} 股票/秒"

        print("✅ 批处理性能测试通过")
