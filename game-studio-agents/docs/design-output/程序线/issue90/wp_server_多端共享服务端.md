# wp_server · 多端共享服务端实现（Issue #90）

- **工作包**：wp_server 多端共享服务端
- **部门**：程序线
- **主责角色**：server_dev
- **模块**：server / cross-platform
- **产出物类型**：server_impl（服务端实现文档）
- **场景**：Issue #90「跨平台架构增强」——需保证 Web→Cocos→Unity→UE 多端共享一套服务端架构

---

## 一、服务端架构设计

### 1.1 整体架构

```
┌──────────────────────────────────────────────────────────────┐
│                    多端共享服务端（Cross-Platform Server）    │
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │  Web/React│  │  Cocos   │  │  Unity   │  │    UE    │    │
│  └─────┬────┘  └─────┬────┘  └─────┬────┘  └─────┬────┘    │
│        │             │             │             │          │
│        └─────────────┴──────┬──────┴─────────────┘          │
│                             │                                │
│                   ┌─────────▼─────────┐                     │
│                   │  统一网关 (Gateway) │                     │
│                   │  · 协议转换       │                      │
│                   │  · 负载均衡       │                      │
│                   │  · 鉴权认证       │                      │
│                   └─────────┬─────────┘                     │
│                             │                                │
│  ┌──────────────────────────▼──────────────────────────┐    │
│  │                业务服务集群（微服务）                 │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐  │    │
│  │  │ 账号服务 │ │ 玩法服务 │ │ 战斗服务 │ │ 社交   │  │    │
│  │  └────┬─────┘ └────┬─────┘ └────┬─────┘ └───┬────┘  │    │
│  │  ┌────┴─────┐ ┌────┴─────┐ ┌────┴─────┐ ┌────┴────┐ │    │
│  │  │ 叙事服务 │ │ 经济服务 │ │ 任务服务 │ │ 存档服务│ │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └─────────┘ │    │
│  └──────────────────────────┬──────────────────────────┘    │
│                             │                                │
│  ┌──────────────────────────▼──────────────────────────┐    │
│  │                数据存储层（统一账本）                 │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐  │    │
│  │  │ 玩家数据 │ │ 世界状态 │ │ 经济账本 │ │ 任务   │  │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └────────┘  │    │
│  └─────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

### 1.2 技术选型

| 组件 | 技术方案 | 选型理由 |
|------|---------|---------|
| 网关 | Nginx + gRPC Gateway | 高并发、支持协议转换 |
| 业务服务 | Go + gRPC | 高性能、原生并发 |
| 数据存储 | MySQL + Redis | 关系型 + 缓存 |
| 消息队列 | Kafka | 异步解耦、高吞吐 |
| 状态同步 | 服务端权威（Server-Authoritative） | 多端一致 |
| 版本管理 | Protobuf + Git | 前后端契约管理 |

### 1.3 多端协议统一

```protobuf
// common.proto - 多端统一通信协议
syntax = "proto3";

package game.server;

// 统一请求消息
message GameRequest {
    string request_id = 1;       // 请求 ID
    string player_id = 2;        // 玩家 ID
    int32 client_version = 3;    // 客户端版本
    string platform = 4;         // 平台标识（web/cocos/unity/ue）
    oneof payload {
        LoginRequest login = 10;
        GameplayRequest gameplay = 11;
        CombatRequest combat = 12;
        QuestRequest quest = 13;
        EconomyRequest economy = 14;
    }
}

// 统一响应消息
message GameResponse {
    string request_id = 1;
    int32 status = 2;            // 0=成功，非0=错误码
    string message = 3;
    oneof payload {
        LoginResponse login = 10;
        GameplayResponse gameplay = 11;
        CombatResponse combat = 12;
        QuestResponse quest = 13;
        EconomyResponse economy = 14;
    }
}

// 账号登录
message LoginRequest {
    string platform = 1;          // 来源平台
    string token = 2;             // 平台 token
    string device_id = 3;
}
message LoginResponse {
    string session_token = 1;
    PlayerData player = 2;
}

// 玩法同步
message GameplayRequest {
    string scene_id = 1;
    repeated PlayerAction actions = 2;
}
message GameplayResponse {
    WorldState world_state = 1;
    repeated EventDelta deltas = 2;
}

