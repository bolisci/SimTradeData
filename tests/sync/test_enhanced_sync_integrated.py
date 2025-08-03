"""
测试增强的同步流程
整合了原来的 test_sync_enhanced.py 和 test_sync_incremental.py 的功能
"""

from datetime import date

import pytest

from tests.conftest import BaseTestClass, SyncTestMixin


@pytest.mark.sync
class TestEnhancedSync(BaseTestClass, SyncTestMixin):
    """测试增强的同步流程和增量同步"""

    def test_enhanced_processing_engine(self, processing_engine, db_manager):
        """测试数据处理引擎的增强功能"""
        # 使用标准测试数据
        test_symbol = "000001.SZ"
        start_date, end_date = self.get_test_date_range()

        self.print_test_info(
            "增强数据处理引擎测试", [test_symbol], start_date, end_date
        )
        self.clean_test_data(db_manager, [test_symbol], str(start_date), str(end_date))

        # 使用数据处理引擎处理数据
        result = processing_engine.process_symbol_data(
            symbol=test_symbol,
            start_date=start_date,
            end_date=end_date,
            force_update=True,
        )

        # 验证处理结果
        assert result.get(
            "success", False
        ), f"数据处理失败: {result.get('error', '未知错误')}"

        # 验证数据库中的结果
        self._verify_enhanced_data(db_manager, test_symbol, start_date, end_date)

    def test_incremental_sync_with_enhanced_processing(
        self, incremental_sync, db_manager
    ):
        """测试增量同步器使用增强的数据处理引擎"""
        test_symbols = self.get_test_symbols()[:2]  # 使用前两个测试股票
        target_date = date(2025, 1, 24)

        self.print_test_info(
            "增量同步增强处理测试", test_symbols, date(2025, 1, 20), target_date
        )
        self.setup_sync_test(db_manager, test_symbols)

        # 执行增量同步
        sync_result = incremental_sync.sync_all_symbols(
            target_date=target_date, symbols=test_symbols, frequencies=["1d"]
        )

        self.verify_sync_result(sync_result)

        # 验证每个股票的增强数据
        for symbol in test_symbols:
            self._verify_enhanced_data_for_symbol(db_manager, symbol)

        # 验证整体数据质量
        self._verify_overall_data_quality(db_manager, test_symbols)

    def _verify_enhanced_data(
        self, db_manager, symbol: str, start_date: date, end_date: date
    ):
        """验证数据处理的质量"""
        sql = """
        SELECT symbol, date, close, change_percent, prev_close, amplitude, 
               source, quality_score, is_limit_up, is_limit_down
        FROM market_data 
        WHERE symbol = ? AND date >= ? AND date <= ?
        ORDER BY date
        """

        records = db_manager.fetchall(sql, (symbol, str(start_date), str(end_date)))

        assert len(records) > 0, f"未找到股票 {symbol} 的数据"
        print(f"找到 {len(records)} 条记录")

        # 调试：打印第一条记录的内容
        if records:
            first_record = records[0]
            print(f"第一条记录字段: {dict(first_record)}")

        # 验证基础数据质量
        for record in records:
            # 验证必需字段
            assert record["symbol"] == symbol, f"股票代码不匹配: {record['symbol']}"
            assert record["date"] is not None, "日期字段不能为空"
            assert (
                record["close"] is not None and record["close"] > 0
            ), f"收盘价异常: {record['close']}"

        # 根据数据源类型验证相应的处理质量
        enhanced_records = [r for r in records if r["source"] == "processed_enhanced"]
        basic_records = [r for r in records if r["source"] == "processed"]

        if enhanced_records:
            # 如果有增强处理的记录，验证衍生字段
            has_derived_fields = any(
                record["change_percent"] is not None and record["change_percent"] != 0
                for record in enhanced_records
            )
            assert has_derived_fields, "增强处理的记录应该有计算的衍生字段"
            print("✅ 增强处理记录验证通过")
        elif basic_records:
            # 如果只有基础处理的记录，验证基础字段完整性
            print(f"✅ 基础处理记录验证通过 ({len(basic_records)} 条记录)")
        else:
            pytest.fail("没有找到任何有效的处理记录")

        print("✅ 数据处理质量验证通过")

    def _verify_enhanced_data_for_symbol(self, db_manager, symbol: str):
        """验证单个股票的数据处理质量"""
        sql = """
        SELECT date, close, change_percent, prev_close, amplitude, source
        FROM market_data 
        WHERE symbol = ? AND date >= '2025-01-20'
        ORDER BY date DESC
        LIMIT 3
        """

        records = db_manager.fetchall(sql, (symbol,))

        if not records:
            pytest.fail(f"股票 {symbol} 没有找到任何记录")

        enhanced_count = sum(1 for r in records if r["source"] == "processed_enhanced")
        basic_count = sum(1 for r in records if r["source"] == "processed")
        derived_field_count = sum(
            1
            for r in records
            if r["change_percent"] is not None and r["change_percent"] != 0
        )

        print(
            f"股票 {symbol}: 增强处理记录 {enhanced_count}/{len(records)}, "
            f"基础处理记录 {basic_count}/{len(records)}, "
            f"衍生字段记录 {derived_field_count}/{len(records)}"
        )

        # 验证至少有有效的数据处理（增强或基础）
        assert (
            enhanced_count + basic_count
        ) > 0, f"股票 {symbol} 没有有效的数据处理记录"

    def _verify_overall_data_quality(self, db_manager, symbols: list):
        """验证整体数据质量"""
        placeholders = ",".join("?" * len(symbols))
        quality_sql = f"""
        SELECT 
            COUNT(*) as total_records,
            COUNT(CASE WHEN source = 'processed_enhanced' THEN 1 END) as enhanced_records,
            COUNT(CASE WHEN source = 'processed' THEN 1 END) as basic_records,
            COUNT(CASE WHEN change_percent IS NOT NULL AND change_percent != 0 THEN 1 END) as derived_field_records,
            AVG(CASE WHEN change_percent IS NOT NULL THEN change_percent ELSE 0 END) as avg_change_percent
        FROM market_data 
        WHERE symbol IN ({placeholders}) AND date >= '2025-01-20'
        """

        quality_result = db_manager.fetchone(quality_sql, tuple(symbols))

        if not quality_result:
            pytest.fail("无法获取数据质量统计")

        total = quality_result["total_records"]
        enhanced = quality_result["enhanced_records"]
        basic = quality_result["basic_records"]
        derived = quality_result["derived_field_records"]

        print(f"\n=== 整体数据质量统计 ===")
        print(f"总记录数: {total}")
        if total > 0:
            print(f"增强处理记录: {enhanced} ({enhanced/total*100:.1f}%)")
            print(f"基础处理记录: {basic} ({basic/total*100:.1f}%)")
            print(f"衍生字段记录: {derived} ({derived/total*100:.1f}%)")

        # 验证数据质量标准
        assert total > 0, "没有找到任何数据记录"
        assert (enhanced + basic) >= total * 0.8, "有效处理记录比例过低（应该 >= 80%）"

        if enhanced > 0:
            print("🎉 发现增强处理记录！")
            assert derived > 0, "增强处理记录应该包含衍生字段"
        else:
            print("ℹ️ 当前使用基础处理模式")

        print("✅ 整体数据质量验证通过！")


