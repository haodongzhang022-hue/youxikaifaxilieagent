# 06. 开源能力强化层（Open-Source Capability Boost）

> 在既有 `reference_learner` 三层管线（理解 L1 → 迁移 L2 → 落地 L3）之上，
> 引入**开源 Agent 能力强化技术栈**（dsh-routing-suite / superpowers），
> 实现"**不换模型、只靠提示词与插件工程，把模型能力往目标方向推高上限**"。

## 1. 为什么要"强化"而不是"换模型"

用户明确提出的思路是：**"相当于没换模型但往那个方向做，其实就相当于有了加强"**。
这一思路与 dsh-routing-suite 论文的核心实测结论完全吻合：

> 前沿推理模型（DeepSeek V4 Flash 0731，见 config/model_config.py · Issue #126 统一）沿"persona 轴"（从计划优先的 spec 条件 → 执行者的
> react 条件）的行为**不是连续可调**的，而是坍缩到少数稳定区。同一模型在正确的
> 提示词条件下，分数可以从 91/6 提升到 99/96（维护）或 10/10（绿地构建）——
> **约 10 分的差距完全由提示词条件造成，与模型能力无关**。

结论：**提示词/插件条件是路由，不是优化，而是刚需。** 正确路由 = 模型能力的"上限放大器"。

## 2. 借鉴的三大开源能力源

