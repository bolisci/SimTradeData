# PTrade 缓存系统设计文档

## 🎯 系统概述

PTrade缓存系统是SimTradeData的核心组件，负责高效缓存和管理股票数据，为PTrade API提供快速响应。

## 🏗️ 架构设计

### 缓存层次结构

```
┌─────────────────────────────────────────┐
│              PTrade API                 │
├─────────────────────────────────────────┤
│           缓存管理层                     │
│  ┌─────────────┬─────────────────────┐   │
│  │  内存缓存    │     磁盘缓存         │   │
│  │  (Redis)    │   (SQLite/File)     │   │
│  └─────────────┴─────────────────────┘   │
├─────────────────────────────────────────┤
│           数据同步层                     │
│  ┌─────────────┬─────────────────────┐   │
│  │  实时同步    │     批量同步         │   │
│  │ (WebSocket) │   (定时任务)        │   │
│  └─────────────┴─────────────────────┘   │
├─────────────────────────────────────────┤
│           数据源层                       │
│  ┌─────────────┬─────────────────────┐   │
│  │  BaoStock   │     AkShare         │   │
│  │  QStock     │     其他数据源       │   │
│  └─────────────┴─────────────────────┘   │
└─────────────────────────────────────────┘
```

## 📊 缓存策略

### 1. 分层缓存策略

#### L1 缓存 - 内存缓存
- **存储**: Redis/内存字典
- **容量**: 1GB
- **TTL**: 5-60分钟
- **用途**: 热点数据、实时数据

#### L2 缓存 - 磁盘缓存
- **存储**: SQLite数据库
- **容量**: 无限制
- **TTL**: 1-30天
- **用途**: 历史数据、冷数据

### 2. 缓存键设计

```python
# 缓存键格式
cache_key = f"{data_type}:{symbol}:{frequency}:{date}:{params_hash}"

# 示例
"ohlcv:000001.SZ:1d:2024-01-24:abc123"
"indicators:000001.SZ:1h:2024-01-24:def456"
"fundamentals:000001.SZ:Q4:2023-12-31:ghi789"
```

### 3. 缓存更新策略

#### 主动更新
- 定时任务批量更新
- 数据源变化触发更新
- 用户请求触发更新

#### 被动更新
- 缓存过期自动更新
- LRU淘汰机制
- 容量限制触发清理

## 🔄 数据同步机制

### 1. 实时同步

```python
class RealtimeSync:
    def __init__(self):
        self.websocket_clients = {}
        self.update_queue = Queue()
    
    async def handle_market_data(self, data):
        # 更新缓存
        await self.cache_manager.update(data)
        
        # 推送给订阅客户端
        await self.broadcast_update(data)
    
    async def subscribe_symbol(self, symbol, client):
        # 订阅股票数据更新
        self.websocket_clients[client] = symbol
```

### 2. 批量同步

```python
class BatchSync:
    def __init__(self):
        self.sync_scheduler = Scheduler()
    
    def schedule_daily_sync(self):
        # 每日收盘后同步
        self.sync_scheduler.add_job(
            self.sync_daily_data,
            trigger='cron',
            hour=16, minute=0
        )
    
    async def sync_daily_data(self):
        # 批量同步当日数据
        symbols = self.get_active_symbols()
        for symbol in symbols:
            await self.sync_symbol_data(symbol)
```

## 🚀 性能优化

### 1. 查询优化

#### 索引策略
```sql
-- 主要索引
CREATE INDEX idx_symbol_date ON market_data(symbol, date);
CREATE INDEX idx_symbol_frequency ON market_data(symbol, frequency);
CREATE INDEX idx_date_range ON market_data(date, symbol);

-- 复合索引
CREATE INDEX idx_symbol_date_freq ON market_data(symbol, date, frequency);
```

#### 查询优化
```python
# 批量查询优化
def get_multiple_symbols_data(symbols, date_range):
    # 使用IN查询而不是循环查询
    sql = """
    SELECT * FROM market_data 
    WHERE symbol IN ({}) 
    AND date BETWEEN ? AND ?
    """.format(','.join(['?'] * len(symbols)))
    
    return self.db.execute(sql, symbols + date_range)
```

### 2. 内存管理

#### 对象池
```python
class DataObjectPool:
    def __init__(self, max_size=1000):
        self.pool = []
        self.max_size = max_size
    
    def get_object(self):
        if self.pool:
            return self.pool.pop()
        return MarketDataObject()
    
    def return_object(self, obj):
        if len(self.pool) < self.max_size:
            obj.reset()
            self.pool.append(obj)
```

#### 内存监控
```python
class MemoryMonitor:
    def __init__(self):
        self.memory_threshold = 0.8  # 80%
    
    def check_memory_usage(self):
        usage = psutil.virtual_memory().percent / 100
        if usage > self.memory_threshold:
            self.trigger_cache_cleanup()
```

## 📈 缓存指标监控

