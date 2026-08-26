# 统一派发工作能力模块

> 派发工作是**高频复用的模块能力**，已统一开发为 `config/dispatch_capability.py`，
> 所有 Agent（经理 / 部门 Agent / 生态角色 / CodeBuddy 等）都可对接使用。
> 本文档说明**用法规则**与**使用时机**，让每个 Agent 都具备这项能力。

---

## 一、为什么需要统一派发能力

在分布式协作体系中，派发工作是最高频的协作动作：

- 经理要派发工作包给部门；
- 部门要分包给协办角色；
- 生态角色要把任务派发给下游；
- 评审发现问题要派发修复给 CodeBuddy；
- 验收通过要解锁下游并级联派发。

过去每个 Agent 各自实现一套派发逻辑，**散兵作战**、能力不统一。
现在统一为 `DispatchCapability` 模块后，**所有 Agent 共享同一套派发 API、规则、时机**，
形成真正可协作的体系。

---

## 二、能力 API

```python
from dispatch_capability import DispatchCapability

cap = DispatchCapability(caller_role="producer", bus=bus)

# 1. 派发单个任务
result = cap.dispatch(
    task_name="UI 制作",
    owner="tech_artist",
    priority="HIGH",
    payload={"module": "ui_ux"},
)

# 2. 派发标准工作包
result = cap.dispatch_work_package({
    "id": "wp_ui_ux",
    "label": "生态 UI/UX 接入流水线",
    "owner": "eco_tech_artist",
    "department": "美术线",
    "priority": "HIGH",
    "depends_on": ["wp_art_direction"],
})

# 3. 批量派发（含依赖自动处理）
results = cap.dispatch_batch([wp1, wp2, wp3])

# 4. 标记完成 → 自动解锁下游
unlocked = cap.on_complete("wp_art_direction")

# 5. 标记失败
cap.on_fail("wp_ui_ux", "评审未通过")

# 6. 查询任务状态
status = cap.track("wp_ui_ux")

# 7. 派发统计
summary = cap.summary()
```

---

## 三、用法规则（DISPATCH_GUIDE）

### 1. 何时派发（时机判定）

| 时机 | 触发条件 | 动作 |
|------|---------|------|
| 新需求拆解 | 收到架构蓝图/新 Issue | 拆解为工作包 → 派发 |
| 验收解锁 | 上游产出验收通过 | 自动解锁下游 → 级联派发 |
| 打回返工 | 收到 REVIEW_RESULT 打回 | 重新派发给原 owner |
| 逾期升级 | 任务超 DDL / 阻塞 | 升级派发给上级/仲裁 |

### 2. 派发给谁（寻址方式）

| 方式 | 说明 |
|------|------|
| `role_id` 直投 | 任务派发给指定角色（部门 Agent / 生态角色） |
| `topic` 广播 | 通知所有订阅某主题的角色 |
| 依赖解锁 | `on_complete` 自动把下游就绪任务重新派发 |

### 3. 派发什么（内容规范）

工作包标准字段：

```json
{
  "id": "wp_xxx",              // 工作包唯一 id
  "label": "工作包名称",
  "owner": "role_id",          // 承接角色
  "department": "美术线",
  "priority": "HIGH",          // LOW / NORMAL / HIGH / URGENT
  "depends_on": ["wp_yyy"],    // 依赖的前置工作包 id
  "payload": {"..."}           // 附加数据
}
```

### 4. 派发后（跟踪闭环）

- 经 `Scheduler.enqueue` 入队 → `publish TASK_ASSIGN` 到 `message_bus`；
- 用 `on_complete` 解锁下游 → 自动派发依赖它的任务；
- 用 `on_fail` 标记失败 → 通知相关方；
- 用 `track` 查询任务状态 → 供进度督导使用。

### 5. 关键约定

- **派发前确认 owner 已注册**：目标 `role_id` 须注册到 `message_bus`（`bus.register()` 或已有 handler）；
- **依赖未满足自动 BLOCKED**：有依赖的任务在依赖完成前保持 `BLOCKED` 状态；
- **异步通信**：所有派发经 `message_bus` 异步投递，不直接调用目标方法；
- **任务 id 对齐依赖**：`task_id` 必须与工作包 `id`（`wp_xxx`）一致，`depends_on` 才能被调度器解析。

---

## 四、各 Agent 如何对接

### 1. BaseAgent（所有 Agent 基类）

已内置派发能力，直接使用：

```python
class MyAgent(BaseAgent):
    def handle_task(self, msg):
        # 通过 this 对象直接派发
        self.dispatch("任务名", "target_role", priority="HIGH")
        self.dispatch_work_package({"id": "wp_x", "owner": "target", ...})
        self.dispatch_complete("wp_x")
        self.dispatch_track("wp_x")
```

### 2. GameProducerAgent（经理）

已覆写 `dispatch_capability()` 复用现有 scheduler，与派发流水线共享：

```python
self.dispatch_capability().dispatch("美术品质基准", "eco_art_director",
                                     priority="HIGH")
```

### 3. EcosystemRoleRegistry（生态角色注册）

通过 `DispatchCapability` 可让生态角色也派发任务：

```python
from dispatch_capability import DispatchCapability
cap = DispatchCapability("eco_art_director", bus=bus)
cap.dispatch("UI 制作", "eco_tech_artist", priority="HIGH")
```

### 4. 新增 Agent

任何新 Agent 只需继承 `BaseAgent` 即可自动获得派发能力，无需额外配置。

---

## 五、验证

运行测试信号灯验证派发能力：

```bash
bash game-studio-agents/tests/test_dispatch_capability.sh
```

或直接运行演示：

```bash
python3 game-studio-agents/config/dispatch_capability.py
```
