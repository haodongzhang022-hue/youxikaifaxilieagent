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
│   └── reference-learning-agent/  # 游戏借鉴学习 Agent 设计（能力/行为逻辑/触发时机/Mod规范/强化层）
├── config/
│   ├── roles.yaml               # Agent 岗位定义文件（职责/任务/协作/状态机，含 reference_learner 强化层）
│   ├── agent_behavior.py        # Agent 行为逻辑框架（决策/通信/协作/异常 + 强化层机制）
│   └── agent_boost/             # 能力强化层（思维模式路由 / 科研探索 / 博弈评审）
│       ├── routing_preset.yaml  #   三波段思维模式路由预设（spec/react/weak）
│       ├── research_engine.py   #   科研探索引擎（元学习/树探索/假设求证/多Agent博弈）
│       └── debate_reviewer.yaml #   多 Agent 博弈评审配置
└── README.md                    # 本文件
```

## 🎭 岗位体系总览（六大板块）

| 板块 | 岗位 | Agent化优先级 |
|------|------|-------------|
| **策划线** | 制作人、主策划、系统策划、数值策划、关卡策划、剧情策划、战斗策划 | ★★★ |
| **程序线** | 技术总监、客户端、服务端、引擎、AI、工具链 | ★★★ |
| **美术线** | 主美、原画、3D建模、动画、特效、UI/UX、TA、音频 | ★★☆ |
| **测试线** | 测试工程师、自动化测试 | ★★★ |
| **项目管理** | 项目经理、版本管理 | ★★★ |
| **运营线** | 数据分析师、游戏运营、**游戏借鉴学习Agent** | ★★☆ |

## 🧠 每个岗位包含的内容

```yaml
岗位:
  - role_id: 岗位唯一标识
  - name: 中文名
  - department: 所属板块
  - level: 管理岗/执行岗/专家岗
  - responsibilities: 职责列表
  - tasks: 具体任务（含输入/流程/输出/触发条件）
  - workflows: 工作流程
  - collaboration: 协作关系（接收/发送/审批）
  - state_machine: 行为状态机
  - agent_logic: Agent行为逻辑（决策点/知识库/输出格式）
```

## 🔄 迭代路线

- **v0.1** ✅ 岗位定义 + 行为逻辑框架
- **v0.2** 🔜 Agent 消息通信协议实现
- **v0.3** 🔜 单个 Agent 自动执行
- **v0.4** 🔜 多 Agent 协作流水线
- **v0.5** 🔜 质量闭环与数据驱动
- **v0.8** 🔜 能力强化层（思维模式路由 + 科研探索 + 可插拔强化Mod）

## ✨ 强化层（Capability Boost）

`reference_learner` 岗位已引入**开源能力强化层**（借鉴 dsh-routing-suite / superpowers）：

- **思维模式路由**：按任务自动路由到 spec/react/weak，不换模型即推高上限（见 `07-routing-modes.md`）
- **科研探索**：元学习、树探索、假设求证思维链、多 Agent 博弈（见 `08-scientific-exploration.md`）
- **可插拔强化 Mod**：强化能力封装为可注入/回滚的 Mod

## 🚀 快速开始

查看岗位定义：
```bash
# 查看所有岗位定义
cat config/roles.yaml

# 查看Agent行为逻辑框架
cat config/agent_behavior.py

# 查看岗位体系调研报告
cat docs/岗位体系调研.md
```

---

**下一步迭代方向**：
1. 选定 1-2 个核心岗位（如系统策划、QA），实现其 Agent 化的最小可用版本
2. 设计 Agent 间消息通信协议（消息总线）
3. 建立开发→测试的自动流水线
