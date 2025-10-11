#!/usr/bin/env python3
"""
SimTradeData 命令行工具

提供全量下载、增量更新、缺口补充和断点续传等数据同步功能的命令行接口。
"""

import argparse
import logging
import sys
from datetime import date, datetime, timedelta
from typing import List

from .config import Config
from .data_sources import DataSourceManager
from .database import DatabaseManager
from .preprocessor import DataProcessingEngine
from .sync import SyncManager

# 只禁用外部库的进度条，但保留我们自己的
# os.environ['TQDM_DISABLE'] = '1'  # 注释掉这行


# 设置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class SimTradeDataCLI:
    """SimTradeData 命令行工具"""

    def __init__(self, db_path: str = None, config_path: str = None):
        """初始化CLI工具"""
        # 加载配置
        self.config = Config(config_path) if config_path else Config()

        # 设置数据库路径
        if db_path:
            self.config.set("database.path", db_path)

        # 初始化组件
        self.db_manager = DatabaseManager(
            self.config.get("database.path", "data/simtradedata.db")
        )
        self.data_source_manager = DataSourceManager(
            self.config, db_manager=self.db_manager
        )
        self.processing_engine = DataProcessingEngine(
            self.db_manager, self.data_source_manager, self.config
        )
        self.sync_manager = SyncManager(
            self.db_manager,
            self.data_source_manager,
            self.processing_engine,
            self.config,
        )

    def full_sync(
        self,
        target_date: str = None,
        symbols: List[str] = None,
        frequencies: List[str] = None,
    ) -> bool:
        """
        执行全量数据同步

        Args:
            target_date: 目标日期 (YYYY-MM-DD)
            symbols: 股票代码列表
            frequencies: 频率列表 (1d, 5m, 15m, 30m, 1h)

        Returns:
            bool: 是否成功
        """
        try:
            # 解析目标日期
            if target_date:
                target_date = datetime.strptime(target_date, "%Y-%m-%d").date()
            else:
                target_date = date.today()

            # 设置默认频率
            if not frequencies:
                frequencies = ["1d"]

            logger.info(f"🚀 starting full data synchronization")
            logger.info(f"target date : {target_date}")
            logger.info(f"stock count : {len(symbols) if symbols else ' all '}")
            logger.info(f"data frequency : {', '.join(frequencies)}")

            # 执行同步
            result = self.sync_manager.run_full_sync(
                target_date=target_date, symbols=symbols, frequencies=frequencies
            )

            # 输出结果
            # unified_error_handler会包装结果为 {"success": True, "data": {...}}
            if result.get("success"):
                summary = result.get("data", {}).get("summary", {})
            else:
                summary = (
                    result.get("data", {}).get("summary", {})
                    if result.get("data")
                    else {}
                )

            logger.info(f"✅ full synchronization completed !")
            logger.info(f"successful phases : {summary.get('successful_phases', 0)}")
            logger.info(f"failed phases : {summary.get('failed_phases', 0)}")

            return summary.get("failed_phases", 0) == 0

        except Exception as e:
            logger.error(f"❌ full synchronization failed : {e}")
            return False

    def incremental_sync(
        self,
        start_date: str,
        end_date: str = None,
        symbols: List[str] = None,
        frequency: str = "1d",
    ) -> bool:
        """
        执行增量数据同步

        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)，默认为今天
            symbols: 股票代码列表
            frequency: 数据频率

        Returns:
            bool: 是否成功
        """
        try:
            # 解析日期
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            if end_date:
                end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
            else:
                end_date = date.today()

            logger.info(f"📈 starting incremental data synchronization")
            logger.info(f"date range : {start_date} to {end_date}")
            logger.info(f"stock count : {len(symbols) if symbols else ' all '}")
            logger.info(f"data frequency : {frequency}")

            # 如果没有指定股票，获取所有活跃股票
            if not symbols:
                # 从数据库获取活跃股票列表
                sql = (
                    "SELECT symbol FROM stocks WHERE status = 'active' ORDER BY symbol"
                )
                result = self.db_manager.fetchall(sql)
                if result:
                    symbols = [row["symbol"] for row in result]
                    logger.info(f"retrieve from database {len(symbols)} active stocks")
                else:
                    raise ValueError(
                        "数据库中没有活跃股票，请先运行 full-sync 更新股票列表"
                    )

            # 执行增量同步
            total_success = 0
            total_error = 0

            for symbol in symbols:
                try:
                    result = self.sync_manager.incremental_sync.sync_symbol_range(
                        symbol, start_date, end_date, frequency
                    )
                    total_success += result.get("success_count", 0)
                    total_error += result.get("error_count", 0)
                    logger.info(
                        f"{symbol}: succeeded {result.get('success_count', 0)} records"
                    )
                except Exception as e:
                    logger.error(f"{symbol}: failed - {e}")
                    total_error += 1

            logger.info(f"✅ incremental synchronization completed !")
            logger.info(f"total successes : {total_success} records")
            logger.info(f"total errors : {total_error} records")

            return total_error == 0

        except Exception as e:
            logger.error(f"❌ incremental synchronization failed : {e}")
            return False

    def gap_detection_and_fix(
        self,
        start_date: str,
        end_date: str = None,
        symbols: List[str] = None,
        frequencies: List[str] = None,
    ) -> bool:
        """
        执行缺口检测和修复

        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)，默认为今天
            symbols: 股票代码列表
            frequencies: 频率列表

        Returns:
            bool: 是否成功
        """
        try:
            # 解析日期
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            if end_date:
                end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
            else:
                end_date = date.today()

            # 设置默认频率
            if not frequencies:
                frequencies = ["1d"]

            logger.info(f"🔍 starting gap detection and repair")
            logger.info(f"date range : {start_date} to {end_date}")
            logger.info(f"stock count : {len(symbols) if symbols else ' all '}")
            logger.info(f"data frequency : {', '.join(frequencies)}")

            # 执行缺口检测
            detection_result = self.sync_manager.gap_detector.detect_all_gaps(
                start_date=start_date,
                end_date=end_date,
                symbols=symbols,
                frequencies=frequencies,
            )

            # 如果发现缺口，执行自动修复
            fix_result = {}
            if detection_result.get("summary", {}).get("total_gaps", 0) > 0:
                fix_result = self.sync_manager._auto_fix_gaps(detection_result)

            detection_summary = detection_result.get("summary", {})
            logger.info(f"🔍 gap detection result :")
            logger.info(f"found gaps : {detection_summary.get('total_gaps', 0)}")
            logger.info(
                f"stocks involved : {detection_summary.get('symbols_with_gaps', 0)}"
            )

            if fix_result:
                logger.info(f"🔧 gap repairing result :")
                logger.info(
                    f"attempting fixes : {fix_result.get('attempted_fixes', 0)}"
                )
                logger.info(
                    f"successful fixes : {fix_result.get('successful_fixes', 0)}"
                )

            logger.info(f"✅ gap detection and repair completed !")

            return True

        except Exception as e:
            logger.error(f"❌ gap detection and repair failed : {e}")
            return False

    def resume_sync(self, symbol: str, frequency: str = "1d") -> bool:
        """
        断点续传同步

        Args:
            symbol: 股票代码
            frequency: 数据频率

        Returns:
            bool: 是否成功
        """
        try:
            logger.info(f"🔄 starting resume from breakpoint synchronization")
            logger.info(f"stock code : {symbol}")
            logger.info(f"data frequency : {frequency}")

            # 查询最后同步状态
            sql = """
                SELECT last_sync_date, last_data_date 
                FROM sync_status 
                WHERE symbol = ? AND frequency = ?
            """
            status = self.db_manager.fetchone(sql, (symbol, frequency))

            if status and status["last_data_date"]:
                last_date = datetime.strptime(
                    status["last_data_date"], "%Y-%m-%d"
                ).date()
                resume_date = last_date + timedelta(days=1)
                target_date = date.today()

                logger.info(f"last synchronization : {last_date}")
                logger.info(f"resume point : {resume_date}")
                logger.info(f"target date : {target_date}")

                # 执行续传
                result = self.sync_manager.incremental_sync.sync_symbol_range(
                    symbol, resume_date, target_date, frequency
                )

                logger.info(f"✅ resume from breakpoint completed !")
                logger.info(f"succeeded : {result.get('success_count', 0)} records")
                logger.info(f"failed : {result.get('error_count', 0)} records")

                return result.get("error_count", 0) == 0
            else:
                logger.warning(
                    f"⚠️ not found {symbol} synchronization status , suggest using full synchronization"
                )
                return False

        except Exception as e:
            logger.error(f"❌ resume from breakpoint failed : {e}")
            return False

    def status(self) -> bool:
        """查看同步状态"""
        try:
            logger.info(f"📊 synchronization status query")

            # 查询同步状态统计
            sql = """
                SELECT 
                    frequency,
                    COUNT(*) as total_symbols,
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
                    COUNT(CASE WHEN status = 'running' THEN 1 END) as running,
                    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed,
                    MAX(last_sync_date) as latest_sync
                FROM sync_status 
                GROUP BY frequency
            """

            results = self.db_manager.fetchall(sql)

            if results:
                logger.info(
                    "frequency | total | completed | running | failed | latest synchronization"
                )
                logger.info("   " + "-" * 50)
                for row in results:
                    logger.info(
                        f"   {row['frequency']:6} | {row['total_symbols']:4} | "
                        f"{row['completed']:4} | {row['running']:6} | "
                        f"{row['failed']:4} | {row['latest_sync'] or 'N/A'}"
                    )
            else:
                logger.info("no synchronization status records")

            return True

        except Exception as e:
            logger.error(f"❌ status query failed : {e}")
            return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="SimTradeData 数据同步命令行工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 全量同步今天的数据
  python -m simtradedata full-sync

  # 全量同步指定日期
  python -m simtradedata full-sync --target-date 2024-01-20

  # 增量同步指定日期范围
  python -m simtradedata incremental --start-date 2024-01-01 --end-date 2024-01-10

  # 缺口检测和修复
  python -m simtradedata gap-fix --start-date 2024-01-01

  # 断点续传
  python -m simtradedata resume --symbol 000001.SZ

  # 查看同步状态
  python -m simtradedata status
        """,
    )

    # 全局参数
    parser.add_argument("--db-path", help="数据库文件路径")
    parser.add_argument("--config", help="配置文件路径")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    parser.add_argument(
        "--quiet", "-q", action="store_true", help="静默模式，只显示进度条和关键信息"
    )

    # 子命令
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # 全量同步
    full_parser = subparsers.add_parser("full-sync", help="全量数据同步")
    full_parser.add_argument("--target-date", help="目标日期 (YYYY-MM-DD)")
    full_parser.add_argument("--symbols", nargs="+", help="股票代码列表")
    full_parser.add_argument("--symbols-file", help="股票代码文件路径（每行一个代码）")
    full_parser.add_argument("--all-stocks", action="store_true", help="下载所有股票")
    full_parser.add_argument(
        "--frequencies",
        nargs="+",
        default=["1d"],
        help="数据频率 (1d, 5m, 15m, 30m, 1h)",
    )

    # 增量同步
    inc_parser = subparsers.add_parser("incremental", help="增量数据同步")
    inc_parser.add_argument("--start-date", required=True, help="开始日期 (YYYY-MM-DD)")
    inc_parser.add_argument("--end-date", help="结束日期 (YYYY-MM-DD)")
    inc_parser.add_argument("--symbols", nargs="+", help="股票代码列表")
    inc_parser.add_argument("--frequency", default="1d", help="数据频率")

    # 缺口修复
    gap_parser = subparsers.add_parser("gap-fix", help="缺口检测和修复")
    gap_parser.add_argument("--start-date", required=True, help="开始日期 (YYYY-MM-DD)")
    gap_parser.add_argument("--end-date", help="结束日期 (YYYY-MM-DD)")
    gap_parser.add_argument("--symbols", nargs="+", help="股票代码列表")
    gap_parser.add_argument("--frequencies", nargs="+", default=["1d"], help="数据频率")

    # 断点续传
    resume_parser = subparsers.add_parser("resume", help="断点续传同步")
    resume_parser.add_argument("--symbol", required=True, help="股票代码")
    resume_parser.add_argument("--frequency", default="1d", help="数据频率")

    # 状态查询
    subparsers.add_parser("status", help="查看同步状态")

    # 解析参数
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # 设置日志级别和进度条
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    elif args.quiet:
        # 静默模式：只显示ERROR以上级别，保留进度条
        from .utils.progress_bar import sync_progress

        sync_progress.disable_logs = True

        # 设置根日志级别为ERROR，但不影响stdout输出
        logging.getLogger().setLevel(logging.ERROR)

        # 特别禁用这些模块的WARNING日志
        for module_name in [
            "simtradedata.preprocessor.engine",
            "simtradedata.data_sources.baostock_adapter",
            "simtradedata.data_sources.mootdx_adapter",
            "simtradedata.data_sources.manager",
            "simtradedata.sync.incremental",
        ]:
            logging.getLogger(module_name).setLevel(logging.ERROR)

    try:
        # 创建CLI实例
        cli = SimTradeDataCLI(args.db_path, args.config)

        # 执行命令
        success = False

        if args.command == "full-sync":
            success = cli.full_sync(args.target_date, args.symbols, args.frequencies)
        elif args.command == "incremental":
            success = cli.incremental_sync(
                args.start_date, args.end_date, args.symbols, args.frequency
            )
        elif args.command == "gap-fix":
            success = cli.gap_detection_and_fix(
                args.start_date, args.end_date, args.symbols, args.frequencies
            )
        elif args.command == "resume":
            success = cli.resume_sync(args.symbol, args.frequency)
        elif args.command == "status":
            success = cli.status()

        # 使用os._exit()强制退出，跳过所有清理和析构函数
        # 这样可以避免qstock session.close()阻塞
        import os

        os._exit(0 if success else 1)

    except KeyboardInterrupt:
        logger.info("user interrupted operation")
        # 使用os._exit()强制退出，跳过所有清理和析构函数
        # 这样可以避免qstock session.close()阻塞
        import os

        os._exit(1)
    except Exception as e:
        logger.error(f"executing failed : {e}")
        import os

        os._exit(1)


if __name__ == "__main__":
    sys.exit(main())
