# 多端共享服务端（Cross-Platform Server）

> 对齐 Issue #90「跨平台架构增强」· wp_server 多端共享服务端
> 核心命题：**一套服务支撑全部平台**，Web/Cocos/Unity/UE 共享统一协议与服务端权威逻辑

## 架构

```
┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│  Web/React│  │  Cocos   │  │  Unity   │  │    UE    │
└─────┬────┘  └─────┬────┘  └─────┬────┘  └─────┬────┘
      └─────────────┴──────┬──────┴─────────────┘
                           │
                  ┌────────▼────────┐
                  │  统一网关 Gateway │
                  │ ·协议转换         │
                  │ ·鉴权认证         │
                  │ ·路由分发         │
                  └────────┬────────┘
                           │
                  ┌────────▼────────┐
                  │   业务服务       │
                  │ ·账号/Auth       │
                  │ ·玩法/Gameplay   │
                  │ ·战斗/Combat     │
                  │ ·经济/Economy    │
                  └─────────────────┘
```

## 目录结构

```
server/
├── proto/                 # 统一通信协议
│   └── messages.py        # GameRequest/GameResponse 消息定义
├── core/                  # 服务端核心
│   ├── gateway.py         # 统一网关（协议转换/鉴权/路由）
│   ├── auth_service.py    # 账号服务（多端登录/会话/绑定）
│   ├── world_state.py     # 服务端权威世界状态管理器
│   ├── gameplay_service.py # 玩法服务（场景/事件）
│   ├── combat_service.py  # 战斗服务（定点数结算/掉落）
│   └── economy_service.py # 经济服务（统一账本/防作弊）
└── tests/
    └── test_server.py     # 服务端核心测试
```

## 核心能力

### 1. 统一协议（proto/messages.py）

以 JSON 序列化，语义对齐 Protobuf 定义：

```python
# 统一请求
req = GameRequest.create(
    player_id="P_xxx",
    msg_type="combat_result",
    payload={"session_token": "xxx", "action": "start", "seed": 42},
    platform="web",
)
```

### 2. 服务端权威（world_state.py）

- 所有玩法决策在服务端计算
- 客户端只做表现层 + 输入采集
- 快照 + 增量版本号保证多端同步

### 3. 定点数战斗结算（combat_service.py）

- 复用中间件 `FixedPoint` 定点数逻辑
- 伤害/掉落跨端 bit 级一致
- 确定性掉落（同 seed 同 loot）

### 4. 统一经济账本（economy_service.py）

- 服务端统一记账，防作弊
- 交易记录全审计
- 跨玩家转账

## 快速验证

```bash
PYTHONPATH=. python3 server/tests/test_server.py -v
```

预期：**全部测试通过**。

## 接入方式

各引擎客户端通过 `Gateway.handle()` 统一入口发送 `GameRequest`，接收 `GameResponse`：

```python
from server.proto.messages import GameRequest, GameResponse
from server.core.gateway import Gateway

gateway = Gateway()

# 登录
resp = gateway.handle(GameRequest.create(
    "temp", "login",
    {"token": "token_xxx", "device_id": "dev_1"},
    platform="web",
))

# 玩法操作（需 session_token）
resp = gateway.handle(GameRequest.create(
    player_id, "gameplay_action",
    {"session_token": token, "action": {"type": "move", "x": 10, "z": 20}},
))
```

> 与中间件（middleware/）配合使用：中间件负责引擎侧确定性逻辑，
> 服务端负责跨端共享状态与服务端权威结算。
