"""
多市场支持演示

展示港股、美股适配器和多市场统一管理功能。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from datetime import datetime
from unittest.mock import Mock

import pytz

from simtradedata.config import Config
from simtradedata.database import DatabaseManager
from simtradedata.markets import (
    CurrencyConverter,
    HKMarketAdapter,
    MultiMarketManager,
    TimezoneHandler,
    USMarketAdapter,
)

# 设置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def demo_hk_market_adapter():
    """演示港股市场适配器"""
    print("\n🇭🇰 港股市场适配器演示")
    print("=" * 50)

    # 创建模拟数据库管理器
    db_manager = Mock(spec=DatabaseManager)
    config = Config()

    # 创建港股适配器
    adapter = HKMarketAdapter(db_manager, config)

    print(f"🔧 港股适配器配置:")
    print(f"  市场代码: {adapter.market_code}")
    print(f"  货币: {adapter.currency}")
    print(f"  时区: {adapter.timezone}")
    print(f"  交易时间: {adapter._format_trading_hours()}")

    # 测试股票代码标准化
    print(f"\n📝 股票代码标准化:")
    test_symbols = ["00700", "700", "01234", "00700.HK"]
    for symbol in test_symbols:
        normalized = adapter._normalize_symbol(symbol)
        print(f"  {symbol} -> {normalized}")

    # 测试股票信息适配
    print(f"\n📊 股票信息适配:")
    hk_stock_data = {
        "symbol": "00700",
        "name": "腾讯控股",
        "name_en": "Tencent Holdings Ltd",
        "status": "L",
        "type": "O",
        "industry": "软件服务",
        "sector": "科技",
        "list_date": "2004-06-16",
        "lot_size": 100,
        "total_share": 9600000000,
        "float_share": 9500000000,
    }

    adapted_stock = adapter.adapt_stock_info(hk_stock_data)
    print(f"  原始数据: {hk_stock_data['symbol']} - {hk_stock_data['name']}")
    print(f"  适配结果:")
    print(f"    股票代码: {adapted_stock['symbol']}")
    print(f"    市场: {adapted_stock['market']}")
    print(f"    货币: {adapted_stock['currency']}")
    print(f"    状态: {adapted_stock['status']}")
    print(f"    股票类型: {adapted_stock['stock_type']}")
    print(f"    每手股数: {adapted_stock['lot_size']}")

    # 测试价格数据适配
    print(f"\n💰 价格数据适配:")
    hk_price_data = {
        "symbol": "00700",
        "trade_date": "2024-01-20",
        "open": 320.5,
        "high": 325.0,
        "low": 318.0,
        "close": 322.5,
        "volume": 12500000,
        "preclose": 320.0,
        "turnover": 4031250000,
        "lot_volume": 125000,
    }

    adapted_price = adapter.adapt_price_data(hk_price_data)
    print(f"  交易日期: {adapted_price['trade_date']}")
    print(f"  开盘价: {adapted_price['open']} {adapted_price['currency']}")
    print(f"  最高价: {adapted_price['high']} {adapted_price['currency']}")
    print(f"  最低价: {adapted_price['low']} {adapted_price['currency']}")
    print(f"  收盘价: {adapted_price['close']} {adapted_price['currency']}")
    print(f"  涨跌额: {adapted_price['change']:.2f}")
    print(f"  涨跌幅: {adapted_price['change_percent']:.2f}%")
    print(f"  成交量: {adapted_price['volume']:,}")
    print(f"  成交额: {adapted_price['turnover']:,}")
    print(f"  无涨跌停: {adapted_price['unlimited']}")

    # 获取市场信息
    print(f"\n🏢 港股市场信息:")
    market_info = adapter.get_market_info()
    print(f"  市场名称: {market_info['market_name']}")
    print(f"  交易所: {market_info['exchange']}")
    print(f"  价格精度: {market_info['price_precision']} 位小数")
    print(f"  是否有涨跌停: {market_info['has_price_limit']}")
    print(f"  支持频率: {', '.join(market_info['supported_frequencies'])}")


def demo_us_market_adapter():
    """演示美股市场适配器"""
    print("\n🇺🇸 美股市场适配器演示")
    print("=" * 50)

    # 创建模拟数据库管理器
    db_manager = Mock(spec=DatabaseManager)
    config = Config()

    # 创建美股适配器
    adapter = USMarketAdapter(db_manager, config)

    print(f"🔧 美股适配器配置:")
    print(f"  市场代码: {adapter.market_code}")
    print(f"  货币: {adapter.currency}")
    print(f"  时区: {adapter.timezone}")
    print(f"  交易时间: {adapter._format_trading_hours()}")

    # 测试股票代码标准化
    print(f"\n📝 股票代码标准化:")
    test_symbols = ["AAPL", "MSFT", "GOOGL", "AAPL.US"]
    for symbol in test_symbols:
        normalized = adapter._normalize_symbol(symbol)
        print(f"  {symbol} -> {normalized}")

    # 测试股票信息适配
    print(f"\n📊 股票信息适配:")
    us_stock_data = {
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "exchange": "NASDAQ",
        "status": "ACTIVE",
        "type": "CS",
        "industry": "Technology",
        "sector": "Consumer Electronics",
        "market_cap": 3000000000000,
        "beta": 1.2,
        "dividend_yield": 0.5,
        "forward_pe": 25.5,
    }

    adapted_stock = adapter.adapt_stock_info(us_stock_data)
    print(f"  原始数据: {us_stock_data['symbol']} - {us_stock_data['name']}")
    print(f"  适配结果:")
    print(f"    股票代码: {adapted_stock['symbol']}")
    print(f"    市场: {adapted_stock['market']}")
    print(f"    交易所: {adapted_stock['exchange']}")
    print(f"    货币: {adapted_stock['currency']}")
    print(f"    股票类型: {adapted_stock['stock_type']}")
    print(f"    市值: ${adapted_stock['market_cap']:,}")
    print(f"    贝塔系数: {adapted_stock['beta']}")
    print(f"    股息率: {adapted_stock['dividend_yield']}%")

    # 测试价格数据适配
    print(f"\n💰 价格数据适配:")
    us_price_data = {
        "symbol": "AAPL",
        "trade_date": "2024-01-20",
        "open": 150.0,
        "high": 152.5,
        "low": 149.0,
        "close": 151.5,
        "volume": 50000000,
        "preclose": 150.5,
        "adj_close": 151.2,
        "dividend": 0.25,
        "premarket_close": 150.8,
        "afterhours_close": 151.8,
    }

    adapted_price = adapter.adapt_price_data(us_price_data)
    print(f"  交易日期: {adapted_price['trade_date']}")
    print(f"  开盘价: ${adapted_price['open']}")
    print(f"  最高价: ${adapted_price['high']}")
    print(f"  最低价: ${adapted_price['low']}")
    print(f"  收盘价: ${adapted_price['close']}")
    print(f"  复权收盘价: ${adapted_price['adj_close']}")
    print(f"  涨跌额: ${adapted_price['change']:.2f}")
    print(f"  涨跌幅: {adapted_price['change_percent']:.2f}%")
    print(f"  成交量: {adapted_price['volume']:,}")
    print(f"  股息: ${adapted_price['dividend']}")
    print(f"  盘前收盘: ${adapted_price['premarket_close']}")
    print(f"  盘后收盘: ${adapted_price['afterhours_close']}")

    # 获取市场信息
    print(f"\n🏢 美股市场信息:")
    market_info = adapter.get_market_info()
    print(f"  市场名称: {market_info['market_name_en']}")
    print(f"  支持交易所: {', '.join(market_info['exchanges'])}")
    print(f"  价格精度: {market_info['price_precision']} 位小数")
    print(f"  支持盘前交易: {market_info['supports_premarket']}")
    print(f"  支持盘后交易: {market_info['supports_afterhours']}")


def demo_multi_market_manager():
    """演示多市场管理器"""
    print("\n🌍 多市场管理器演示")
    print("=" * 50)

    # 创建模拟数据库管理器
    db_manager = Mock(spec=DatabaseManager)
    config = Config()

    # 创建多市场管理器
    manager = MultiMarketManager(db_manager, config)

    print(f"🔧 多市场管理器配置:")
    print(f"  支持市场: {manager.get_supported_markets()}")
    print(f"  默认市场: {manager.default_market}")
    print(f"  启用适配器: {list(manager.adapters.keys())}")

    # 测试股票代码市场解析
    print(f"\n🔍 股票代码市场解析:")
    test_symbols = [
        "00700.HK",
        "AAPL.US",
        "000001.SZ",
        "600000.SS",
        "00700",
        "AAPL",
        "000001",
        "600000",
    ]

    for symbol in test_symbols:
        market = manager.parse_symbol_market(symbol)
        normalized = manager.normalize_symbol(symbol, market)
        print(f"  {symbol} -> 市场: {market}, 标准化: {normalized}")

    # 测试跨市场股票信息适配
    print(f"\n📊 跨市场股票信息适配:")

    # 港股数据
    hk_data = {
        "symbol": "00700",
        "name": "腾讯控股",
        "status": "L",
        "type": "O",
        "lot_size": 100,
    }
    hk_adapted = manager.adapt_stock_info(hk_data, "HK")
    print(
        f"  港股: {hk_adapted['symbol']} - {hk_adapted['name']} ({hk_adapted['currency']})"
    )

    # 美股数据
    us_data = {
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "exchange": "NASDAQ",
        "status": "ACTIVE",
        "type": "CS",
    }
    us_adapted = manager.adapt_stock_info(us_data, "US")
    print(
        f"  美股: {us_adapted['symbol']} - {us_adapted['name']} ({us_adapted['currency']})"
    )

    # A股数据
    sz_data = {
        "symbol": "000001",
        "name": "平安银行",
        "status": "active",
        "type": "ordinary",
    }
    sz_adapted = manager.adapt_stock_info(sz_data, "SZ")
    print(
        f"  A股: {sz_adapted['symbol']} - {sz_adapted['name']} ({sz_adapted['currency']})"
    )

    # 获取所有市场信息
    print(f"\n🏢 所有市场信息:")
    markets_info = manager.get_all_markets_info()
    for market, info in markets_info.items():
        if "market_name" in info:
            print(
                f"  {market}: {info.get('market_name', info.get('market_name_en', 'Unknown'))}"
            )
            print(f"    货币: {info.get('currency', 'N/A')}")
            print(f"    时区: {info.get('timezone', 'N/A')}")
            print(f"    交易时间: {info.get('trading_hours', 'N/A')}")


def demo_currency_converter():
    """演示货币转换器"""
    print("\n💱 货币转换器演示")
    print("=" * 50)

    # 创建模拟数据库管理器
    db_manager = Mock(spec=DatabaseManager)

    # 模拟汇率查询返回
    def mock_fetchone(sql, params=None):
        if "USD" in params and "CNY" in params:
            return {"exchange_rate": 7.2}
        elif "HKD" in params and "CNY" in params:
            return {"exchange_rate": 0.92}
        elif "USD" in params and "HKD" in params:
            return {"exchange_rate": 7.8}
        return None

    db_manager.fetchone.side_effect = mock_fetchone

    config = Config()
    converter = CurrencyConverter(db_manager, config)

    print(f"🔧 货币转换器配置:")
    print(f"  支持货币: {converter.get_supported_currencies()}")
    print(f"  基准货币: {converter.base_currency}")

    # 测试货币转换
    print(f"\n💰 货币转换示例:")

    conversions = [
        (100.0, "USD", "CNY"),
        (1000.0, "HKD", "CNY"),
        (100.0, "USD", "HKD"),
        (720.0, "CNY", "USD"),
        (100.0, "USD", "USD"),  # 相同货币
    ]

    for amount, from_curr, to_curr in conversions:
        converted = converter.convert(amount, from_curr, to_curr)
        if converted is not None:
            print(f"  {amount} {from_curr} = {converted:.2f} {to_curr}")
        else:
            print(f"  {amount} {from_curr} -> {to_curr}: 转换失败")

    # 测试货币信息
    print(f"\n💴 货币信息:")
    currencies = ["CNY", "USD", "HKD", "EUR"]
    for currency in currencies:
        info = converter.get_currency_info(currency)
        if info:
            print(
                f"  {currency}: {info['name']} ({info['symbol']}) - 精度: {info['precision']} 位"
            )

    # 测试价格数据货币转换
    print(f"\n📊 价格数据货币转换:")
    price_data = {
        "symbol": "AAPL.US",
        "trade_date": "2024-01-20",
        "currency": "USD",
        "open": 150.0,
        "high": 152.5,
        "low": 149.0,
        "close": 151.5,
        "volume": 50000000,
    }

    print(f"  原始数据 (USD):")
    print(f"    开盘: ${price_data['open']}")
    print(f"    收盘: ${price_data['close']}")

    # 转换为人民币
    converted_data = converter.convert_price_data(price_data, "CNY")
    print(f"  转换后 (CNY):")
    print(f"    开盘: ¥{converted_data['open']:.2f}")
    print(f"    收盘: ¥{converted_data['close']:.2f}")
    print(f"    原始货币: {converted_data['original_currency']}")


def demo_timezone_handler():
    """演示时区处理器"""
    print("\n🕐 时区处理器演示")
    print("=" * 50)

    config = Config()
    handler = TimezoneHandler(config)

    print(f"🔧 时区处理器配置:")
    print(f"  默认时区: {handler.default_timezone}")
    print(f"  市场时区: {handler.market_timezones}")

    # 测试获取市场时区
    print(f"\n🌏 市场时区:")
    for market in ["SZ", "HK", "US"]:
        tz = handler.get_market_timezone(market)
        print(f"  {market}: {tz.zone}")

    # 测试获取市场时间
    print(f"\n⏰ 当前市场时间:")
    current_utc = datetime.now(pytz.UTC)
    print(f"  UTC时间: {current_utc.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    for market in ["SZ", "HK", "US"]:
        market_time = handler.get_market_time(market, current_utc)
        print(f"  {market}时间: {market_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    # 测试时区转换
    print(f"\n🔄 时区转换示例:")

    # 创建一个上海时间
    shanghai_dt = datetime(2024, 1, 20, 10, 30, 0)
    print(f"  上海时间: {shanghai_dt} (Asia/Shanghai)")

    # 转换到其他时区
    conversions = [
        ("Asia/Shanghai", "Asia/Hong_Kong"),
        ("Asia/Shanghai", "America/New_York"),
        ("Asia/Shanghai", "UTC"),
    ]

    for from_tz, to_tz in conversions:
        converted = handler.convert_timezone(shanghai_dt, from_tz, to_tz)
        print(f"  -> {to_tz}: {converted.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    # 测试时区信息
    print(f"\n📋 时区信息:")
    timezones = ["Asia/Shanghai", "Asia/Hong_Kong", "America/New_York"]
    for tz_name in timezones:
        info = handler.get_timezone_info(tz_name)
        print(f"  {tz_name}:")
        print(f"    当前时间: {info['current_time']}")
        print(f"    UTC偏移: {info['utc_offset']}")
        print(f"    夏令时: {info['dst_active']}")


def main():
    """主演示函数"""
    print("🚀 SimTradeData 多市场支持演示")
    print("=" * 60)

    try:
        # 演示各个组件
        demo_hk_market_adapter()
        demo_us_market_adapter()
        demo_multi_market_manager()
        demo_currency_converter()
        demo_timezone_handler()

        print("\n🎉 多市场支持演示完成!")
        print("\n📝 总结:")
        print("✅ 港股适配器: 支持港股特有字段、交易时间、代码格式")
        print("✅ 美股适配器: 支持美股特有字段、盘前盘后、复权数据")
        print("✅ 多市场管理器: 统一管理、智能解析、跨市场适配")
        print("✅ 货币转换器: 多货币支持、实时汇率、价格数据转换")
        print("✅ 时区处理器: 多时区支持、交易时间管理、时区转换")
        print("✅ 全球化支持: A股、港股、美股统一接口")

    except Exception as e:
        logger.error(f"演示过程中出现错误: {e}")
        raise


if __name__ == "__main__":
    main()