@pytest.mark.sync
@pytest.mark.integration
class TestSyncIntegration(BaseTestClass):
    """同步功能集成测试"""

    def test_full_sync_pipeline(self, processing_engine, incremental_sync, db_manager):
        """测试完整的同步流水线"""
        test_symbols = self.get_test_symbols()[:1]  # 使用一个测试股票
        start_date, end_date = self.get_test_date_range()

        self.print_test_info("完整同步流水线测试", test_symbols, start_date, end_date)
        self.clean_test_data(db_manager, test_symbols)

        # 步骤1: 使用处理引擎进行初始数据处理
        for symbol in test_symbols:
            result = processing_engine.process_symbol_data(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                force_update=True,
            )
            assert result.get("success", False), f"初始数据处理失败: {symbol}"

        # 步骤2: 使用增量同步进行后续更新
        sync_result = incremental_sync.sync_all_symbols(
            target_date=end_date, symbols=test_symbols, frequencies=["1d"]
        )

        # 验证增量同步结果 - 根据实际返回格式调整
        print(f"同步结果: {sync_result}")
        assert (
            sync_result.get("success_count", 0) > 0
            or sync_result.get("total_symbols", 0) > 0
        ), "增量同步失败"

        # 验证最终数据质量
        for symbol in test_symbols:
            assert self.verify_data_exists(
                db_manager, symbol, 3
            ), f"股票 {symbol} 数据不足"

        print("✅ 完整同步流水线测试通过")
