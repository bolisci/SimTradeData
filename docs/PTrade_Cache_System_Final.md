# PTrade SQLite数据缓存系统 - 最终设计方案

## 🎯 系统概述

基于64个PTrade API，设计高性能SQLite数据缓存系统：
- **多市场支持**: A股(SZ/SS)、港股(HK)、美股(US)
- **多频率支持**: 1d/1m/5m/15m/30m/60m/120m/1w/1y
- **多数据源融合**: AkShare、BaoStock、QStock智能组合
- **预处理架构**: 离线预处理 + 毫秒级直查
- **完全兼容**: PTrade API调用方式完全不变

## 🏗️ 核心架构

```
数据流程: 多源下载 → 离线预处理 → PTrade格式存储 → 毫秒级直查
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ 多源数据下载 │ → │ 离线预处理   │ → │ PTrade格式  │ → │ 毫秒级查询   │
│ AkShare     │    │ 清洗+融合   │    │ 标准存储    │    │ 直接SQL     │
│ BaoStock    │    │ 复权+指标   │    │ 多市场支持  │    │ 无需组装    │
│ QStock      │    │ 质量控制    │    │ 优化索引    │    │ 高并发      │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

## 📊 数据库设计

### 核心表结构

```sql
-- 1. PTrade历史数据表 (支持多市场多频率)
CREATE TABLE market_data (
    symbol TEXT NOT NULL,             -- 股票代码 (000001.SZ/600000.SS/00700.HK/AAPL.US)
    market TEXT NOT NULL,             -- 市场 (SZ/SS/HK/US)
    trade_date DATE NOT NULL,         -- 交易日期
    trade_time TIME,                  -- 交易时间 (分钟线用)
    frequency TEXT NOT NULL,          -- 频率 (1d/1m/5m/15m/30m/60m/120m/1w/1y)
    
    -- PTrade API标准字段
    open REAL, high REAL, low REAL, close REAL,
    volume REAL, money REAL, price REAL,
    
    -- 日线专用字段 (A股)
    preclose REAL, high_limit REAL, low_limit REAL,
    unlimited INTEGER DEFAULT 0,
    
    -- 估值指标 (预计算)
    pe_ratio REAL, pb_ratio REAL, turnover_rate REAL,
    
    -- 技术指标 (预计算，仅日线)
    ma5 REAL, ma10 REAL, ma20 REAL, ma60 REAL,
    
    UNIQUE(symbol, trade_date, trade_time, frequency)
);

