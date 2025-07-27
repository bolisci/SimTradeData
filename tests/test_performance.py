"""
测试性能优化模块

验证查询优化器、缓存管理器、并发处理器和性能监控器功能。
"""

import logging
import time
from unittest.mock import Mock, patch

import pytest

from simtradedata.config import Config
from simtradedata.database import DatabaseManager
from simtradedata.performance import (
    CacheManager,
    ConcurrentProcessor,
    PerformanceMonitor,
    QueryOptimizer,
)
from simtradedata.performance.concurrent_processor import TaskPriority

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestQueryOptimizer:
    """测试查询优化器"""

    @pytest.fixture
    def mock_db_manager(self):
        """模拟数据库管理器"""
        db_manager = Mock(spec=DatabaseManager)

        # 模拟查询结果
        db_manager.fetchall.return_value = [
            {"symbol": "000001.SZ", "close": 10.5, "trade_date": "2024-01-20"}
        ]

        return db_manager

    def test_initialization(self, mock_db_manager):
        """测试初始化"""
        config = Config()
        optimizer = QueryOptimizer(mock_db_manager, config)

        assert optimizer.db_manager is mock_db_manager
        assert optimizer.config is config
        assert optimizer.enable_query_cache == True
        assert len(optimizer.query_patterns) > 0

        logger.info("✅ 查询优化器初始化测试通过")

    def test_optimize_query(self, mock_db_manager):
        """测试查询优化"""
        optimizer = QueryOptimizer(mock_db_manager)

        # 测试基本查询优化
        sql = "SELECT * FROM daily_data WHERE symbol = '000001.SZ'"
        optimized_sql, params = optimizer.optimize_query(sql, ())

        assert "LIMIT" in optimized_sql
        assert params == ()

        logger.info("✅ 查询优化测试通过")

    def test_execute_with_cache(self, mock_db_manager):
        """测试带缓存的查询执行"""
        optimizer = QueryOptimizer(mock_db_manager)

        sql = "SELECT * FROM daily_data WHERE symbol = ?"
        params = ("000001.SZ",)

        # 第一次查询（缓存未命中）
        result1 = optimizer.execute_with_cache(sql, params)
        assert result1 is not None
        assert optimizer.cache_stats["misses"] == 1

        # 第二次查询（缓存命中）
        result2 = optimizer.execute_with_cache(sql, params)
        assert result2 == result1
        assert optimizer.cache_stats["hits"] == 1

        logger.info("✅ 缓存查询执行测试通过")

    def test_suggest_indexes(self, mock_db_manager):
        """测试索引建议"""
        optimizer = QueryOptimizer(mock_db_manager)

        # 获取索引建议
        suggestions = optimizer.suggest_indexes("daily_data")

        assert len(suggestions) > 0
        assert all("table" in s for s in suggestions)
        assert all("columns" in s for s in suggestions)

        logger.info("✅ 索引建议测试通过")

    def test_get_optimizer_stats(self, mock_db_manager):
        """测试获取优化器统计"""
        optimizer = QueryOptimizer(mock_db_manager)

        stats = optimizer.get_optimizer_stats()

        assert "optimizer_name" in stats
        assert "cache_stats" in stats
        assert "optimization_features" in stats

        logger.info("✅ 优化器统计测试通过")


class TestCacheManager:
    """测试缓存管理器"""

    def test_initialization(self):
        """测试初始化"""
        config = Config()
        cache_manager = CacheManager(config)

        assert cache_manager.config is config
        assert cache_manager.enable_l1_cache == True
        assert cache_manager.l1_cache is not None
        assert len(cache_manager.cache_strategies) > 0

        logger.info("✅ 缓存管理器初始化测试通过")

    def test_cache_operations(self):
        """测试缓存操作"""
        cache_manager = CacheManager()

        # 测试设置和获取
        key = "test_key"
        value = {"data": "test_value"}
        data_type = "test_data"

        # 设置缓存
        success = cache_manager.set(key, value, data_type)
        assert success == True

        # 获取缓存
        cached_value = cache_manager.get(key, data_type)
        assert cached_value == value

        # 检查存在性
        exists = cache_manager.exists(key, data_type)
        assert exists == True

        # 删除缓存
        deleted = cache_manager.delete(key, data_type)
        assert deleted == True

        # 验证删除
        cached_value = cache_manager.get(key, data_type)
        assert cached_value is None

        logger.info("✅ 缓存操作测试通过")

    def test_cache_strategies(self):
        """测试缓存策略"""
        cache_manager = CacheManager()

        # 测试不同数据类型的缓存策略
        cache_manager.set("key1", "value1", "stock_info")
        cache_manager.set("key2", "value2", "daily_data")
        cache_manager.set("key3", "value3", "realtime_data")

        # 验证缓存策略生效
        strategies = cache_manager.get_cache_strategies()
        assert "stock_info" in strategies
        assert "daily_data" in strategies
        assert "realtime_data" in strategies

        logger.info("✅ 缓存策略测试通过")

    def test_cache_stats(self):
        """测试缓存统计"""
        cache_manager = CacheManager()

        # 执行一些缓存操作
        cache_manager.set("key1", "value1")
        cache_manager.get("key1")
        cache_manager.get("nonexistent_key")

        # 获取统计信息
        stats = cache_manager.get_cache_stats()

        assert "cache_manager" in stats
        assert "l1_cache" in stats
        assert "operations" in stats
        assert stats["operations"]["sets"] > 0

        logger.info("✅ 缓存统计测试通过")


