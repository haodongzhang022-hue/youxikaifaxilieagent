# 游戏借鉴学习 Agent（Game Reference Learning Agent）设计

> 作为 `game-studio-agents` 岗位体系中的一个**运营/研究线岗位**，负责从其他游戏借鉴玩法经验，
> 并以"创意工坊模组（Mod）"方式落地到自有游戏。

## 1. 背景与目标

我们希望在自有游戏中引入一套"**从其他游戏借鉴玩法经验**"的机制——把其他游戏的优秀机制"读懂、拆解、迁移"，并以类似"**创意工坊模组**"的方式落到我们自己的游戏中。

这套机制由一个专属 Agent 全权负责，本设计文档定义该 Agent 的：

1. **能力（Capabilities）** —— 它能做什么
2. **行为逻辑（Behavior Logic）** —— 它如何决策与执行
3. **触发时机（Trigger Timing）** —— 什么时候被唤醒/调用

> 该 Agent 对应 `config/roles.yaml` 中的 `reference_learner` 岗位。

## 2. 核心心智模型：三层管线

借鉴机制本质上是"**理解 → 拆解 → 落地**"的流水线，对应 Agent 的三层心智：

```
┌────────────────────────────────────────────────────────────┐
│  输入层：目标游戏素材（视频 / 文档 / 代码 / 玩法描述 / 截图）  │
└───────────────────────────┬────────────────────────────────┘
                            ▼
┌────────────────────────────────────────────────────────────┐
│  L1 理解层（Game Comprehension）                           │
│   · 玩法机制识别  · 系统拆解  · 数值/循环  · 心智模型还原     │
└───────────────────────────┬────────────────────────────────┘
                            ▼
┌────────────────────────────────────────────────────────────┐
│  L2 迁移层（Reference Transfer）                           │
│   · 适配度评估  · 取舍裁剪  · 与自有游戏融合  · 创新点挖掘   │
└───────────────────────────┬────────────────────────────────┘
                            ▼
┌────────────────────────────────────────────────────────────┐
│  L3 落地层（Mod Implementation）                           │
│   · 模组化改造：视觉 / 展现 / 功能模块                      │
│   · 生成可执行 Mod 定义 · 预览与回滚                        │
└────────────────────────────────────────────────────────────┘
```

- **创意工坊模组化**：所有"借鉴落地"都以"**模组（Mod）**"为最小交付单元，与主游戏解耦、可插拔、可开关、可回滚。
- 三层之间由统一的 **Mod 描述规范（Manifest）** 串联，保证"理解结论"能无损地传递为"可落地改动"。

## 3. 本文档结构

| 文档 | 内容 |
|------|------|
| [01-capabilities.md](./01-capabilities.md) | 能力模块定义 |
| [02-behavior-logic.md](./02-behavior-logic.md) | 行为逻辑与决策流程 |
| [03-trigger-timing.md](./03-trigger-timing.md) | 触发时机与调度策略 |
| [04-mod-schema.md](./04-mod-schema.md) | 创意工坊模组（Mod）数据规范 |
| [05-workflow.md](./05-workflow.md) | 端到端工作流与示例 |
| [06-boost-capabilities.md](./06-boost-capabilities.md) | **强化层总览**（开源能力：dsh-routing-suite / superpowers） |
| [07-routing-modes.md](./07-routing-modes.md) | **思维模式路由强化**（spec/react/weak 三波段） |
| [08-scientific-exploration.md](./08-scientific-exploration.md) | **科研探索能力**（元学习/树探索/假设求证/多Agent博弈） |
| [09-exploration-modes.md](./09-exploration-modes.md) | **校验机制·探索多模式**（渠道广度×信息类型×探索深度） |
| [10-calibration.md](./10-calibration.md) | **校准机制·相似度控制**（相似度检测/档位控制/多轮迭代） |
| [11-boost-usage.md](./11-boost-usage.md) | **强化能力使用标注**（怎么用/何时用/如何开关·独立Issue跟踪） |

## 3.1 强化层（Capability Boost）

在既有三层管线之上，借鉴开源 Agent 能力强化技术栈（dsh-routing-suite 的思维模式路由与
注入器、superpowers 的方法论技能包），实现"不换模型、只靠提示词/插件工程推高上限"：

- **思维模式路由**（07）：按任务类型自动路由到 spec（计划-集体）/react（执行者）/weak（自分类），
  首请求锁定，过渡带回避。
- **科研探索**（08）：元学习（从借鉴中迭代策略）、树探索（多分支推演+剪枝）、
  假设求证思维链（先假设后求证）、多 Agent 博弈（不同思维链辩论评审）。
- **可插拔强化 Mod**：强化能力封装为可注入/回滚的 Mod（借鉴 dsh-super-injector）。

实现见 `config/agent_boost/`（路由预设、科研引擎、博弈评审配置）。

> **注意**：强化能力（boost：路由/科研探索/博弈）因其**功能独立、可单独使用**，已拆分为单独的
> Issue 跟踪其标注与用法（见仓库 Issues），不在本 Issue 的"借鉴管线"范围内混排。
> **使用标注见 [11-boost-usage.md](./11-boost-usage.md)**（怎么用/何时用/如何开关/分级/风险）。

## 3.2 校验与校准机制（探索多模式 + 相似度控制）

在进入分析前，`reference_learner` 先做**校验决策**（怎么探索），落地前做**校准控制**（像到什么程度）：

- **探索多模式**（09）：从多少渠道（single/multi/all）× 包含哪些信息类型（美术/视频/动效/数值/代码/心智/合规）× 多深（glance/dig/full）三维组合，内置 6 个档位，并支持"反向借鉴/避坑"模式。
- **相似度校准**（10）：可检测借鉴相似度（逐维度打分），可控制相似度档位（一模一样 / 7 成参考 / 只近似代码逻辑 / 只了解避免踩坑），并支持多轮迭代校准直到达到目标档位，且上线后持续校准。

实现见 `config/agent_boost/exploration_preset.yaml`、`config/agent_boost/calibration_preset.yaml` 与
`agent_behavior.py` 中的 `ExplorationPlanner`、`CalibrationEngine` 类。

## 4. 与岗位体系的关系

该 Agent 作为运营/研究线的一个新岗位 `reference_learner` 加入 `roles.yaml`，遵循既有岗位定义结构
（`role_id` / `responsibilities` / `tasks` / `state_machine` / `agent_logic`），
并复用全局协作规则与消息总线协议。详细岗位定义见 `config/roles.yaml`。

## 4.1 对接通用基础设施（v0.3）

`reference_learner` 已对接仓库升级后的通用基础设施（`agent_core` / `message_bus` / `task_scheduler`），
并落地为**可运行实现** `config/reference_learner_agent.py::ReferenceLearnerAgent`：

- **内核**：继承 `agent_core.BaseAgent`，获得生命周期 / 状态机 / 决策引擎 / 消息收发能力；
- **协作**：通过 `message_bus.MessageBus` 收发 `TASK_ASSIGN` / `REVIEW_RESULT` / `APPROVAL_REQUEST` 等消息，
  与制作人、上下游岗位协作；
- **调度**：通过 `task_scheduler.Scheduler` 将借鉴任务入队，按优先级 / 依赖自动派发；
- **强化层**：复用 `agent_behavior.CapabilityBoost` 统一入口，在对应阶段调用
  `plan_exploration`（探索规划）/ `tree_search` + `review_decision`（科研决策）/ `calibrate_similarity`（相似度校准）/ `reflect_learning`（元学习复盘）。

```bash
python3 config/reference_learner_agent.py   # 运行可运行实现（含端到端演示）
```
