# 游戏开发 Agent 岗位体系

> 基于人类游戏开发分工，建立可被 Agent 替代的岗位体系与行为逻辑框架。

## 📋 项目概述

本项目的目标是将游戏开发全流程中的**人类岗位分工**转化为 **Agent 可执行的岗位模型**，
每个岗位都有明确的职责、任务、产出物、工作流程和行为逻辑。

## 📁 目录结构

```
game-studio-agents/
├── docs/
│   ├── 岗位体系调研.md          # 游戏开发行业岗位调研报告
│   └── reference-learning-agent/  # 游戏借鉴学习 Agent 设计（能力/行为逻辑/触发时机/Mod规范/强化层）
├── config/
│   ├── roles.yaml               # Agent 岗位定义文件（职责/任务/协作/状态机，含 reference_learner 强化层）
│   ├── role_presets.yaml        # ⭐ 角色分层预设体系（角色级/技术栈级/小组级，按需启用）
│   ├── agent_behavior.py        # Agent 行为逻辑框架（决策/通信/协作/异常 + 强化层机制）
│   ├── agent_core.py            # ⭐ 通用 Agent 内核基类（生命周期/状态机/决策，v0.3，可运行）
│   ├── message_bus.py           # ⭐ 通用消息总线（事件驱动通信，v0.3，可运行）
│   ├── task_scheduler.py        # ⭐ 任务队列与事件驱动调度器（优先级/依赖，v0.3，可运行）
│   └── agent_boost/             # 能力强化层（思维模式路由 / 科研探索 / 博弈评审 / 探索 / 校准）
│       ├── routing_preset.yaml  #   三波段思维模式路由预设（spec/react/weak）
│       ├── research_engine.py   #   科研探索引擎（元学习/树探索/假设求证/多Agent博弈）
│       ├── debate_reviewer.yaml #   多 Agent 博弈评审配置
│       ├── exploration_preset.yaml # 探索多模式预设（渠道×类型×深度）
│       └── calibration_preset.yaml # 相似度控制与多轮迭代校准预设
└── README.md                    # 本文件
```

## 🧩 通用基础设施（解耦补充）

> 以下是**与具体岗位 / 生态角色完全解耦**的底层基础设施，无论后续架构如何调整都必然复用。
> 当前以 **v0.3** 落地为可运行的 Python 模块：

| 模块 | 作用 | 解耦性 |
|------|------|--------|
| `message_bus.py` | 统一消息协议 + 事件驱动消息总线（DIRECT/TOPIC/ANYCAST 三种投递，优先级队列，拦截器，审计追踪） | 与角色无关，所有 Agent 通信的基础 |
| `agent_core.py` | 通用 Agent 内核基类（生命周期状态机 / 混合决策引擎 / 知识库 / 消息收发 / 经验学习） | 与角色无关，任何角色继承复用 |
| `task_scheduler.py` | 任务队列（优先级 / DDL / 依赖） + 事件驱动调度器（任务就绪自动派发） | 与角色无关，供零工池 / 进度督导复用 |

```bash
# 运行各模块自带的演示
python3 config/message_bus.py      # 消息总线：投递 / 订阅 / 优先级 / 广播
python3 config/agent_core.py       # Agent 内核：状态机 / 决策 / 消息处理
python3 config/task_scheduler.py   # 调度器：优先级 / 依赖解锁 / 事件派发
```

**设计原则**：三者互相解耦、可独立替换；`agent_core` 与 `task_scheduler` 依赖 `message_bus` 作为统一通信层，但彼此不互相依赖，方便架构师审查后按需重组。

## 🎭 角色分层预设体系（可扩展备用预设）

> **背景**：为支持可扩展性，无需把每种可能都做成正式角色（每个岗位 >3 个会过度膨胀）。
> 本体系把**同一岗位/岗位族的多种变体**作为**备用预设**预置，按需启用。
> 例如：同样的美工，不同美术风格可预设进美工角色；技术岗不同技术栈可预设；
> 还能按生态组织成**小组**（UE5小组 / Godot小组 / Web React小组 / 页面引擎小组）。

定义文件：`config/role_presets.yaml`，分**三个层级**：

| 层级 | 类型 | 说明 | 示例 |
|------|------|------|------|
| **L1** | 角色级预设 `role_presets` | 针对单个岗位的变体（风格/技术栈/侧重） | 原画师·水墨风、客户端·UE5、数值·肉鸽向 |
| **L2** | 技术栈级预设 `stack_presets` | 针对程序线岗位族的整套技术方案 | UE5生态 / Godot生态 / Web(React) / 页面引擎 |
| **L3** | 小组级预设 `team_presets` | 面向某一生态组织的小组，可整体启用 | UE5小组 / Godot小组 / Web前端小组 / 页面引擎小组 |

**启用方式（按需求启用即可）**：
1. **只读参考**：读取 preset 字段并入现有正式角色
2. **实例化**：将 preset 复制为 `roles.yaml` 中的正式角色（`status: agent_enabled`）
3. **小组编排**：通过 L3 `team_presets` 组合多角色/技术栈，作为一组 Agent 整体启用

