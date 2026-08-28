# youxikaifaxilieagent —— 游戏开发系列 Agent

本仓库承载"游戏开发系列 Agent"（Game Development Series Agents）的整体设计与实现。

核心框架位于 [game-studio-agents/](./game-studio-agents/)，
参考其 [README](./game-studio-agents/README.md) 了解岗位体系总览。

## 机制驱动自动化编排（游戏向经理）

本仓库流程推进**由事件机制驱动，非手动 / 命令**。

- **游戏向经理**（[game_producer_agent.py](./game-studio-agents/config/game_producer_agent.py)）：把架构蓝图拆解为部门工作包，按部门分配任务与资源，自动推进分工协作。
- **自动化流水线**（[.cnb.yml](./.cnb.yml)）：Issue 新建自动拆解派单、PR 提交自动评审、满足门禁自动合并、合并后自动解锁下游。
- **测试信号灯**（[test_producer_agent.sh](./game-studio-agents/tests/test_producer_agent.sh)）：借鉴架构师 Agent 护栏，对架构蓝图消费 / 打回阻塞 / 状态机等关键链路做断言，未通过即红灯阻塞。
- **系统化改进**（借鉴 [dongjiagoushi](https://cnb.cool/dongdongxiaozu/dongjiagoushi) 架构师方法论）：见 [docs/architect-improvement.md](./game-studio-agents/docs/architect-improvement.md)
- **详细说明**：见 [docs/game-orchestration.md](./game-studio-agents/docs/game-orchestration.md)
- **统一可视化指挥中枢**（渐进式 / 可溯源 / 降熵决策）：见 [docs/unified-command-center.md](./game-studio-agents/docs/unified-command-center.md)
- **信息接口层**（FastAPI，接口层与人工可视层分离：AI 读 `/ai/*`，前端读 `/dashboard/*`）：见 [docs/api-layer.md](./game-studio-agents/docs/api-layer.md)
- **统一派发工作能力**（所有 Agent 共享的高频复用模块）：见 [docs/dispatch-capability.md](./game-studio-agents/docs/dispatch-capability.md)
  - 统一开发，每个 Agent（经理/部门/生态/CodeBuddy）都具备派发能力；
  - 包含用法规则（何时派发/派发给谁/派发什么）与使用时机；
  - 实现：[config/dispatch_capability.py](./game-studio-agents/config/dispatch_capability.py)

```bash
# 运行游戏向经理演示
python3 game-studio-agents/config/game_producer_agent.py

# 启动信息接口层（AI 机器接口 + 可视化通用接口）
pip install -r game-studio-agents/api/requirements.txt
python3 game-studio-agents/api/main.py   # http://localhost:8000/docs
```

## 当前聚焦：游戏借鉴学习 Agent

当前首个聚焦的子 Agent 为 **游戏借鉴学习 Agent（Game Reference Learning Agent）**，
负责从其他游戏借鉴玩法经验，并以"创意工坊模组（Mod）"方式落地到自有游戏。

- **岗位定义**：见 [config/roles.yaml](./game-studio-agents/config/roles.yaml) 中的 `reference_learner`
- **详细设计**：见 [docs/reference-learning-agent/](./game-studio-agents/docs/reference-learning-agent/)
  - [能力模块](./game-studio-agents/docs/reference-learning-agent/01-capabilities.md)
  - [行为逻辑](./game-studio-agents/docs/reference-learning-agent/02-behavior-logic.md)
  - [触发时机](./game-studio-agents/docs/reference-learning-agent/03-trigger-timing.md)
  - [Mod 数据规范](./game-studio-agents/docs/reference-learning-agent/04-mod-schema.md)
  - [端到端工作流](./game-studio-agents/docs/reference-learning-agent/05-workflow.md)

## 跨仓库 NPC 召唤指南

本仓库的 NPC 角色（游戏向经理 / 代码审查员 / CodeBuddy）可在**其它仓库**跨仓库召唤，
无需在本仓库内操作。跨仓库 `@` 调用平台已原生支持，格式如下：

```
@dongdongxiaozu/youxikaifaxilieagent(角色名) 需求描述
```

### 支持的角色（按流水线顺序排列）

**核心编排角色**

| 角色 | 用途 |
|------|------|
| 游戏向经理 | 机制化拆解需求 / 派发部门工作包 / 推进协作 |
| 代码审查员 | 审查 PR 代码质量 / 架构 / 安全 |
| CodeBuddy | 评审修复 / 手动指令处理 |
| 合并确认员 | 确认已合并标签 Issue 是否可关闭 / 需新提任务 |

**六大部门 NPC（按流水线顺序）**

| 部门 | 部门内角色 | 用途 |
|------|-----------|------|
| 策划线 | 主策划/系统策划/数值策划/关卡策划/剧情策划/战斗策划 | 玩法/系统/数值/关卡/剧情/战斗设计 |
| 程序线 | 技术总监/客户端/服务端/引擎/AI/工具链 | 客户端/服务端/引擎/AI/工具链开发 |
| 美术线 | 主美/原画/建模/动画/特效/UI/TA/音频 | 原画/建模/动画/特效/UI/TA/音频 |
| 测试线 | 测试工程师/自动化测试 | 功能/性能/自动化测试 |
| 项目管理 | 项目经理/版本管理 | 项目排期/资源协调/版本发布 |
| 运营线 | 数据分析/竞品调研/游戏运营 | 数据分析/竞品调研/游戏运营 |

> **部门 = NPC 小组 · 统一头机制**：每个部门都是一个 NPC 小组，以部门名为**统一头**
> 对外承接，`@仓库(策划线)` 相当于一次 @ 部门内多个角色（系统策划/数值策划等）。
>
> **组内协作（必做）**：部门头收到跨角色任务后，经协作工作台把子任务 **@分工** 拆派给
> 部门内各角色执行，全程留痕可审计（见 `group_audit`）。
>
> **跨部门协作（必做）**：任务需要其他部门协助时，部门间可 **@协作请求/转交**
> （如策划线 @程序线 评审技术方案），复用协作工作台 `request_peer`。
>
> 该机制复用「@ 其他 agent 安排记忆和任务」的复用能力 + 协作规则，代码实现见
> `department_agents.py`（DepartmentAgent 统一头）、`dispatch_capability.py`
> （`dispatch_to_department`）、`role_collaboration.py`（协作工作台）。

> **流水线已接通（非仅声明）**：六大部门 NPC 已在 `.cnb.yml` 配置对应的 `npc:go`
> 执行阶段——`issue.open`（游戏向经理拆解派单后按部门执行）与
> `pull_request.merged`（合并后下游解锁执行）两条链路各含 6 个部门执行阶段。
> 游戏向经理 `@部门名` 派发工作包后，流水线会真正驱动对应部门 NPC 承接执行
> （组内协作拆派 + 跨部门协作 + 上报验收），不再是"只声明、无执行"的断档。
> 护栏：`tests/test_dept_npc_pipeline.sh` 校验每个注册部门在 `.cnb.yml` 都有
> 对应 npc:go 阶段，防止再断档。

**跨部门服务圈（非六大执行部门）**

| 角色 | 用途 |
|------|------|
| 协作支持圈 | 进度督导 + 合并确认等跨部门服务（催进度 / 确认合并） |

> 协作支持圈**不属于**六大执行部门，是跨部门服务圈，服务于所有部门。

**部门内可@的具体角色（按优先级）**

- **策划线**：制作人 / 主策划 / 系统策划 / 数值策划 / 关卡策划 / 剧情策划 / 战斗策划
- **程序线**：技术总监 / 客户端程序员 / 服务端程序员 / 引擎程序员 / 游戏AI程序员 / 工具链程序员
- **美术线**：主美 / 原画师 / 3D建模师 / 动画师 / 特效师 / UI-UX设计师 / 技术美术 / 音频设计师
- **测试线**：测试工程师 / 自动化测试工程师
- **项目管理**：项目经理 / 版本管理
- **运营线**：数据分析师 / 游戏运营 / 游戏借鉴学习Agent

### 合并标签确认机制

仓库通过定时探查自动确认已打上「已合并」标签但仍 open 的 Issue，判断是否还有
内容需要推进。机制类似审查机制（探查合并标签 Issue 个数，数量 > 0 即触发确认）：

- **合并确认员**（[merged_confirm_agent.py](./game-studio-agents/config/merged_confirm_agent.py)）：
  独立于 CodeBuddy，专责确认环节；
- 已合并且无后续任务 → **关闭** Issue；
- 已合并但有明确后续任务（未派发）→ **新建 Issue 承接**并分配任务，关闭原 Issue；
- 已合并但仍有阻塞/待复核/依赖未收尾 → **保留** Issue。

```bash
# 运行合并确认 Agent 自测
python3 game-studio-agents/config/merged_confirm_agent.py

# 运行测试信号灯
bash game-studio-agents/tests/test_merged_confirm_agent.sh
```

### 让角色出现在 `@` 选择器（可点选，无需手敲全名）

CNB 平台的 `@` 选择器只收录「已关注仓库中的 NPC」。要让角色自动补全、直接点选：

1. **关注（Star）本仓库** `dongdongxiaozu/youxikaifaxilieagent`（及需要召唤的其它仓库）；
2. 关注后，在本仓库或其它仓库输入 `@`，选择器即可检索到本仓库已注册的 NPC 角色，
   输入角色关键词（如"经理""审查")还能自动联想补全；
