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

### 支持的角色

| 角色 | 用途 |
|------|------|
| 游戏向经理 | 机制化拆解需求 / 派发部门工作包 / 推进协作 |
| 代码审查员 | 审查 PR 代码质量 / 架构 / 安全 |
| 合并确认员 | 确认已合并标签 Issue 是否可关闭 / 需新提任务 |
| CodeBuddy | 评审修复 / 手动指令处理 |

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
