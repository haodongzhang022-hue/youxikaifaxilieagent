# 机制驱动自动化编排（Game Orchestration）

> 本文档说明本仓库如何通过**事件驱动机制**（而非手动 `/` 命令）自动推进游戏开发流程，
> 以及"游戏向经理"如何把架构蓝图拆解为部门工作包并完成资源分配与分工协作。

## 一、核心理念：机制驱动，非手动推进

本项目的流程推进**全部由平台事件机制自动触发**，无需人工手动发 `/` 命令去"推一下进度"。
协同依赖的是 **CI 流水线（.cnb.yml）+ 消息总线 + 任务调度器**，形成"事件 → 自动编排 → 自动协作 → 自动验收"的闭环。

```
事件触发（Issue/PR/合并） → 流水线 npc:go 唤醒游戏向经理
    → 拆解架构为部门工作包 → 分配任务/资源 → task_scheduler 按依赖派发
    → 部门 Agent 完成 → 事件解锁下游 → 验收 → 自动合并/更新 → 下一阶段
```

## 二、游戏向经理（GameProducerAgent）

### 角色定位

`game_producer_agent.py` 融合了 **制作人** 与 **项目经理** 的核心职责，是"游戏向经理"的可运行实现：

- **拆解架构**：把架构蓝图（愿景/技术架构/里程碑）拆解为部门可执行的工作包。
- **分配任务与资源**：为每个工作包指定责任部门、主责角色、协办角色与资源优先级。
- **分工协作**：通过 `task_scheduler` 建立部门间依赖，按依赖自动解锁下游部门，形成流水线。

### 六大部门协作

| 部门 | 承接模块 | 主责角色 | 产出 |
|------|---------|---------|------|
| 策划线 design | 玩法/系统、数值模型 | lead_designer 等 | 设计文档、数值表 |
| 程序线 program | 客户端、服务端、引擎、AI | cto、client_dev 等 | 代码、构建包 |
| 美术线 art | 美术风格、UI/UX、音频 | art_director 等 | 美术资源、UI 规范 |
| 测试线 qa | 功能/性能/自动化测试 | qa_engineer、auto_qa | 测试报告、Bug 清单 |
| 项目管理 pm | 版本/发版与里程碑 | project_manager | 版本计划、门禁结论 |
| 运营线 ops | 数据分析、借鉴学习 | data_analyst 等 | 数据报告、玩法 Mod |

> 部门角色表在 `boot()` 时从 `config/roles.yaml` **动态解析**，并对齐 `producer`（制作人）为
> 默认经理岗位（排除经理自派单），避免硬编码与架构约束偏离。

### 部门间依赖（自动解锁）

程序/美术依赖策划先给设计 → 测试依赖程序+美术产出 → 发版依赖测试通过 → 运营依赖全链路。
任一上游完成并验收，调度器自动解锁下游，**全程无需人工推进**。

### 运行

```bash
# 运行游戏向经理演示（架构拆解 → 部门分配 → 事件驱动派发）
python3 config/game_producer_agent.py
```

## 三、自动化编排流水线（.cnb.yml）

`.cnb.yml` 定义了全套事件驱动机制，覆盖从需求到合并的完整闭环：

| 触发事件 | 自动动作 | 说明 |
|---------|---------|------|
| `issue.open` | 游戏向经理 NPC 拆解架构并派单 | 新需求进来自动拆解分发 |
| `pull_request` | 测试信号灯 → 分配评审人 → NPC 评审 | 提交先跑断言，未通过即红灯阻塞 |
| `pull_request.mergeable` | 评审门禁 → `git:auto-merge` 自动合并 | 评审通过且无打回项才放行合并 |
| `pull_request.merged` | 解锁下游 + 更新 Issue | 合并后自动推进下一阶段 |
| `pull_request.changes_requested` | 返工协调派单 | 打回自动派返工任务 |

> 通过这套流水线，项目的每个阶段都会在事件触发后**自动推进**，
> 人工只需关注评审意见与里程碑验收，无需手动维护进度。

**两道机器护栏**（借鉴架构师 Agent）：
1. **测试信号灯**：PR 提交先跑 `test_producer_agent.sh`（12 项断言），断言失败即红灯阻塞，不放行评审/合并；
2. **合并门禁**：`pull_request.mergeable` 在 `git:auto-merge` 前增加评审门禁 NPC 校验，避免与 NPC 评审 / changes_requested 打回竞争。

> 所有 `npc:go` 阶段共用 `.cnb.yml` 中的 **YAML 锚点镜像**（`&npc_image` / `*npc_image`），
> 一处修改全局生效，保证供应链一致。

## 四、编排状态可观测与督导（v0.6.2）

