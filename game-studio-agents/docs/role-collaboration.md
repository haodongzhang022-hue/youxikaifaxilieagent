# 角色间协作层 · 多角色互相@（任务转交 + 分工协作）

## 一、背景与目标

在多人/多 Agent 协作体系中，仅支持「经理→部门」的**纵向派单**是不够的。真实的协作开发中，
**任意角色之间**都需要能够互相 **@** 进行：

- **任务转交**：A 把任务 @ 转交给 B，B 可接受 / 拒绝 / 退回 / 再转交
- **分工协作**：A 把一个大任务 @ 拆分为多个子任务，分发给多个角色**并行协作**，并汇总进度
- **协作请求**：A @ 请求 B 协助当前任务（双向补充）

本层提供一套**可审计、可回退、状态机约束**的协作能力，让多角色互相@ 的转交与分工真正落地。

## 二、核心能力

| 能力 | 事件类型 | 说明 |
|------|---------|------|
| **@转交** | `HANDOFF` | 角色 A 把任务转交给 B，记录 `transfer_chain` |
| **@分工** | `DELEGATE` | A 把一个任务拆为多子任务分发给多角色并行协作，汇总进度 |
| **@协作请求** | `COLLAB_REQ` | A 请求 B 协助某任务 |
| **@回执** | `ACK` | 承接方处理：`ACCEPT` / `REJECT` / `RETURN` / `COMPLETE` / `REHANDOFF` |
| **进度通知** | `COLLAB_NOTIFY` | 分工进度汇总与协作状态广播 |

### 转交/分工承接状态机

```
OFFERED（已发出）→ ACCEPTED（接受）/ DECLINED（拒绝）
ACCEPTED → IN_PROGRESS（执行）→ DONE（完成）/ RETURNED（退回）
RETURNED → OFFERED（可再转交） / DONE
任意环节持有者可 REHANDOFF（再转交）给第三位角色
```

### 转交链留痕

每次转交都记录 `origin`（发起者）→ `owner`（当前持有者）→ `transfer_chain`（转交链），
全程可**审计**、可**回退**（`RETURN` 回到上一持有者）。

## 三、文件与接入

### 文件

| 文件 | 作用 |
|------|------|
| `config/role_collaboration.py` | 协作能力层（`CollaborationWorkbench`） |
| `config/game_producer_agent.py` | 经理 Agent 接入：`self.collab` + 便捷方法 |
| `tests/test_role_collaboration.sh` | 测试信号灯（15 项断言，已接入 CI） |

### 经理 Agent 接入方式

```python
from game_producer_agent import GameProducerAgent

m = GameProducerAgent(bus=bus)
m.boot()

# 1) @转交工作包
m.handoff_wp("wp_client", "system_designer", "client_dev", title="客户端界面")

# 2) @分工工作包（并行协作）
m.delegate_wp("wp_testing", "project_manager",
              [{"role": "qa_engineer", "desc": "功能测试"},
               {"role": "auto_qa", "desc": "自动化回归"}],
              title="全量测试")

# 3) 查询协作状态（审计）
m.collab_status("wp_client")
```

### 任意角色直接使用 `CollaborationWorkbench`

```python
from role_collaboration import CollaborationWorkbench
wb = CollaborationWorkbench()

# @转交
wb.handoff("task_1", "标题", "A", "B", note="说明")

# 承接方处理
wb.acknowledge("task_1", "B", "ACCEPT")            # 接受
wb.acknowledge("task_1", "B", "REJECT", reason="忙")  # 拒绝
wb.acknowledge("task_1", "B", "REHANDOFF", reassign_to="C")  # 再转交
wb.acknowledge("task_1", "B", "RETURN", reason="需求不明确")  # 退回

# @分工
wb.delegate("task_2", "标题", "PM",
            [{"role": "qa", "desc": "功能"}, {"role": "auto", "desc": "回归"}])
wb.sub_ack("task_2", "task_2__sub1", "qa", "ACCEPT")
wb.sub_ack("task_2", "task_2__sub1", "qa", "COMPLETE")
print(wb.sub_progress("task_2"))   # 分工进度汇总

# 审计
print(wb.audit("task_1"))          # 转交链 + 全事件留痕
```

## 四、对接消息总线

`game_producer_agent.py` 的 `handle_task` 已增加协作事件路由：

```python
if msg.type in ("HANDOFF", "DELEGATE", "COLLAB_REQ", "ACK", "COLLAB_NOTIFY"):
    self._on_collab_event(msg)
```

协作事件通过 `message_bus` 传递，`build_message` 构造即可触发。

## 五、测试验证

```bash
bash game-studio-agents/tests/test_role_collaboration.sh
# 测试信号灯结果: 15 通过 / 0 失败 🟢
```

覆盖：@转交 / 接受 / 拒绝 / 再转交 / 退回 / @分工 / 分工进度 / @协作请求 / 转交链留痕审计 / 经理接入。
