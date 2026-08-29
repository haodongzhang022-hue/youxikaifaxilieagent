# wp_server · 服务端无状态+协议先行（Protobuf 资产库）

- **工作包**：wp_server 服务端无状态+协议先行（Protobuf 资产库）
- **部门**：程序线
- **主责角色**：server_dev + tools_dev
- **模块**：server
- **产出物类型**：tech_impl（技术实现文档 + 代码）
- **场景**：Issue #112「游戏向架构师的开发」——服务端需无状态+协议先行

---

## 一、核心实现：无状态服务端

### 1.1 StatelessSessionManager（无状态会话管理）

JWT 风格 Token，自包含会话信息：
- `player_id`（玩家标识）
- `stage`（当前游戏阶段）
- `iat/exp`（签发/过期时间）
- HMAC SHA-256 签名验证

**关键优势**：服务端不存储会话状态 → 可平滑迁移到 Go 集群。

### 1.2 StatelessGateway（无状态网关）

- 请求自包含全部上下文（无状态）
- 会话通过 Token 自包含验证
- 幂等保证：相同 request_id 返回缓存结果
- 阶段感知：Token 中携带阶段信息，可校验阶段匹配

### 1.3 幂等性保证

```
相同 request_id + 相同 payload → 返回缓存结果
```

---

## 二、核心实现：协议先行（Protobuf 资产库）

### 2.1 protocol.proto 协议定义

**4 个枚举**：
- Platform（平台标识）
- ErrorCode（错误码）
- MsgType（消息类型）
- GameStage（游戏阶段）

**13 个消息**：
- 核心：PlayerData / GameRequest / GameResponse
- 登录：LoginRequest / LoginResponse
- 玩法：GameplayActionRequest / GameplaySnapshotResponse
- 战斗：CombatRequest / CombatResponse
- 经济：EconomyTransferRequest / EconomyTransferResponse
- 阶段：StageTransitionRequest / StageTransitionResponse

### 2.2 ProtocolCodegen（多语言代码生成器）

从 protocol.proto 自动生成：

| 语言 | 生成类型 | 代码行数 |
|------|---------|---------|
| Python | dataclass | ~156 行 |
| TypeScript | interface | ~140 行 |
| C# | class | ~159 行 |
| C++ | struct | ~148 行 |

### 2.3 向后兼容检查

- 不删除已有字段
- 不修改已有字段类型
- 新增字段必须标记 optional

---

## 三、跨阶段资产：协议库

```
server/proto/protocol.proto  ← 单一协议源
    ↓ 生成
  Python / TypeScript / C# / C++
```

**价值**：只要协议不崩，前后端随便换人、换语言、换引擎，对接成本永远是零。

---

## 四、组内分工记录（group_audit）

| 子任务 | 承接角色 | 产出说明 |
|--------|---------|---------|
| Protobuf协议资产库 + 服务端无状态设计落地 | server_dev | protocol.proto + stateless_server.py |
| 协议生成工具链设计 | tools_dev | protocol_tools.py（4语言代码生成） |

> 分工经协作工作台（CollaborationWorkbench）`delegate` 记录，全程留痕可审计。

---

## 五、测试验证

```bash
bash game-studio-agents/tests/test_stateless_server.sh
# 13/13 通过 🟢
```

### 测试覆盖

| 验证项 | 结果 |
|--------|:---:|
| 无状态 Token 创建与验证 | ✅ |
| Token 自包含玩家/阶段信息 | ✅ |
| 无效 Token 拒绝 | ✅ |
| 幂等性保证 | ✅ |
| 协议解析完整（13消息/4枚举） | ✅ |
| 四种语言代码生成 | ✅ |
| 向后兼容检查 | ✅ |
| 阶段感知 | ✅ |

---

## 六、验收通过后解锁下游

- **wp_client**（客户端逻辑/表现分离）：程序线内部级联解锁
- **美术线 wp_art_direction**：程序线产出到位后级联解锁
