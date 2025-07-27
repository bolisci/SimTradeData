"""
增量同步器

负责检测最后数据日期，计算增量数据范围，执行批量数据同步。
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from ..config import Config
from ..data_sources import DataSourceManager
from ..database import DatabaseManager
from ..preprocessor import DataProcessingEngine

logger = logging.getLogger(__name__)


class IncrementalSync:
    """增量同步器"""

    def __init__(
        self,
        db_manager: DatabaseManager,
        data_source_manager: DataSourceManager,
        processing_engine: DataProcessingEngine,
        config: Config = None,
    ):
        """
        初始化增量同步器

        Args:
            db_manager: 数据库管理器
            data_source_manager: 数据源管理器
            preprocessor: 数据预处理器
            config: 配置对象
        """
        self.db_manager = db_manager
        self.data_source_manager = data_source_manager
        self.processing_engine = processing_engine
        self.preprocessor = processing_engine  # 兼容性别名
        self.config = config or Config()

        # 同步配置
        self.max_sync_days = self.config.get("sync.max_sync_days", 30)
        self.batch_size = self.config.get("sync.batch_size", 50)
        self.max_workers = self.config.get("sync.max_workers", 3)
        self.sync_frequencies = self.config.get("sync.frequencies", ["1d"])
        self.enable_parallel = self.config.get("sync.enable_parallel", True)

        # 同步统计
        self.sync_stats = {
            "total_symbols": 0,
            "success_count": 0,
            "error_count": 0,
            "skipped_count": 0,
            "sync_date_ranges": {},
            "errors": [],
        }

        logger.info("增量同步器初始化完成")

    def sync_all_symbols(
        self,
        target_date: date = None,
        symbols: List[str] = None,
        frequencies: List[str] = None,
        progress_bar=None,
    ) -> Dict[str, Any]:
        """
        同步所有股票的增量数据

        Args:
            target_date: 目标日期，默认为今天
            symbols: 股票代码列表，默认为所有活跃股票
            frequencies: 频率列表，默认为配置中的频率

        Returns:
            Dict[str, Any]: 同步结果
        """
        if target_date is None:
            target_date = datetime.now().date()

        if frequencies is None:
            frequencies = self.sync_frequencies

        try:
            logger.info(f"开始增量同步: 目标日期={target_date}, 频率={frequencies}")

            # 重置统计
            self._reset_stats()

            # 获取需要同步的股票列表
            if symbols is None:
                symbols = self._get_active_symbols()

            self.sync_stats["total_symbols"] = len(symbols)

            # 按频率同步
            for frequency in frequencies:
                freq_result = self._sync_frequency_data(
                    symbols, target_date, frequency, progress_bar
                )
                self.sync_stats["sync_date_ranges"][frequency] = freq_result

            # 更新同步状态
            self._update_sync_status(target_date, self.sync_stats)

            logger.info(
                f"增量同步完成: 成功={self.sync_stats['success_count']}, "
                f"错误={self.sync_stats['error_count']}, "
                f"跳过={self.sync_stats['skipped_count']}"
            )

            return self.sync_stats.copy()

        except Exception as e:
            logger.error(f"增量同步失败: {e}")
            raise

    def sync_symbol_range(
        self, symbol: str, start_date: date, end_date: date, frequency: str = "1d"
    ) -> Dict[str, Any]:
        """
        同步单个股票的日期范围数据

        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            frequency: 频率

        Returns:
            Dict[str, Any]: 同步结果
        """
        try:
            logger.info(
                f"同步股票范围数据: {symbol} {start_date} 到 {end_date} {frequency}"
            )

            result = {
                "symbol": symbol,
                "start_date": str(start_date),
                "end_date": str(end_date),
                "frequency": frequency,
                "success_count": 0,
                "error_count": 0,
                "sync_dates": [],
            }

            # 批量同步整个日期范围
            try:
                # 使用数据处理引擎批量处理日期范围数据
                process_result = self.processing_engine.process_stock_data(
                    symbol, start_date, end_date, frequency, force_update=True
                )

                # 统计结果
                result["success_count"] = len(process_result.get("processed_dates", []))
                result["error_count"] = len(process_result.get("failed_dates", []))
                result["sync_dates"] = process_result.get("processed_dates", [])

                logger.debug(
                    f"批量处理结果: 成功={result['success_count']}, 失败={result['error_count']}"
                )

            except Exception as e:
                logger.error(f"批量同步失败 {symbol} {start_date}-{end_date}: {e}")
                result["error_count"] = 1

            logger.info(
                f"股票范围同步完成: {symbol}, 成功={result['success_count']}, "
                f"错误={result['error_count']}"
            )

            return result

        except Exception as e:
            logger.error(f"股票范围同步失败 {symbol}: {e}")
            raise

    def get_last_data_date(self, symbol: str, frequency: str = "1d") -> Optional[date]:
        """
        获取股票的最后数据日期

        Args:
            symbol: 股票代码
            frequency: 频率

        Returns:
            Optional[date]: 最后数据日期，如果没有数据则返回None
        """
        try:
            sql = """
            SELECT MAX(date) as last_date
            FROM market_data
            WHERE symbol = ? AND frequency = ?
            """

            result = self.db_manager.fetchone(sql, (symbol, frequency))

            if result and result["last_date"]:
                return datetime.strptime(result["last_date"], "%Y-%m-%d").date()
            else:
                return None

        except Exception as e:
            logger.error(f"获取最后数据日期失败 {symbol}: {e}")
            return None

    def calculate_sync_range(
        self, symbol: str, target_date: date, frequency: str = "1d"
    ) -> Tuple[Optional[date], date]:
        """
        计算增量同步的日期范围

        Args:
            symbol: 股票代码
            target_date: 目标日期
            frequency: 频率

        Returns:
            Tuple[Optional[date], date]: (开始日期, 结束日期)
        """
        try:
            # 获取最后数据日期
            last_date = self.get_last_data_date(symbol, frequency)

            if last_date is None:
                # 没有历史数据，从配置的默认开始日期同步
                default_start = self.config.get("sync.default_start_date", "2020-01-01")
                start_date = datetime.strptime(default_start, "%Y-%m-%d").date()

                # 限制最大同步天数
                max_start = target_date - timedelta(days=self.max_sync_days)
                if start_date < max_start:
                    start_date = max_start

                logger.info(f"首次同步 {symbol}: {start_date} 到 {target_date}")
                return start_date, target_date
            else:
                # 有历史数据，从最后日期的下一天开始
                start_date = last_date + timedelta(days=1)

                # 检查是否尝试同步未来日期
                today = datetime.now().date()
                if target_date > today:
                    target_date = today
                    logger.debug(f"目标日期调整为今天: {target_date}")

                if start_date > target_date:
                    # 已经是最新数据
                    logger.debug(f"数据已是最新 {symbol}: 最后日期={last_date}")
                    return None, target_date

                logger.debug(f"增量同步 {symbol}: {start_date} 到 {target_date}")
                return start_date, target_date

        except Exception as e:
            logger.error(f"计算同步范围失败 {symbol}: {e}")
            return None, target_date

    def _sync_frequency_data(
        self, symbols: List[str], target_date: date, frequency: str, progress_bar=None
    ) -> Dict[str, Any]:
        """同步特定频率的数据"""
        logger.info(f"同步频率数据: {frequency}, 股票数量: {len(symbols)}")

        result = {
            "frequency": frequency,
            "total_symbols": len(symbols),
            "success_count": 0,
            "error_count": 0,
            "skipped_count": 0,
            "sync_ranges": {},
        }

        # 使用流水线模式：下载串行，处理并发
        result.update(
            self._sync_pipeline(symbols, target_date, frequency, progress_bar)
        )

        # 更新总统计
        self.sync_stats["success_count"] += result["success_count"]
        self.sync_stats["error_count"] += result["error_count"]
        self.sync_stats["skipped_count"] += result["skipped_count"]

        return result

    def _sync_sequential(
        self, symbols: List[str], target_date: date, frequency: str, progress_bar=None
    ) -> Dict[str, Any]:
        """串行同步"""
        result = {
            "success_count": 0,
            "error_count": 0,
            "skipped_count": 0,
            "sync_ranges": {},
        }

        for symbol in symbols:
            try:
                # 计算同步范围
                start_date, end_date = self.calculate_sync_range(
                    symbol, target_date, frequency
                )

                if start_date is None:
                    result["skipped_count"] += 1
                    # 更新进度条
                    if progress_bar:
                        progress_bar.update(1)
                    continue

                # 同步数据
                sync_result = self.sync_symbol_range(
                    symbol, start_date, end_date, frequency
                )

                if sync_result["success_count"] > 0:
                    result["success_count"] += 1
                    result["sync_ranges"][symbol] = {
                        "start_date": str(start_date),
                        "end_date": str(end_date),
                        "sync_count": sync_result["success_count"],
                    }
                else:
                    result["error_count"] += 1

                # 更新进度条
                if progress_bar:
                    progress_bar.update(1)

            except Exception as e:
                logger.error(f"串行同步失败 {symbol}: {e}")
                result["error_count"] += 1
                self.sync_stats["errors"].append(
                    {"symbol": symbol, "frequency": frequency, "error": str(e)}
                )
                # 更新进度条
                if progress_bar:
                    progress_bar.update(1)

        return result

    def _sync_parallel(
        self, symbols: List[str], target_date: date, frequency: str, progress_bar=None
    ) -> Dict[str, Any]:
        """并行同步"""
        result = {
            "success_count": 0,
            "error_count": 0,
            "skipped_count": 0,
            "sync_ranges": {},
        }

        # 分批处理
        symbol_batches = [
            symbols[i : i + self.batch_size]
            for i in range(0, len(symbols), self.batch_size)
        ]

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交任务
            future_to_batch = {
                executor.submit(
                    self._sync_symbol_batch, batch, target_date, frequency
                ): batch
                for batch in symbol_batches
            }

            # 收集结果
            for future in as_completed(future_to_batch):
                batch = future_to_batch[future]
                try:
                    batch_result = future.result()
                    result["success_count"] += batch_result["success_count"]
                    result["error_count"] += batch_result["error_count"]
                    result["skipped_count"] += batch_result["skipped_count"]
                    result["sync_ranges"].update(batch_result["sync_ranges"])

                except Exception as e:
                    logger.error(f"并行同步批次失败: {batch}, 错误: {e}")
                    result["error_count"] += len(batch)

        return result

    def _sync_symbol_batch(
        self, symbols: List[str], target_date: date, frequency: str
    ) -> Dict[str, Any]:
        """同步股票批次"""
        batch_result = {
            "success_count": 0,
            "error_count": 0,
            "skipped_count": 0,
            "sync_ranges": {},
        }

        for symbol in symbols:
            try:
                # 计算同步范围
                start_date, end_date = self.calculate_sync_range(
                    symbol, target_date, frequency
                )

                if start_date is None:
                    batch_result["skipped_count"] += 1
                    continue

                # 同步数据
                sync_result = self.sync_symbol_range(
                    symbol, start_date, end_date, frequency
                )

                if sync_result["success_count"] > 0:
                    batch_result["success_count"] += 1
                    batch_result["sync_ranges"][symbol] = {
                        "start_date": str(start_date),
                        "end_date": str(end_date),
                        "sync_count": sync_result["success_count"],
                    }
                else:
                    batch_result["error_count"] += 1

            except Exception as e:
                logger.error(f"批次同步失败 {symbol}: {e}")
                batch_result["error_count"] += 1

        return batch_result

    def _get_active_symbols(self) -> List[str]:
        """获取活跃股票列表"""
        try:
            sql = """
            SELECT symbol FROM stocks
            WHERE status = 'active'
            ORDER BY symbol
            """
            results = self.db_manager.fetchall(sql)

            if results:
                return [row["symbol"] for row in results]
            else:
                logger.warning("数据库中无活跃股票")
                return []

        except Exception as e:
            logger.error(f"获取活跃股票列表失败: {e}")
            return []

    def _is_trading_day(self, target_date: date) -> bool:
        """检查是否为交易日"""
        try:
            sql = """
            SELECT is_trading FROM trading_calendar
            WHERE date = ? AND market = 'CN'
            """
            result = self.db_manager.fetchone(sql, (str(target_date),))

            if result:
                return bool(result["is_trading"])
            else:
                # 不再使用简化fallback，必须有正确的交易日历数据
                raise RuntimeError(f"交易日历数据缺失，日期: {target_date}")

        except Exception as e:
            logger.error(f"检查交易日失败: {e}")
            # 不再使用简化fallback，必须有正确的交易日历数据
            raise RuntimeError(f"无法获取交易日历数据: {e}")

    def _reset_stats(self):
        """重置同步统计"""
        self.sync_stats = {
            "total_symbols": 0,
            "success_count": 0,
            "error_count": 0,
            "skipped_count": 0,
            "sync_date_ranges": {},
            "errors": [],
        }

    def _update_sync_status(self, target_date: date, stats: Dict[str, Any]):
        """更新同步状态"""
        try:
            # 使用正确的字段名（与数据库表结构匹配）
            sql = """
            INSERT OR REPLACE INTO sync_status
            (symbol, frequency, last_sync_date, last_data_date, status,
             error_message, total_records, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """

            sync_status = "completed" if stats["error_count"] == 0 else "failed"
            error_msg = f"成功={stats['success_count']}, 错误={stats['error_count']}"

            # 为增量同步创建一个汇总记录
            self.db_manager.execute(
                sql,
                (
                    "ALL_SYMBOLS",  # symbol
                    "1d",  # frequency
                    str(target_date),  # last_sync_date
                    str(target_date),  # last_data_date
                    sync_status,  # status
                    error_msg,  # error_message
                    stats["success_count"],  # total_records
                    datetime.now().isoformat(),  # updated_at
                ),
            )

        except Exception as e:
            logger.error(f"更新同步状态失败: {e}")

    def get_sync_stats(self) -> Dict[str, Any]:
        """获取同步统计信息"""
        return self.sync_stats.copy()

    def _sync_pipeline(
        self, symbols: List[str], target_date: date, frequency: str, progress_bar=None
    ) -> Dict[str, Any]:
        """
        流水线同步：下载串行，处理并发

        Args:
            symbols: 股票代码列表
            target_date: 目标日期
            frequency: 频率
            progress_bar: 进度条

        Returns:
            同步结果
        """
        result = {
            "success_count": 0,
            "error_count": 0,
            "skipped_count": 0,
            "sync_ranges": {},
        }

        # 计算需要同步的股票和日期范围
        sync_tasks = []
        for symbol in symbols:
            try:
                start_date, end_date = self.calculate_sync_range(
                    symbol, target_date, frequency
                )

                if start_date is None:
                    result["skipped_count"] += 1
                    if progress_bar:
                        progress_bar.update(1)
                    continue

                sync_tasks.append((symbol, start_date, end_date))

            except Exception as e:
                logger.error(f"计算同步范围失败 {symbol}: {e}")
                result["error_count"] += 1
                if progress_bar:
                    progress_bar.update(1)

        if not sync_tasks:
            return result

        # 使用数据处理引擎的流水线模式
        # 将同步任务转换为处理引擎需要的格式
        task_symbols = [task[0] for task in sync_tasks]

        # 为了简化，这里使用最早的开始日期和目标日期
        min_start_date = min(task[1] for task in sync_tasks)

        try:
            # 调用数据处理引擎的流水线处理
            pipeline_result = self.processing_engine.process_symbols_batch_pipeline(
                symbols=task_symbols,
                start_date=min_start_date,
                end_date=target_date,
                batch_size=5,  # 减少批次大小到5只股票
                max_workers=2,  # 减少处理线程到2个
                progress_bar=progress_bar,  # 传递进度条
            )

            # 转换结果格式
            result["success_count"] = pipeline_result["success_count"]
            result["error_count"] += pipeline_result["error_count"]

            # 为成功的股票创建同步范围记录
            for symbol in pipeline_result["processed_symbols"]:
                # 找到对应的任务
                for task_symbol, start_date, end_date in sync_tasks:
                    if task_symbol == symbol:
                        result["sync_ranges"][symbol] = {
                            "start_date": str(start_date),
                            "end_date": str(end_date),
                            "sync_count": 1,  # 简化处理
                        }
                        break

            # 进度条已经在流水线处理中更新了，这里不需要重复更新

        except Exception as e:
            logger.error(f"流水线同步失败: {e}")
            result["error_count"] += len(sync_tasks)
            # 如果整个流水线失败，更新所有剩余进度
            if progress_bar:
                progress_bar.update(len(task_symbols))

        return result
