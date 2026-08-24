# 游戏向经理 Agent 系统化改进（借鉴架构师 Agent 方法论）

> 本文件由 `dongdongxiaozu/dongjiagoushi`（架构师 Agent）的「架构八步方法论 +
> 安全护栏 + 接力/回转/打断协议 + 测试信号灯」驱动，对本仓库"游戏向经理 Agent +
> 机制驱动编排"做一次系统性的研究与改进落地。

## 一、为什么借鉴架构师 Agent

跨库调研 `dongjiagoushi`（[公开](https://cnb.cool/dongdongxiaozu/dongjiagoushi)）发现，
其沉淀了一套成熟的架构工程化方法论，与本仓库"机制驱动、非手动推进"理念高度契合，可直接迁移强化：

| 架构师实践 | 本项目现状 | 改进价值 |
|-----------|-----------|---------|
| **架构八步方法论**（调研→拓扑→可行性→工程方案→分工→进度→索引→复盘） | 缺系统化的架构闭环 | 让每轮迭代有可核验交付物与留痕 |
| **CP1/CP2/CP3 暂停确认点** | 打回仅靠 `changes_requested` 事件 | 引入人类审批门禁，防止误合并 |
| **回转/打断协议** | 打回只阻塞不返工 | 支持 `[回转]` 打回重做、`[打断]` 断点续跑 |
| **测试信号灯（护栏）** | 无自动化验收断言 | 未真正跑通即红灯阻塞，防"半成品" |
| **Issue 模块版本管理** | 无模块能力演进线 | 支持模块阶段性多次加强 |
| **接力卡 / 三层触发** | 部门协作无强制触发 | 协作角色被硬约束而非靠自觉 |

## 二、八步方法论落地方案

### 2/8 顶层架构拓扑（本仓库现状）

```mermaid
flowchart TB
    subgraph 触发层
    E1[issue.open] --> E2[pull_request] --> E3[pull_request.mergeable]
    E3 --> E4[pull_request.merged]
    end
    subgraph 编排层
    G[游戏向经理 GameProducerAgent]
    end
    subgraph 执行层
    D1[策划线] --> D2[程序线/美术线] --> D3[测试线] --> D4[项目管理] --> D5[运营线]
    end
    subgraph 基础设施
    BUS[MessageBus] --- SCHED[TaskScheduler] --- CORE[BaseAgent]
    end
    E1 --> G --> SCHED
    SCHED --> D1
```

### 3/8 可行性验证结论

- **消息总线 + 调度器 + Agent 内核**：已可运行，评审 Bug 已修复（架构蓝图消费、打回阻塞、状态机告警）。
- **自动合并门禁**：已在 `pull_request.mergeable` 增加评审门禁 NPC 校验，避免与评审/打回竞争。
- **测试信号灯**：新增 `tests/test_producer_agent.sh`，对关键修复做静态/功能断言。

### 4/8 工程实施方案（本 PR 已落地）

| 改进项 | 落点 | 说明 |
|-------|------|------|
| 架构蓝图消费修复 | `game_producer_agent.py` | `build_task_assign` 入参在 `content['inputs']['architecture']`，修正读取路径并补断言 |
| 打回真正阻塞 | `game_producer_agent.py` | 打回时调用 `scheduler.on_fail` + `queue.block`，下游被真正阻塞 |
| 自动合并门禁 | `.cnb.yml` | `pull_request.mergeable` 前增加评审门禁 NPC 校验 |
| 状态机告警修复 | `agent_core.py` | `ANALYZING -> IDLE` 补入 `DEFAULT_TRANSITIONS` |
| 测试信号灯 | `tests/test_producer_agent.sh` | 5 项断言覆盖关键修复 |

### 5/8 分工与协作规则（改进方向）

- **回转协议**：部门产出打回后，经理把返工任务以 `[回转]` 重新派发给原部门，形成"打回 → 返工 → 重验"闭环，而非只阻塞。
- **接力卡**：部门工作包携带"任务书 + 输入上下文 + 输出契约"，保证跨角色无痕接手。
- **三层强制触发**：协作角色由显式声明 / 语义向量 / AGENTS.md 规则兜底触发，非纸面说明。

### 6/8 进度对齐（路线图）

| 阶段 | 内容 | 状态 |
|------|------|------|
| v0.5 | 游戏向经理：架构拆解 + 部门分工协作 | ✅ |
| v0.6 | 机制驱动自动化流水线（.cnb.yml 事件驱动） | ✅ |
| v0.6.1 | 评审修复 + 合并门禁 + 测试信号灯 | ✅ 本 PR |
| v0.7 | 多部门 Agent 端到端联动跑通全流程 | 🔜 |
| v0.8 | 接入回转/打断协议 + 经验记忆库 | 🔜 |

### 7/8 索引建立

- 关键代码：`game_producer_agent.py` / `agent_core.py` / `message_bus.py` / `task_scheduler.py`
- 流水线：`.cnb.yml` / `.cnb/settings.yml`
- 测试：`tests/test_producer_agent.sh`
- 文档：本文件 + `game-orchestration.md`

### 8/8 汇报与复盘

**本次改进**：修复 1 个关键功能 Bug + 2 个一致性/编排问题，引入"测试信号灯"与"合并门禁"两道机器护栏，
并验证跨库借用架构师方法论在本仓库可落地、可复用。

**风险与待办**：
1. 部门 Agent 目前多为框架级实现，端到端真实协作（v0.7）尚未跑通；
2. `[回转]`/`[打断]` 协议、经验记忆库（v0.8）为下一阶段演进项；
3. `.cnb.yml` 使用 `default-npc:latest`，生产环境建议固定镜像版本。

> 借鉴来源：`dongdongxiaozu/dongjiagoushi` 的 `架构八步方法论`、`测试信号灯`、`回转/打断协议`、`Issue 版本管理`。
