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
│   ├── reference-learning-agent/  # 游戏借鉴学习 Agent 设计（能力/行为逻辑/触发时机/Mod规范/强化层）
│   ├── game-orchestration.md      # 游戏向经理 + 机制驱动自动化编排
│   ├── unified-command-center.md  # 统一管理与可视化指挥中枢（降熵/渐进式/可溯源）
│   └── api-layer.md               # 信息接口层（接口层与人工可视层分离）
├── config/
│   ├── roles.yaml               # Agent 岗位定义文件（职责/任务/协作/状态机，含 reference_learner 强化层）
│   ├── role_presets.yaml        # ⭐ 角色分层预设体系（角色级/技术栈级/小组级，按需启用）
│   ├── project_type_presets.yaml # ⭐ 项目类型/产品阶段/团队规模选型预设（与 role_presets 互补）
│   ├── agent_behavior.py        # Agent 行为逻辑框架（决策/通信/协作/异常 + 强化层机制）
│   ├── agent_core.py            # ⭐ 通用 Agent 内核基类（生命周期/状态机/决策，v0.3，可运行）
│   ├── message_bus.py           # ⭐ 通用消息总线（事件驱动通信，v0.3，可运行）
│   ├── task_scheduler.py        # ⭐ 任务队列与事件驱动调度器（优先级/依赖，v0.3，可运行）
│   ├── game_producer_agent.py   # ⭐ 游戏向经理 Agent（架构拆解→部门分工→机制驱动派发，v0.1，可运行）
│   ├── department_agents.py     # ⭐ 六大部门 Agent（策划/程序/美术/测试/项目管理/运营，v0.1，可运行）
│   ├── run_end_to_end.py        # ⭐ 多部门 Agent 端到端联动（策划→程序→美术→测试→发版→运营，v0.1，可运行）
│   ├── preset_instantiator.py   # ⭐ 预设实例化器（选型→实例化预设为正式角色→组装团队，v0.8，可运行）
│   └── agent_boost/             # 能力强化层（思维模式路由 / 科研探索 / 博弈评审 / 探索 / 校准）
│       ├── routing_preset.yaml  #   三波段思维模式路由预设（spec/react/weak）
│       ├── research_engine.py   #   科研探索引擎（元学习/树探索/假设求证/多Agent博弈）
│       ├── debate_reviewer.yaml #   多 Agent 博弈评审配置
│       ├── exploration_preset.yaml # 探索多模式预设（渠道×类型×深度）
│       └── calibration_preset.yaml # 相似度控制与多轮迭代校准预设
├── api/                        # ⭐ 信息接口层（FastAPI，接口层与人工可视层分离，v0.9，可运行）
│   ├── models.py               #   四层信息模型（L0总览/L1聚合/L2明细/L3原始）
│   ├── aggregator.py           #   降熵聚合引擎（聚类/折叠/摘要 + 判断生成）
│   ├── runtime.py              #   运行时快照提取（bus/scheduler/manager → 统一快照）
│   ├── app.py                  #   FastAPI 应用（/ai/* 机器接口 + /dashboard/* 可视化接口）
│   ├── main.py                 #   启动入口
│   ├── requirements.txt        #   依赖
│   └── test_api.sh             #   接口层测试信号灯
├── tests/
│   ├── test_producer_agent.sh   #   编排逻辑测试信号灯
│   ├── test_instantiator.sh     #   预设实例化器测试信号灯（v0.8）
│   └── test_end_to_end.sh       #   多部门 Agent 端到端联动测试信号灯（v0.7）
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
python3 config/department_agents.py  # 六大部门 Agent：策划/程序/美术/测试/项目管理/运营
python3 config/run_end_to_end.py   # 多部门 Agent 端到端联动（全链路自动跑通）
```

**设计原则**：三者互相解耦、可独立替换；`agent_core` 与 `task_scheduler` 依赖 `message_bus` 作为统一通信层，但彼此不互相依赖，方便架构师审查后按需重组。

## 🎮 游戏向经理与机制驱动编排

> 新增 `game_producer_agent.py`：把架构蓝图拆解为部门工作包，按部门分配任务与资源，
> 并通过 `message_bus` + `task_scheduler` 事件驱动自动推进部门协作，全程无需手动 / 命令。
> 详见 [docs/game-orchestration.md](./docs/game-orchestration.md)。

```bash
# 运行游戏向经理演示（架构拆解 → 部门分配 → 事件驱动派发）
python3 config/game_producer_agent.py
```

## 📌 进度督导（Progress Pusher · 程序规则化 + 声明化策略）

> 协作支持圈角色：**盯 DDL、主动催、识别阻塞并升级**。v1.0 把 v0.2 的独立演示
> 升级为**可生效**的督导 Agent（三层设计，见 [docs/进度督导使用指南.md](./docs/进度督导使用指南.md)）：
> - **程序规则化**（`config/progress_pusher.py`）：继承 `BaseAgent`，复用 `TaskQueue/MessageBus`，
>   用 `DecisionEngine` 规则引擎做确定性决策（WATCH / PUSH / WARN / ESCALATE），接入总线真正生效；
> - **声明化策略**（`config/progress_pusher_policy.yaml`）：阈值/节奏/打扰成本可调，**不碰代码**；
> - **skill/用法**（`docs/进度督导使用指南.md`）：稳定可用的部署与使用说明。

```bash
# 运行进度督导演示（4 类场景：WATCH/PUSH/ESCALATE/WARN）
python3 config/progress_pusher.py

