# 01 · 开源项目探索报告

> 目标：深入探索 `Claude-Code-Game-Studios`（49 agents 协作开发游戏）与 `dongjiagoushi`（架构师框架），
> 明确哪些能力可同步复用、哪些需改版，为构建「游戏向架构师团队」提供依据。
>
> 执行者：CodeBuddy（游戏开发系列 Agent 体系）
> 场景：Issue #10「对比借鉴开源项目」

---

## 一、探索对象总览

| 项目 | 仓库 | 定位 | 规模 |
|------|------|------|------|
| **Claude-Code-Game-Studios** | `github.com/Donchitos/Claude-Code-Game-Studios` | 把单个 Claude Code 会话变成完整游戏开发工作室 | 49 agents · 73 skills · 12 hooks · 11 rules · 41 templates |
| **dongjiagoushi** | `cnb.cool/dongdongxiaozu/dongjiagoushi` | 官方 `@CodeBuddy` 化身「架构师」的模块化工程实践框架 | 架构八步 + 协作角色 + 数据底座（2500 并发） |

---

## 二、Claude-Code-Game-Studios 深度分析

### 2.1 三层工作室层级（49 agents）

项目按真实工作室组织，共 **3 层、49 个专用 subagent**：

```
Tier 1 — 总监层（Opus）
  creative-director（创意总监）   technical-director（技术总监）   producer（制作人）

Tier 2 — 部门主管层（Sonnet）
  game-designer   lead-programmer   art-director   audio-director
  narrative-director   qa-lead   release-manager   localization-lead

Tier 3 — 专家层（Sonnet/Haiku）
  gameplay-programmer  engine-programmer  ai-programmer  network-programmer
  tools-programmer  ui-programmer  systems-designer  level-designer
  economy-designer  technical-artist  sound-designer  writer  world-builder
  ux-designer  prototyper  performance-analyst  devops-engineer
  analytics-engineer  security-engineer  qa-tester  accessibility-specialist
  live-ops-designer  community-manager
  + 引擎专家：godot-*/unity-*/ue-*（Godot/Unity/Unreal 三套）
```

### 2.2 核心机制（可直接借鉴）

| 机制 | 说明 | 借鉴价值 |
|------|------|---------|
| **垂直委派** | 领导→主管→专家，复杂决策不跳级 | ⭐ 高：游戏向团队骨干 |
| **水平咨询** | 同层 agent 可互相咨询，但不可跨域做绑定决策 | ⭐ 高 |
| **冲突升级** | 设计冲突升级到 creative-director，技术冲突升级到 technical-director | ⭐ 高 |
| **变更传播** | 设计变更影响多域时由 producer 协调传播 | ⭐ 高 |
| **Gate 裁决** | 总监 gate（`CD-PILLARS`/`TD-*`）以 `[GATE-ID]: APPROVE/CONCERNS/REJECT` 令牌化输出 | ⭐ 高 |
| **文件即记忆** | `production/session-state/active.md` 活体检查点，跨压缩/崩溃恢复 | ⭐ 高 |
| **上下文预算** | 按任务类型分级（light/medium/heavy）管理 token | 中 |
| **MDA 框架** | Mechanics-Dynamics-Aesthetics 游戏设计分析 | ⭐ 高 |
| **创作理论** | 自我决定理论 / 心流 / Bartle 玩家类型 | ⭐ 高：游戏向核心 |
| **Model 分层** | Haiku/Sonnet/Opus 按复杂度分配 | 中 |

### 2.3 73 个 skills 分类（可直接复用的工作流）

- **Onboarding**：`/start` `/help` `/project-stage-detect` `/setup-engine` `/adopt`
- **Game Design**：`/brainstorm` `/map-systems` `/design-system` `/quick-design` `/review-all-gdds`
- **Art & Assets**：`/art-bible` `/asset-spec` `/asset-audit`
- **UX**：`/ux-design` `/ux-review`
- **Architecture**：`/create-architecture` `/architecture-decision` `/architecture-review` `/create-control-manifest`
- **Stories & Sprints**：`/create-epics` `/create-stories` `/dev-story` `/sprint-plan` `/sprint-status` `/story-done` `/estimate`
- **Reviews**：`/design-review` `/code-review` `/balance-check` `/content-audit` `/scope-check` `/gate-check` `/security-audit`
- **QA & Testing**：`/qa-plan` `/regression-suite` `/smoke-check` `/soak-test`
- **团队技能**：`/team-audio` `/team-combat` `/team-level` `/team-live-ops` `/team-narrative` `/team-polish` `/team-qa` `/team-release` `/team-ui`