// 战斗结算
message CombatRequest {
    string combat_id = 1;
    CombatResult result = 2;
}
message CombatResponse {
    RewardData rewards = 1;
    int32 xp_earned = 2;
}
```

---

## 二、多端一致性保障

### 2.1 服务端权威架构

```
[Web客户端] ──┐
[Cocos客户端] ──┤──→ [统一网关] ──→ [业务服务] ──→ [数据存储]
[Unity客户端] ──┤         │              │            │
[UE客户端]   ──┘         │              │            │
                        └── [状态快照] ←─┴── [世界状态] ←┘
```

**核心原则**：
- 所有玩法决策在服务端计算（伤害/掉落/任务进度）
- 客户端只负责表现层 + 输入采集
- 服务端权威时间戳保证多端同步

### 2.2 状态同步协议

```python
# 状态同步核心逻辑
class WorldStateSync:
    """世界状态同步管理器"""
    
    SYNC_INTERVAL_MS = 100      # 100ms 同步间隔
    SNAPSHOT_SIZE = 2048        # 快照最大字节数
    
    def __init__(self):
        self.world_state = {}    # 世界状态
        self.deltas = []         # 增量变更
    
    def apply_action(self, player_id, action):
        """应用玩家动作（服务端权威计算）"""
        # 1. 校验合法性（碰撞/规则/权限）
        if not self.validate(action):
            return {'status': 'rejected'}
        
        # 2. 更新世界状态
        deltas = self.compute_delta(action)
        
        # 3. 记录增量
        self.deltas.extend(deltas)
        
        # 4. 广播给相关玩家
        return {'status': 'accepted', 'deltas': deltas}
    
    def snapshot(self):
        """生成状态快照"""
        return {
            'timestamp': self.server_time,
            'entities': self.world_state,
            'version': self.version,
        }
```

### 2.3 数值一致性（定点数）

```python
# 定点数服务端实现
from decimal import Decimal, getcontext

