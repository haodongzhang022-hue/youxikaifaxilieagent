# 信息接口层（API Layer）· 接口层与人工可视层分离

> 本文档说明指挥中枢的**信息接口层**（`game-studio-agents/api/`）。
> 核心设计目标：**接口层与人工看的层分离**——
> - **AI 读取 → 调 `/ai/*` 机器接口**（结构化、低冗余、聚合、可溯源）；
> - **人类查看 → 前端调 `/dashboard/*` 通用接口**渲染可视化页面；
> 两者共用同一套降熵聚合引擎，但 AI 接口聚焦"决策所需最小充分信号"，
> 避免 AI 每次读取都混入人类偏好展示内容，从而减少无效上下文、提升效率。

---

## 〇、为什么"接口层"是必需的

多 Agent 协同（游戏向经理 → 六大部门 → 调度器 → 消息总线）会产生**海量、零散、
高频**事件流。无论 AI 还是人类，直接读原始事件都是高信息熵的噪音。

因此需要一个**统一的、可查询的管理接口层**，它：

1. **整合**：把 `message_bus`（事件流）、`task_scheduler`（任务状态）、
   `game_producer_agent`（工作包/验收）等不同来源统一成一套可查询视图；
2. **降熵**：把 N 条事件压缩为"关键信息 + 判断信息 + 依据链"；
3. **分离**：为 AI 与人类分别提供各自适合的消费形态（接口层 vs 可视层）。

> 这与"FastAPI 做接口整合"的既有实践一致：接口层是管理数据的中枢，
> 前端（人工可视层）只是接口的一个消费端，AI 是另一个消费端。

---

## 一、接口层与人工可视层如何分离

```
                  ┌─────────────────────────────────────────┐
                  │      多 Agent 协同（数据源）              │
                  │  message_bus / task_scheduler / 经理Agent │
                  └──────────────────┬──────────────────────┘
                                     │ 统一快照 (runtime.build_snapshot)
                                     ▼
                  ┌─────────────────────────────────────────┐
                  │        信息接口层（本 api/ 包）            │
                  │       降熵聚合引擎 (Aggregator)           │
                  │   /ai/*        机器接口（供 AI 读取）      │
                  │   /dashboard/* 通用接口（供前端渲染）      │
                  └────────┬──────────────────┬──────────────┘
                           │                  │
              ┌────────────▼──────┐   ┌───────▼────────────┐
              │  AI 消费端         │   │  人类可视化前端     │
              │  读取 /ai/* 聚合   │   │  读 /dashboard/*   │
              │  信号，低冗余决策  │   │  L0→L3 渐进式展示   │
              └───────────────────┘   └────────────────────┘
```

**关键点**：
- AI 与人类**不共享同一份展示内容**；AI 读的是干净的机器信号，人类看的是可视页面；
- 同一份底层数据，经同一聚合引擎，分别以"机器友好"与"展示友好"两种形态输出；
- 人类前端若想下钻，也能通过 `/dashboard/*` 拿到 L0-L3 完整数据（渐进式）。

---

## 二、接口清单

### 2.1 AI 专用机器接口（`/ai/*`）

供 AI 每次读取时获取"决策所需最小充分信号"，低冗余、结构化。

| 接口 | 层 | 用途（AI 决策视角） |
|------|:--:|---------------------|
| `GET /ai/overview` | L0 | 一眼拿到全局健康度 + 关键指标 + 判断（要不要介入） |
| `GET /ai/workpackages?group_by=department\|status` | L1 | 聚类后工作包 + 判断信息（哪些在推进/卡住） |
| `GET /ai/workpackages/{id}` | L2 | 单个工作包完整结构化信息（含风险/判断/溯源） |
| `GET /ai/risks` | L1 | 风险聚类 + 判断（给谁派返工） |
| `GET /ai/tasks` | L2 | 调度器任务状态概览（推进进度） |
| `GET /ai/events?limit=&msg_type=` | L3 | 原始事件流（核实判断的溯源证据） |

AI 消费示例：
```
GET /ai/overview
→ { layer: "L0", data: { health: "critical", metrics: [...],
                          judgments: [{ conclusion: "存在阻塞或风险，建议介入协调",
                                        evidence_chain: [...], confidence: "high",
                                        suggested_action: "..." }] },
    meta: {...}, source: {...} }
```

### 2.2 人类可视化通用接口（`/dashboard/*`）

