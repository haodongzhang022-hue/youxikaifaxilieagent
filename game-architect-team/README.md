# 🎮 游戏向架构师团队（game-architect-team）

> 融合 **Claude-Code-Game-Studios**（49 agents 游戏开发工作室）+ **dongjiagoushi**（架构师工程协作框架），
> 构建一套**面向游戏开发的多 agent 架构师团队**。这是 Issue #10「对比借鉴开源项目」的落地成果。

## 核心能力

| 能力 | 说明 |
|------|------|
| **游戏向架构师** | 架构师从通用软件架构改版为**游戏系统架构**（玩法/数值/关卡/经济全链路），融合 CCGS creative-director + technical-director + dongjiagoushi 架构八步 |
| **引擎阶段化** | 架构绑定**游戏引擎**（Cocos/Unity/UE）与**游戏阶段**；阶段边界检查「阶段不对就算错」，防 Cocos 阶段做 UE 阶段的事 |
| **游戏·架构·总师助理** | 参考 dongjiagoushi 总师助理：专责改错改框架 + 引擎阶段纠偏，保总师主线上下文纯净 |
| **渐进式资产库** | 协议(Protobuf)/配置表/核心算法三层资产跨阶段复用，换引擎只换零件不推翻重来 |
| **游戏向经理** | 经理融合 CCGS producer + dongjiagoushi 经理，做**游戏排期**（里程碑/垂直切片/软硬封）+ DAG 调度 + 分形小组并行 |
| **常规流程 + 条件触发** | 常规跑完整流程（架构→策划→程序→美术→测试→发行）；条件触发按需引入角色（三层触发机制） |
| **数据库支撑** | agents/messages/tasks/progress/archives/stats + collab 多表，SQLite/PG 可切 |
| **共享记忆** | 以功能单位为粒度，存**结构化二次/三次整理内容 + 任务 + 技能**，非完整记忆 |
| **缓存优化** | 共享部分**只增不改不减，修改只追加**，追加部分权重更高（relevance×weight） |

## 目录结构

```
game-architect-team/
├── README.md                          # 本文件
├── docs/
│   ├── 01-exploration-report.md       # 开源项目探索报告（CCGS + dongjiagoushi）
│   ├── 02-game-architect-team.md      # 游戏向架构师团队设计（架构师/经理改版）
│   ├── 03-shared-memory.md            # 共享记忆机制设计（只增不改只追加）
│   ├── 04-game-engine-staged-architecture.md  # ⭐ 游戏引擎阶段化架构指南（Cocos/Unity/UE + 阶段边界）
│   └── 05-framework-dev.md            # 框架开发测试记录
├── config/
│   └── team.yaml                      # 团队角色 + DAG 流水线 + 条件触发映射 + 共享记忆配置
└── src/
    ├── shared_memory.py               # ⭐ 共享记忆库（不可变 + 只追加 + 权重）
    └── game_team_demo.py              # 游戏向团队端到端演示（作为测试）
```

## 快速验证

```bash
# 1. 共享记忆机制自测（只增不改不减 + 修改只追加 + 权重递增）
python3 src/shared_memory.py

# 2. 游戏向架构师团队端到端演示（架构→策划→程序→测试 + 条件触发 + 共享记忆）
python3 src/game_team_demo.py
```

## 关键设计（对应 Issue #10 诉求）

1. **灵活互相@协作而不丢失主线** → DAG 主线 + 分形小组 + 接力卡/版本整合
2. **架构师和经理改版** → 游戏·架构·总师（游戏系统架构）+ 游戏·架构·总师助理（引擎阶段纠偏/改框架）+ 游戏·制作·经理（游戏排期调度）
3. **常规流程 + 条件触发** → 三层触发机制（含阶段越界→总师助理语义触发）
4. **引擎阶段化** → 架构绑定引擎与阶段，阶段边界检查「阶段不对就算错」，DAG 主线含 stage_gate 阶段边界审查
5. **渐进式资产库** → 协议/配置表/核心算法跨阶段复用，换引擎不推翻重来
6. **数据库支撑** → 六表 + collab 多表
7. **共享记忆（功能单位 + 结构化整理 + 任务 + 技能）** → 非完整记忆
8. **缓存优化（只增不改只追加 + 权重）** → immutable + append-only + weight

## 与现有 game-studio-agents 的关系

本设计是现有 `game-studio-agents`（游戏开发岗位体系）的**架构升级版**：
- 复用其完整游戏岗位定义（roles.yaml）
- 注入 dongjiagoushi 的架构师协作骨架（DAG/分形/数据库/条件触发/共享记忆）
- 形成「游戏岗位体系 × 架构师协作框架」融合