3. 直接点选或手敲 `@slug(角色名)` 即可跨仓库调用。

> 若在 `@` 选择器里没看到角色，通常是因为**尚未关注该仓库**——关注后即建立关联。
> 相关角色配置见 [.cnb/settings.yml](./.cnb/settings.yml)。

## 通用 Agent 身份自适应模块（AgentIdentity）

本仓库所有 Agent（CodeBuddy / 代码审查员 / 游戏向经理 / 合并确认员）在需要
`@` 召唤其他角色时，**必须**先通过 [agent_identity.py](./game-studio-agents/config/agent_identity.py)
自适应识别当前仓库上下文，再据此生成正确的召唤格式。

### 为什么需要自适应

被外部仓库跨仓库召唤时，当前仓库的 slug 可能是任意 `owner/repo`，**不能写死**。
`agent_identity.py` 从 CNB 环境变量（`CNB_REPO_SLUG` / `CNB_GROUP_SLUG` / `CNB_REPO_NAME`）
自动探测当前仓库，据此生成正确的 `@owner/repo(角色名)` 格式。

### 核心能力

| 能力 | 说明 |
|------|------|
| `detect_repo_context()` | 从环境变量 / git remote 自动探测仓库（owner + repo + slug） |
| `build_mention(role, slug)` | 生成 `@owner/repo(角色名)` 召唤格式 |
| `decide_mention_strategy()` | 判断同仓库 vs 跨仓库，给出正确策略 |
| `get_codebuddy_mention()` | 获取本仓库 CodeBuddy 的完整召唤格式 |
| `get_handler_mention()` | 获取本仓库处理专员的完整召唤格式 |

