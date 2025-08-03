"""
独立测试交易日历增量更新逻辑
直接检查具体的执行路径
"""

from datetime import date, datetime

import pytest

from tests.conftest import BaseTestClass


@pytest.mark.sync
@pytest.mark.database
@pytest.mark.slow
class TestCalendarUpdateLogic(BaseTestClass):
    """独立测试交易日历增量更新逻辑"""

    def test_calendar_update_logic_detailed(
        self, db_manager, data_source_manager, processing_engine, config
    ):
        """直接测试交易日历更新逻辑的详细过程"""
        from simtradedata.sync import SyncManager

        self.print_test_info(
            "交易日历增量更新逻辑详细测试", [], date(2025, 1, 1), date(2025, 6, 24)
        )

        # 清理2025年数据，但保留之前的数据
        db_manager.execute('DELETE FROM trading_calendar WHERE date >= "2025-01-01"')
        print("✅ 已清理2025年以后的数据")

        # 验证现有数据
        existing_range = self._get_existing_calendar_range(db_manager)
        print(
            f"现有数据: {existing_range['min_date']} 到 {existing_range['max_date']}, "
            f"共{existing_range['count']}条"
        )

        # 创建同步管理器
        sync_manager = SyncManager(
            db_manager, data_source_manager, processing_engine, config
        )

        # 目标日期：2025年
        target_date = date(2025, 6, 24)
        print(f"目标日期: {target_date}")

        # 分析更新需求
        years_to_update = self._analyze_update_requirements(existing_range, target_date)
        print(f"最终需要更新的年份: {years_to_update}")

        assert len(years_to_update) > 0, "应该检测到需要更新的年份"

        # 实际调用方法
        print(f"\n🚀 调用 _update_trading_calendar({target_date})")
        result = sync_manager._update_trading_calendar(target_date)

        print(f"方法返回结果: {result}")

        # 验证更新结果
        self._verify_update_results(db_manager, existing_range, result)

    def test_calendar_year_range_logic(self, db_manager):
        """测试年份范围计算逻辑"""
        # 模拟不同的现有数据范围
        test_cases = [
            {
                "existing_min": date(2020, 1, 1),
                "existing_max": date(2025, 12, 31),
                "target_date": date(2027, 1, 24),
                "expected_years": [2026, 2027, 2028],
            },
            {
                "existing_min": date(2024, 1, 1),
                "existing_max": date(2028, 12, 31),
                "target_date": date(2027, 1, 24),
                "expected_years": [],  # 数据已足够
            },
        ]

        for i, case in enumerate(test_cases, 1):
            print(f"\n测试用例 {i}:")
            years_needed = self._calculate_years_needed(
                case["existing_min"], case["existing_max"], case["target_date"]
            )

            print(
                f"  现有范围: {case['existing_min'].year}-{case['existing_max'].year}"
            )
            print(f"  目标日期: {case['target_date']}")
            print(f"  计算结果: {years_needed}")
            print(f"  预期结果: {case['expected_years']}")

            assert (
                years_needed == case["expected_years"]
            ), f"用例{i}失败: 期望{case['expected_years']}, 实际{years_needed}"

        print("✅ 年份范围计算逻辑测试通过")

    def _get_existing_calendar_range(self, db_manager):
        """获取现有交易日历范围"""
        result = db_manager.fetchone(
            "SELECT MIN(date) as min_date, MAX(date) as max_date, COUNT(*) as count FROM trading_calendar"
        )
        # 处理空结果的情况
        if result and result["count"] > 0:
            return result
        else:
            return {"min_date": None, "max_date": None, "count": 0}

    def _analyze_update_requirements(self, existing_range, target_date):
        """分析更新需求"""
        print("\n🧪 分析增量更新需求...")

        if existing_range["count"] == 0 or not existing_range["min_date"]:
            print("没有现有数据，需要获取所有年份")
            needed_start_year = target_date.year - 1
            needed_end_year = target_date.year + 1
            return list(range(needed_start_year, needed_end_year + 1))

        existing_min = datetime.strptime(existing_range["min_date"], "%Y-%m-%d").date()
        existing_max = datetime.strptime(existing_range["max_date"], "%Y-%m-%d").date()

        needed_start_year = target_date.year - 1  # 2026
        needed_end_year = target_date.year + 1  # 2028

        print(f"现有数据年份范围: {existing_min.year}-{existing_max.year}")
        print(f"需要的年份范围: {needed_start_year}-{needed_end_year}")

        years_to_update = []

        if existing_min.year > needed_start_year:
            early_years = list(range(needed_start_year, existing_min.year))
            years_to_update.extend(early_years)
            print(f"需要添加更早年份: {early_years}")

        if existing_max.year < needed_end_year:
            later_years = list(range(existing_max.year + 1, needed_end_year + 1))
            years_to_update.extend(later_years)
            print(f"需要添加更晚年份: {later_years}")

        return years_to_update

    def _calculate_years_needed(self, existing_min, existing_max, target_date):
        """计算需要的年份（用于单元测试）"""
        needed_start_year = target_date.year - 1
        needed_end_year = target_date.year + 1

        years_to_update = []

        if existing_min.year > needed_start_year:
            early_years = list(range(needed_start_year, existing_min.year))
            years_to_update.extend(early_years)

        if existing_max.year < needed_end_year:
            later_years = list(range(existing_max.year + 1, needed_end_year + 1))
            years_to_update.extend(later_years)

        return years_to_update

    def _verify_update_results(self, db_manager, existing_range, result):
        """验证更新结果"""
        # 验证数据库变化
        final_range = db_manager.fetchone(
            "SELECT MIN(date) as min_date, MAX(date) as max_date, COUNT(*) as count FROM trading_calendar"
        )
        print(
            f"更新后数据: {final_range['min_date']} 到 {final_range['max_date']}, "
            f"共{final_range['count']}条"
        )

        # 检查是否真的添加了新数据
        new_records = final_range["count"] - existing_range["count"]
        print(f"新增记录数: {new_records}")

        assert new_records > 0, "应该有新增记录"
        assert result.get("updated_records", 0) > 0, "返回结果应该显示有更新"

        print("✅ 增量更新成功！")

    def test_cleanup_test_data(self, db_manager):
        """清理测试数据"""
        # 恢复测试环境
        db_manager.execute('DELETE FROM trading_calendar WHERE date >= "2026-01-01"')
        print("🧹 测试数据已清理")


@pytest.mark.sync
@pytest.mark.unit
class TestCalendarUpdateUnit(BaseTestClass):
    """交易日历更新单元测试"""

    def test_year_calculation_edge_cases(self):
        """测试年份计算的边界情况"""
        # 测试各种边界情况
        edge_cases = [
            # 目标日期正好是年份边界
            {"target": date(2027, 1, 1), "expected_buffer": (2026, 2028)},
            {"target": date(2027, 12, 31), "expected_buffer": (2026, 2028)},
            # 目标日期在年份中间
            {"target": date(2027, 6, 15), "expected_buffer": (2026, 2028)},
        ]

        for case in edge_cases:
            target = case["target"]
            expected = case["expected_buffer"]

            # 模拟计算逻辑
            needed_start = target.year - 1
            needed_end = target.year + 1

            assert (
                needed_start,
                needed_end,
            ) == expected, f"目标日期{target}的缓冲年份计算错误"

        print("✅ 年份计算边界情况测试通过")
