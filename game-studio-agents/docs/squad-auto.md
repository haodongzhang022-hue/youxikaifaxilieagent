# 可调配小组自动化调度 (SquadAutoScheduler)

> 在可调配小组池（SquadPool）基础上，实现「自动触发调配 + 自动释放」的完整自动化闭环。
> 解决「需要手动调用 `dispatch_to_squad()` / `release_squad()`」的痛点。

---

## 一、要解决的问题

**既有 SquadPool** 提供了「可被调配、不隶属部门、可重复调用、多组并行」的能力，但需要**手动**触发：

```python
# 手动调配
cap.dispatch_to_squad_by_domain("client_dev", wp, "程序线")
# 手动释放
cap.release_squad(squad_id)
```

这要求每个调用方都知道「何时调配」「何时释放」。**自动化模块**把这两个动作接入部门 Agent 执行流程，实现：

```
收到工作包 →（工作包声明 squad_domain）→ 自动调配小组 → 执行 → 自动释放回池
```

---

## 二、核心机制

### 1. 自动触发调配

当工作包携带 `squad_domain` 字段时，部门 Agent 收到该工作包后**自动**从小组池调配对应领域的小组执行：

```python
# 工作包声明需要可调配小组
wp = {
    "id": "wp_client_001",
    "label": "客户端 UI",
    "squad_domain": "client_dev",  # ← 声明需要可调配小组
}
```

触发规则：
- `work_package['squad_domain']` 存在 → 自动调配小组；
- 自动按领域匹配空闲小组（负载均衡：选 assign_count 最少者）；
- 无可用小组时**不阻塞**部门执行（部门走自身内部实现兜底）。

### 2. 自动释放

工作包执行完成（上报 REVIEW_RESULT）后，**自动**把调配的小组释放回池：

```python
# 无需手动调用，部门 Agent 在交付后自动执行
auto.auto_release_for_wp("wp_client_001")
```

设计要点：
- 工作包 id → 小组 id 映射留痕，完成后精确归还；
- 幂等：同一工作包重复释放不产生副作用；
- 容错：小组处于 BLOCKED 时不强制释放（保留待修复）。

### 3. 重复调用

小组释放后回到 `IDLE`，可被**其他部门/后续工作包**再次调配。每次调配 `assign_count` 递增留痕。

---

## 三、文件结构

```
config/
├── squad_auto.py          # 自动化调度核心（SquadAutoScheduler）
├── squad_pool.py          # 可调配小组池（既有，被自动化调度复用）
├── dispatch_capability.py # 统一派发能力（既有，自动化调度调用其派发）
└── department_agents.py   # 部门 Agent（接入自动触发/自动释放钩子）

docs/
└── squad-auto.md          # 本文档

tests/
└── test_squad_auto.sh     # 自动化调度测试信号灯
```

---

## 四、接入方式

### 对部门 Agent（自动）

在 `department_agents.py` 的 `DepartmentAgent` 基类中已接入：
- `_auto_squad_dispatch(work_package)`：收到工作包时自动触发调配；
- `_auto_squad_release(work_package_id)`：工作包完成后自动释放。

**无需额外编码**：只要工作包声明了 `squad_domain`，部门 Agent 就会自动从小组池调配小组执行。

### 对调度器/经理（可选手动）

任何持有 `DispatchCapability` 的 Agent 可手动调用：
```python
auto = SquadAutoScheduler(squad_pool=pool)
auto.auto_acquire_and_dispatch(wp, cap, department="程序线")
auto.auto_release_for_wp(wp["id"])
```

---

## 五、测试

```bash
cd game-studio-agents
bash tests/test_squad_auto.sh
```

覆盖场景：
1. 自动触发调配（工作包声明 squad_domain）
2. 自动释放（工作包完成后归还小组）
3. 重复调用（同一小组被再次调配）
4. 未声明 squad_domain 不触发
5. 无可用小组不阻塞部门执行
6. 与既有 SquadPool / DispatchCapability 回归