### 使用方式

```python
from agent_identity import get_identity

identity = get_identity()
ctx = identity.detect_repo_context()
print(ctx.full_slug)  # 如 "dongdongxiaozu/youxikaifaxilieagent"

mention = identity.get_codebuddy_mention()
# "@dongdongxiaozu/youxikaifaxilieagent(CodeBuddy)"
```

### 跨仓库 vs 同仓库

- **同仓库**：可直接 `@角色名`，但建议仍用完整格式消除歧义；
- **跨仓库**：**必须**用完整格式 `@owner/repo(角色名)` 带壳召唤，
  否则会被路由到系统级或他仓 NPC，导致权限受限。

### 测试

```bash
# 运行自适应模块自测
python3 game-studio-agents/config/agent_identity.py

# 运行测试信号灯
bash game-studio-agents/tests/test_agent_identity.sh
```

---

## 🎮 引擎桥接层（Engine Bridge）

> 面向 **Windows + Cocos Creator + Unreal Engine 5** 引擎环境的统一桥接架构。
> 通过 **MCP（Model Context Protocol）** 和 **引擎插件** 控制引擎，
> 为游戏开发 Agent 系统提供引擎能力访问的标准化接口。

**核心设计**：
- **统一抽象**：Agent 使用同一套 `EngineCommand` 与 Cocos/UE5 交互，无需关心底层差异；
- **MCP 优先**：首选通过 MCP 协议与引擎 MCP Server 通信；
- **插件补充**：MCP 不可用时降级到引擎原生插件；
- **Windows 适配**：面向 Windows 环境的路径探测与端点管理；
- **测试可验证**：35 项测试信号灯覆盖全部模块。