### 1. 关键指标

```python
class CacheMetrics:
    def __init__(self):
        self.hit_rate = 0.0
        self.miss_rate = 0.0
        self.eviction_rate = 0.0
        self.memory_usage = 0.0
        self.response_time = 0.0
    
    def calculate_hit_rate(self):
        total_requests = self.hits + self.misses
        self.hit_rate = self.hits / total_requests if total_requests > 0 else 0
```

### 2. 监控面板

```python
class CacheMonitoringDashboard:
    def get_cache_status(self):
        return {
            "hit_rate": self.metrics.hit_rate,
            "memory_usage": self.get_memory_usage(),
            "cache_size": self.get_cache_size(),
            "eviction_count": self.get_eviction_count(),
            "top_accessed_keys": self.get_top_keys()
        }
```

## 🔧 配置管理

### 1. 缓存配置

```yaml
cache:
  # 内存缓存配置
  memory:
    max_size: 1000000  # 最大条目数
    ttl: 300          # 默认TTL(秒)
    eviction_policy: "lru"
  
  # 磁盘缓存配置
  disk:
    path: "data/cache.db"
    max_size: "10GB"
    compression: true
  
  # 预热配置
  warmup:
    enabled: true
    symbols: ["000001.SZ", "000002.SZ"]
    data_types: ["ohlcv", "indicators"]
```

### 2. 性能调优

```yaml
performance:
  # 并发配置
  max_concurrent_requests: 100
  request_timeout: 30
  
  # 批处理配置
  batch_size: 1000
  batch_timeout: 5
  
  # 连接池配置
  connection_pool:
    min_connections: 5
    max_connections: 20
    idle_timeout: 300
```

## 🛠️ 实现细节

### 1. 缓存管理器

```python
class PTradeCacheManager:
    def __init__(self, config):
        self.l1_cache = MemoryCache(config.memory)
        self.l2_cache = DiskCache(config.disk)
        self.metrics = CacheMetrics()
    
    async def get(self, key):
        # L1缓存查找
        data = await self.l1_cache.get(key)
        if data:
            self.metrics.record_hit("l1")
            return data
        
        # L2缓存查找
        data = await self.l2_cache.get(key)
        if data:
            self.metrics.record_hit("l2")
            # 提升到L1缓存
            await self.l1_cache.set(key, data)
            return data
        
        self.metrics.record_miss()
        return None
    
    async def set(self, key, data, ttl=None):
        # 同时写入L1和L2缓存
        await self.l1_cache.set(key, data, ttl)
        await self.l2_cache.set(key, data, ttl)
```

### 2. 数据预热

```python
class CacheWarmer:
    def __init__(self, cache_manager, data_source):
        self.cache = cache_manager
        self.data_source = data_source
    
    async def warmup_popular_data(self):
        # 预热热门股票数据
        popular_symbols = self.get_popular_symbols()
        for symbol in popular_symbols:
            await self.warmup_symbol_data(symbol)
    
    async def warmup_symbol_data(self, symbol):
        # 预热单个股票的常用数据
        today = datetime.now().date()
        
        # 预热最近30天的日线数据
        data = await self.data_source.get_daily_data(
            symbol, today - timedelta(days=30), today
        )
        
        cache_key = f"ohlcv:{symbol}:1d:recent"
        await self.cache.set(cache_key, data)
```

## 📋 API接口

### 1. 缓存操作API

```python
# 获取缓存数据
GET /api/cache/{key}

# 设置缓存数据
POST /api/cache/{key}
{
    "data": {...},
    "ttl": 300
}

# 删除缓存数据
DELETE /api/cache/{key}

# 清空缓存
DELETE /api/cache/clear
```

### 2. 监控API

```python
# 获取缓存状态
GET /api/cache/status

# 获取缓存指标
GET /api/cache/metrics

# 获取热门键
GET /api/cache/top-keys
```

## 🔍 故障排除

### 1. 常见问题

#### 缓存命中率低
- 检查TTL设置是否合理
- 检查缓存键是否正确
- 检查内存限制是否足够

#### 内存使用过高
- 调整缓存大小限制
- 优化数据结构
- 增加淘汰频率

#### 响应时间慢
- 检查磁盘I/O性能
- 优化查询语句
- 增加索引

### 2. 监控告警

```python
class CacheAlertManager:
    def check_alerts(self):
        metrics = self.cache.get_metrics()
        
        # 命中率告警
        if metrics.hit_rate < 0.8:
            self.send_alert("缓存命中率过低", metrics.hit_rate)
        
        # 内存使用告警
        if metrics.memory_usage > 0.9:
            self.send_alert("缓存内存使用过高", metrics.memory_usage)
```

## 📚 相关文档

- [API参考文档](API_REFERENCE.md)
- [性能优化指南](Performance_Guide.md)
- [监控运维指南](Operations_Guide.md)
- [故障排除指南](Troubleshooting_Guide.md)