### 2.4 待改版点（对游戏向架构师团队而言）

| 原项目能力 | 问题 | 改版方向 |
|-----------|------|---------|
| **Subagents / Agent Teams** | 基于 Claude Code 单会话 Task 机制，无跨会话长期协作 | 改版为 CNB 上可 `@` 召唤的 NPC 协作 + 数据库承载 |
| **creative-director** | 只管创作方向，无"架构师总览全局"的工程决策力 | 融合 dongjiagoushi「架构八步」，成为**游戏·架构·总师** |
| **producer** | 制作人只管排期/资源，无 DAG 调度、分形扩展、数据库底座 | 融合 dongjiagoushi「架构·经理」+ DAG/分形/数据底座，成为**游戏·制作经理** |
| **文件即记忆** | 单仓库文件，无结构化共享记忆、无版本整合、无 ACL | 改版为**共享记忆库**（结构化二次/三次整理内容，只增不改只追加） |
| **无数据库底座** | 协作靠文件，无法支撑大量并发 agent 互通 | 引入 dongjiagoushi 六表 + collab 多表数据库 |

---

## 三、dongjiagoushi 深度分析

### 3.1 架构八步方法论（⭐ 核心能力）

```
调研 → 顶层架构拓扑 → 可行性验证 → 工程实施方案 → 分工与协作规则
→ 进度对齐 → 索引建立 → 汇报与复盘
```
每步产出可核验交付物，关键节点 ⏸CP1/CP2/CP3 暂停确认点由人类把关。

### 3.2 可复用的模块化工程能力

| 模块 | 能力 | 对游戏向的价值 |
|------|------|--------------|
| **DAG 工作流**（graph.py） | 有向无环图，依赖满足即并行，非直线流水线 | ⭐ 高：游戏系统可并行开发 |
| **分形扩展**（fractal.py） | 开发任务分形为多小组并行，小组内可递归再分形 | ⭐ 高：大规模游戏团队 |
| **条件触发三层机制** | ① 显式声明 `[触发:X]`；② 语义向量触发；③ rules 固定触发 | ⭐ 高：正是用户要的"条件触发式引入角色" |
| **数据库底座**（data/） | 六表：agents/messages/tasks/progress/archives/stats；SQLite/PG 可切 | ⭐ 高：协作数据库支撑 |
| **协作引擎**（collab/） | entities/spaces/acl/versions/commits/requirements/skills/memory 多表；loc:// 寻址 | ⭐ 高：共享记忆 + 权限 |
| **经验记忆库**（memory/） | LanceDB/云端双兼容，MemoryRecord 统一向量格式，语义向量触发 | ⭐ 高：共享记忆检索 |
| **安全护栏** | ⏸CP 暂停点 + 回转/打断协议 | ⭐ 高 |
| **一库多角色** | 单一仓库共享架构/流水线/知识库，接力卡传上下文 | 中 |

### 3.3 待改版点（从通用工程 → 游戏向）

| 原能力 | 问题 | 改版方向 |
|--------|------|---------|
| **架构·总师** | 面向通用软件架构，无游戏领域认知 | 融入 CCGS 的 creative-director 创作方法论 + technical-director 技术 + 数值/关卡/经济等游戏域建模 |
| **架构·产品** | 通用需求澄清 | 改版为**游戏·策划**（承接玩法/系统/数值/关卡需求） |
| **架构·经理** | 通用调度 | 融合 CCGS producer，加游戏排期（里程碑/垂直切片/软封/硬封） |
| **架构·评审** | 通用代码评审 | 加游戏特有的平衡性评审、GDD 一致性评审、Game Feel 评审 |
| **架构·测试** | 通用测试 | 加游戏特有 playtest、性能/帧率、关卡可玩性、回归验证 |

