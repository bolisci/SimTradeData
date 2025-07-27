"""
查询缓存

提供查询结果缓存功能，提高重复查询的性能。
"""

import hashlib
import logging
import pickle
import time
from typing import Any, Dict, List, Optional

from ..config import Config

logger = logging.getLogger(__name__)


class QueryCache:
    """查询缓存"""

    def __init__(self, config: Config = None):
        """
        初始化查询缓存

        Args:
            config: 配置对象
        """
        self.config = config or Config()

        # 缓存配置
        self.enable_cache = self.config.get("api.cache_enabled", True)
        self.cache_ttl = self.config.get("api.cache_ttl", 300)  # 5分钟
        self.max_cache_size = self.config.get("api.max_cache_size", 1000)
        self.cache_compression = self.config.get("api.cache_compression", True)

        # 内存缓存存储
        self._cache_store: Dict[str, Dict[str, Any]] = {}
        self._cache_access_times: Dict[str, float] = {}

        logger.info(f"查询缓存初始化完成，启用状态: {self.enable_cache}")

    def get(self, cache_key: str) -> Optional[Any]:
        """
        获取缓存数据

        Args:
            cache_key: 缓存键

        Returns:
            Optional[Any]: 缓存的数据，如果不存在或过期则返回None
        """
        if not self.enable_cache:
            return None

        try:
            if cache_key not in self._cache_store:
                return None

            cache_entry = self._cache_store[cache_key]

            # 检查是否过期
            if self._is_expired(cache_entry):
                self._remove(cache_key)
                return None

            # 更新访问时间
            self._cache_access_times[cache_key] = time.time()

            # 解压缩数据
            data = cache_entry["data"]
            if cache_entry.get("compressed", False):
                data = pickle.loads(data)

            logger.debug(f"缓存命中: {cache_key}")
            return data

        except Exception as e:
            logger.error(f"获取缓存失败 {cache_key}: {e}")
            return None

    def set(self, cache_key: str, data: Any, ttl: int = None) -> bool:
        """
        设置缓存数据

        Args:
            cache_key: 缓存键
            data: 要缓存的数据
            ttl: 生存时间（秒），为None时使用默认值

        Returns:
            bool: 是否设置成功
        """
        if not self.enable_cache:
            return False

        try:
            if ttl is None:
                ttl = self.cache_ttl

            # 检查缓存大小限制
            if len(self._cache_store) >= self.max_cache_size:
                self._evict_lru()

            # 压缩数据
            cache_data = data
            compressed = False

            if self.cache_compression:
                try:
                    cache_data = pickle.dumps(data)
                    compressed = True
                except Exception as e:
                    logger.warning(f"数据压缩失败，使用原始数据: {e}")
                    cache_data = data

            # 存储缓存条目
            cache_entry = {
                "data": cache_data,
                "compressed": compressed,
                "created_time": time.time(),
                "ttl": ttl,
                "access_count": 0,
            }

            self._cache_store[cache_key] = cache_entry
            self._cache_access_times[cache_key] = time.time()

            logger.debug(f"缓存设置成功: {cache_key}, TTL: {ttl}s")
            return True

        except Exception as e:
            logger.error(f"设置缓存失败 {cache_key}: {e}")
            return False

    def remove(self, cache_key: str) -> bool:
        """
        删除缓存

        Args:
            cache_key: 缓存键

        Returns:
            bool: 是否删除成功
        """
        return self._remove(cache_key)

    def clear(self) -> bool:
        """
        清空所有缓存

        Returns:
            bool: 是否清空成功
        """
        try:
            self._cache_store.clear()
            self._cache_access_times.clear()
            logger.info("缓存已清空")
            return True
        except Exception as e:
            logger.error(f"清空缓存失败: {e}")
            return False

    def generate_cache_key(self, query_type: str, **kwargs) -> str:
        """
        生成缓存键

        Args:
            query_type: 查询类型
            **kwargs: 查询参数

        Returns:
            str: 缓存键
        """
        try:
            # 构建缓存键字符串
            key_parts = [query_type]

            # 按键排序确保一致性
            for key in sorted(kwargs.keys()):
                value = kwargs[key]
                if isinstance(value, list):
                    value = ",".join(sorted(map(str, value)))
                key_parts.append(f"{key}={value}")

            key_string = "|".join(key_parts)

            # 生成MD5哈希
            cache_key = hashlib.md5(key_string.encode("utf-8")).hexdigest()

            logger.debug(f"生成缓存键: {key_string} -> {cache_key}")
            return cache_key

        except Exception as e:
            logger.error(f"生成缓存键失败: {e}")
            return f"{query_type}_{int(time.time())}"

    def _is_expired(self, cache_entry: Dict[str, Any]) -> bool:
        """检查缓存是否过期"""
        created_time = cache_entry["created_time"]
        ttl = cache_entry["ttl"]
        return time.time() - created_time > ttl

    def _remove(self, cache_key: str) -> bool:
        """删除缓存条目"""
        try:
            if cache_key in self._cache_store:
                del self._cache_store[cache_key]
            if cache_key in self._cache_access_times:
                del self._cache_access_times[cache_key]
            return True
        except Exception as e:
            logger.error(f"删除缓存失败 {cache_key}: {e}")
            return False

    def _evict_lru(self):
        """LRU缓存淘汰"""
        try:
            if not self._cache_access_times:
                return

            # 找到最久未访问的缓存键
            lru_key = min(
                self._cache_access_times.keys(),
                key=lambda k: self._cache_access_times[k],
            )

            self._remove(lru_key)
            logger.debug(f"LRU淘汰缓存: {lru_key}")

        except Exception as e:
            logger.error(f"LRU淘汰失败: {e}")

    def cleanup_expired(self) -> int:
        """
        清理过期缓存

        Returns:
            int: 清理的缓存数量
        """
        try:
            expired_keys = []

            for cache_key, cache_entry in self._cache_store.items():
                if self._is_expired(cache_entry):
                    expired_keys.append(cache_key)

            for key in expired_keys:
                self._remove(key)

            logger.debug(f"清理过期缓存: {len(expired_keys)} 个")
            return len(expired_keys)

        except Exception as e:
            logger.error(f"清理过期缓存失败: {e}")
            return 0

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            Dict[str, Any]: 缓存统计
        """
        try:
            total_entries = len(self._cache_store)

            # 计算缓存大小
            total_size = 0
            expired_count = 0

            for cache_entry in self._cache_store.values():
                if self._is_expired(cache_entry):
                    expired_count += 1

                data = cache_entry["data"]
                if isinstance(data, bytes):
                    total_size += len(data)
                else:
                    # 估算对象大小
                    total_size += len(str(data))

            return {
                "enabled": self.enable_cache,
                "total_entries": total_entries,
                "expired_entries": expired_count,
                "active_entries": total_entries - expired_count,
                "estimated_size_bytes": total_size,
                "max_cache_size": self.max_cache_size,
                "default_ttl": self.cache_ttl,
                "compression_enabled": self.cache_compression,
            }

        except Exception as e:
            logger.error(f"获取缓存统计失败: {e}")
            return {"error": str(e)}

    # 删除复杂的模式失效方法，保持简洁

    def warm_up(self, queries: List[Dict[str, Any]]) -> int:
        """
        缓存预热

        Args:
            queries: 预热查询列表

        Returns:
            int: 预热的查询数量
        """
        try:
            warmed_count = 0

            for query in queries:
                query_type = query.get("type")
                params = query.get("params", {})

                if query_type:
                    cache_key = self.generate_cache_key(query_type, **params)

                    # 如果缓存不存在，可以在这里执行查询并缓存结果
                    # 这里只是生成缓存键，实际的预热需要在API路由器中实现
                    if cache_key not in self._cache_store:
                        warmed_count += 1

            logger.info(f"缓存预热完成: {warmed_count} 个查询")
            return warmed_count

        except Exception as e:
            logger.error(f"缓存预热失败: {e}")
            return 0