class TestConcurrentProcessor:
    """测试并发处理器"""

    def test_initialization(self):
        """测试初始化"""
        config = Config()
        processor = ConcurrentProcessor(config)

        assert processor.config is config
        assert processor.max_workers > 0
        assert processor.running == True
        assert len(processor.worker_threads) > 0

        logger.info("✅ 并发处理器初始化测试通过")

    def test_submit_task(self):
        """测试提交任务"""
        processor = ConcurrentProcessor()

        def test_func(x, y):
            return x + y

        # 提交任务
        task_id = processor.submit_task(test_func, 1, 2)
        assert task_id is not None

        # 获取结果
        result = processor.get_result(task_id, timeout=5)
        assert result is not None
        assert result.success == True
        assert result.result == 3

        logger.info("✅ 任务提交测试通过")

    def test_batch_tasks(self):
        """测试批量任务"""
        processor = ConcurrentProcessor()

        def square(x):
            return x * x

        # 批量提交任务
        tasks = [{"func": square, "args": (i,)} for i in range(5)]

        task_ids = processor.submit_batch_tasks(tasks)
        assert len(task_ids) == 5

        # 批量获取结果
        results = processor.get_batch_results(task_ids, timeout=5)
        assert len(results) == 5

        # 验证结果
        for i, task_id in enumerate(task_ids):
            if task_id in results:
                result = results[task_id]
                assert result.success == True
                assert result.result == i * i

        logger.info("✅ 批量任务测试通过")

    def test_parallel_execution(self):
        """测试并行执行"""
        processor = ConcurrentProcessor()

        def multiply(x, y):
            time.sleep(0.1)  # 模拟耗时操作
            return x * y

        # 并行执行
        args_list = [(i, 2) for i in range(5)]
        results = processor.execute_parallel(multiply, args_list)

        assert len(results) == 5
        # 验证结果（并行执行结果顺序可能不同）
        expected_results = {i * 2 for i in range(5)}
        actual_results = {result for result in results if result is not None}
        assert actual_results == expected_results

        logger.info("✅ 并行执行测试通过")

    def test_task_priority(self):
        """测试任务优先级"""
        processor = ConcurrentProcessor()

        def test_func(value):
            return value

        # 提交不同优先级的任务
        low_task = processor.submit_task(test_func, "low", priority=TaskPriority.LOW)
        high_task = processor.submit_task(test_func, "high", priority=TaskPriority.HIGH)

        # 获取结果
        low_result = processor.get_result(low_task, timeout=5)
        high_result = processor.get_result(high_task, timeout=5)

        assert low_result.success == True
        assert high_result.success == True

        logger.info("✅ 任务优先级测试通过")

    def test_processor_stats(self):
        """测试处理器统计"""
        processor = ConcurrentProcessor()

        stats = processor.get_stats()

        assert "processor_name" in stats
        assert "max_workers" in stats
        assert "features" in stats
        assert stats["running"] == True

        logger.info("✅ 处理器统计测试通过")