---

## 四、融合方案：可同步复用清单

### 4.1 直接从 CCGS 同步复用（游戏领域能力）

1. **49 个游戏岗位 agent 定义** → 全部保留，作为专家层
2. **73 个 skills 工作流** → 全部保留，作为游戏工作流技能
3. **MDA 框架 / 创作理论 / 玩家心理** → 作为游戏向架构师的方法论底座
4. **Gate 裁决令牌化机制** → 游戏门禁
5. **文件即记忆 / 上下文管理** → 作为共享记忆的单仓库载体参考

### 4.2 从 dongjiagoushi 同步复用（工程协作能力）

1. **架构八步方法论** → 架构师核心流程
2. **DAG 工作流 + 分形扩展** → 游戏团队并行编排
3. **数据库底座（六表）+ 协作引擎（多表）** → 协作数据库支撑
4. **条件触发三层机制** → 按需引入角色
5. **经验记忆库 + 语义向量触发** → 共享记忆检索
6. **安全护栏 / 回转 / 打断协议** → 质量保障

### 4.3 需全新设计（改版 + 创新）

1. **游戏·架构·总师**：融合 creative-director + technical-director + 架构八步
2. **游戏·制作经理**：融合 producer + 架构·经理 + DAG/分形调度
3. **共享记忆机制**：结构化二次/三次整理内容 + 任务 + 技能，**只增不改只追加**（用户核心诉求）
4. **缓存优化**：共享部分只增不改不减，修改只追加，追加部分权重高

---

## 五、核心设计洞察（回答用户的核心诉求）

### 5.1 "灵活互相@协作而不丢失主线"
- 用 dongjiagoushi 的 **loc:// 寻址 + 实体解耦**，让 agent 可被独立 `@` 且不互相踩
- 用 **DAG + 分形** 保主线（总师/经理定主线，小组并行分支，统一向上交付）
- 用 **接力卡/版本整合** 让上下文跨会话不丢失

### 5.2 "常规流程 + 条件触发式引入角色"
- **常规流程**：架构八步 + 策划→程序→美术→测试→发布的 DAG 主流程（跑完整流程）
- **条件触发**：三层触发机制——缺数值就召数值策划、遇到平衡问题召经济设计师、平衡性差召 QA……

### 5.3 "共享记忆（结构化二次/三次整理内容 + 任务 + 技能）"
- 不是存完整对话，而是**整理后的结构化产物**：
  - 内容层：机制分析 / 系统设计 / 决策记录 / 里程碑结论（二次整理）
  - 任务层：任务卡 / 依赖 / 状态 / 验收（结构化任务）
  - 技能层：已验证的工作流 / playbook（可复用技能）
- 按**功能单位**共享（如"背包系统"一组记忆），不全局共享

### 5.4 "共享部分只增不改不减，修改只追加，追加部分权重高"
- 核心缓存设计：
  - **只增**：新经验只新增记录，不覆盖旧记录
  - **不改不减**：历史共享内容不可变（保证缓存命中率）
  - **修改只追加**：对某条记忆的修订，作为**新版本追加**到末尾，旧版本保留
  - **权重高**：最新追加版本检索权重更高（`version` 越大命中权重越高），保证时效性优先于历史命中率

---

## 六、结论

两个项目互补性极强：

- **Claude-Code-Game-Studios** 提供了**游戏领域纵深**（49 岗位 + 73 工作流 + 创作方法论），
  解决"游戏开发该有哪些角色、该怎么做"。
- **dongjiagoushi** 提供了**工程协作横梁**（架构八步 + DAG/分形 + 数据库 + 条件触发 + 记忆库），
  解决"这些角色怎么协作、怎么调度、怎么共享记忆、怎么不丢失主线"。

**融合产物 = 游戏向架构师团队**：以 dongjiagoushi 的工程协作骨架为底座，注入 CCGS 的游戏领域血肉，
并按用户的核心诉求（共享记忆只增不改只追加 + 缓存优化）做定制。

下一份文档（`02-game-architect-team.md`）给出完整的游戏向架构师团队设计。
