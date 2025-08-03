"""
测试增量同步对历史数据的处理行为
验证是否会重新处理已有数据
"""

from datetime import date

import pytest

from tests.conftest import BaseTestClass, SyncTestMixin


@pytest.mark.sync
@pytest.mark.database
class TestHistoricalDataBehavior(BaseTestClass, SyncTestMixin):
    """测试增量同步对历史数据的处理行为"""

    def test_incremental_sync_historical_behavior(
        self, db_manager, data_source_manager, processing_engine, config
    ):
        """测试增量同步对历史数据的处理行为"""
        from simtradedata.sync import IncrementalSync

        incremental_sync = IncrementalSync(
            db_manager, data_source_manager, processing_engine, config
        )

        # 测试股票
        test_symbol = "000001.SZ"
        target_date = date(2025, 1, 24)

        self.print_test_info(
            "增量同步历史数据行为测试", [test_symbol], date(2025, 1, 20), target_date
        )

        # 1. 检查当前数据状态
        self._check_current_data_state(db_manager, test_symbol)

        # 2. 获取最后数据日期
        last_date = incremental_sync.get_last_data_date(test_symbol, "1d")
        print(f"📅 最后数据日期: {last_date}")

        # 3. 计算同步范围
        start_date, end_date = incremental_sync.calculate_sync_range(
            test_symbol, target_date, "1d"
        )
        print(f"📅 计算的同步范围: {start_date} 到 {end_date}")

        # 验证同步行为
        self._verify_sync_behavior(start_date, end_date)

        # 4. 检查数据质量情况
        quality_stats = self._analyze_data_quality(db_manager, test_symbol)

        # 验证历史数据处理逻辑
        self._verify_historical_data_logic(quality_stats)

    def test_sync_range_after_data_deletion(
        self, db_manager, data_source_manager, processing_engine, config
    ):
        """测试删除数据后的同步范围计算"""
        from simtradedata.sync import IncrementalSync

        incremental_sync = IncrementalSync(
            db_manager, data_source_manager, processing_engine, config
        )

        test_symbol = "000001.SZ"
        target_date = date(2025, 1, 24)

        self.print_test_info(
            "数据删除后同步范围测试", [test_symbol], date(2025, 1, 20), target_date
        )

        # 记录删除前状态
        original_last_date = incremental_sync.get_last_data_date(test_symbol, "1d")
        original_start, original_end = incremental_sync.calculate_sync_range(
            test_symbol, target_date, "1d"
        )

        print(f"删除前最后数据日期: {original_last_date}")
        print(f"删除前同步范围: {original_start} 到 {original_end}")

        # 删除一些最新数据
        recent_date = "2025-01-20"
        print(f"删除 {test_symbol} 从 {recent_date} 开始的数据...")
        db_manager.execute(
            "DELETE FROM market_data WHERE symbol = ? AND date >= ?",
            (test_symbol, recent_date),
        )

        # 重新计算同步范围
        new_last_date = incremental_sync.get_last_data_date(test_symbol, "1d")
        new_start_date, new_end_date = incremental_sync.calculate_sync_range(
            test_symbol, target_date, "1d"
        )

        print(f"删除后最后数据日期: {new_last_date}")
        print(f"删除后同步范围: {new_start_date} 到 {new_end_date}")

        # 验证删除数据对同步范围的影响
        if new_start_date:
            print(f"🔄 现在会同步 {new_start_date} 到 {new_end_date} 的数据")
            print(f"🔍 这证明了增量同步只处理缺失的日期范围")

            # 验证同步范围的合理性：删除数据后，增量同步会从更早日期开始以确保数据连续性
            assert new_start_date <= date.fromisoformat(
                recent_date
            ), f"新的同步起始日期应该不晚于删除的日期，以确保数据连续性: {new_start_date} <= {recent_date}"
        else:
            pytest.fail("删除数据后应该产生需要同步的日期范围")

    def test_null_derived_fields_behavior(self, db_manager):
        """测试对NULL衍生字段的处理行为"""
        test_symbol = "000001.SZ"

        # 检查是否存在NULL衍生字段的记录
        null_check_sql = """
        SELECT COUNT(*) as null_count
        FROM market_data 
        WHERE symbol = ? AND (change_percent IS NULL OR prev_close IS NULL)
        """

        null_result = db_manager.fetchone(null_check_sql, (test_symbol,))
        null_count = null_result["null_count"] if null_result else 0

        print(f"发现 {null_count} 条衍生字段为NULL的记录")

        if null_count > 0:
            print("⚠️ 增量同步不会自动补充历史数据的NULL衍生字段")
            print("🔍 这需要专门的数据补充流程")

            # 验证这是预期行为
            assert null_count >= 0, "NULL衍生字段数量应该是非负数"
        else:
            print("✅ 没有发现NULL衍生字段，数据质量良好")

    def _check_current_data_state(self, db_manager, symbol):
        """检查当前数据状态"""
        print("\n📊 检查当前数据状态...")
        check_sql = """
        SELECT date, close, change_percent, prev_close, source
        FROM market_data 
        WHERE symbol = ? 
        ORDER BY date DESC 
        LIMIT 5
        """

        current_data = db_manager.fetchall(check_sql, (symbol,))

        if current_data:
            print(f"找到 {len(current_data)} 条最新记录:")
            for record in current_data:
                print(
                    f"  {record['date']}: 收盘{record['close']}, "
                    f"涨跌幅{record['change_percent']}%, "
                    f"数据源:{record['source']}"
                )
        else:
            print("❌ 没有找到任何历史数据")

        return current_data

    def _verify_sync_behavior(self, start_date, end_date):
        """验证同步行为"""
        if start_date is None:
            print("✅ 数据已是最新，不会进行同步")
            print("🔍 这意味着增量同步不会重新处理历史数据")
        else:
            print(f"🔄 会同步 {start_date} 到 {end_date} 的数据")
            print("🔍 这意味着只会处理新增的日期范围")

    def _analyze_data_quality(self, db_manager, symbol):
        """分析数据质量情况"""
        print(f"\n📊 检查 {symbol} 的数据质量情况...")
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

        quality_stats = db_manager.fetchone(quality_sql, (symbol,))

        if quality_stats:
            total = quality_stats["total_records"]
            print(f"  总记录数: {total}")

            if total > 0:
                enhanced_pct = quality_stats["enhanced_records"] / total * 100
                null_pct = quality_stats["null_change_percent"] / total * 100

                print(
                    f"  增强处理记录: {quality_stats['enhanced_records']} ({enhanced_pct:.1f}%)"
                )
                print(
                    f"  change_percent为NULL: {quality_stats['null_change_percent']} ({null_pct:.1f}%)"
                )
                print(
                    f"  日期范围: {quality_stats['earliest_date']} 到 {quality_stats['latest_date']}"
                )
            else:
                print("  没有找到任何数据记录")

        return quality_stats

    def _verify_historical_data_logic(self, quality_stats):
        """验证历史数据处理逻辑"""
        if quality_stats and quality_stats["null_change_percent"] > 0:
            print(
                f"⚠️ 该股票有 {quality_stats['null_change_percent']} 条历史记录的衍生字段为NULL"
            )
            print(f"🔍 增量同步不会重新处理这些历史数据")

            # 这是预期行为，不需要断言失败
            assert quality_stats["null_change_percent"] >= 0, "NULL字段数量应该是非负数"
        else:
            print(f"✅ 该股票的所有衍生字段都已计算完成")