```bash
# 运行引擎桥接层测试
bash game-studio-agents/tests/test_engine_bridge.sh
```

详见 [game-studio-agents/docs/engine-bridge/README.md](./game-studio-agents/docs/engine-bridge/README.md)。

---

## 功能模块验收测试体系

本仓库建立了**以功能模块为单位**的验收测试体系。每个功能模块有独立的测试脚本，
验收以实际运行测试断言为唯一依据。

### 功能模块划分

| # | 功能模块 | 测试脚本 | 断言数 |
|---|---------|---------|-------|
| 1 | 消息总线 | `tests/modules/test_mod_message_bus.sh` | 9 |
| 2 | 任务调度 | `tests/modules/test_mod_task_scheduler.sh` | 9 |
| 3 | Agent 内核 | `tests/modules/test_mod_agent_core.sh` | 7 |
| 4 | Agent 身份自适应 | `tests/modules/test_mod_agent_identity.sh` | 6 |
| 5 | 角色协作层 | `tests/modules/test_mod_collaboration.sh` | 8 |
| 6 | 统一派发能力 | `tests/modules/test_mod_dispatch.sh` | 8 |
| 7 | 游戏向经理 | `tests/modules/test_mod_game_producer.sh` | 9 |
| 8 | 部门 Agent | `tests/modules/test_mod_department_agents.sh` | 11 |
| 9 | 进度督导 | `tests/modules/test_mod_progress_pusher.sh` | 9 |
| 10 | 发版质量门禁 | `tests/modules/test_mod_release_gate.sh` | 7 |
| 11 | 生态角色 | `tests/modules/test_mod_ecosystem_roles.sh` | 6 |
| 12 | 美术线生态角色 | `tests/modules/test_mod_art_ecosystem.sh` | 16 |
| 13 | 预设实例化 | `tests/modules/test_mod_instantiator.sh` | 6 |
| 14 | 合并确认 | `tests/modules/test_mod_merged_confirm.sh` | 7 |
| 15 | 借鉴学习 | `tests/modules/test_mod_reference_learner.sh` | 4 |
| 16 | 端到端联动 | `tests/modules/test_mod_end_to_end.sh` | 6 |

**合计：16 个功能模块，128 项断言。**

### 运行方式

```bash
# 一键运行全部功能模块测试
bash game-studio-agents/tests/modules/test_all_modules.sh

# 单独运行某个功能模块
bash game-studio-agents/tests/modules/test_mod_message_bus.sh
```

每个模块验收通过 = 实际运行测试脚本所有断言通过。测试在 CI 流水线中自动执行，
未通过即阻塞合并。
