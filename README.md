# youxikaifaxilieagent —— 游戏开发系列 Agent

本仓库承载"游戏开发系列 Agent"（Game Development Series Agents）的整体设计与实现。

核心框架位于 [game-studio-agents/](./game-studio-agents/)，
参考其 [README](./game-studio-agents/README.md) 了解岗位体系总览。

## 机制驱动自动化编排（游戏向经理）

本仓库流程推进**由事件机制驱动，非手动 / 命令**。

- **游戏向经理**（[game_producer_agent.py](./game-studio-agents/config/game_producer_agent.py)）：把架构蓝图拆解为部门工作包，按部门分配任务与资源，自动推进分工协作。
- **六部门执行 Agent**（[department_agents.py](./game-studio-agents/config/department_agents.py)）：策划/程序/美术/测试/项目管理/运营六大部门各一个执行 Agent，真正承接并执行被派发的工作包，产出交付物后上报验收。
- **端到端联动**（[game_team_orchestration.py](./game-studio-agents/config/game_team_orchestration.py)）：经理 + 六部门 Agent 串成流水线，跑通「策划→程序→美术→测试→发版→运营」全链路，验收→解锁下游→自动推进闭环（12 工作包全部 DONE）。
- **自动化流水线**（[.cnb.yml](./.cnb.yml)）：Issue 新建自动拆解派单、PR 提交自动评审、满足门禁自动合并、合并后自动解锁下游。
- **测试信号灯**（[test_producer_agent.sh](./game-studio-agents/tests/test_producer_agent.sh) 与 [test_team_orchestration.sh](./game-studio-agents/tests/test_team_orchestration.sh)）：借鉴架构师 Agent 护栏，对架构蓝图消费 / 打回阻塞 / 状态机 / 端到端联动等关键链路做断言，未通过即红灯阻塞。
- **系统化改进**（借鉴 [dongjiagoushi](https://cnb.cool/dongdongxiaozu/dongjiagoushi) 架构师方法论）：见 [docs/architect-improvement.md](./game-studio-agents/docs/architect-improvement.md)
- **详细说明**：见 [docs/game-orchestration.md](./game-studio-agents/docs/game-orchestration.md)
- **统一可视化指挥中枢**（渐进式 / 可溯源 / 降熵决策）：见 [docs/unified-command-center.md](./game-studio-agents/docs/unified-command-center.md)
- **信息接口层**（FastAPI，接口层与人工可视层分离：AI 读 `/ai/*`，前端读 `/dashboard/*`）：见 [docs/api-layer.md](./game-studio-agents/docs/api-layer.md)

```bash
# 运行游戏向经理演示
python3 game-studio-agents/config/game_producer_agent.py

# 运行六部门执行 Agent 演示
python3 game-studio-agents/config/department_agents.py

# 运行端到端联动（经理 + 六部门跑通全链路）
python3 game-studio-agents/config/game_team_orchestration.py

# 运行 v0.7 端到端联动测试信号灯
bash game-studio-agents/tests/test_team_orchestration.sh

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