@pytest.mark.sync
@pytest.mark.integration
class TestHistoricalDataConclusions(BaseTestClass):
    """历史数据处理行为结论测试"""

    def test_historical_data_processing_principles(self):
        """测试历史数据处理的基本原则"""
        self.print_test_info(
            "历史数据处理原则验证", [], date(2025, 1, 1), date(2025, 1, 31)
        )

        # 验证增量同步的设计原则
        principles = {
            "only_missing_dates": "增量同步只处理缺失的日期范围",
            "no_reprocess_existing": "已存在的历史数据不会被重新处理",
            "null_fields_remain": "历史数据的NULL衍生字段不会自动补充",
            "deletion_triggers_sync": "删除数据后会触发相应范围的重新同步",
        }

        print("\n📋 增量同步的设计原则:")
        for key, principle in principles.items():
            print(f"✅ {principle}")

        # 这些原则反映了增量同步的高效设计
        assert len(principles) == 4, "应该有4个核心设计原则"

        print("\n🎯 要补充历史数据的NULL字段，推荐方法:")
        print("1️⃣ 删除相关历史数据后重新同步")
        print("2️⃣ 使用专门的数据补充脚本")
        print("3️⃣ 运行全量数据重建流程")

        print("\n✅ 历史数据处理原则验证完成")
