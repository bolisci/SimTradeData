"""
测试交易日历增量更新功能
验证交易日历只在需要时更新，而不是每次都重新下载
"""

import time
from datetime import date

import pytest

from tests.conftest import BaseTestClass


@pytest.mark.sync
@pytest.mark.database
class TestIncrementalCalendarUpdate(BaseTestClass):
    """测试交易日历增量更新功能"""

    def test_calendar_update_within_existing_range(
        self, db_manager, data_source_manager, processing_engine, config
    ):
        """测试目标日期在现有范围内应该跳过更新"""
        from simtradedata.sync import SyncManager

        sync_manager = SyncManager(
            db_manager, data_source_manager, processing_engine, config
        )

        # 先创建一些测试数据，确保数据库有现有的交易日历
        test_dates = [
            ("2024-01-01", 1),
            ("2024-01-02", 1),
            ("2024-01-03", 1),
            ("2025-01-01", 1),
            ("2025-01-02", 1),
            ("2025-01-03", 1),
            ("2025-12-30", 1),
            ("2025-12-31", 1),
            ("2026-01-01", 1),
        ]
        for date_str, is_trading in test_dates:
            db_manager.execute(
                "INSERT OR REPLACE INTO trading_calendar (date, market, is_trading_day) VALUES (?, ?, ?)",
                (date_str, "CN", is_trading),
            )

        # 检查当前交易日历状态
        current_range = self._get_current_calendar_range(db_manager)
        self.print_test_info(
            "交易日历增量更新测试（范围内日期）",
            [],
            date(2025, 1, 20),
            date(2025, 1, 24),
        )

        if current_range and current_range["count"] > 0:
            print(
                f"现有数据范围: {current_range['min_date']} 到 {current_range['max_date']}"
            )
            print(f"总记录数: {current_range['count']}")
        else:
            print("❌ 没有现有交易日历数据")

        # 测试目标日期在现有范围内 - 应该跳过更新
        target_date_within = date(2025, 1, 24)
        start_time = time.time()

        result = sync_manager._update_trading_calendar(target_date_within)
        elapsed_time = time.time() - start_time

        print(f"更新结果: {result}")
        print(f"耗时: {elapsed_time:.2f}秒")

        # 验证跳过了不必要的更新
        assert (
            result.get("status") == "skipped" or result.get("updated_records") == 0
        ), "应该跳过不必要的更新"

        print("✅ 成功跳过不必要的更新！")

    def test_calendar_update_future_date(
        self, db_manager, data_source_manager, processing_engine, config
    ):
        """测试目标日期需要未来年份应该增量更新"""
        from simtradedata.sync import SyncManager

        sync_manager = SyncManager(
            db_manager, data_source_manager, processing_engine, config
        )

        self.print_test_info(
            "交易日历增量更新测试（未来日期）", [], date(2026, 1, 1), date(2026, 1, 24)
        )

        # 目标日期需要未来年份 - 应该增量更新
        target_date_future = date(2026, 1, 24)  # 需要2025-2027年数据

        # 先删除2026年以后的数据（如果有的话）
        db_manager.execute("DELETE FROM trading_calendar WHERE date >= '2026-01-01'")

        start_time = time.time()
        result = sync_manager._update_trading_calendar(target_date_future)
        elapsed_time = time.time() - start_time

        print(f"更新结果: {result}")
        print(f"耗时: {elapsed_time:.2f}秒")

        # 验证进行了增量更新
        updated_records = result.get("updated_records", 0)
        assert (
            updated_records > 0
        ), f"应该进行增量更新，但更新记录数为: {updated_records}"

        print(f"✅ 成功增量更新了 {updated_records} 条记录！")

        # 验证添加了2025年数据（系统会更新target_date所在年份的前后1年）
        count_2025 = db_manager.fetchone(
            "SELECT COUNT(*) as count FROM trading_calendar WHERE date >= '2025-01-01' AND date < '2026-01-01'"
        )

        assert count_2025 and count_2025["count"] > 0, "应该添加2025年数据"
        print(f"✅ 成功添加了2025年数据: {count_2025['count']}条记录")

    def test_calendar_update_duplicate_call(
        self, db_manager, data_source_manager, processing_engine, config
    ):
        """测试重复调用相同目标日期应该跳过"""
        from simtradedata.sync import SyncManager

        sync_manager = SyncManager(
            db_manager, data_source_manager, processing_engine, config
        )

        target_date_future = date(2027, 1, 24)

        # 确保数据已存在（从前一个测试）
        count_before = db_manager.fetchone(
            "SELECT COUNT(*) as count FROM trading_calendar WHERE date >= '2027-01-01'"
        )

        if not count_before or count_before["count"] == 0:
            # 如果没有数据，先运行一次
            sync_manager._update_trading_calendar(target_date_future)

        # 再次调用相同目标日期 - 应该跳过
        start_time = time.time()
        result = sync_manager._update_trading_calendar(target_date_future)
        elapsed_time = time.time() - start_time

        print(f"重复调用结果: {result}")
        print(f"耗时: {elapsed_time:.2f}秒")

        # 验证跳过了重复更新
        assert result.get("updated_records", 0) == 0, "应该跳过重复更新"

        print("✅ 成功跳过重复更新！")
        print(f"⚡ 重复调用只用了 {elapsed_time:.2f}秒，避免了不必要的网络IO")

    def test_calendar_cleanup(self, db_manager):
        """清理测试数据"""
        # 恢复原始状态（删除测试添加的未来数据）
        print("🧹 清理测试数据...")
        db_manager.execute("DELETE FROM trading_calendar WHERE date >= '2026-01-01'")
        print("✅ 测试数据清理完成")

    def _get_current_calendar_range(self, db_manager):
        """获取当前交易日历范围"""
        result = db_manager.fetchone(
            "SELECT MIN(date) as min_date, MAX(date) as max_date, COUNT(*) as count FROM trading_calendar"
        )
        # 处理空结果的情况
        if result and result["count"] > 0:
            return result
        else:
            return {"min_date": None, "max_date": None, "count": 0}


@pytest.mark.sync
@pytest.mark.integration
class TestCalendarIntegration(BaseTestClass):
    """交易日历集成测试"""

    def test_full_calendar_workflow(
        self, db_manager, data_source_manager, processing_engine, config
    ):
        """测试完整的交易日历工作流程"""
        from simtradedata.sync import SyncManager

        sync_manager = SyncManager(
            db_manager, data_source_manager, processing_engine, config
        )

        self.print_test_info(
            "完整交易日历工作流程测试", [], date(2025, 1, 1), date(2025, 12, 31)
        )

        # 1. 检查初始状态
        initial_count = db_manager.fetchone(
            "SELECT COUNT(*) as count FROM trading_calendar WHERE date >= '2025-01-01'"
        )
        print(f"初始2025年数据: {initial_count['count'] if initial_count else 0}条")

        # 2. 执行更新
        sync_manager._update_trading_calendar(date(2025, 12, 31))

        # 3. 验证结果
        final_count = db_manager.fetchone(
            "SELECT COUNT(*) as count FROM trading_calendar WHERE date >= '2025-01-01' AND date <= '2025-12-31'"
        )

        assert final_count and final_count["count"] > 0, "应该有2025年的交易日历数据"
        print(f"最终2025年数据: {final_count['count']}条")
        print("✅ 完整工作流程测试通过")