- **打回仅阻塞 + 返工通知**：部门产出打回时仅 `queue.block`（不再产生 FAILED 瞬时态），并另发 `rework` 返工通知给责任部门。
- **终态保留**：`ACCEPT`（验收通过）/ `TRACK_DEPS`（打回跟踪）作为业务终态保留，`report()` 可真实反映最近一次验收结果，直至下一次编排重置。
- **心跳督导**：`heartbeat()` 定期扫描 `BLOCKED`/逾期工作包，向责任部门广播 `supervise` 督导通知，让"阻塞/逾期扫描"真正落地。

## 五、与通用基础设施的对接

游戏向经理基于升级后的通用内核落地：

| 基础设施 | 对接方式 |
|---------|---------|
| `agent_core.BaseAgent` | `GameProducerAgent(BaseAgent)` 继承通用内核，覆写 `handle_task` 实现编排状态机 |
| `message_bus.MessageBus` | 通过总线收发 `TASK_ASSIGN` / `REVIEW_RESULT` / `NOTIFICATION`，实现部门协作 |
| `task_scheduler.Scheduler` | 工作包入调度队列，按依赖自动派发，完成/失败发布事件解锁下游 |

## 六、迭代路线

- **v0.1** ✅ 岗位定义 + 行为逻辑框架
- **v0.3** ✅ 通用基础设施：消息总线 / Agent 内核 / 任务调度
- **v0.4** ✅ reference_learner 对接基础设施
- **v0.5** ✅ 游戏向经理 Agent：架构拆解 + 部门分工协作
- **v0.6** ✅ 机制驱动自动化流水线（.cnb.yml 事件驱动，非手动 / 命令）
- **v0.6.2** ✅ 打回仅阻塞+返工通知、状态终态可观测、岗位对齐 roles.yaml、心跳督导
- **v0.7** ✅ 多部门 Agent 端到端联动跑通全流程（六部门执行 Agent + 端到端编排）
- **v0.9** 🔜 统一可视化指挥中枢（信息分层模型 + 降熵聚合，见 [unified-command-center.md](./unified-command-center.md)）

---

## 七、多部门 Agent 端到端联动（v0.7）

v0.5/v0.6 只实现了「游戏向经理」的拆解与派发，但工作包派发后**没有真正的执行者**去接收、产出、回传，无法跑通「验收→解锁下游」闭环。
v0.7 补齐了这一关键短板：**为六大部门实现执行 Agent**，让部门真正承接并执行被派发的工作包。

### 7.1 六部门执行 Agent（`config/department_agents.py`）

| 部门 Agent | role_id | 承接模块 | 交付物 |
|-----------|---------|---------|-------|
| 策划线 | lead_designer | gameplay / numeric_model | 设计文档 |
| 程序线 | cto | client / server / engine / ai_logic | 代码 |
| 美术线 | art_director | art_direction / ui_ux / audio | 美术资源 |
| 测试线 | qa_engineer | testing | 测试报告 |
| 项目管理 | project_manager | release | 发版计划 |
| 运营线 | data_analyst | data_ops | 数据报告 |

**统一执行机制（`DepartmentAgent` 基类）**：
- 接收 `TASK_ASSIGN` 派单 → 从 `payload['work_package']` 取工作包；
- 调用子类 `execute_work_package` 产出部门交付物；
- 上报 `REVIEW_RESULT` 给经理 → 经理验收通过 → 调度器自动解锁下游；
- 接收 `rework` 返工通知 → 进入 `REWORK` 态重新加工，形成闭环。

> **关键约定**：每个部门只创建**单一 Agent 实例**（role 唯一），避免同 role 多实例
> 同时注册总线 handler 导致一条消息被重复消费（重复交付/重复解锁）。

### 7.2 端到端编排（`config/game_team_orchestration.py`）

把「游戏向经理 + 六部门执行 Agent」串成一条端到端流水线：

```
下发架构蓝图 → 经理拆解 12 个工作包 → 策划线（无依赖）先执行
  → 上报 REVIEW_RESULT → 经理验收 → 自动解锁程序/美术
  → 程序/美术执行 → 验收 → 解锁测试 → 解锁发版 → 解锁运营
  → 全部 DONE，形成「策划→程序→美术→测试→发版→运营」自动流水线
```

```bash
python3 config/game_team_orchestration.py   # 端到端联动演示（12 工作包全 DONE）
```

### 7.3 v0.7 测试信号灯（`tests/test_team_orchestration.sh`）

21 项断言覆盖：六部门 Agent 可启动、12 工作包全链路 DONE、依赖解锁正确、
验收→解锁→自动推进闭环、返工机制、同 role 单实例防重复消费。已接入 `.cnb.yml` 测试信号灯。

### 7.4 部门 Agent 接入机制化派单

真实场景下，部门 Agent 只需像端到端编排那样在总线注册后，
经理/调度器派发的工作包即可被自动接收执行——全程事件驱动、无人工 `/` 命令推进。
