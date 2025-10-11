"""
配置管理器

处理配置文件加载、验证、更新等操作。
合并了原来的Config和ConfigManager类的功能。
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml

from ..core.base_manager import BaseManager
from .defaults import get_default_config

logger = logging.getLogger(__name__)


class Config(BaseManager):
    """
    统一的配置管理类

    集成了配置加载、验证、管理和单例模式功能
    """

    _instance: Optional["Config"] = None

    def __new__(
        cls,
        config_path: Optional[str] = None,
        config_dict: Optional[Dict] = None,
        singleton: bool = True,
        **dependencies,
    ):
        """
        创建配置实例

        Args:
            config_path: 配置文件路径
            config_dict: 配置字典 (优先级高于文件)
            singleton: 是否使用单例模式
            **dependencies: 依赖对象
        """
        if singleton and cls._instance is not None:
            return cls._instance

        instance = super().__new__(cls)
        if singleton:
            cls._instance = instance
        return instance

    def __init__(
        self,
        config_path: Optional[str] = None,
        config_dict: Optional[Dict] = None,
        singleton: bool = True,
        **dependencies,
    ):
        """
        初始化配置

        Args:
            config_path: 配置文件路径
            config_dict: 配置字典 (优先级高于文件)
            singleton: 是否使用单例模式
            **dependencies: 依赖对象
        """
        # 避免重复初始化单例
        if singleton and hasattr(self, "_initialized"):
            return

        # 初始化配置数据
        self._config = get_default_config()
        self.config_path = config_path
        self._singleton = singleton

        # 加载配置文件
        if config_path and Path(config_path).exists():
            self._load_from_file(config_path)

        # 覆盖配置字典
        if config_dict:
            self._merge_config(config_dict)

        # 加载环境变量
        self._load_from_env()

        # 验证配置
        self._validate_config()

        # 调用BaseManager初始化
        super().__init__(config=self, **dependencies)

        if singleton:
            self._initialized = True

        logger.info("configuration loading completed")

    def _init_specific_config(self):
        """初始化配置管理器特定配置"""
        # 配置相关设置
        self.auto_reload = self._get_config("auto_reload", True)
        self.config_validation = self._get_config("config_validation", True)
        self.backup_config = self._get_config("backup_config", True)
        self.environment_override = self._get_config("environment_override", True)

    def _init_components(self):
        """初始化配置组件"""
        pass  # Config没有需要初始化的组件

    def _get_required_attributes(self) -> list:
        """获取必需属性列表"""
        return ["_config"]

    @classmethod
    def initialize(
        cls, config_path: Optional[str] = None, config_dict: Optional[Dict] = None
    ) -> "Config":
        """
        初始化配置实例（单例模式）

        Args:
            config_path: 配置文件路径
            config_dict: 配置字典

        Returns:
            Config: 配置实例
        """
        return cls(config_path=config_path, config_dict=config_dict, singleton=True)

    @classmethod
    def get_instance(cls) -> "Config":
        """获取配置实例"""
        if cls._instance is None:
            raise RuntimeError("配置未初始化，请先调用 initialize() 或创建实例")
        return cls._instance

    @classmethod
    def create_instance(
        cls, config_path: Optional[str] = None, config_dict: Optional[Dict] = None
    ) -> "Config":
        """
        创建新的配置实例（非单例）

        Args:
            config_path: 配置文件路径
            config_dict: 配置字典

        Returns:
            Config: 新的配置实例
        """
        return cls(config_path=config_path, config_dict=config_dict, singleton=False)

    def _load_from_file(self, config_path: str):
        """从文件加载配置"""
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                file_config = yaml.safe_load(f)
                if file_config:
                    self._merge_config(file_config)
                    logger.info(f"loading configuration from file : {config_path}")
        except Exception as e:
            logger.error(f"loading configuration file failed : {e}")
            raise

    def _load_from_env(self):
        """从环境变量加载配置"""
        env_mappings = {
            "PTRADE_DB_PATH": ("database", "path"),
            "PTRADE_LOG_LEVEL": ("logging", "level"),
            "PTRADE_SYNC_ENABLED": ("sync", "enabled"),
            "PTRADE_SYNC_SCHEDULE": ("sync", "daily_schedule"),
            "PTRADE_MOOTDX_ENABLED": ("data_sources", "mootdx", "enabled"),
            "PTRADE_BAOSTOCK_ENABLED": ("data_sources", "baostock", "enabled"),
            "PTRADE_QSTOCK_ENABLED": ("data_sources", "qstock", "enabled"),
        }

        for env_key, config_path in env_mappings.items():
            env_value = os.getenv(env_key)
            if env_value is not None:
                self._set_nested_value(config_path, self._convert_env_value(env_value))
                logger.debug(
                    f"loading from environment variable : {env_key} = {env_value}"
                )

    def _convert_env_value(self, value: str) -> Union[str, bool, int, float]:
        """转换环境变量值类型"""
        # 布尔值
        if value.lower() in ("true", "false"):
            return value.lower() == "true"

        # 整数
        try:
            return int(value)
        except ValueError:
            pass

        # 浮点数
        try:
            return float(value)
        except ValueError:
            pass

        # 字符串
        return value

    def _merge_config(self, new_config: Dict[str, Any]):
        """合并配置"""

        def merge_dict(base: Dict, update: Dict):
            for key, value in update.items():
                if (
                    key in base
                    and isinstance(base[key], dict)
                    and isinstance(value, dict)
                ):
                    merge_dict(base[key], value)
                else:
                    base[key] = value

        merge_dict(self._config, new_config)

    def _set_nested_value(self, path: tuple, value: Any):
        """设置嵌套配置值"""
        config = self._config
        for key in path[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        config[path[-1]] = value

    def _validate_config(self):
        """验证配置"""
        # 验证必需的配置项
        required_keys = [
            ("database", "path"),
            ("markets", "enabled"),
            ("data_sources",),
            ("frequencies", "supported"),
        ]

        for key_path in required_keys:
            if not self._has_nested_key(key_path):
                raise ValueError(f"缺少必需的配置项: {'.'.join(key_path)}")

        # 验证市场配置
        enabled_markets = self.get("markets.enabled", [])
        for market in enabled_markets:
            if not self._has_nested_key(("markets", market)):
                raise ValueError(f"市场 {market} 缺少配置")

        # 验证数据源配置
        for source in ["mootdx", "baostock", "qstock"]:
            if not self._has_nested_key(("data_sources", source)):
                logger.warning(f"data source {source} missing configuration")

        logger.info("configuration validation passed")

    def _has_nested_key(self, key_path: tuple) -> bool:
        """检查嵌套键是否存在"""
        config = self._config
        try:
            for key in key_path:
                config = config[key]
            return True
        except (KeyError, TypeError):
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值 (支持点号分隔的嵌套键)

        Args:
            key: 配置键 (如: 'database.path')
            default: 默认值

        Returns:
            Any: 配置值
        """
        keys = key.split(".")
        config = self._config

        try:
            for k in keys:
                config = config[k]
            return config
        except (KeyError, TypeError):
            return default

    def set(self, key: str, value: Any):
        """
        设置配置值 (支持点号分隔的嵌套键)

        Args:
            key: 配置键
            value: 配置值
        """
        keys = key.split(".")
        config = self._config

        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        config[keys[-1]] = value

    def update(self, updates: Dict[str, Any]):
        """批量更新配置"""
        for key, value in updates.items():
            self.set(key, value)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return self._config.copy()

    def reload(self, config_path: Optional[str] = None):
        """重新加载配置"""
        if config_path is None:
            config_path = self.config_path

        if config_path and Path(config_path).exists():
            self._config = get_default_config()
            self._load_from_file(config_path)
            self._load_from_env()
            self._validate_config()
            logger.info("configuration reloaded")
        else:
            logger.warning(
                "unable to reload configuration : configuration file not found"
            )

    def save_to_file(self, file_path: Optional[str] = None):
        """保存配置到文件"""
        if file_path is None:
            file_path = self.config_path

        if file_path is None:
            raise ValueError("未指定保存路径")

        try:
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                yaml.dump(
                    self._config,
                    f,
                    default_flow_style=False,
                    allow_unicode=True,
                    indent=2,
                )
            logger.info(f"configuration saved to : {file_path}")
        except Exception as e:
            logger.error(f"saving configuration file failed : {e}")
            raise

    # 便捷方法
    def get_database_config(self) -> Dict[str, Any]:
        """获取数据库配置"""
        return self.get("database", {})

    def get_market_config(self, market: Optional[str] = None) -> Dict[str, Any]:
        """获取市场配置"""
        if market:
            return self.get(f"markets.{market}", {})
        return self.get("markets", {})

    def get_data_source_config(self, source: Optional[str] = None) -> Dict[str, Any]:
        """获取数据源配置"""
        if source:
            return self.get(f"data_sources.{source}", {})
        return self.get("data_sources", {})

    def get_sync_config(self) -> Dict[str, Any]:
        """获取同步配置"""
        return self.get("sync", {})

    def get_logging_config(self) -> Dict[str, Any]:
        """获取日志配置"""
        return self.get("logging", {})

    def is_market_enabled(self, market: str) -> bool:
        """检查市场是否启用"""
        enabled_markets = self.get("markets.enabled", [])
        return market in enabled_markets

    def is_data_source_enabled(self, source: str) -> bool:
        """检查数据源是否启用"""
        return self.get(f"data_sources.{source}.enabled", False)

    def is_frequency_supported(self, frequency: str) -> bool:
        """检查频率是否支持"""
        supported = self.get("frequencies.supported", [])
        return frequency in supported

    def get_enabled_apis(self) -> list:
        """获取启用的API列表"""
        return self.get("api.enabled_apis", [])


# 为了向后兼容，保留ConfigManager作为Config的别名
ConfigManager = Config