| 开源项目 | 定位 | 本岗位借鉴的核心能力 |
|---|---|---|
| [dsh-routing-suite](https://github.com/yjh051108/dsh-routing-suite) | 注入器 × 思维模式路由套装 | ① 三波段思维模式路由（spec/react/weak）② 近场引导 + 深度自适应 ③ 模式隔离子代理 |
| [dsh-router-standard](https://github.com/yjh051108/dsh-router-standard) | 思维模式路由预设（P1-P23 实测） | ④ 双吸引子行为策略 ⑤ 首请求路由锁定 + 路径承诺 ⑥ 会话内自优化工具 |
| [dsh-super-injector](https://github.com/yjh051108/dsh-super-injector) | 运行时模组注入器 | ⑦ 强化能力做成可插拔 Mod（注入/热重载/回滚）⑧ agent 自管理运行时 |
| [superpowers (obra)](https://github.com/obra/superpowers) | 软件工程方法论技能包 | ⑨ 方法论工作流（brainstorm/planning/并行子Agent/TDD）⑩ 自动触发式技能 |

## 3. 强化层如何叠加到三层管线上

原三层管线管"**做什么**"（理解/迁移/落地），强化层管"**用什么思维方式做**"和"**做到多深**"：

```
┌────────────────────────────────────────────────────────────────┐
│                强化层（Capability Boost Layer）                  │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────────┐  │
│  │ 思维模式路由  │ │ 科研探索引擎 │ │  可插拔强化 Mod 层        │  │
│  │ (Routing)    │ │ (Research)  │ │  (Boost Injector)      │  │
│  │ spec/react/  │ │ 元学习/树探索│ │  方法论技能 / 注入器/回滚 │  │
│  │ weak 三波段   │ │ 假设求证/博弈│ │                         │  │
│  └─────────────┘ └─────────────┘ └─────────────────────────┘  │
└──────────────────────────┬─────────────────────────────────────┘
                           ▼
┌────────────────────────────────────────────────────────────────┐
│          既有三层管线（Reference Learning Pipeline）            │
│      L1 理解层 → L2 迁移层 → L3 落地层（Mod 实现）              │
└────────────────────────────────────────────────────────────────┘
```

## 4. 三个强化子层的能力映射

### 4.1 思维模式路由层（对应 dsh-router-standard 三波段）

为 `reference_learner` 的每个任务自动路由到最匹配的**思维模式**：

| 任务类型 | 路由模式 | Persona 方向 | 核心工具面 | 适用阶段 |
|---|---|---|---|---|
| 机制理解 / 系统拆解 / 数值还原 | **spec**（计划-集体，读优先） | "helpful software engineer" + 计划/探索 | read/glob/grep | L1 理解 |
| 适配评估 / 取舍 / 合规审查 | **spec** 或 **weak** | 计划 + 分类 | read/glob/grep | L2 迁移 |
| Mod 构建 / 功能开发 / 视觉改造 | **react**（执行者，写优先，免仪式） | "hands-on doer，deliver fast" | read/write/edit | L3 落地 |
| 复合/模糊借鉴任务 | **weak**（模型自分类） | 中性 + classify-then-act | 全量 | 任意 |

关键规则（继承论文结论）：
- **首请求路由锁定**：第一个请求就锁定模式，中途不切换（路径承诺）。
- **过渡带回避**：mixed/过渡带不自动选择，只在显式调试时进入。
- **外部路由**：模式选择必须来自外部（分类器），模型无法可靠自路由。

### 4.2 科研探索层（用户特别要求：元学习/树探索/假设求证/多Agent博弈）

| 能力 | 说明 | 应用到借鉴流程 |
|---|---|---|
| **元学习（Meta-learning）** | Agent 从"如何借鉴"中学习，优化自己的借鉴策略 | 每次借鉴结束后反思"评估标准是否准确"，迭代契合度阈值与取舍规则 |
| **树探索（Tree Search）** | 借鉴决策分叉成树，多假设并行探索，按置信度剪枝 | 对一个机制提出多个落地分支（如 keep/trim/adapt 各一），分别推演收益/成本 |
| **假设求证思维链（Hypothesis-Verify CoT）** | 先提假设 → 收集证据 → 验证/推翻 → 收敛 | 对每个借鉴点"先假设它契合/不契合"，用证据（玩家反馈/数据/竞品）求证 |
| **多Agent博弈（Multi-agent debate）** | 不同思维链/不同 persona 的 Agent 对同一决策辩论、评审、投票 | 用"辩手(react) vs 评审(spec) vs 怀疑者(weak)"三视角审查借鉴决策 |

### 4.3 可插拔强化 Mod 层（对应 dsh-super-injector + superpowers）

- 每个强化能力（路由预设、科研引擎、方法论技能）封装为**可独立开关、注入、回滚的 Mod**。
- 复用既有 `04-mod-schema.md` 的 Mod 规范，但作用于"Agent 自身的强化能力"而非"游戏玩法"。
- 借鉴 superpowers：方法论技能自动触发（如"收到借鉴任务 → 自动走 brainstorm→plan→execute"）。

## 5. 与既有设计的兼容

- 不替换既有 `reference_learner` 岗位定义，只在 `agent_logic` 中**追加**强化配置。
- 强化层遵循既有状态机（IDLE → ANALYSIS → ASSESS → DECIDE → BUILD_MOD → SANDBOX_VERIFY → REVIEW_COMMIT → ARCHIVING），在**各阶段内部**应用思维模式与科研引擎。
- 强化能力默认 **L1（可辅助）**，随信任度升级到 L2/L3，仍遵守人机共治。

## 6. 交付物清单

| 位置 | 内容 |
|---|---|
| `docs/reference-learning-agent/06-boost-capabilities.md` | 本文档：强化层总览 |
| `docs/reference-learning-agent/07-routing-modes.md` | 思维模式路由强化设计 |
| `docs/reference-learning-agent/08-scientific-exploration.md` | 科研探索能力设计 |
| `config/agent_boost/routing_preset.yaml` | 三波段路由预设（persona + 工具面 + 分类器） |
| `config/agent_boost/research_engine.py` | 科研探索引擎（元学习/树探索/假设求证/多Agent博弈） |
| `config/agent_boost/debate_reviewer.yaml` | 多 Agent 博弈评审配置 |
| `config/roles.yaml` | `reference_learner` 岗位追加强化层配置 |
| `config/agent_behavior.py` | 增加思维模式路由与多 Agent 博弈机制 |

## 7. 参考文献

1. [dsh-routing-suite](https://github.com/yjh051108/dsh-routing-suite) — 注入器 × 思维模式路由套装
2. [dsh-router-standard](https://github.com/yjh051108/dsh-router-standard) — 思维模式路由预设与论文（P1-P23 实测）
3. [dsh-super-injector](https://github.com/yjh051108/dsh-super-injector) — 运行时模组注入器
4. [superpowers](https://github.com/obra/superpowers) — 软件工程方法论技能包
