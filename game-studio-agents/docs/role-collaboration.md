# 角色间协作层（Role Collaboration）：多角色互相 @ 转交 / 分工 / 协作

> 本文档描述本仓库新增的**多角色互相 @ 进行任务转交与分工协作**能力。
> 它是对现有"经理 → 部门"纵向派单的**横向补强**：任意角色（策划、程序、美术、
> 测试、运营，乃至经理自身）都能直接 @ 其他角色转交任务、请求协助、拆分分工。

## 一、为什么需要横向协作层

现有协作机制（`message_bus` + `task_scheduler` + `game_producer_agent`）解决的是
**纵向流水线**：经理拆解 → 按部门派单 → 依赖解锁 → 验收。这保证"生产 → 质检 →
协作 → 验收"的主干，但缺少**平级/跨角色之间直接互动**的能力：

| 现实协作场景 | 现有机制 | 本协作层补充 |
|-------------|---------|-------------|
| 数值策划发现需要玩法规则数据 | ❌ 只能等经理重派 | ✅ `@转交` 给系统策划 |
| 客户端实现卡在美术资源未到位 | ❌ 无法直接求助 | ✅ `@请求` 美术协助 |
| 战斗系统需多部门并行开发 | 经理统一拆包 | ✅ 任意角色可 `@分工` 拆子任务 |
| 接了转交任务但能力不足 | ❌ 无法退回 | ✅ `@退回` 给原主/再转交 |

## 二、核心能力

### 1. @转交（Task Transfer）
角色 A 把任务 @ 转交给角色 B，B 可：
- **接受**（`TRANSFER_ACCEPT`）：任务持有者变更为 B；
- **拒绝**（`TRANSFER_REJECT`）：任务仍归 A；
- **退回**（`TRANSFER_BACK` / CALLBACK）：B 无法完成时退回原发起人；
- **再转交**：B 发现自己也不合适，可继续 @ 给 C。

### 2. @协作请求（Collab Request）
角色 A @ 请求角色 B 协助某任务（带分工切分点/原因），B 响应接受或婉拒。

### 3. @分工拆解（Work Split）
角色（经理或任意成员）将一个**大任务** @ 拆分为多个**子任务**，分发给多个角色
并行协作，并汇总各子任务的承接进度。

### 4. 转交链留痕（Collab Ledger）
每次 @ 转交 / 分工 / 协作都写入**协作账本**，可查询任意任务的：
- `origin` 最初发起者；
- `owner` 当前实际持有者；
- `transfer_chain` 完整转交链（from → to → status → kind → reason），
  全程可审计、可回退。

## 三、代码入口

### 核心模块：`config/role_collaboration.py`

| 类 | 职责 |
|----|------|
| `CollabLedger` | 协作留痕账本：记录所有 @ 转交/协作/分工，可追溯转交链与回退 |
| `TransferCoordinator` | @转交协调器：transfer / accept / reject / transfer_back |
| `SplitCoordinator` | @分工协调器：split / ack / report_split |
| `RoleCollabHub` | 一站式入口：handoff / handback / delegate / ack_subtask / report |

### 接入经理 Agent：`config/game_producer_agent.py`
- `GameProducerAgent` 内置 `self.collab = RoleCollabHub(bus)`；
- `handle_task` 新增协作事件路由（`TASK_TRANSFER / WORKSPLIT / COLLAB_REQUEST` 等）；
- 便捷方法：`handoff_wp(wp_id, to_role, reason)` 转交工作包、
  `delegate_wp(wp_id, assignments)` 分工工作包。

## 四、快速使用示例

```python
from role_collaboration import RoleCollabHub
from task_scheduler import Task
from message_bus import MessageBus

bus = MessageBus()
hub = RoleCollabHub(bus)
bus.register("balance_designer"); bus.register("system_designer")

# 1) 数值策划 @转交 给系统策划
task = Task(id="wp_numeric", name="数值建模", owner="balance_designer")
hub.handoff("balance_designer", "system_designer", task,
            reason="需要玩法规则数据才能建模")
hub.accept_transfer("system_designer", "balance_designer", "wp_numeric")

# 2) 查看转交链
print(hub.report("wp_numeric"))
# -> {owner: "system_designer", origin: "balance_designer", transfer_chain: [...]}
```

## 五、测试信号灯

新增 `tests/test_role_collaboration.sh`（10 项断言），验证：
1. 模块可导入；
2. @分工生成 4 条子任务、4 角色全部承接；
3. @转交接受后 owner 变更；
4. @退回后 owner 恢复原主、转交链含 CALLBACK 留痕；
5. 经理 Agent 内置 collab 且能路由 @转交 / @分工 事件。

已接入 `.cnb.yml` 的 `pull_request` →「测试信号灯」阶段，随 PR 自动执行。