供前端渲染，贯穿 L0-L3 渐进式展开（前端设计见 `unified-command-center.md`）。

| 接口 | 层 | 用途（前端页面） |
|------|:--:|----------------|
| `GET /dashboard/overview` | L0 | 全局总览页首屏 |
| `GET /dashboard/workpackages` | L1 | 工作包看板页（含 members 供下钻） |
| `GET /dashboard/dependencies` | L1 | 部门协作页（依赖拓扑） |
| `GET /dashboard/risks` | L1 | 风险与阻塞页 |
| `GET /dashboard/workpackages/{id}` | L2 | 点击单个工作包展开明细 |
| `GET /dashboard/events` | L3 | 事件溯源页 |

> `/dashboard/workpackages` 返回的 `groups[].members` 供前端下钻到 `/dashboard/workpackages/{id}`，
> 每个工作包的 `judgment` 携带 `evidence_chain`，可再溯源到 `/dashboard/events`。

---

## 三、数据模型（四层信息）

对应 `docs/unified-command-center.md` 的信息分层模型，统一返回
`{ meta(聚合摘要), data(明细), source(溯源指针) }`：

| 层 | 模型 | 说明 |
|----|------|------|
| L0 | `Overview` | 健康度 + 关键指标 + 风险 + 判断 |
| L1 | `Aggregate` | 聚类分组 + 判断信息（聚类→折叠→摘要） |
| L2 | `WorkPackageDetail` / `TaskDetail` | 单个实体完整结构化信息 |
| L3 | `RawEvent` | 原始事件流（可溯源证据） |
| - | `Judgment` | 判断 + 依据链 + 置信度 + 建议动作 |

---

## 四、启动与接入

### 4.1 启动服务

```bash
pip install -r game-studio-agents/api/requirements.txt
python3 game-studio-agents/api/main.py          # 默认 127.0.0.1:8000（仅本机）
# 跨机访问（务必配置鉴权令牌，避免信息泄露）:
HOST=0.0.0.0 API_TOKEN=<your-token> python3 game-studio-agents/api/main.py
# 交互式文档: http://localhost:8000/docs
```

> **安全说明**：默认仅绑定本机 `127.0.0.1`。需跨机访问时设置 `HOST=0.0.0.0`，
> 并务必设置 `API_TOKEN` 启用 Bearer 鉴权——`/ai/*` 与 `/dashboard/*` 均需携带
> `Authorization: Bearer <API_TOKEN>` 头，`/health` 健康检查不鉴权。未设置 `API_TOKEN`
> 时默认放行（仅适用于本机开发场景）。

### 4.2 附加到运行中的编排（AI / 系统接入）

接口层可附加到**正在运行的** `GameProducerAgent` 实例，实时读取其状态：

```python
from api.app import app, attach_runtime
# 运行中的 manager（由消息总线事件驱动推进）
attach_runtime(manager=manager, bus=bus)
# 之后即可通过 /ai/* 与 /dashboard/* 读取该实例的实时降熵快照
```

未附加时默认拉起一次示范编排（bootstrap）作为演示数据源。

### 4.3 架构说明

```
game-studio-agents/api/
├── __init__.py          # 包说明
├── models.py            # 四层信息模型（Pydantic）
├── aggregator.py        # 降熵聚合引擎（聚类/折叠/摘要 + 判断生成）
├── runtime.py           # 运行时快照提取（bus/scheduler/manager → 统一快照）
├── app.py               # FastAPI 应用（/ai/* 与 /dashboard/* 路由）
├── main.py              # 启动入口
└── requirements.txt     # 依赖
```

---

## 五、降熵与决策支撑的落地

聚合引擎通过"聚类 → 折叠 → 摘要"三步降熵：

- **聚类**：按部门/状态/风险把海量工作包与事件分组成类；
- **折叠**：聚合结果只暴露 `key/label/count/summary`，细节折叠进明细层；
- **摘要**：N 条事件压缩为一句话结论，并附加**判断信息**。

每个判断都携带 `evidence_chain + confidence + suggested_action`，确保
**"拿到足够信息做决策，而非靠猜测"**，且任何判断都可下钻到 L3 原始层溯源。

**信息论检验**：AI / 用户无需看全部事件也能做对决策（降熵），且想看任何一条
判断的原始依据都能找到（可溯源）——这正是"接口层与可视层分离"的价值所在。