-- 2. 股票基础信息表
CREATE TABLE ptrade_stock_info (
    symbol TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    market TEXT NOT NULL,             -- SZ/SS/HK/US
    industry TEXT,
    list_date DATE,
    currency TEXT DEFAULT 'CNY',      -- CNY/HKD/USD
    timezone TEXT DEFAULT 'Asia/Shanghai',
    last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. 交易日历表 (多市场)
CREATE TABLE ptrade_calendar (
    trade_date DATE NOT NULL,
    market TEXT NOT NULL,
    is_trading INTEGER NOT NULL,
    open_time TIME,
    close_time TIME,
    PRIMARY KEY(trade_date, market)
);

-- 4. 财务数据表
CREATE TABLE ptrade_fundamentals (
    symbol TEXT NOT NULL,
    report_date DATE NOT NULL,
    report_type TEXT NOT NULL,        -- Q1/Q2/Q3/Q4
    revenue REAL, net_profit REAL, eps REAL,
    roe REAL, roa REAL,
    UNIQUE(symbol, report_date, report_type)
);

-- 5. 市场数据源配置表
CREATE TABLE market_data_source_config (
    market TEXT NOT NULL,
    frequency TEXT NOT NULL,
    data_type TEXT NOT NULL,
    priority_1 TEXT, priority_2 TEXT, priority_3 TEXT,
    is_supported INTEGER DEFAULT 1,
    PRIMARY KEY(market, frequency, data_type)
);
```

### 索引优化

```sql
-- 多市场多频率索引
CREATE INDEX idx_history_symbol_freq_date ON market_data(symbol, frequency, trade_date);
CREATE INDEX idx_history_market_freq_date ON market_data(market, frequency, trade_date);
CREATE INDEX idx_history_symbol_freq_datetime ON market_data(symbol, frequency, trade_date, trade_time);
```

## 🏭 数据预处理引擎

### 核心组件

```python
class DataPreprocessor:
    """数据预处理引擎"""
    
    def process_daily_data(self, target_date=None, frequencies=['1d']):
        """处理每日增量数据"""
        symbols = self._get_active_symbols()
        
        for frequency in frequencies:
            for symbol in symbols:
                # 1. 解析市场
                market = self._parse_market_from_symbol(symbol)
                
                # 2. 收集原始数据
                raw_data = self._collect_raw_data(symbol, target_date, frequency, market)
                
                # 3. 转换PTrade格式
                ptrade_data = self._convert_to_ptrade(raw_data, symbol, frequency, market)
                
                # 4. 预计算指标 (仅日线)
                if frequency == '1d':
                    ptrade_data = self._calculate_indicators(ptrade_data)
                
                # 5. 存储
                self._store_ptrade_data(ptrade_data)
    
    def _collect_raw_data(self, symbol, date, frequency, market):
        """根据市场选择数据源"""
        priorities = self._get_market_source_priorities(market, frequency)
        
        for source_name in priorities:
            try:
                if frequency == '1d':
                    return self.sources[source_name].get_daily_data(symbol, date)
                else:
                    return self.sources[source_name].get_minute_data(symbol, date, frequency)
            except Exception as e:
                continue
        
        raise Exception(f"无法获取数据: {symbol} {date} {frequency}")
    
    def _parse_market_from_symbol(self, symbol):
        """解析市场"""
        if symbol.endswith('.SZ'): return 'SZ'
        elif symbol.endswith('.SS'): return 'SS'
        elif symbol.endswith('.HK'): return 'HK'
        elif symbol.endswith('.US'): return 'US'
        else:
            # 根据代码前缀推断
            if symbol.startswith('00') or symbol.startswith('30'): return 'SZ'
            elif symbol.startswith('60') or symbol.startswith('68'): return 'SS'
            return 'SZ'
```

## ⚡ 高性能API路由器

```python
class APIRouter:
    """PTrade API路由器"""
    
    def route_call(self, api_name, **kwargs):
        """路由API调用 - 直接查询预处理数据"""
        builder = self.query_builders[api_name]
        sql, params = builder.build_query(**kwargs)
        return pd.read_sql(sql, self.db.connection, params=params)

class HistoryQueryBuilder:
    """历史数据查询构建器"""
    
    def build_query(self, security_list, start_date=None, end_date=None, 
                   frequency='1d', fields=None, **kwargs):
        """构建查询SQL"""
        symbols = self._normalize_symbols(security_list)
        field_list = self._normalize_fields(fields, frequency)
        
        base_fields = ['symbol', 'trade_date']
        if frequency not in ['1d', '1w', '1y']:
            base_fields.append('trade_time')
        
        sql = f"""
        SELECT {', '.join(base_fields + field_list)}
        FROM market_data 
        WHERE symbol IN ({','.join(['?'] * len(symbols))})
        AND frequency = ?
        """
        
        params = symbols + [frequency]
        
        if start_date:
            sql += " AND trade_date >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND trade_date <= ?"
            params.append(end_date)
        
        sql += " ORDER BY symbol, trade_date"
        if frequency not in ['1d', '1w', '1y']:
            sql += ", trade_time"
        
        return sql, params
```

## 🔄 数据同步策略

### 增量同步

```python
class IncrementalSync:
    """增量同步管理器"""
    
    def sync_incremental(self, data_type='daily'):
        """从上次更新点同步到今天"""
        symbols = self._get_active_symbols()
        today = datetime.now().date()
        
        for symbol in symbols:
            # 获取最后数据日期
            last_date = self._get_last_data_date(symbol)
            
            if last_date is None:
                start_date = self._get_list_date(symbol) or '2020-01-01'
            else:
                start_date = self._get_next_trade_date(last_date)
            
            if start_date <= today:
                self._sync_date_range(symbol, start_date, today)

class GapDetector:
    """数据缺口检测和修复"""
    
    def detect_and_fix_gaps(self, symbol=None, max_gap_days=30):
        """检测并修复数据缺口"""
        gaps = self._detect_gaps(symbol)
        
        for gap in gaps:
            if gap['days'] <= max_gap_days:
                self._fill_gap(symbol, gap['start'], gap['end'])
```

## 🌍 多市场支持

### 市场配置

```python
MARKET_CONFIG = {
    'SZ': {
        'name': '深圳证券交易所',
        'data_sources': ['baostock', 'akshare', 'qstock'],
        'frequencies': ['1d', '1m', '5m', '15m', '30m', '60m'],
        'features': ['涨跌停', 'T+1', '集合竞价']
    },
    'SS': {
        'name': '上海证券交易所',
        'data_sources': ['baostock', 'akshare', 'qstock'],
        'frequencies': ['1d', '1m', '5m', '15m', '30m', '60m'],
        'features': ['涨跌停', 'T+1', '集合竞价']
    },
    'HK': {
        'name': '香港证券交易所',
        'data_sources': ['akshare'],
        'frequencies': ['1d'],  # 仅日线
        'features': ['无涨跌停', 'T+0']
    },
    'US': {
        'name': '美国证券交易所',
        'data_sources': ['akshare'],
        'frequencies': ['1d'],  # 仅日线
        'features': ['无涨跌停', 'T+0', '盘前盘后']
    }
}
```

## 🎮 使用示例

```python
# A股查询 (完整功能)
sz_data = ptrade.get_history('000001.SZ', start_date='2024-01-01', frequency='1d')
ss_minute = ptrade.get_history('600000.SS', start_date='2024-01-20', frequency='5m')

# 港股查询 (仅日线)
hk_data = ptrade.get_history('00700.HK', start_date='2024-01-01', frequency='1d')

# 美股查询 (仅日线)
us_data = ptrade.get_history('AAPL.US', start_date='2024-01-01', frequency='1d')

# 多市场混合查询
multi_market = ptrade.get_history(['000001.SZ', '00700.HK', 'AAPL.US'], start_date='2024-01-01')

# 数据同步
sync = IncrementalSync()
result = sync.sync_incremental('daily')

# 缺口检测修复
detector = GapDetector()
gaps = detector.detect_and_fix_gaps('000001.SZ')
```

## 📊 性能指标

| 操作类型 | 响应时间 | 并发支持 | 存储估算 |
|---------|---------|----------|----------|
| 单股票1年日线 | 10-30ms | 100+ | ~50KB |
| 单股票1年5分钟线 | 50-100ms | 50+ | ~2MB |
| 50股票1年日线 | 100-300ms | 50+ | ~2.5MB |
| 多市场混合查询 | 20-80ms | 80+ | 变化 |

## 🚀 部署配置

```yaml
# config.yaml
database:
  path: "./data/simtradedata.db"

markets:
  enabled: ["SZ", "SS", "HK", "US"]
  
data_sources:
  akshare: {enabled: true, timeout: 10}
  baostock: {enabled: true, timeout: 15}
  qstock: {enabled: true, timeout: 10}

sync:
  daily_schedule: "02:00"
  frequencies: ["1d", "5m", "15m", "30m", "60m"]
  auto_gap_fix: true
  max_gap_days: 30
```

这个设计提供了完整的多市场、多频率、高性能SQLite数据缓存解决方案。
