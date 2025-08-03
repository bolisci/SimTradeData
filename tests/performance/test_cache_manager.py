"""
测试缓存管理器

验证CacheManager的BaseManager架构迁移是否成功。
"""

import logging

import pytest

from simtradedata.config import Config
from simtradedata.performance.cache_manager import CacheManager

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestCacheManager:
    """测试缓存管理器"""

    @pytest.fixture
    def cache_manager(self):
        """创建缓存管理器实例"""
        config = Config()
        return CacheManager(config=config)

    def test_initialization(self, cache_manager):
        """测试初始化"""
        assert cache_manager is not None
        assert hasattr(cache_manager, "l1_cache")
        assert hasattr(cache_manager, "l2_cache")
        assert hasattr(cache_manager, "stats")
        assert hasattr(cache_manager, "cache_strategies")

        logger.info("✅ 缓存管理器初始化测试通过")

    def test_set_and_get(self, cache_manager):
        """测试设置和获取缓存"""
        # 测试设置缓存
        set_result = cache_manager.set("test_key", "test_value", "test_type")
        assert set_result["success"] == True
        assert set_result["data"] == True

        # 测试获取缓存
        get_result = cache_manager.get("test_key", "test_type")
        assert get_result["success"] == True
        assert get_result["data"] == "test_value"

        logger.info("✅ 设置和获取缓存测试通过")

    def test_delete(self, cache_manager):
        """测试删除缓存"""
        # 先设置缓存
        cache_manager.set("delete_key", "delete_value", "test_type")

        # 删除缓存
        delete_result = cache_manager.delete("delete_key", "test_type")
        assert delete_result["success"] == True
        assert delete_result["data"] == True

        # 验证已删除
        get_result = cache_manager.get("delete_key", "test_type")
        assert get_result["success"] == True
        assert get_result["data"] is None

        logger.info("✅ 删除缓存测试通过")

    def test_exists(self, cache_manager):
        """测试检查缓存存在"""
        # 测试不存在的键
        exists_result = cache_manager.exists("non_exist_key", "test_type")
        assert exists_result["success"] == True
        assert exists_result["data"] == False

        # 设置缓存后测试存在
        cache_manager.set("exist_key", "exist_value", "test_type")
        exists_result = cache_manager.exists("exist_key", "test_type")
        assert exists_result["success"] == True
        assert exists_result["data"] == True

        logger.info("✅ 检查缓存存在测试通过")

    def test_clear(self, cache_manager):
        """测试清空缓存"""
        # 设置一些缓存
        cache_manager.set("key1", "value1", "test_type")
        cache_manager.set("key2", "value2", "test_type")

        # 清空缓存
        clear_result = cache_manager.clear()
        assert clear_result["success"] == True
        assert clear_result["data"] == True

        # 验证缓存已清空
        get_result1 = cache_manager.get("key1", "test_type")
        get_result2 = cache_manager.get("key2", "test_type")
        assert get_result1["data"] is None
        assert get_result2["data"] is None

        logger.info("✅ 清空缓存测试通过")

    def test_get_cache_stats(self, cache_manager):
        """测试获取缓存统计"""
        # 执行一些缓存操作
        cache_manager.set("stats_key", "stats_value", "test_type")
        cache_manager.get("stats_key", "test_type")
        cache_manager.get("non_exist_key", "test_type")

        # 获取统计信息
        stats_result = cache_manager.get_cache_stats()
        assert stats_result["success"] == True

        stats = stats_result["data"]
        assert "cache_manager" in stats
        assert "total_requests" in stats
        assert "l1_cache" in stats
        assert "l2_cache" in stats
        assert "operations" in stats

        # 验证统计数据
        assert stats["operations"]["sets"] >= 1
        assert stats["total_requests"] >= 2

        logger.info("✅ 获取缓存统计测试通过")

    def test_add_cache_strategy(self, cache_manager):
        """测试添加缓存策略"""
        add_result = cache_manager.add_cache_strategy("custom_data", 7200, "l2")
        assert add_result["success"] == True
        assert add_result["data"] == True

        # 验证策略已添加
        strategies_result = cache_manager.get_cache_strategies()
        assert strategies_result["success"] == True

        strategies = strategies_result["data"]
        assert "custom_data" in strategies
        assert strategies["custom_data"]["ttl"] == 7200
        assert strategies["custom_data"]["level"] == "l2"

        logger.info("✅ 添加缓存策略测试通过")

    def test_validation_errors(self, cache_manager):
        """测试参数验证错误"""
        # 测试空键
        get_result = cache_manager.get("")
        assert get_result["success"] == False
        assert "缓存键不能为空" in get_result["message"]

        set_result = cache_manager.set("", "value")
        assert set_result["success"] == False
        assert "缓存键不能为空" in set_result["message"]

        delete_result = cache_manager.delete("")
        assert delete_result["success"] == False
        assert "缓存键不能为空" in delete_result["message"]

        exists_result = cache_manager.exists("")
        assert exists_result["success"] == False
        assert "缓存键不能为空" in exists_result["message"]

        # 测试无效的缓存策略参数
        strategy_result = cache_manager.add_cache_strategy("", 3600, "l1")
        assert strategy_result["success"] == False
        assert "数据类型不能为空" in strategy_result["message"]

        strategy_result = cache_manager.add_cache_strategy("test", -1, "l1")
        assert strategy_result["success"] == False
        assert "TTL必须为非负数" in strategy_result["message"]

        strategy_result = cache_manager.add_cache_strategy("test", 3600, "l3")
        assert strategy_result["success"] == False
        assert "缓存级别必须为l1或l2" in strategy_result["message"]

        logger.info("✅ 参数验证错误测试通过")


def test_cache_manager_integration():
    """缓存管理器集成测试"""
    logger.info("🚀 开始缓存管理器集成测试...")

    # 创建缓存管理器
    config = Config()
    cache_manager = CacheManager(config=config)

    # 测试基本操作流程
    assert cache_manager.set(
        "integration_key", {"data": "integration_value"}, "integration"
    )["success"]

    get_result = cache_manager.get("integration_key", "integration")
    assert get_result["success"] == True
    assert get_result["data"]["data"] == "integration_value"

    assert cache_manager.exists("integration_key", "integration")["data"] == True

    # 测试缓存策略
    assert cache_manager.add_cache_strategy("integration", 1800, "l1")["success"]

    strategies = cache_manager.get_cache_strategies()["data"]
    assert "integration" in strategies
    assert strategies["integration"]["ttl"] == 1800

    # 获取统计信息
    stats = cache_manager.get_cache_stats()["data"]
    assert stats["operations"]["sets"] >= 1
    assert stats["total_requests"] >= 1

    # 清理
    assert cache_manager.clear()["success"]

    logger.info("🎉 缓存管理器集成测试通过!")


if __name__ == "__main__":
    # 运行集成测试
    test_cache_manager_integration()

    # 运行pytest测试
    pytest.main([__file__, "-v"])
