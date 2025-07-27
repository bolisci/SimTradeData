#!/usr/bin/env python3
"""
数据库初始化脚本

创建SimTradeData所需的数据库表结构。
"""

import argparse
import logging
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from simtradedata.database import DatabaseManager, create_database_schema

# 设置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def init_database(
    db_path: str, force: bool = False, validate_only: bool = False
) -> bool:
    """
    初始化数据库

    Args:
        db_path: 数据库文件路径
        force: 是否强制重新创建
        validate_only: 仅验证，不创建

    Returns:
        bool: 是否成功
    """
    try:
        db_path = Path(db_path)

        if validate_only:
            logger.info(f"🔍 验证数据库架构: {db_path}")
            if not db_path.exists():
                logger.error(f"❌ 数据库文件不存在: {db_path}")
                return False
        else:
            logger.info(f"🚀 初始化数据库: {db_path}")

            # 检查是否需要强制重新创建
            if db_path.exists() and force:
                logger.warning(f"⚠️  删除现有数据库: {db_path}")
                db_path.unlink()
            elif db_path.exists() and not force:
                logger.info(f"📁 数据库已存在，将验证架构")

        # 确保目录存在
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # 创建数据库管理器
        db_manager = DatabaseManager(str(db_path))

        if validate_only:
            # 验证表结构 - 使用schema.py中定义的表名
            from simtradedata.database.schema import DATABASE_SCHEMA

            tables = list(DATABASE_SCHEMA.keys())

            missing_tables = []
            for table in tables:
                sql = f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'"
                result = db_manager.fetchone(sql)
                if not result:
                    missing_tables.append(table)

            if missing_tables:
                logger.error(f"❌ 缺少表: {', '.join(missing_tables)}")
                return False
            else:
                logger.info(f"✅ 数据库架构验证通过")
                return True
        else:
            # 创建表结构
            logger.info("📋 创建数据库表结构...")
            create_database_schema(db_manager)

            # 验证创建结果
            sql = "SELECT name FROM sqlite_master WHERE type='table'"
            tables = db_manager.fetchall(sql)
            table_names = [table["name"] for table in tables]

            logger.info(f"✅ 数据库初始化完成!")
            logger.info(f"   数据库路径: {db_path}")
            logger.info(f"   创建表数量: {len(table_names)}")
            logger.info(f"   表列表: {', '.join(table_names)}")

            return True

    except Exception as e:
        logger.error(f"❌ 数据库初始化失败: {e}")
        return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="SimTradeData 数据库初始化工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 创建新数据库
  python scripts/init_database.py --db-path data/simtradedata.db
  
  # 强制重新创建
  python scripts/init_database.py --db-path data/simtradedata.db --force
  
  # 仅验证架构
  python scripts/init_database.py --db-path data/simtradedata.db --validate-only
        """,
    )

    parser.add_argument("--db-path", required=True, help="数据库文件路径")
    parser.add_argument("--force", action="store_true", help="强制重新创建数据库")
    parser.add_argument(
        "--validate-only", action="store_true", help="仅验证架构，不创建"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")

    args = parser.parse_args()

    # 设置日志级别
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        success = init_database(args.db_path, args.force, args.validate_only)
        return 0 if success else 1

    except KeyboardInterrupt:
        logger.info("用户中断操作")
        return 1
    except Exception as e:
        logger.error(f"执行失败: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
