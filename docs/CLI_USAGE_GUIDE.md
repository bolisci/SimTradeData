# SimTradeData CLI 使用指南

## 🚀 快速开始

SimTradeData 提供了完整的命令行工具，支持全量下载、增量更新、缺口补充和断点续传等数据同步功能。

### 安装和配置

```bash
# 安装依赖
poetry install

# 查看帮助
poetry run python -m simtradedata --help
```

## 📋 命令概览

| 命令 | 功能 | 说明 |
|------|------|------|
| `full-sync` | 全量数据同步 | 下载指定日期的完整数据 |
| `incremental` | 增量数据同步 | 同步指定日期范围的数据 |
| `gap-fix` | 缺口检测和修复 | 检测并修复数据缺口 |
| `resume` | 断点续传同步 | 从上次中断处继续同步 |
| `status` | 查看同步状态 | 显示当前同步状态统计 |

## 🔧 详细用法

### 1. 全量数据同步

**基本用法**：
```bash
# 同步今天的数据（所有股票，日线数据）
poetry run python -m simtradedata full-sync

# 同步指定日期
poetry run python -m simtradedata full-sync --target-date 2024-01-20

# 同步指定股票
poetry run python -m simtradedata full-sync --symbols 000001.SZ 000002.SZ 600000.SS

# 同步多种频率数据
poetry run python -m simtradedata full-sync --frequencies 1d 5m 15m
```

**参数说明**：
- `--target-date`: 目标日期 (YYYY-MM-DD 格式)
- `--symbols`: 股票代码列表，支持多个
- `--frequencies`: 数据频率，支持 1d, 5m, 15m, 30m, 1h

### 2. 增量数据同步

**基本用法**：
```bash
# 同步指定日期范围
poetry run python -m simtradedata incremental --start-date 2024-01-01 --end-date 2024-01-10

# 同步到今天
poetry run python -m simtradedata incremental --start-date 2024-01-01

# 同步指定股票
poetry run python -m simtradedata incremental --start-date 2024-01-01 --symbols 000001.SZ

# 同步分钟线数据
poetry run python -m simtradedata incremental --start-date 2024-01-01 --frequency 5m
```

**参数说明**：
- `--start-date`: 开始日期 (必需)
- `--end-date`: 结束日期 (可选，默认为今天)
- `--symbols`: 股票代码列表
- `--frequency`: 数据频率 (默认为 1d)

### 3. 缺口检测和修复

**基本用法**：
```bash
# 检测并修复指定日期范围的缺口
poetry run python -m simtradedata gap-fix --start-date 2024-01-01

# 检测指定日期范围
poetry run python -m simtradedata gap-fix --start-date 2024-01-01 --end-date 2024-01-10

# 检测指定股票的缺口
poetry run python -m simtradedata gap-fix --start-date 2024-01-01 --symbols 000001.SZ

# 检测多种频率的缺口
poetry run python -m simtradedata gap-fix --start-date 2024-01-01 --frequencies 1d 5m
```

**参数说明**：
- `--start-date`: 开始日期 (必需)
- `--end-date`: 结束日期 (可选，默认为今天)
- `--symbols`: 股票代码列表
- `--frequencies`: 数据频率列表

### 4. 断点续传同步

**基本用法**：
```bash
# 续传指定股票的日线数据
poetry run python -m simtradedata resume --symbol 000001.SZ

# 续传分钟线数据
poetry run python -m simtradedata resume --symbol 000001.SZ --frequency 5m
```

**参数说明**：
- `--symbol`: 股票代码 (必需)
- `--frequency`: 数据频率 (默认为 1d)

### 5. 查看同步状态

**基本用法**：
```bash
# 查看所有同步状态
poetry run python -m simtradedata status
```

**输出示例**：
```
📊 同步状态查询
   频率    | 总数 | 完成 | 运行中 | 失败 | 最新同步
   --------------------------------------------------
   1d     | 4000 | 3950 |      0 |   50 | 2024-01-20
   5m     |  100 |   95 |      0 |    5 | 2024-01-20
```

## ⚙️ 全局参数

所有命令都支持以下全局参数：

```bash
# 指定数据库路径
poetry run python -m simtradedata --db-path /path/to/database.db status

# 指定配置文件
poetry run python -m simtradedata --config /path/to/config.yaml status

# 详细输出模式
poetry run python -m simtradedata --verbose full-sync
```

## 📝 实用示例

### 场景1：初次使用，下载历史数据

```bash
# 1. 先下载最近一个月的日线数据
poetry run python -m simtradedata incremental --start-date 2024-01-01 --end-date 2024-01-31

# 2. 检查是否有缺口
poetry run python -m simtradedata gap-fix --start-date 2024-01-01 --end-date 2024-01-31

# 3. 查看同步状态
poetry run python -m simtradedata status
```

### 场景2：每日数据更新

```bash
# 每天运行一次，同步最新数据
poetry run python -m simtradedata full-sync
```

### 场景3：修复特定股票的数据

```bash
# 1. 检测特定股票的缺口
poetry run python -m simtradedata gap-fix --start-date 2024-01-01 --symbols 000001.SZ

# 2. 如果有中断，使用断点续传
poetry run python -m simtradedata resume --symbol 000001.SZ
```

### 场景4：批量下载多只股票

```bash
# 下载指定股票列表的数据
poetry run python -m simtradedata incremental \
  --start-date 2024-01-01 \
  --symbols 000001.SZ 000002.SZ 600000.SS 600036.SS \
  --frequency 1d
```

## 🔍 故障排除

### 常见问题

1. **数据库连接失败**
   ```bash
   # 检查数据库路径是否正确
   poetry run python -m simtradedata --db-path data/simtradedata.db status
   ```

2. **同步中断**
   ```bash
   # 使用断点续传恢复
   poetry run python -m simtradedata resume --symbol 000001.SZ
   ```

3. **数据缺口**
   ```bash
   # 运行缺口检测和修复
   poetry run python -m simtradedata gap-fix --start-date 2024-01-01
   ```

### 日志和调试

```bash
# 启用详细日志
poetry run python -m simtradedata --verbose full-sync

# 查看系统状态
poetry run python -m simtradedata status
```

## 🚀 自动化脚本

### 每日同步脚本

创建 `daily_sync.sh`：
```bash
#!/bin/bash
cd /path/to/SimTradeData

# 每日全量同步
poetry run python -m simtradedata full-sync

# 检查并修复缺口
poetry run python -m simtradedata gap-fix --start-date $(date -d "7 days ago" +%Y-%m-%d)

# 显示状态
poetry run python -m simtradedata status
```

### 定时任务 (Crontab)

```bash
# 每天凌晨2点执行同步
0 2 * * * /path/to/daily_sync.sh >> /var/log/simtradedata.log 2>&1
```

---

**SimTradeData CLI - 强大的金融数据同步工具**  
*支持全量下载 | 增量更新 | 缺口补充 | 断点续传*