> **可扩展约定**：预设为**轻量定义**，只给差异化字段（personality/风格/技术栈/工具链/侧重），
> 复用 `base_role` 的正式定义（responsibilities/tasks/状态机），从而支持低成本横向扩展。

## 🎭 岗位体系总览（六大板块）

> ✅ **差异化角色**：每个岗位均配置 **≥2 个差异化角色**，角色间在**性格（personality）** 与**侧重方向**上形成互补，以适应不同项目阶段与目标的需求。

| 板块 | 岗位（角色数） | Agent化优先级 |
|------|------|-------------|
| **策划线** | 制作人×2、主策划×2、系统策划×2、数值策划×2、关卡策划×2、剧情策划×2、战斗策划×2 | ★★★ |
| **程序线** | 技术总监×2、客户端×2、服务端×2、引擎×2、AI×2、工具链×2 | ★★★ |
| **美术线** | 主美×2、原画×2、3D建模×2、动画×2、特效×2、UI/UX×2、TA×2、音频×2 | ★★☆ |
| **测试线** | 测试工程师×2、自动化测试×2 | ★★★ |
| **项目管理** | 项目经理×2、版本管理×2 | ★★★ |
| **运营线** | 数据分析师×2、游戏运营×2、游戏借鉴学习Agent×2 | ★★☆ |

## 🧠 每个岗位包含的内容

```yaml
岗位:
  - role_id: 岗位唯一标识
  - name: 中文名
  - department: 所属板块
  - level: 管理岗/执行岗/专家岗
  - personality: 角色性格特征（差异化核心）
  - responsibilities: 职责列表
  - tasks: 具体任务（含输入/流程/输出/触发条件）
  - workflows: 工作流程
  - collaboration: 协作关系（接收/发送/审批）
  - state_machine: 行为状态机
  - agent_logic: Agent行为逻辑（决策点/知识库/输出格式）
```

## ✨ 游戏借鉴学习 Agent（reference_learner）

`reference_learner` 是运营线新增的研究岗，负责**从其他游戏借鉴玩法经验，并以创意工坊模组（Mod）方式落地**。

它已在 `config/roles.yaml` 中完整定义（职责 / 任务 / 协作 / 状态机 / `agent_logic`），并引入**开源能力强化层**
（借鉴 dsh-routing-suite / superpowers / 科研方法）：

- **思维模式路由**：按任务自动路由到 spec/react/weak，不换模型即推高上限（见 `07-routing-modes.md`）
- **科研探索**：元学习、树探索、假设求证思维链、多 Agent 博弈（见 `08-scientific-exploration.md`）
- **探索多模式**：渠道×信息类型×深度三维档位（见 `09-exploration-modes.md`）
- **相似度校准**：控制借鉴相似度档位（一模一样/7成/只代码/只避坑）并多轮迭代（见 `10-calibration.md`）
- **可插拔强化 Mod**：强化能力封装为可注入/回滚的 Mod（见 `11-boost-usage.md`）

### 与通用基础设施的对接

`reference_learner` 基于升级后的通用内核 `agent_core.BaseAgent` 落地为可运行实现：

| 基础设施 | 对接方式 |
|---------|---------|
| `agent_core.BaseAgent` | `ReferenceLearnerAgent(BaseAgent)` 继承通用内核，覆写 `handle_task` 实现借鉴落地状态机 |
| `message_bus.MessageBus` | 通过总线收发 `TASK_ASSIGN` / `REVIEW_RESULT` / `ARTIFACT_DELIVERY` 等消息，与上下游岗位协作 |
| `task_scheduler.Scheduler` | 借鉴任务入调度队列，按优先级/依赖自动派发，完成/失败发布事件 |
| 强化层 `agent_boost` | 在 `DECIDE` 状态调用科研探索（树探索/博弈），在分析前调用探索规划，在构建后调用相似度校准 |

```bash
# 运行 reference_learner 的可运行实现（含演示）
python3 config/reference_learner_agent.py
```

## 🔄 迭代路线

- **v0.1** ✅ 岗位定义 + 行为逻辑框架
- **v0.3** ✅ 通用基础设施：消息总线 / Agent 内核 / 任务调度（解耦补充）
- **v0.4** ✅ reference_learner 对接基础设施，落地为可运行 Agent（复用强化层）
- **v0.5** 🔜 多 Agent 协作流水线（接入消息总线 + 调度器）
- **v0.6** 🔜 质量闭环与数据驱动

## 🚀 快速开始

查看岗位定义：
```bash
# 查看所有岗位定义
cat config/roles.yaml

# 查看角色分层预设体系（可扩展备用预设）
cat config/role_presets.yaml

# 查看Agent行为逻辑框架
cat config/agent_behavior.py

# 查看 reference_learner 可运行实现
cat config/reference_learner_agent.py

# 查看岗位体系调研报告
cat docs/岗位体系调研.md
```

---

**下一步迭代方向**：
1. ✅ 消息总线 / Agent 内核 / 任务调度已落地为可运行模块
2. ✅ reference_learner 对接基础设施并复用强化层，落地为可运行 Agent
3. 🔜 接入 `message_bus` + `task_scheduler`，建立「策划→程序→测试」自动流水线