class TestPerformanceMonitor:
    """测试性能监控器"""

    def test_initialization(self):
        """测试初始化"""
        config = Config()
        config.set("performance_monitor.enable_monitoring", False)  # 禁用自动监控

        monitor = PerformanceMonitor(config)

        assert monitor.config is config
        assert monitor.enable_monitoring == False
        assert len(monitor.thresholds) > 0

        logger.info("✅ 性能监控器初始化测试通过")

    @patch("psutil.cpu_percent")
    @patch("psutil.virtual_memory")
    @patch("psutil.disk_usage")
    def test_collect_system_metrics(self, mock_disk, mock_memory, mock_cpu):
        """测试收集系统指标"""
        # 模拟系统指标
        mock_cpu.return_value = 50.0
        mock_memory.return_value = Mock(percent=60.0, used=8 * 1024**3)
        mock_disk.return_value = Mock(used=100 * 1024**3, total=500 * 1024**3)

        config = Config()
        config.set("performance_monitor.enable_monitoring", False)
        monitor = PerformanceMonitor(config)

        metrics = monitor.collect_system_metrics()

        assert "cpu_usage" in metrics
        assert "memory_usage" in metrics
        assert "disk_usage" in metrics
        assert metrics["cpu_usage"].value == 50.0

        logger.info("✅ 系统指标收集测试通过")

    def test_record_custom_metrics(self):
        """测试记录自定义指标"""
        config = Config()
        config.set("performance_monitor.enable_monitoring", False)
        monitor = PerformanceMonitor(config)

        # 记录自定义指标
        monitor.record_metric("test_metric", 100.0, "count")
        monitor.record_response_time("test_operation", 0.5)
        monitor.record_error("test_operation", "timeout")

        # 获取指标
        metrics = monitor.get_metrics()

        assert "test_metric" in metrics
        assert "response_time_test_operation" in metrics
        assert "error_count_test_operation" in metrics

        logger.info("✅ 自定义指标记录测试通过")

    def test_metric_summary(self):
        """测试指标摘要"""
        config = Config()
        config.set("performance_monitor.enable_monitoring", False)
        monitor = PerformanceMonitor(config)

        # 记录一系列指标
        for i in range(10):
            monitor.record_metric("test_summary", float(i), "count")

        # 获取摘要
        summary = monitor.get_metric_summary("test_summary")

        assert "count" in summary
        assert "min" in summary
        assert "max" in summary
        assert "avg" in summary
        assert summary["min"] == 0.0
        assert summary["max"] == 9.0

        logger.info("✅ 指标摘要测试通过")

    def test_custom_collector(self):
        """测试自定义收集器"""
        config = Config()
        config.set("performance_monitor.enable_monitoring", False)
        monitor = PerformanceMonitor(config)

        def custom_collector():
            return {"custom_metric1": 42.0, "custom_metric2": 84.0}

        # 添加自定义收集器
        monitor.add_custom_collector("test_collector", custom_collector)

        assert "test_collector" in monitor.custom_collectors

        logger.info("✅ 自定义收集器测试通过")

    def test_threshold_alerts(self):
        """测试阈值告警"""
        config = Config()
        config.set("performance_monitor.enable_monitoring", False)
        monitor = PerformanceMonitor(config)

        # 设置阈值
        monitor.set_threshold("test_metric", 50.0)

        # 添加告警回调
        alert_triggered = []

        def alert_callback(metric_name, value, threshold):
            alert_triggered.append((metric_name, value, threshold))

        monitor.add_alert_callback(alert_callback)

        # 记录超过阈值的指标
        monitor.record_metric("test_metric", 60.0)

        # 验证告警触发
        assert len(alert_triggered) == 1
        assert alert_triggered[0][0] == "test_metric"
        assert alert_triggered[0][1] == 60.0
        assert alert_triggered[0][2] == 50.0

        logger.info("✅ 阈值告警测试通过")

    def test_monitor_stats(self):
        """测试监控器统计"""
        config = Config()
        config.set("performance_monitor.enable_monitoring", False)
        monitor = PerformanceMonitor(config)

        stats = monitor.get_monitor_stats()

        assert "monitor_name" in stats
        assert "features" in stats
        assert "running" in stats

        logger.info("✅ 监控器统计测试通过")


def test_performance_integration():
    """性能优化模块集成测试"""
    logger.info("🚀 开始性能优化模块集成测试...")

    # 创建配置
    config = Config()
    config.set("performance_monitor.enable_monitoring", False)  # 禁用自动监控

    # 创建模拟数据库管理器
    db_manager = Mock(spec=DatabaseManager)
    db_manager.fetchall.return_value = [{"result": "test"}]

    # 测试查询优化器
    optimizer = QueryOptimizer(db_manager, config)

    # 测试查询优化
    sql = "SELECT * FROM daily_data WHERE symbol = ?"
    params = ("000001.SZ",)
    result = optimizer.execute_with_cache(sql, params)
    assert result is not None

    # 测试缓存管理器
    cache_manager = CacheManager(config)

    # 测试缓存操作
    cache_manager.set("test_key", "test_value", "test_type")
    cached_value = cache_manager.get("test_key", "test_type")
    assert cached_value == "test_value"

    # 测试并发处理器
    processor = ConcurrentProcessor(config)

    # 测试任务提交
    def test_task(x):
        return x * 2

    task_id = processor.submit_task(test_task, 5)
    result = processor.get_result(task_id, timeout=5)
    assert result.success == True
    assert result.result == 10

    # 测试性能监控器
    monitor = PerformanceMonitor(config)

    # 测试指标记录
    monitor.record_metric("test_metric", 100.0, "count")
    metrics = monitor.get_metrics("test_metric")
    assert "test_metric" in metrics
    assert len(metrics["test_metric"]) == 1

    # 获取各组件统计
    optimizer_stats = optimizer.get_optimizer_stats()
    cache_stats = cache_manager.get_cache_stats()
    processor_stats = processor.get_stats()
    monitor_stats = monitor.get_monitor_stats()

    # 验证统计信息
    assert "optimizer_name" in optimizer_stats
    assert "cache_manager" in cache_stats
    assert "processor_name" in processor_stats
    assert "monitor_name" in monitor_stats

    # 清理资源
    processor.stop_workers()
    monitor.stop_monitoring()

    logger.info("🎉 性能优化模块集成测试通过!")


if __name__ == "__main__":
    # 运行集成测试
    test_performance_integration()

    # 运行pytest测试
    pytest.main([__file__, "-v"])