class FixedPoint:
    """32bit 定点数（1/1000 精度）"""
    SCALE = 1000
    
    def __init__(self, value):
        if isinstance(value, float):
            self.value = int(value * self.SCALE)
        elif isinstance(value, int):
            self.value = value * self.SCALE
        elif isinstance(value, FixedPoint):
            self.value = value.value
        else:
            raise TypeError(f"不支持类型: {type(value)}")
    
    def __add__(self, other):
        return FixedPoint(self.value + other.value)
    
    def __mul__(self, other):
        return FixedPoint(self.value * other.value // self.SCALE)
    
    def to_float(self):
        return self.value / self.SCALE
    
    def serialize(self) -> int:
        """序列化为整数（传输时节省带宽）"""
        return self.value
```

---

## 三、核心服务模块

### 3.1 账号服务

| 功能 | 说明 | 接口 |
|------|------|------|
| 多端登录 | 支持 Web/Cocos/Unity/UE 平台账号 | `POST /auth/login` |
| 会话管理 | Token 签发/续期/吊销 | `POST /auth/refresh` |
| 多端绑定 | 同一玩家跨端登录 | `POST /auth/bind` |
| 数据迁移 | 平台间数据互通 | `POST /auth/migrate` |

### 3.2 玩法服务

```yaml
# 玩法服务配置（跨端统一）
world_config:
  max_players_per_world: 100
  auto_save_interval: 60s
  day_night_cycle: 10min
  
scene_config:
  - scene_id: "LVL_001"
    type: "main_story"
    max_players: 4
    procedural_seed: 42

event_config:
  - event_id: "EVT_SPRING_FESTIVAL"
    start_time: "2026-02-01T00:00:00Z"
    end_time: "2026-02-15T00:00:00Z"
```

### 3.3 战斗服务

- 服务端权威战斗结算
- 战斗帧率固定 30Hz（与客户端 Tick 对齐）
- 伤害计算使用定点数（保证多端一致）
- 掉落表驱动 + 统一随机种子管理

### 3.4 任务与叙事服务

```yaml
# 任务服务配置
quest_config:
  sync_mode: "server_authoritative"   # 服务端权威
  progress_storage: "redis"           # 进度缓存
  cross_platform: true                # 跨端共享
  
narrative_config:
  dialogue_sync: true                 # 对话进度同步
  choice_sync: true                   # 选择分支同步
  cutscene_sync: false                # 过场不同步（各端独立）
```

### 3.5 经济服务

- 统一货币体系（金币/星核/蚀潮石）
- 服务端统一账本（防作弊）
- 跨端货币互通
- 每日产出上限 + 消耗锚点

---

## 四、安全与防护

### 4.1 多端安全策略

| 安全威胁 | 防护方案 |
|---------|---------|
| 内存修改/外挂 | 服务端权威 + 行为检测（AI 辅助） |
| 协议篡改 | TLS + 签名校验 |
| 账号盗用 | 多因子认证 + 设备指纹 |
| 经济作弊 | 交易记录全审计 + 异常模式检测 |
| 多端同步漏洞 | 事件溯源 + 防重放 |

### 4.2 数据一致性保障

```sql
-- 统一玩家数据表（跨端共享）
CREATE TABLE player_data (
    player_id      VARCHAR(64) PRIMARY KEY,
    level          INT NOT NULL DEFAULT 1,
    exp            INT NOT NULL DEFAULT 0,
    gold           BIGINT NOT NULL DEFAULT 0,
    star_core      INT NOT NULL DEFAULT 0,
    eroding_stone  INT NOT NULL DEFAULT 0,
    platform       VARCHAR(16) NOT NULL,    -- web/cocos/unity/ue
    last_login_ts  BIGINT NOT NULL,
    data_version   INT NOT NULL DEFAULT 1,  -- 乐观锁版本
    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

---

## 五、部署架构

### 5.1 多端共用一套服务

```
┌─ Web 客户端 ─┐   ┌─ Cocos ─┐   ┌─ Unity ─┐   ┌─ UE ─┐
└──────┬───────┘   └────┬────┘   └────┬────┘   └──┬───┘
       │                │            │           │
       └──────┬─────────┴─────┬──────┴───────────┘
              │               │
       ┌──────▼──────┐  ┌─────▼──────┐
       │  网关集群    │  │  CDN/负载  │
       │ (Nginx+gRPC)│  │  均衡      │
       └──────┬──────┘  └────────────┘
              │
       ┌──────▼──────────────────────────────────┐
       │          服务集群（Kubernetes）          │
       │  ┌─────────┐ ┌─────────┐ ┌─────────┐   │
       │  │ 账号服务 │ │ 玩法服务 │ │ 战斗服务│   │
       │  └─────────┘ └─────────┘ └─────────┘   │
       │  ┌─────────┐ ┌─────────┐ ┌─────────┐   │
       │  │ 任务服务 │ │ 经济服务 │ │ 社交服务│   │
       │  └─────────┘ └─────────┘ └─────────┘   │
       └──────┬──────────────────────────────────┘
              │
       ┌──────▼──────────────────────────────────┐
       │            数据存储层                    │
       │  MySQL(主) + Redis(缓存) + Kafka(异步)  │
       └─────────────────────────────────────────┘
```

### 5.2 部署策略

- **一套代码多端部署**：不区分平台，所有客户端连接同一服务
- **横向扩展**：按用户量自动扩容（K8s HPA）
- **多区域容灾**：主备切换 + 跨区域同步
- **灰度发布**：多端独立灰度，降低发布风险

---

## 六、交付物与验收标准

| 交付物 | 路径 | 验收标准 |
|--------|------|---------|
| 多端统一协议定义 | `server/proto/common.proto` | 覆盖登录/玩法/战斗/任务/经济 |
| 账号服务实现 | `server/services/auth/` | 支持 4 平台登录 + 多端绑定 |
| 玩法服务实现 | `server/services/gameplay/` | 服务端权威状态同步 |
| 战斗服务实现 | `server/services/combat/` | 定点数结算 + 30Hz Tick |
| 经济服务实现 | `server/services/economy/` | 统一账本 + 防作弊 |
| 部署配置 | `server/deploy/` | K8s 配置 + 网关规则 |

**验收指标**：
- 4 平台连接同一服务，状态同步一致率 100%
- 同配置战斗结算偏差 = 0（定点数保证）
- API 响应时间 P95 < 100ms
- 并发连接 ≥ 100K

---

> 产出：server_dev 承接，基于策划线 wp_numeric_model 数值模型 + 架构师中间件架构设计。
