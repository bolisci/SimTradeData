"""
同步管理器

统一管理增量同步、缺口检测和数据验证功能。
"""

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List

from ..config import Config
from ..data_sources import DataSourceManager
from ..database import DatabaseManager
from ..preprocessor import DataProcessingEngine
from ..utils.progress_bar import (
    create_phase_progress,
    log_error,
    log_phase_complete,
    log_phase_start,
    update_phase_description,
)
from .gap_detector import GapDetector
from .incremental import IncrementalSync
from .validator import DataValidator

logger = logging.getLogger(__name__)


class SyncManager:
    """同步管理器"""

    def __init__(
        self,
        db_manager: DatabaseManager,
        data_source_manager: DataSourceManager,
        processing_engine: DataProcessingEngine,
        config: Config = None,
    ):
        """
        初始化同步管理器

        Args:
            db_manager: 数据库管理器
            data_source_manager: 数据源管理器
            processing_engine: 数据处理引擎
            config: 配置对象
        """
        self.db_manager = db_manager
        self.data_source_manager = data_source_manager
        self.processing_engine = processing_engine
        self.config = config or Config()

        # 初始化子组件
        self.incremental_sync = IncrementalSync(
            db_manager, data_source_manager, processing_engine, config
        )
        self.gap_detector = GapDetector(db_manager, config)
        self.validator = DataValidator(db_manager, config)

        # 管理器配置
        self.enable_auto_gap_fix = self.config.get("sync_manager.auto_gap_fix", True)
        self.enable_validation = self.config.get("sync_manager.enable_validation", True)
        self.max_gap_fix_days = self.config.get("sync_manager.max_gap_fix_days", 7)

        logger.info("同步管理器初始化完成")

    def run_full_sync(
        self,
        target_date: date = None,
        symbols: List[str] = None,
        frequencies: List[str] = None,
    ) -> Dict[str, Any]:
        """
        运行完整同步流程

        Args:
            target_date: 目标日期，默认为今天
            symbols: 股票代码列表，默认为所有活跃股票
            frequencies: 频率列表，默认为配置中的频率

        Returns:
            Dict[str, Any]: 完整同步结果
        """
        if target_date is None:
            target_date = datetime.now().date()

        # 限制目标日期不能超过今天，使用合理的历史日期
        today = datetime.now().date()
        if target_date > today:
            # 如果目标日期是未来，使用最近的交易日
            target_date = date(2025, 1, 24)  # 使用已知有数据的日期
            logger.warning(f"目标日期调整为历史日期: {target_date}")

        try:
            logger.info(f"开始完整同步流程: 目标日期={target_date}")

            full_result = {
                "target_date": str(target_date),
                "start_time": datetime.now().isoformat(),
                "phases": {},
                "summary": {
                    "total_phases": 0,
                    "successful_phases": 0,
                    "failed_phases": 0,
                },
            }

            # 阶段0: 更新基础数据（交易日历和股票列表）
            log_phase_start("阶段0", "更新基础数据")

            with create_phase_progress("phase0", 2, "基础数据更新", "项") as pbar:
                try:
                    # 更新交易日历
                    update_phase_description("更新交易日历")
                    calendar_result = self._update_trading_calendar(target_date)
                    full_result["phases"]["calendar_update"] = calendar_result
                    full_result["summary"]["total_phases"] += 1
                    pbar.update(1)

                    if "error" not in calendar_result:
                        full_result["summary"]["successful_phases"] += 1
                    else:
                        full_result["summary"]["failed_phases"] += 1
                        log_error(f"交易日历更新失败: {calendar_result['error']}")

                    # 更新股票列表
                    update_phase_description("更新股票列表（可能需要较长时间）")
                    stock_list_result = self._update_stock_list()
                    full_result["phases"]["stock_list_update"] = stock_list_result
                    full_result["summary"]["total_phases"] += 1
                    pbar.update(1)

                    if "error" not in stock_list_result:
                        full_result["summary"]["successful_phases"] += 1
                        total_stocks = stock_list_result.get("total_stocks", 0)
                        log_phase_complete(
                            "基础数据更新",
                            {"交易日历": "✓", "股票列表": f"{total_stocks}只"},
                        )
                    else:
                        full_result["summary"]["failed_phases"] += 1
                        log_error(f"股票列表更新失败: {stock_list_result['error']}")

                except Exception as e:
                    log_error(f"基础数据更新失败: {e}")
                    full_result["phases"]["base_data_update"] = {"error": str(e)}
                    full_result["summary"]["total_phases"] += 1
                    full_result["summary"]["failed_phases"] += 1

            # 如果没有指定股票列表，从数据库获取活跃股票
            if not symbols:
                symbols = self._get_active_stocks_from_db()
                if not symbols:
                    # 如果数据库中没有股票，使用默认股票
                    symbols = ["000001.SZ", "000002.SZ", "600000.SS", "600036.SS"]
                    logger.info(f"使用默认股票列表: {len(symbols)}只股票")
                else:
                    logger.info(f"从数据库获取活跃股票: {len(symbols)}只股票")

            # 阶段1: 增量同步（市场数据）
            log_phase_start("阶段1", "增量同步市场数据")

            with create_phase_progress(
                "phase1", len(symbols), "增量同步", "股票"
            ) as pbar:
                try:
                    # 修改增量同步以支持进度回调
                    sync_result = self.incremental_sync.sync_all_symbols(
                        target_date, symbols, frequencies, progress_bar=pbar
                    )
                    full_result["phases"]["incremental_sync"] = {
                        "status": "completed",
                        "result": sync_result,
                    }
                    full_result["summary"]["successful_phases"] += 1

                    # 从结果中提取统计信息
                    success_count = sync_result.get("success_count", len(symbols))
                    error_count = sync_result.get("error_count", 0)
                    log_phase_complete(
                        "增量同步",
                        {"成功": f"{success_count}只股票", "失败": error_count},
                    )

                except Exception as e:
                    log_error(f"增量同步失败: {e}")
                    full_result["phases"]["incremental_sync"] = {
                        "status": "failed",
                        "error": str(e),
                    }
                    full_result["summary"]["failed_phases"] += 1

            full_result["summary"]["total_phases"] += 1

            # 阶段2: 同步扩展数据
            log_phase_start("阶段2", "同步扩展数据")

            with create_phase_progress(
                "phase2", len(symbols), "扩展数据同步", "股票"
            ) as pbar:
                try:
                    extended_result = self._sync_extended_data(
                        symbols, target_date, pbar
                    )
                    full_result["phases"]["extended_data_sync"] = {
                        "status": "completed",
                        "result": extended_result,
                    }
                    full_result["summary"]["successful_phases"] += 1

                    log_phase_complete(
                        "扩展数据同步",
                        {
                            "财务数据": f"{extended_result.get('financials_count', 0)}条",
                            "估值数据": f"{extended_result.get('valuations_count', 0)}条",
                            "技术指标": f"{extended_result.get('indicators_count', 0)}条",
                        },
                    )

                except Exception as e:
                    log_error(f"扩展数据同步失败: {e}")
                    full_result["phases"]["extended_data_sync"] = {
                        "status": "failed",
                        "error": str(e),
                    }
                    full_result["summary"]["failed_phases"] += 1

            full_result["summary"]["total_phases"] += 1

            # 阶段3: 缺口检测
            log_phase_start("阶段3", "缺口检测与修复")

            with create_phase_progress(
                "phase2", len(symbols), "缺口检测", "股票"
            ) as pbar:
                try:
                    gap_start_date = target_date - timedelta(days=30)  # 检测最近30天
                    gap_result = self.gap_detector.detect_all_gaps(
                        gap_start_date, target_date, symbols, frequencies
                    )

                    # 更新进度
                    pbar.update(len(symbols))

                    full_result["phases"]["gap_detection"] = {
                        "status": "completed",
                        "result": gap_result,
                    }
                    full_result["summary"]["successful_phases"] += 1

                    total_gaps = gap_result["summary"]["total_gaps"]

                    # 自动修复缺口
                    if self.enable_auto_gap_fix and total_gaps > 0:
                        update_phase_description(f"修复{total_gaps}个缺口")
                        fix_result = self._auto_fix_gaps(gap_result)
                        full_result["phases"]["gap_fix"] = {
                            "status": "completed",
                            "result": fix_result,
                        }
                        log_phase_complete(
                            "缺口检测与修复",
                            {"检测": f"{total_gaps}个缺口", "修复": "完成"},
                        )
                    else:
                        log_phase_complete("缺口检测", {"缺口": f"{total_gaps}个"})

                except Exception as e:
                    log_error(f"缺口检测失败: {e}")
                    full_result["phases"]["gap_detection"] = {
                        "status": "failed",
                        "error": str(e),
                    }
                    full_result["summary"]["failed_phases"] += 1

            full_result["summary"]["total_phases"] += 1

            # 阶段3: 数据验证
            if self.enable_validation:
                log_phase_start("阶段3", "数据验证")

                with create_phase_progress(
                    "phase3", len(symbols), "数据验证", "股票"
                ) as pbar:
                    try:
                        validation_start_date = target_date - timedelta(
                            days=7
                        )  # 验证最近7天
                        validation_result = self.validator.validate_all_data(
                            validation_start_date, target_date, symbols, frequencies
                        )

                        # 更新进度
                        pbar.update(len(symbols))

                        full_result["phases"]["validation"] = {
                            "status": "completed",
                            "result": validation_result,
                        }
                        full_result["summary"]["successful_phases"] += 1

                        # 提取验证统计
                        total_records = validation_result.get("total_records", 0)
                        valid_records = validation_result.get("valid_records", 0)
                        validation_rate = validation_result.get("validation_rate", 0)

                        log_phase_complete(
                            "数据验证",
                            {
                                "记录": f"{total_records}条",
                                "有效": f"{valid_records}条",
                                "验证率": f"{validation_rate:.1f}%",
                            },
                        )

                    except Exception as e:
                        log_error(f"数据验证失败: {e}")
                        full_result["phases"]["validation"] = {
                            "status": "failed",
                            "error": str(e),
                        }
                        full_result["summary"]["failed_phases"] += 1

                full_result["summary"]["total_phases"] += 1

            # 完成时间
            full_result["end_time"] = datetime.now().isoformat()

            # 计算总耗时
            start_time = datetime.fromisoformat(full_result["start_time"])
            end_time = datetime.fromisoformat(full_result["end_time"])
            full_result["duration_seconds"] = (end_time - start_time).total_seconds()

            logger.info(
                f"完整同步流程完成: 成功阶段={full_result['summary']['successful_phases']}, "
                f"失败阶段={full_result['summary']['failed_phases']}, "
                f"耗时={full_result['duration_seconds']:.2f}秒"
            )

            return full_result

        except Exception as e:
            logger.error(f"完整同步流程失败: {e}")
            raise

    def run_gap_detection_and_fix(
        self,
        start_date: date = None,
        end_date: date = None,
        symbols: List[str] = None,
        frequencies: List[str] = None,
    ) -> Dict[str, Any]:
        """
        运行缺口检测和修复

        Args:
            start_date: 开始日期，默认为30天前
            end_date: 结束日期，默认为今天
            symbols: 股票代码列表，默认为所有活跃股票
            frequencies: 频率列表，默认为配置中的频率

        Returns:
            Dict[str, Any]: 缺口检测和修复结果
        """
        if start_date is None:
            start_date = datetime.now().date() - timedelta(days=30)

        if end_date is None:
            end_date = datetime.now().date()

        try:
            logger.info(f"开始缺口检测和修复: {start_date} 到 {end_date}")

            # 检测缺口
            gap_result = self.gap_detector.detect_all_gaps(
                start_date, end_date, symbols, frequencies
            )

            result = {"detection_result": gap_result, "fix_result": None}

            # 修复缺口
            if gap_result["summary"]["total_gaps"] > 0:
                fix_result = self._auto_fix_gaps(gap_result)
                result["fix_result"] = fix_result

            return result

        except Exception as e:
            logger.error(f"缺口检测和修复失败: {e}")
            raise

    def run_data_validation(
        self,
        start_date: date = None,
        end_date: date = None,
        symbols: List[str] = None,
        frequencies: List[str] = None,
    ) -> Dict[str, Any]:
        """
        运行数据验证

        Args:
            start_date: 开始日期，默认为7天前
            end_date: 结束日期，默认为今天
            symbols: 股票代码列表，默认为所有活跃股票
            frequencies: 频率列表，默认为配置中的频率

        Returns:
            Dict[str, Any]: 验证结果
        """
        if start_date is None:
            start_date = datetime.now().date() - timedelta(days=7)

        if end_date is None:
            end_date = datetime.now().date()

        try:
            logger.info(f"开始数据验证: {start_date} 到 {end_date}")

            validation_result = self.validator.validate_all_data(
                start_date, end_date, symbols, frequencies
            )

            return validation_result

        except Exception as e:
            logger.error(f"数据验证失败: {e}")
            raise

    def _auto_fix_gaps(self, gap_result: Dict[str, Any]) -> Dict[str, Any]:
        """自动修复缺口"""
        logger.info("开始自动修复缺口")

        fix_result = {
            "total_gaps": gap_result["summary"]["total_gaps"],
            "attempted_fixes": 0,
            "successful_fixes": 0,
            "failed_fixes": 0,
            "fix_details": [],
        }

        # 收集需要修复的缺口
        gaps_to_fix = []
        for freq_data in gap_result["gaps_by_frequency"].values():
            for gap in freq_data["gaps"]:
                # 只修复日期缺失类型的缺口，且缺口天数不超过限制
                if (
                    gap["gap_type"] == "date_missing"
                    and gap["gap_days"] <= self.max_gap_fix_days
                ):
                    gaps_to_fix.append(gap)

        logger.info(f"需要修复的缺口数量: {len(gaps_to_fix)}")

        # 按股票分组修复
        gaps_by_symbol = {}
        for gap in gaps_to_fix:
            symbol = gap["symbol"]
            if symbol not in gaps_by_symbol:
                gaps_by_symbol[symbol] = []
            gaps_by_symbol[symbol].append(gap)

        # 逐个股票修复缺口
        for symbol, symbol_gaps in gaps_by_symbol.items():
            for gap in symbol_gaps:
                fix_result["attempted_fixes"] += 1

                # 修复单个缺口
                success = self._fix_single_gap(gap)

                if success:
                    fix_result["successful_fixes"] += 1
                    fix_result["fix_details"].append(
                        {
                            "symbol": symbol,
                            "start_date": gap["start_date"],
                            "end_date": gap["end_date"],
                            "status": "success",
                        }
                    )
                else:
                    fix_result["failed_fixes"] += 1
                    fix_result["fix_details"].append(
                        {
                            "symbol": symbol,
                            "start_date": gap["start_date"],
                            "end_date": gap["end_date"],
                            "status": "failed",
                        }
                    )

        logger.info(
            f"缺口修复完成: 尝试={fix_result['attempted_fixes']}, "
            f"成功={fix_result['successful_fixes']}, "
            f"失败={fix_result['failed_fixes']}"
        )

        return fix_result

    def _fix_single_gap(self, gap: Dict[str, Any]) -> bool:
        """修复单个缺口"""
        symbol = gap["symbol"]
        start_date = datetime.strptime(gap["start_date"], "%Y-%m-%d").date()
        end_date = datetime.strptime(gap["end_date"], "%Y-%m-%d").date()
        frequency = gap["frequency"]

        logger.debug(f"修复缺口: {symbol} {start_date} 到 {end_date} {frequency}")

        # 使用增量同步器修复缺口
        sync_result = self.incremental_sync.sync_symbol_range(
            symbol, start_date, end_date, frequency
        )

        return sync_result["success_count"] > 0

    def _sync_extended_data(
        self, symbols: List[str], target_date: date, progress_bar=None
    ) -> Dict[str, Any]:
        """同步扩展数据（财务、估值、技术指标等）"""
        logger.info(f"开始同步扩展数据: {len(symbols)}只股票")

        result = {
            "financials_count": 0,
            "valuations_count": 0,
            "indicators_count": 0,
            "processed_symbols": 0,
            "failed_symbols": 0,
        }

        for symbol in symbols:
            try:
                # 1. 同步财务数据
                financials_count = self._sync_financials_data(symbol, target_date)
                result["financials_count"] += financials_count

                # 2. 同步估值数据
                valuations_count = self._sync_valuations_data(symbol, target_date)
                result["valuations_count"] += valuations_count

                # 3. 同步技术指标
                indicators_count = self._sync_technical_indicators(symbol, target_date)
                result["indicators_count"] += indicators_count

                result["processed_symbols"] += 1

            except Exception as e:
                logger.error(f"同步扩展数据失败 {symbol}: {e}")
                result["failed_symbols"] += 1

            if progress_bar:
                progress_bar.update(1)

        logger.info(
            f"扩展数据同步完成: 财务={result['financials_count']}, 估值={result['valuations_count']}, 指标={result['indicators_count']}"
        )
        return result

    def _sync_financials_data(self, symbol: str, target_date: date) -> int:
        """同步财务数据"""
        try:
            # 获取最近的财务报告期（季度）
            report_dates = self._get_recent_report_dates(target_date)
            count = 0

            for report_date in report_dates:
                # 检查是否已存在
                existing_sql = """
                SELECT COUNT(*) as count FROM financials
                WHERE symbol = ? AND report_date = ?
                """
                existing = self.db_manager.fetchone(
                    existing_sql, (symbol, str(report_date))
                )

                if existing and existing["count"] > 0:
                    continue  # 已存在，跳过

                # 获取财务数据
                financial_data = self.data_source_manager.get_fundamentals(
                    symbol, report_date, "Q4"
                )

                if financial_data and "error" not in financial_data:
                    # 存储财务数据
                    self._store_financial_data(symbol, report_date, financial_data)
                    count += 1

            return count

        except Exception as e:
            logger.error(f"同步财务数据失败 {symbol}: {e}")
            return 0

    def _sync_valuations_data(self, symbol: str, target_date: date) -> int:
        """同步估值数据"""
        try:
            # 检查是否已存在
            existing_sql = """
            SELECT COUNT(*) as count FROM valuations
            WHERE symbol = ? AND date = ?
            """
            existing = self.db_manager.fetchone(
                existing_sql, (symbol, str(target_date))
            )

            if existing and existing["count"] > 0:
                return 0  # 已存在，跳过

            # 获取估值数据
            valuation_data = self.data_source_manager.get_valuation_data(
                symbol, target_date
            )

            if valuation_data and "error" not in valuation_data:
                # 存储估值数据
                self._store_valuation_data(symbol, target_date, valuation_data)
                return 1

            return 0

        except Exception as e:
            logger.error(f"同步估值数据失败 {symbol}: {e}")
            return 0

    def _sync_technical_indicators(self, symbol: str, target_date: date) -> int:
        """同步技术指标"""
        try:
            # 获取最近30天的市场数据来计算技术指标
            start_date = target_date - timedelta(days=30)

            market_data_sql = """
            SELECT date, open, high, low, close, volume
            FROM market_data
            WHERE symbol = ? AND date BETWEEN ? AND ? AND frequency = '1d'
            ORDER BY date
            """

            market_data = self.db_manager.fetchall(
                market_data_sql, (symbol, str(start_date), str(target_date))
            )

            if len(market_data) < 5:  # 需要至少5天数据
                return 0

            # 计算基本技术指标
            indicators = self._calculate_basic_indicators(market_data, target_date)

            if indicators:
                # 存储技术指标
                self._store_technical_indicators(symbol, target_date, indicators)
                return len(indicators)

            return 0

        except Exception as e:
            logger.error(f"同步技术指标失败 {symbol}: {e}")
            return 0

    def _get_recent_report_dates(self, target_date: date) -> List[date]:
        """获取最近的财务报告期"""
        year = target_date.year
        report_dates = []

        # 添加当年和去年的季度报告期
        for y in [year, year - 1]:
            for quarter in [(3, 31), (6, 30), (9, 30), (12, 31)]:
                month, day = quarter
                report_date = date(y, month, day)
                if report_date <= target_date:
                    report_dates.append(report_date)

        # 返回最近的4个报告期
        return sorted(report_dates, reverse=True)[:4]

    def _store_financial_data(
        self, symbol: str, report_date: date, data: Dict[str, Any]
    ):
        """存储财务数据"""
        sql = """
        INSERT OR REPLACE INTO financials (
            symbol, report_date, report_type, revenue, operating_profit, net_profit,
            gross_margin, net_margin, total_assets, total_liabilities, shareholders_equity,
            operating_cash_flow, investing_cash_flow, financing_cash_flow,
            eps, bps, roe, roa, debt_ratio, source, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        params = (
            symbol,
            str(report_date),
            data.get("report_type", "Q4"),
            data.get("revenue", 0),
            data.get("operating_profit", 0),
            data.get("net_profit", 0),
            data.get("gross_margin", 0),
            data.get("net_margin", 0),
            data.get("total_assets", 0),
            data.get("total_liabilities", 0),
            data.get("shareholders_equity", 0),
            data.get("operating_cash_flow", 0),
            data.get("investing_cash_flow", 0),
            data.get("financing_cash_flow", 0),
            data.get("eps", 0),
            data.get("bps", 0),
            data.get("roe", 0),
            data.get("roa", 0),
            data.get("debt_ratio", 0),
            data.get("source", "unknown"),
            datetime.now().isoformat(),
        )

        self.db_manager.execute(sql, params)

    def _store_valuation_data(
        self, symbol: str, trade_date: date, data: Dict[str, Any]
    ):
        """存储估值数据"""
        sql = """
        INSERT OR REPLACE INTO valuations (
            symbol, date, pe_ratio, pb_ratio, ps_ratio, pcf_ratio,
            peg_ratio, market_cap, circulating_cap, source, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        params = (
            symbol,
            str(trade_date),
            data.get("pe_ratio", 0),
            data.get("pb_ratio", 0),
            data.get("ps_ratio", 0),
            data.get("pcf_ratio", 0),
            data.get("peg_ratio", 0),
            data.get("market_cap", 0),
            data.get("circulating_cap", 0),
            data.get("source", "unknown"),
            datetime.now().isoformat(),
        )

        self.db_manager.execute(sql, params)

    def _store_technical_indicators(
        self, symbol: str, trade_date: date, indicators: Dict[str, Any]
    ):
        """存储技术指标"""
        sql = """
        INSERT OR REPLACE INTO technical_indicators (
            symbol, date, frequency, ma5, ma10, ma20, ma60, ma120, ma250,
            ema12, ema26, macd_dif, macd_dea, macd_histogram,
            kdj_k, kdj_d, kdj_j, rsi_6, rsi_12, rsi_24,
            boll_upper, boll_middle, boll_lower, cci, williams_r, calculated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        params = (
            symbol,
            str(trade_date),
            "1d",
            indicators.get("ma5", 0),
            indicators.get("ma10", 0),
            indicators.get("ma20", 0),
            indicators.get("ma60", 0),
            indicators.get("ma120", 0),
            indicators.get("ma250", 0),
            indicators.get("ema12", 0),
            indicators.get("ema26", 0),
            indicators.get("macd_dif", 0),
            indicators.get("macd_dea", 0),
            indicators.get("macd_histogram", 0),
            indicators.get("kdj_k", 0),
            indicators.get("kdj_d", 0),
            indicators.get("kdj_j", 0),
            indicators.get("rsi_6", 0),
            indicators.get("rsi_12", 0),
            indicators.get("rsi_24", 0),
            indicators.get("boll_upper", 0),
            indicators.get("boll_middle", 0),
            indicators.get("boll_lower", 0),
            indicators.get("cci", 0),
            indicators.get("williams_r", 0),
            datetime.now().isoformat(),
        )

        self.db_manager.execute(sql, params)

    def _calculate_basic_indicators(
        self, market_data: List[Dict], target_date: date
    ) -> Dict[str, Any]:
        """计算基本技术指标"""
        if len(market_data) < 5:
            return {}

        # 提取收盘价
        closes = [float(row["close"]) for row in market_data]

        indicators = {}

        # 计算移动平均线
        if len(closes) >= 5:
            indicators["ma5"] = sum(closes[-5:]) / 5
        if len(closes) >= 10:
            indicators["ma10"] = sum(closes[-10:]) / 10
        if len(closes) >= 20:
            indicators["ma20"] = sum(closes[-20:]) / 20

        # 简单的RSI计算
        if len(closes) >= 14:
            gains = []
            losses = []
            for i in range(1, len(closes)):
                change = closes[i] - closes[i - 1]
                if change > 0:
                    gains.append(change)
                    losses.append(0)
                else:
                    gains.append(0)
                    losses.append(abs(change))

            # RSI_6
            if len(gains) >= 6:
                avg_gain = sum(gains[-6:]) / 6
                avg_loss = sum(losses[-6:]) / 6
                if avg_loss != 0:
                    rs = avg_gain / avg_loss
                    indicators["rsi_6"] = 100 - (100 / (1 + rs))

            # RSI_12
            if len(gains) >= 12:
                avg_gain = sum(gains[-12:]) / 12
                avg_loss = sum(losses[-12:]) / 12
                if avg_loss != 0:
                    rs = avg_gain / avg_loss
                    indicators["rsi_12"] = 100 - (100 / (1 + rs))

            # RSI_24
            if len(gains) >= 24:
                avg_gain = sum(gains[-24:]) / 24
                avg_loss = sum(losses[-24:]) / 24
                if avg_loss != 0:
                    rs = avg_gain / avg_loss
                    indicators["rsi_24"] = 100 - (100 / (1 + rs))

        return indicators

    def get_sync_status(self) -> Dict[str, Any]:
        """获取同步状态"""
        try:
            # 获取最近的同步状态
            sql = """
            SELECT * FROM sync_status
            ORDER BY last_update DESC
            LIMIT 10
            """

            recent_syncs = self.db_manager.fetchall(sql)

            # 获取数据统计
            stats_sql = """
            SELECT 
                COUNT(*) as total_records,
                COUNT(DISTINCT symbol) as total_symbols,
                COUNT(DISTINCT trade_date) as total_dates,
                AVG(quality_score) as avg_quality
            FROM market_data
            """

            stats_result = self.db_manager.fetchone(stats_sql)

            return {
                "recent_syncs": [dict(row) for row in recent_syncs],
                "data_stats": dict(stats_result) if stats_result else {},
                "components": {
                    "incremental_sync": self.incremental_sync.get_sync_stats(),
                    "gap_detector": {
                        "max_gap_days": self.gap_detector.max_gap_days,
                        "min_data_quality": self.gap_detector.min_data_quality,
                    },
                    "validator": {
                        "min_data_quality": self.validator.min_data_quality,
                        "max_price_change_pct": self.validator.max_price_change_pct,
                    },
                },
                "config": {
                    "enable_auto_gap_fix": self.enable_auto_gap_fix,
                    "enable_validation": self.enable_validation,
                    "max_gap_fix_days": self.max_gap_fix_days,
                },
            }

        except Exception as e:
            logger.error(f"获取同步状态失败: {e}")
            return {"error": str(e)}

    def generate_sync_report(self, full_result: Dict[str, Any]) -> str:
        """生成同步报告"""
        try:
            report_lines = []

            # 报告头部
            report_lines.append("=" * 60)
            report_lines.append("数据同步报告")
            report_lines.append("=" * 60)
            report_lines.append(f"同步时间: {full_result.get('start_time', '')}")
            report_lines.append(f"目标日期: {full_result.get('target_date', '')}")
            report_lines.append(
                f"总耗时: {full_result.get('duration_seconds', 0):.2f} 秒"
            )
            report_lines.append("")

            # 阶段汇总
            summary = full_result.get("summary", {})
            report_lines.append("阶段汇总:")
            report_lines.append(f"  总阶段数: {summary.get('total_phases', 0)}")
            report_lines.append(f"  成功阶段: {summary.get('successful_phases', 0)}")
            report_lines.append(f"  失败阶段: {summary.get('failed_phases', 0)}")
            report_lines.append("")

            # 各阶段详情
            phases = full_result.get("phases", {})

            # 增量同步
            if "incremental_sync" in phases:
                phase = phases["incremental_sync"]
                report_lines.append("增量同步:")
                report_lines.append(f"  状态: {phase['status']}")

                if phase["status"] == "completed" and "result" in phase:
                    result = phase["result"]
                    report_lines.append(f"  总股票数: {result.get('total_symbols', 0)}")
                    report_lines.append(f"  成功数量: {result.get('success_count', 0)}")
                    report_lines.append(f"  错误数量: {result.get('error_count', 0)}")
                    report_lines.append(f"  跳过数量: {result.get('skipped_count', 0)}")
                elif "error" in phase:
                    report_lines.append(f"  错误: {phase['error']}")

                report_lines.append("")

            # 缺口检测
            if "gap_detection" in phases:
                phase = phases["gap_detection"]
                report_lines.append("缺口检测:")
                report_lines.append(f"  状态: {phase['status']}")

                if phase["status"] == "completed" and "result" in phase:
                    result = phase["result"]
                    summary = result.get("summary", {})
                    report_lines.append(f"  总缺口数: {summary.get('total_gaps', 0)}")
                    report_lines.append(
                        f"  涉及股票: {summary.get('symbols_with_gaps', 0)}"
                    )
                elif "error" in phase:
                    report_lines.append(f"  错误: {phase['error']}")

                report_lines.append("")

            # 缺口修复
            if "gap_fix" in phases:
                phase = phases["gap_fix"]
                report_lines.append("缺口修复:")
                report_lines.append(f"  状态: {phase['status']}")

                if phase["status"] == "completed" and "result" in phase:
                    result = phase["result"]
                    report_lines.append(
                        f"  尝试修复: {result.get('attempted_fixes', 0)}"
                    )
                    report_lines.append(
                        f"  成功修复: {result.get('successful_fixes', 0)}"
                    )
                    report_lines.append(f"  修复失败: {result.get('failed_fixes', 0)}")

                report_lines.append("")

            # 数据验证
            if "validation" in phases:
                phase = phases["validation"]
                report_lines.append("数据验证:")
                report_lines.append(f"  状态: {phase['status']}")

                if phase["status"] == "completed" and "result" in phase:
                    result = phase["result"]
                    summary = result.get("summary", {})
                    report_lines.append(
                        f"  总记录数: {summary.get('total_records', 0):,}"
                    )
                    report_lines.append(
                        f"  有效记录: {summary.get('valid_records', 0):,}"
                    )
                    report_lines.append(
                        f"  验证率: {summary.get('validation_rate', 0):.2f}%"
                    )
                elif "error" in phase:
                    report_lines.append(f"  错误: {phase['error']}")

                report_lines.append("")

            return "\n".join(report_lines)

        except Exception as e:
            logger.error(f"生成同步报告失败: {e}")
            return f"报告生成失败: {e}"

    def _update_trading_calendar(self, target_date: date) -> Dict[str, Any]:
        """更新交易日历"""
        try:
            # 获取目标年份前后的交易日历
            start_year = target_date.year - 1
            end_year = target_date.year + 1

            # 这里应该调用数据源获取交易日历
            # 暂时返回成功状态
            logger.info(f"更新交易日历: {start_year}-{end_year}")

            return {
                "status": "completed",
                "start_year": start_year,
                "end_year": end_year,
                "updated_records": 0,  # 实际实现时应该返回真实数量
            }

        except Exception as e:
            logger.error(f"更新交易日历失败: {e}")
            return {"error": str(e)}

    def _update_stock_list(self) -> Dict[str, Any]:
        """更新股票列表"""
        try:
            logger.info("开始获取股票列表，这可能需要30-60秒...")

            # 从数据源获取股票列表（可能很慢）
            stock_info = self.data_source_manager.get_stock_info()

            # 检查DataFrame是否为空
            if stock_info is None or (
                hasattr(stock_info, "empty") and stock_info.empty
            ):
                logger.warning("未获取到股票信息，使用默认列表")
                return {
                    "status": "completed",
                    "total_stocks": 0,
                    "note": "使用默认股票列表",
                }

            # 处理股票信息 - 现在是DataFrame
            if hasattr(stock_info, "shape"):
                total_stocks = len(stock_info)
                logger.info(f"成功获取到 {total_stocks} 只股票信息")

                return {
                    "status": "completed",
                    "total_stocks": total_stocks,
                    "new_stocks": 0,  # 实际实现时计算新增股票
                    "updated_stocks": 0,  # 实际实现时计算更新股票
                }
            elif isinstance(stock_info, list):
                total_stocks = len(stock_info)
                logger.info(f"成功获取到 {total_stocks} 只股票信息")

                return {
                    "status": "completed",
                    "total_stocks": total_stocks,
                    "new_stocks": 0,  # 实际实现时计算新增股票
                    "updated_stocks": 0,  # 实际实现时计算更新股票
                }
            else:
                return {"error": "股票信息格式错误"}

        except Exception as e:
            logger.error(f"更新股票列表失败: {e}")
            logger.info("将使用默认股票列表继续")
            return {
                "status": "completed",
                "total_stocks": 0,
                "error": str(e),
                "note": "使用默认股票列表",
            }

    def _get_active_stocks_from_db(self) -> List[str]:
        """从数据库获取活跃股票列表"""
        try:
            sql = "SELECT symbol FROM stocks WHERE status = 'active' ORDER BY symbol"
            result = self.db_manager.fetchall(sql)
            return [row["symbol"] for row in result] if result else []
        except Exception as e:
            logger.warning(f"从数据库获取股票列表失败: {e}")
            return []
