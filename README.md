# youxikaifaxilieagent —— 游戏开发系列 Agent

本仓库承载"游戏开发系列 Agent"（Game Development Series Agents）的整体设计与实现。

核心框架位于 [game-studio-agents/](./game-studio-agents/)，
参考其 [README](./game-studio-agents/README.md) 了解岗位体系总览。

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