# 进度督导测试信号灯（已接入 .cnb.yml CI 护栏）
bash tests/test_progress_pusher.sh
```

> **生效链路**：`TaskQueue`（任务状态）→ 督导扫描 → `DecisionEngine` 规则决策 → `MessageBus`
> 发出催办/升级通知给 owner / 项目经理。打扰成本由冷却期 + 最大催办次数控制，避免过度打扰。

## 🌐 信息接口层（接口层与人工可视层分离）

> 新增 `api/`：以 FastAPI 提供**信息接口层**。核心设计是**接口层与人工看的层分离**——
> - **AI 读取 → 调 `/ai/*` 机器接口**（结构化、低冗余、聚合、可溯源）；
> - **人类查看 → 前端调 `/dashboard/*` 通用接口**渲染（L0-L3 渐进式展开）。
>
> 二者共用同一套**降熵聚合引擎**，但 AI 接口聚焦"决策所需最小充分信号"，避免 AI 每次
> 读取都混入人类偏好展示内容，从而减少无效上下文、提升效率。
> 详见 [docs/api-layer.md](./docs/api-layer.md)。

```bash
# 启动信息接口层（AI 机器接口 + 可视化通用接口）
pip install -r api/requirements.txt
python3 api/main.py   # http://localhost:8000/docs

# 接口层测试信号灯
bash api/test_api.sh
```

## 🎭 角色分层预设体系（可扩展备用预设）

> **背景**：为支持可扩展性，无需把每种可能都做成正式角色（每个岗位 >3 个会过度膨胀）。
> 本体系把**同一岗位/岗位族的多种变体**作为**备用预设**预置，按需启用。

定义文件：`config/role_presets.yaml`，分**三个层级**（已大幅扩充）：

| 层级 | 类型 | 说明 | 示例（含扩充） |
|------|------|------|------|
| **L1** | 角色级预设 `role_presets` | 针对单个岗位的变体（风格/技术栈/侧重） | 美术风格（像素/水墨/赛博朋克/PBR/Toon/体素/扁平/2.5D/剪影/蒸汽朋克/水彩/哥特/街机/Q版/黑色电影/手绘/剪纸）、玩法侧重（肉鸽/生存/开放世界/射击/卡牌/MOBA/派对/塔防/叙事/解谜/竞速/音律/放置/模拟/大逃杀/社交）、技术栈（UE5/Unity/Godot/React/Vue/页面引擎/Go/Java/Node/Python/Rust/渲染/数据/云原生/LLM-AI/音频/测试自动化/原生移动端） |
| **L2** | 技术栈级预设 `stack_presets` | 针对程序线岗位族的整套技术方案 | UE5生态 / Godot生态 / Web(React) / 页面引擎 / Unity生态 / AI智能体 / 数据云原生 / **Node.js生态** / **Rust高性能** / **原生移动端** |
| **L3** | 小组级预设 `team_presets` | 面向某一生态组织的小组，可整体启用 | UE5小组 / Godot小组 / Web前端小组 / 页面引擎小组 / Unity小组 / AI智能体小组 / 质量自动化小组 / 运营增长小组 / **Node实时对战小组** / **Rust高性能小组** / **原生移动端小组** / **内容本地化小组** / **美术资产管线小组** |

**启用方式（按需求启用即可）**：
1. **只读参考**：读取 preset 字段并入现有正式角色
2. **实例化**：将 preset 复制为 `roles.yaml` 中的正式角色（`status: agent_enabled`）
3. **小组编排**：通过 L3 `team_presets` 组合多角色/技术栈，作为一组 Agent 整体启用

> **可扩展约定**：预设为**轻量定义**，只给差异化字段（personality/风格/技术栈/工具链/侧重），
> 复用 `base_role` 的正式定义（responsibilities/tasks/状态机），从而支持低成本横向扩展。

## 🎯 项目类型/产品阶段/团队规模预设（选型维度）

> `role_presets.yaml` 解决"这个岗位/技术栈要配什么样的变体"；
> 本文件补充另一层可扩展维度，回答"**这个类型的项目 / 这个产品阶段 / 多大团队，应启用哪些岗位与侧重**"，二者可叠加组合。

定义文件：`config/project_type_presets.yaml`，分**三个维度**（已扩充）：

| 维度 | 类型 | 说明 | 示例 |
|------|------|------|------|
| **P1** | 项目类型预设 `project_types` | 按平台/形态组织的选型建议 | 移动端手游 / PC/主机 / 网页H5 / 小游戏 / 独立游戏 / AI创新 / **VR-AR沉浸式** / **教育严肃游戏** |
| **P2** | 产品阶段预设 `phases` | 按生命周期组织的投入侧重 | 原型验证 / 正式开发 / 上线发布 / 长线运营 / **停运过渡** |
| **P3** | 团队规模预设 `team_scales` | 按团队体量组织的岗位配置 | **极简团队(1-5)** / 小团队(5-15) / 中型(15-60) / 大型(60+) |

**组合用法**：先按项目类型选 P1 → 按产品阶段选 P2 → 按团队规模选 P3 → 再叠加 `role_presets.yaml` 的技术栈/风格角色。

```
移动端手游(P1) + 开发阶段(P2) + 中型团队(P3) → team_unity + team_quality_automation + Unity技术栈角色
VR/AR(P1) + 原型验证(P2) + 小团队(P3)       → team_unity + team_quality_automation + 空间交互角色
AI创新(P1) + 开发阶段(P2) + 中型团队(P3)     → team_ai_agent + team_unity + LLM/AI技术栈角色
独立游戏(P1) + 原型阶段(P2) + 极简团队(P3)  → team_godot + team_ai_agent + 多面手角色预设
```

> **可扩展约定**：与 role_presets 一致为备用预设（`status: preset_standby`），按需启用；
> 本文件只做选型建议、不新增正式角色，通过引用 role_presets 的 preset_id / team_preset_id 组合启用，天然支持横向扩展。

## 🔧 预设实例化器（选型 → 实例化 → 项目团队组装，v0.8）

> 承接 v0.8「预设实例化 → 真实项目团队组装与联动」：把 role_presets / project_type_presets 中选中的**备用预设，实例化为 `roles.yaml` 的正式角色**（`status: agent_enabled`），并按**六大部门**组装成可直接被 `GameProducerAgent` / 部门 Agent 承接调度的项目团队。

定义文件：`config/preset_instantiator.py`

**核心能力**（链式选型 + 一键实例化）：

```python
from preset_instantiator import PresetInstantiator

inst = PresetInstantiator().load()
inst.apply_project_type("ptype_mobile_game")  \   # P1 项目类型
    .apply_phase("phase_production")          \   # P2 产品阶段
    .apply_team_scale("scale_medium")         \   # P3 团队规模
    .select_team("team_unity")                \   # L3 小组
    .select_stack("stack_unity_ecosystem")    \   # L2 技术栈
report = inst.instantiate()                       # 实例化并组装团队
```

**实例化规则**（呼应预设"轻量定义"约定）：
- 取 `base_role` 的完整定义（responsibilities/tasks/state_machine/agent_logic），叠加预设的差异化字段（personality/风格/技术栈）；
- `role_id` 追加后缀（如 `client_dev_unity_1`），`status` 置为 `agent_enabled` 参与调度；
- 按 L3 小组 composition + L2 技术栈 scope + P1 项目类型/P2 阶段关键角色，自动补齐**六大部门**（策划/程序/美术/测试/项目管理/运营），保证团队可联动。

**与 v0.7 多部门 Agent 端到端联动的协同**：实例化产出的正式角色按 `game_producer_agent.DEPARTMENTS` 的部门键（design/program/art/qa/pm/ops）组装，可直接被部门 Agent / 经理按工作包承接，从而把「预设选型」与「多部门端到端联动」两条线打通成同一条流水线。

```bash
python3 config/preset_instantiator.py            # 运行自测（Unity小组示例场景）
bash game-studio-agents/tests/test_instantiator.sh  # 实例化测试信号灯
```

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
- **v0.5** ✅ 游戏向经理 Agent：架构拆解 + 部门分工协作（game_producer_agent.py）
- **v0.6** ✅ 机制驱动自动化编排（.cnb.yml 事件驱动，非手动 / 命令）
- **v0.6.2** ✅ 编排状态可观测与督导：打回仅阻塞+返工通知、状态终态保留、岗位对齐 roles.yaml、心跳督导、镜像锚点复用
- **v0.7** 🔜 多部门 Agent 端到端联动跑通全流程

## 🚀 快速开始

查看岗位定义：
```bash
# 查看所有岗位定义
cat config/roles.yaml

# 查看角色分层预设体系（可扩展备用预设）
cat config/role_presets.yaml

# 查看项目类型/产品阶段/团队规模选型预设
cat config/project_type_presets.yaml

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
