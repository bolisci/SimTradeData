"""
测试数据库工具

提供专用的测试数据库管理功能，包括创建、清理、数据插入等。
"""

import sqlite3
import tempfile
from pathlib import Path
from typing import List, Optional


class MockDatabase:
    """模拟测试数据库管理器"""

    def __init__(self):
        """初始化测试数据库"""
        # 创建临时数据库文件
        self.temp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_file.name
        self.temp_file.close()

        # 建立连接
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row  # 支持字典式访问

        # 创建所有测试表
        self._create_tables()

        # 插入基础测试数据
        self._insert_base_data()

    def _create_tables(self):
        """创建测试表"""
        # 股票信息表
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ptrade_stock_info (
                symbol TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                market TEXT NOT NULL,
                exchange TEXT,
                status TEXT DEFAULT 'active',
                list_date TEXT,
                delist_date TEXT,
                industry TEXT,
                sector TEXT,
                total_share REAL,
                float_share REAL,
                currency TEXT DEFAULT 'CNY',
                timezone TEXT DEFAULT 'Asia/Shanghai',
                trading_hours TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # 历史数据表
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS market_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                market TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                trade_time TEXT,
                frequency TEXT NOT NULL DEFAULT '1d',
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                money REAL,
                price REAL,
                preclose REAL,
                high_limit REAL,
                low_limit REAL,
                unlimited INTEGER DEFAULT 0,
                pe_ratio REAL,
                pb_ratio REAL,
                ps_ratio REAL,
                turnover_rate REAL,
                change_amount REAL,
                change_percent REAL,
                ma5 REAL,
                ma10 REAL,
                ma20 REAL,
                ma60 REAL,
                quality_score INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, trade_date, frequency)
            )
        """
        )

        # 实时数据表
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ptrade_realtime (
                symbol TEXT PRIMARY KEY,
                market TEXT NOT NULL,
                price REAL,
                change_amount REAL,
                change_percent REAL,
                volume INTEGER,
                money REAL,
                bid_price REAL,
                ask_price REAL,
                bid_volume INTEGER,
                ask_volume INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # 财务数据表
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ptrade_fundamentals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                report_date TEXT NOT NULL,
                report_type TEXT NOT NULL,
                revenue REAL,
                net_income REAL,
                total_assets REAL,
                total_equity REAL,
                eps REAL,
                roe REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, report_date, report_type)
            )
        """
        )

        self.conn.commit()

    def _insert_base_data(self):
        """插入基础测试数据"""
        # 插入测试股票
        test_stocks = [
            (
                "000001.SZ",
                "平安银行",
                "SZ",
                "SZSE",
                "active",
                "1991-04-03",
                None,
                "银行",
                "金融",
                19405000000,
                19405000000,
                "CNY",
                "Asia/Shanghai",
                "09:30-11:30,13:00-15:00",
            ),
            (
                "000002.SZ",
                "万科A",
                "SZ",
                "SZSE",
                "active",
                "1991-01-29",
                None,
                "房地产开发",
                "房地产",
                11039152000,
                11039152000,
                "CNY",
                "Asia/Shanghai",
                "09:30-11:30,13:00-15:00",
            ),
            (
                "600000.SS",
                "浦发银行",
                "SS",
                "SSE",
                "active",
                "1999-11-10",
                None,
                "银行",
                "金融",
                29352000000,
                29352000000,
                "CNY",
                "Asia/Shanghai",
                "09:30-11:30,13:00-15:00",
            ),
            (
                "600036.SS",
                "招商银行",
                "SS",
                "SSE",
                "active",
                "2002-04-09",
                None,
                "银行",
                "金融",
                25220000000,
                25220000000,
                "CNY",
                "Asia/Shanghai",
                "09:30-11:30,13:00-15:00",
            ),
            (
                "00700.HK",
                "腾讯控股",
                "HK",
                "HKEX",
                "active",
                "2004-06-16",
                None,
                "互联网",
                "科技",
                9600000000,
                9600000000,
                "HKD",
                "Asia/Hong_Kong",
                "09:30-12:00,13:00-16:00",
            ),
            (
                "00941.HK",
                "中国移动",
                "HK",
                "HKEX",
                "active",
                "1997-10-23",
                None,
                "电信",
                "通信",
                20475000000,
                20475000000,
                "HKD",
                "Asia/Hong_Kong",
                "09:30-12:00,13:00-16:00",
            ),
        ]

        for stock in test_stocks:
            self.conn.execute(
                "INSERT OR REPLACE INTO ptrade_stock_info (symbol, name, market, exchange, status, list_date, delist_date, industry, sector, total_share, float_share, currency, timezone, trading_hours) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                stock,
            )

        # 插入测试历史数据
        test_history = [
            # 000001.SZ 平安银行
            (
                "000001.SZ",
                "SZ",
                "2024-01-15",
                None,
                "1d",
                10.0,
                10.5,
                9.8,
                10.2,
                12500000,
                127500000,
                10.2,
                10.0,  # preclose
                11.0,  # high_limit
                9.0,  # low_limit
                0,  # unlimited
                8.5,  # pe_ratio
                1.2,  # pb_ratio
                1.8,  # ps_ratio
                0.64,  # turnover_rate
                0.2,  # change_amount
                2.0,  # change_percent
                10.1,  # ma5
                10.05,  # ma10
                10.0,  # ma20
                9.95,  # ma60
                1,  # quality_score
            ),
            (
                "000001.SZ",
                "SZ",
                "2024-01-16",
                None,
                "1d",
                10.2,
                10.8,
                10.0,
                10.5,
                15000000,
                157500000,
                10.5,
                10.2,  # preclose
                11.22,  # high_limit
                9.18,  # low_limit
                0,  # unlimited
                8.7,  # pe_ratio
                1.25,  # pb_ratio
                1.85,  # ps_ratio
                0.77,  # turnover_rate
                0.3,  # change_amount
                2.94,  # change_percent
                10.35,  # ma5
                10.25,  # ma10
                10.15,  # ma20
                10.05,  # ma60
                1,  # quality_score
            ),
            (
                "000001.SZ",
                "SZ",
                "2024-01-17",
                None,
                "1d",
                10.5,
                11.0,
                10.3,
                10.8,
                18000000,
                194400000,
                10.8,
                10.5,  # preclose
                11.55,  # high_limit
                9.45,  # low_limit
                0,  # unlimited
                9.0,  # pe_ratio
                1.28,  # pb_ratio
                1.9,  # ps_ratio
                0.93,  # turnover_rate
                0.3,  # change_amount
                2.86,  # change_percent
                10.6,  # ma5
                10.45,  # ma10
                10.3,  # ma20
                10.15,  # ma60
                1,  # quality_score
            ),
            # 600000.SS 浦发银行
            (
                "600000.SS",
                "SS",
                "2024-01-15",
                None,
                "1d",
                8.5,
                8.8,
                8.3,
                8.6,
                8000000,
                68800000,
                8.6,
                8.5,  # preclose
                9.35,  # high_limit
                7.65,  # low_limit
                0,  # unlimited
                6.2,  # pe_ratio
                0.9,  # pb_ratio
                1.1,  # ps_ratio
                0.27,  # turnover_rate
                0.1,  # change_amount
                1.18,  # change_percent
                8.55,  # ma5
                8.5,  # ma10
                8.45,  # ma20
                8.4,  # ma60
                1,  # quality_score
            ),
            (
                "600000.SS",
                "SS",
                "2024-01-16",
                None,
                "1d",
                8.6,
                9.0,
                8.4,
                8.9,
                9500000,
                84550000,
                8.9,
                8.6,  # preclose
                9.46,  # high_limit
                7.74,  # low_limit
                0,  # unlimited
                6.4,  # pe_ratio
                0.92,  # pb_ratio
                1.15,  # ps_ratio
                0.32,  # turnover_rate
                0.3,  # change_amount
                3.49,  # change_percent
                8.75,  # ma5
                8.65,  # ma10
                8.55,  # ma20
                8.45,  # ma60
                1,  # quality_score
            ),
            # 00700.HK 腾讯控股
            (
                "00700.HK",
                "HK",
                "2024-01-15",
                None,
                "1d",
                320.0,
                325.0,
                315.0,
                322.0,
                5000000,
                1610000000,
                322.0,
                320.0,  # preclose
                352.0,  # high_limit
                288.0,  # low_limit
                0,  # unlimited
                15.2,  # pe_ratio
                2.8,  # pb_ratio
                3.5,  # ps_ratio
                0.52,  # turnover_rate
                2.0,  # change_amount
                0.63,  # change_percent
                321.0,  # ma5
                320.5,  # ma10
                320.0,  # ma20
                319.5,  # ma60
                1,  # quality_score
            ),
        ]

        for history in test_history:
            self.conn.execute(
                "INSERT OR REPLACE INTO market_data (symbol, market, trade_date, trade_time, frequency, open, high, low, close, volume, money, price, preclose, high_limit, low_limit, unlimited, pe_ratio, pb_ratio, ps_ratio, turnover_rate, change_amount, change_percent, ma5, ma10, ma20, ma60, quality_score) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                history,
            )

        # 插入测试实时数据
        test_realtime = [
            (
                "000001.SZ",
                "SZ",
                10.8,
                0.3,
                2.86,
                18000000,
                194400000,
                10.75,
                10.80,
                1000,
                800,
            ),
            (
                "600000.SS",
                "SS",
                8.9,
                0.3,
                3.49,
                9500000,
                84550000,
                8.88,
                8.90,
                500,
                600,
            ),
            (
                "00700.HK",
                "HK",
                322.0,
                2.0,
                0.63,
                5000000,
                1610000000,
                321.5,
                322.0,
                100,
                200,
            ),
        ]

        for realtime in test_realtime:
            self.conn.execute(
                "INSERT OR REPLACE INTO ptrade_realtime (symbol, market, price, change_amount, change_percent, volume, money, bid_price, ask_price, bid_volume, ask_volume) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                realtime,
            )

        # 插入测试财务数据
        test_fundamentals = [
            (
                "000001.SZ",
                "2023-12-31",
                "annual",
                150000000000,
                35000000000,
                4500000000000,
                450000000000,
                1.85,
                0.078,
            ),
            (
                "600000.SS",
                "2023-12-31",
                "annual",
                120000000000,
                28000000000,
                3800000000000,
                380000000000,
                1.65,
                0.074,
            ),
        ]

        for fundamental in test_fundamentals:
            self.conn.execute(
                "INSERT OR REPLACE INTO ptrade_fundamentals (symbol, report_date, report_type, revenue, net_income, total_assets, total_equity, eps, roe) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                fundamental,
            )

        self.conn.commit()

    def execute(self, sql: str, params: tuple = None) -> sqlite3.Cursor:
        """执行SQL语句"""
        if params:
            return self.conn.execute(sql, params)
        else:
            return self.conn.execute(sql)

    def fetchall(self, sql: str, params: tuple = None) -> List[sqlite3.Row]:
        """查询所有结果"""
        cursor = self.execute(sql, params)
        return cursor.fetchall()

    def fetchone(self, sql: str, params: tuple = None) -> Optional[sqlite3.Row]:
        """查询单个结果"""
        cursor = self.execute(sql, params)
        return cursor.fetchone()

    def insert_stock(self, symbol: str, name: str, market: str, **kwargs):
        """插入股票信息"""
        exchange = kwargs.get(
            "exchange", market + "SE" if market in ["SZ", "SS"] else "HKEX"
        )
        status = kwargs.get("status", "active")
        list_date = kwargs.get("list_date", "2024-01-01")
        industry = kwargs.get("industry", "其他")
        sector = kwargs.get("sector", "其他")
        total_share = kwargs.get("total_share", 1000000000)
        float_share = kwargs.get("float_share", 1000000000)
        currency = kwargs.get("currency", "CNY")
        timezone = kwargs.get("timezone", "Asia/Shanghai")
        trading_hours = kwargs.get("trading_hours", "09:30-11:30,13:00-15:00")

        self.execute(
            "INSERT OR REPLACE INTO ptrade_stock_info (symbol, name, market, exchange, status, list_date, industry, sector, total_share, float_share, currency, timezone, trading_hours) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                symbol,
                name,
                market,
                exchange,
                status,
                list_date,
                industry,
                sector,
                total_share,
                float_share,
                currency,
                timezone,
                trading_hours,
            ),
        )
        self.conn.commit()

    def insert_history(self, symbol: str, market: str, trade_date: str, **kwargs):
        """插入历史数据"""
        frequency = kwargs.get("frequency", "1d")
        open_price = kwargs.get("open", 10.0)
        high = kwargs.get("high", 10.5)
        low = kwargs.get("low", 9.5)
        close = kwargs.get("close", 10.0)
        volume = kwargs.get("volume", 1000000)
        money = kwargs.get("money", 10000000)
        price = kwargs.get("price", close)
        preclose = kwargs.get("preclose", close)
        high_limit = kwargs.get("high_limit", close * 1.1)
        low_limit = kwargs.get("low_limit", close * 0.9)
        unlimited = kwargs.get("unlimited", 0)
        pe_ratio = kwargs.get("pe_ratio", 10.0)
        pb_ratio = kwargs.get("pb_ratio", 1.5)
        ps_ratio = kwargs.get("ps_ratio", 2.0)
        turnover_rate = kwargs.get("turnover_rate", 1.0)
        change_amount = kwargs.get("change_amount", 0.0)
        change_percent = kwargs.get("change_percent", 0.0)
        ma5 = kwargs.get("ma5", close)
        ma10 = kwargs.get("ma10", close)
        ma20 = kwargs.get("ma20", close)
        ma60 = kwargs.get("ma60", close)
        quality_score = kwargs.get("quality_score", 1)

        self.execute(
            "INSERT OR REPLACE INTO market_data (symbol, market, trade_date, frequency, open, high, low, close, volume, money, price, preclose, high_limit, low_limit, unlimited, pe_ratio, pb_ratio, ps_ratio, turnover_rate, change_amount, change_percent, ma5, ma10, ma20, ma60, quality_score) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                symbol,
                market,
                trade_date,
                frequency,
                open_price,
                high,
                low,
                close,
                volume,
                money,
                price,
                preclose,
                high_limit,
                low_limit,
                unlimited,
                pe_ratio,
                pb_ratio,
                ps_ratio,
                turnover_rate,
                change_amount,
                change_percent,
                ma5,
                ma10,
                ma20,
                ma60,
                quality_score,
            ),
        )
        self.conn.commit()

    def clear_table(self, table_name: str):
        """清空表数据"""
        self.execute(f"DELETE FROM {table_name}")
        self.conn.commit()

    def clear_all_data(self):
        """清空所有测试数据"""
        tables = [
            "stocks",
            "market_data",
            "technical_indicators",
            "financials",
        ]
        for table in tables:
            self.clear_table(table)

        # 重新插入基础数据
        self._insert_base_data()

    def get_stock_count(self) -> int:
        """获取股票数量"""
        result = self.fetchone("SELECT COUNT(*) as count FROM stocks")
        return result["count"] if result else 0

    def get_history_count(self, symbol: Optional[str] = None) -> int:
        """获取历史数据数量"""
        if symbol:
            result = self.fetchone(
                "SELECT COUNT(*) as count FROM market_data WHERE symbol = ?",
                (symbol,),
            )
        else:
            result = self.fetchone("SELECT COUNT(*) as count FROM market_data")
        return result["count"] if result else 0

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()

    def cleanup(self):
        """清理测试数据库"""
        self.close()
        Path(self.db_path).unlink(missing_ok=True)

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.cleanup()
