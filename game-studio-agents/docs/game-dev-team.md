# 游戏开发小组闭环引擎（Game Dev Team）

> 参考 `dongdongxiaozu/dongjiagoushi` 的 DevTeamEngine 与 **Goose** 开源项目的
> 「执行-验证-规划-监督」四维闭环，为**游戏开发程序线**落地「开发小组」机制——
> **多个角色循环的小组**（一套循环 N 个开发，默认 2），而非单个开发自己循环。

## 一、为什么需要开发小组

传统「单 Agent 自循环」（开发自己写码又自己判断"是否完成/是否继续"）极易陷入：

- **回声室效应**：自己写的代码自己评审，容易"自圆其说"
- **死循环**：依赖 LLM 自主决定"是否继续"，极易失控
- **进度漂移**：缺少客观验证与监督，进度难以核验

**Goose** 的多智能体框架正是为解决此问题引入**角色分工 + 层级审核**：
由确定性代码（Orchestrator）控制流转，而不是让 LLM 决定下一步。

## 二、Goose 四维闭环 → 游戏开发程序线映射

| Goose 角色 | 本仓库落地 | 职责 |
|:---|:---|:---|
| **Planner / Leader** | 技术总监（`cto`，小组长） | 定策略、拆任务、收尾整合；不参与具体编写 |
| **Coder / Executor** | N 个开发角色（默认 **2**） | 客户端/服务端/引擎/AI/工具链；只负责"做"，不负责"判" |
| **Reviewer / Critic** | 客观验证器（测试/lint/编译） | 独立于开发运行；只有"否决权" |
| **Orchestrator / Router** | `GameDevTeamEngine` 确定性状态机 | 非 LLM 的确定性代码；控制流转/超时/重试 |

> 代码实现：`config/game_dev_team.py`（`GameDevTeamEngine`）
> 接口 `run_dev_team()` 一站式运行一个开发小组闭环。

## 三、核心机制

### 3.1 一套循环 N 个开发（默认 2）

- `devs_per_team = 2`：一个开发小组 = 小组长（技术总监）+ **2 个开发**并行实现
- 辅助质量闸门（评审/测试）抽到小组外，**不挤占开发名额**
- 开发密度量化 `dev_ratio()`：默认 `2/(2+1) = 0.67`，开发实干占比过半

### 3.2 执行-验证分离

- 开发（Coder）只负责产出，**绝不自行裁定"我完成了"**
- 合格与否由**客观验证器**（测试/lint/编译/资源检查）裁定 → `APPROVED / REJECTED`

### 3.3 确定性状态机（Orchestrator）

```
execute → verify → (REJECTED → rework) / (APPROVED → fuse) → integrate → deliver
```

- `run_round()` 用**确定性代码**决定流转，不让 LLM 决定"下一步/是否结束"
- 全组开发产出 `APPROVED` 后，小组长（Leader）整合 `fuse` 为统一交付物

### 3.4 硬性熔断

- **单开发重做上限** `max_attempts`（默认 3）：超限上报 Leader 换方案（如换算法），不无限重试
- **总迭代上限** `max_iterations`（默认 20）：超限熔断
- **空闲超时** `max_idle_seconds`（默认 1800s）：判定卡死

### 3.5 进度北极星监督

- 每个开发写 `goal_meter`（完成度 0→goal_total），停滞/横跳/重复错误由哨兵拦截
- 过程只写**进度留痕**（rounds 记录），**不投递对话消息**给经理——经理零打扰

### 3.6 干完统一交付

- 全组通过后 `deliver_to_manager()` **一次性交付**给经理（含完整进度回放）
- 未通过客观验证（非 APPROVED）不可交付
- 若注入了 `bus`（消息总线），交付时自动发布 `ARTIFACT_DELIVERY` 消息给 `manager_role`（默认 producer），
  触发调度器下游解锁

### 3.7 确定性同步编排（架构说明）

> **`run_dev_team()` / `GameDevTeamEngine` 是"确定性同步编排"**，不是消息总线驱动的真实多 Agent 消息路由。
> 开发小组内部执行→验证→整合→交付全部由同步代码控制，**不经过 message_bus 分发子任务**。
> 这保证了流转的**确定性**（同样的输入必然产生同样的流转序列），
> 仅最终交付才通过消息总线通知 producer（若注入了 bus）。

**为什么这样设计**：
- 开发小组的核心价值是**确定性状态机**控制流转，而不是异步消息路由
- 让开发小组内部跑在同步代码中，避免异步竞态/回调地狱
- 外部仍然通过消息总线与 producer 集成（`ARTIFACT_DELIVERY` 通知）

## 四、程序线部门接入

`config/department_agents.py` 的 `ProgramDeptAgent` 已接入开发小组闭环：

- 新增 `_run_dev_team_loop()`：按模块自动选择小组内开发角色
  - `client` → 客户端 + 服务端
  - `server` → 服务端 + 引擎
  - `engine` → 引擎 + 客户端
  - `ai_logic` → 游戏AI + 引擎
  - `tools` → 工具链 + 客户端
- 执行工作包时先跑一套循环 2 个开发的确定性编排，再把闭环产出并入 artifact
- 日志留痕：`程序线开发小组闭环：2 开发，密度 0.67`

## 五、用法

```python
# 一站式运行一个开发小组闭环
from game_dev_team import run_dev_team
r = run_dev_team(
    {"id": "wp_a", "module": "client", "label": "战斗系统", "project": "Game"},
    dev_roles=["client_dev", "server_dev"],   # 一套循环 2 个开发
)
print(r["dev_count"], r["dev_ratio"], r["artifact"])

# 接入消息总线（交付时自动发布 ARTIFACT_DELIVERY）
from message_bus import MessageBus
bus = MessageBus()
r = run_dev_team(
    {"id": "wp_b", "module": "server", "label": "服务端", "project": "Game"},
    dev_roles=["server_dev", "engine_dev"],
    bus=bus, manager_role="producer",
)
```

```bash
# 自测冒烟
python3 config/game_dev_team.py

# 测试信号灯
bash tests/test_game_dev_team.sh
```

## 六、测试覆盖

`tests/test_game_dev_team.sh`（15 项信号灯）：

1. 一套循环 N 个开发（默认 2）
2. 执行-验证分离（客观验证器裁定）
3. 确定性状态机（代码控制流转）
4. 硬性熔断（超限上报 Leader）
5. 进度北极星监督（goal_meter 留痕）
6. 干完统一交付（含进度回放）
7. 开发密度量化（dev_ratio）
8. 程序线部门接入（ProgramDeptAgent）

已接入变更感知测试注册表 `hybrid/registry.json`（`test_game_dev_team.sh`）。

## 七、与 dongjiagoushi 的对应

| dongjiagoushi 机制 | 本仓库适配 |
|:---|:---|
| `dev_team.py` DevTeamEngine | `game_dev_team.py` GameDevTeamEngine |
| `devs_per_team=2` | `DEFAULT_DEVS_PER_TEAM = 2` |
| `dev_ratio()` 开发密度 | `dev_ratio()` 开发密度量化 |
| 一套4个角色当一个开发小组 | Leader + N 开发 + 客观验证器 + 确定性状态机 |
| Goose 四维闭环 | Planner/Coder/Reviewer/Orchestrator 完整映射 |
