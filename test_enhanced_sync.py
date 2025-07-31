#!/usr/bin/env python3
"""
测试增强的同步流程
验证衍生字段计算是否在实际同步中生效
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


def test_enhanced_sync():
    """测试增强的同步流程"""
    print("开始测试增强的同步流程...")

    # 初始化组件
    config = Config()
    db_manager = DatabaseManager()
    data_source_manager = DataSourceManager(config)
    processing_engine = DataProcessingEngine(db_manager, data_source_manager, config)

    # 测试单个股票的处理 - 获取更多天数以便计算衍生字段
    test_symbol = "000001.SZ"
    end_date = date(2025, 1, 24)
    start_date = date(2025, 1, 20)  # 获取5天数据

    print(f"测试股票: {test_symbol}, 日期范围: {start_date} 到 {end_date}")

    # 清理测试数据
    print("清理旧的测试数据...")
    db_manager.execute(
        "DELETE FROM market_data WHERE symbol = ? AND date >= ? AND date <= ?",
        (test_symbol, str(start_date), str(end_date)),
    )

    # 使用数据处理引擎处理数据
    print("使用数据处理引擎处理多天数据...")
    result = processing_engine.process_symbol_data(
        symbol=test_symbol, start_date=start_date, end_date=end_date, force_update=True
    )

    print(f"处理结果: {result}")

    # 检查数据库中的结果
    print("检查数据库中的数据...")
    sql = """
    SELECT symbol, date, close, change_percent, prev_close, amplitude, 
           source, quality_score, is_limit_up, is_limit_down
    FROM market_data 
    WHERE symbol = ? AND date >= ? AND date <= ?
    ORDER BY date
    """

    records = db_manager.fetchall(sql, (test_symbol, str(start_date), str(end_date)))

    if records:
        print(f"找到 {len(records)} 条记录:")
        for record in records:
            print(f"  股票: {record['symbol']}")
            print(f"  日期: {record['date']}")
            print(f"  收盘价: {record['close']}")
            print(f"  涨跌幅: {record['change_percent']}%")
            print(f"  前收盘: {record['prev_close']}")
            print(f"  振幅: {record['amplitude']}%")
            print(f"  数据源: {record['source']}")
            print(f"  质量分数: {record['quality_score']}")
            print(f"  涨停: {record['is_limit_up']}")
            print(f"  跌停: {record['is_limit_down']}")
            print("  ---")

        # 验证衍生字段
        record = records[0]
        if record["change_percent"] is not None and record["change_percent"] != 0:
            print("✅ 衍生字段计算成功!")
        else:
            print("❌ 衍生字段计算失败 - change_percent为空或0")

        if record["source"] == "processed_enhanced":
            print("✅ 使用了增强处理引擎!")
        else:
            print(f"❌ 数据源不正确: {record['source']} (预期: processed_enhanced)")
    else:
        print("❌ 没有找到任何记录")

    # 关闭连接
    db_manager.close()
    print("测试完成")


if __name__ == "__main__":
    test_enhanced_sync()
