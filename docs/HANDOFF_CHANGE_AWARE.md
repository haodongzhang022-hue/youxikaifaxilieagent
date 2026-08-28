# 变更范围感知机制 · 交接索引文档

> 仓库：dongdongxiaozu/youxikaifaxilieagent
> 背景：参考 dongdongxiaozu/dongjiagoushi#74（架构师体系）的「变更范围感知」机制，
>       为消除 PR 推送全量跑测试脚本造成的 CPU 浪费而适配。
> 作者：CodeBuddy · 2026-08-28

---

## 一、背景

原「测试信号灯」在每次 PR 推送时**全量串行跑 31 个独立测试脚本 + test_all_modules.sh**
（汇总 17 个模块测试），无论本次改动的是哪个模块。任何一次提交（哪怕改一个字符）都会触发
全量回归，造成巨大的 CPU 浪费（问题见 dongjiagoushi#74 的六条诊断）。

**目标**：PR 推送时**只跑受影响的测试脚本**，合并后 `main.push` 保留全量兜底保证质量。

**借鉴来源**：dongjiagoushi 仓库的 `IncrementalSelector` / `TestRegistry` / 资源路由机制，
本仓库按其思路实现了适配版。

---

## 二、核心机制：变更范围感知（Change-Aware Test Selection）

### 2.1 IncrementalSelector · 变更感知增量选择器

**文件**：`game-studio-agents/hybrid/selector.py`
**作用**：根据 git diff 变更的文件，只选择受影响的测试脚本运行，
避免全量跑 32 个测试脚本（31 独立 + 汇总）造成 CPU 浪费。

**核心能力**：
```python
from hybrid.selector import IncrementalSelector

s = IncrementalSelector(root_dir=".")

# git diff 获取变更文件
files = s.changed_files("HEAD~1", "HEAD")

# 变更文件 → 受影响测试（含依赖传播）
selected = s.select(["game-studio-agents/config/engine_bridge/bridge.py"])
# -> ['test_engine_bridge.sh', 'test_engine_bridge_integration.sh']

# 一键增量选择（默认 HEAD~1..HEAD）
selected = s.incremental()

# 工作区未提交变更
selected = s.incremental_workdir()

# 全量兜底
suite = s.full_suite()
```

**依赖传播防漏测**：
```
test_engine_bridge        covers config/engine_bridge/
test_engine_bridge_integration depends_on test_engine_bridge

变更 config/engine_bridge/bridge.py → 运行 [test_engine_bridge, test_engine_bridge_integration]
```

### 2.2 TestRegistry · 集中测试注册表

**文件**：`game-studio-agents/hybrid/registry.json` + `game-studio-agents/hybrid/registry.py`
**作用**：集中维护「每个测试覆盖哪些源码文件」「测试间依赖关系」
「CPU 成本估算」。

**注册表条目示例**：
```json
{
  "test_engine_bridge.sh": {
    "covers": ["game-studio-agents/config/engine_bridge/"],
    "depends_on": [],
    "cpu_cost_est": 2.0,
    "kind": "core"
  }
}
```

**核心接口**：
```python
from hybrid.registry import (
    all_tests, get, covers, dependencies,
    find_by_source, find_many_by_source,
    impact_closure, affected_tests, summary,
)
```

### 2.3 变更感知的接入方式（CI）

**在 `.cnb.yml` 的「测试信号灯」stage 中**，PR 推送时只跑受影响的测试：
```yaml
- name: 测试信号灯
  script: |
    # 变更范围感知：只跑受影响的测试脚本
    bash scripts/change-aware-test.sh
```

**`main.push`（合并后）保留全量回归兜底**：
```yaml
- name: 测试信号灯（全量）
  script: |
    bash scripts/change-aware-test.sh --all
```

---

## 三、CI 入口脚本

**文件**：`scripts/change-aware-test.sh`
**作用**：bash 版变更感知选择器，供 `.cnb.yml` 直接调用。

```bash
bash scripts/change-aware-test.sh                 # 自动检测变更（PR/push 均适用）
bash scripts/change-aware-test.sh --all           # 强制全量跑
bash scripts/change-aware-test.sh --dry-run       # 只打印将运行的测试，不实际执行
bash scripts/change-aware-test.sh --dry-run --all # 只打印全量测试清单
```

**变更来源判定**（按优先级）：
| 优先级 | 环境变量 / 条件 | 判定 |
|---|---|---|
| 1 | `CNB_PULL_REQUEST_TARGET_SHA` | PR 事件，对比目标分支 SHA 与 HEAD |
| 2 | `CNB_COMMIT` | push 事件，对比上一 commit |
| 3 | 本地 main 分支 | 对比 main...HEAD |
| 4 | 兜底 | 工作区未提交变更 / 全量 |

---

## 四、测试注册表覆盖映射（源码 → 测试）

| 源码模块 | 受影响测试 |
|---|---|
| `config/game_producer_agent.py` | test_producer_agent / test_dispatch_capability / test_role_collaboration / test_design_roles 等 |
| `config/engine_bridge/` | test_engine_bridge / test_engine_bridge_integration |
| `config/engine_integration.py` | test_engine_bridge_integration |
| `config/engine_adapters.py` | test_engine_adapters / test_engine_adaptation |
| `config/role_inventory.py` | test_role_inventory / test_role_inventory_handlers / test_design_roles |
| `config/preset_instantiator.py` | test_instantiator |
| `config/progress_pusher.py` | test_progress_pusher / test_progress_pusher_fullchain |
| `.cnb.yml` / `.cnb/settings.yml` | test_dept_npc_pipeline（配置一致性） |
| `config/framework_upgrade_memory.py` | test_framework_upgrade 系列 |

> 完整映射见 `game-studio-agents/hybrid/registry.json`。

---

## 五、适配收益

| 场景 | 改造前 | 改造后 |
|---|---|---|
| 只改 `engine_bridge/` 某文件 | 全量跑 32 个脚本 | 只跑 2 个引擎测试 |
| 只改 `game_producer_agent.py` | 全量跑 32 个脚本 | 跑相关 ~8 个测试 |
| 只改 `.cnb.yml` | 全量跑 32 个脚本 | 只跑 1 个配置一致性测试 |
| 改测试脚本自身 | 全量跑 32 个脚本 | 不触发（避免递归） |
| PR 合并（main.push） | — | 全量兜底，保证质量 |

**核心**：PR 高频推送场景下 CPU 消耗大幅下降，质量保障由 `main.push` 全量兜底。

---

## 六、可参考文件清单

| 文件 | 作用 |
|---|---|
| `game-studio-agents/hybrid/selector.py` | ⭐ 变更感知增量选择器（核心） |
| `game-studio-agents/hybrid/registry.json` | ⭐ 集中测试注册表（32 个测试的覆盖关系） |
| `game-studio-agents/hybrid/registry.py` | 注册表程序化接口 |
| `scripts/change-aware-test.sh` | ⭐ CI 入口：变更感知测试选择器 |
| `docs/HANDOFF_CHANGE_AWARE.md` | 本文档（交接索引） |

> 借鉴来源（dongjiagoushi 仓库）：
> - `local-agent/hybrid/selector.py` / `registry.json` / `router.py`
> - `docs/HYBRID_OPTIMIZER.md` / `docs/HYBRID_RESOURCE.md`
> - `docs/HANDOFF_CHANGE_AWARE.md`

---

## 七、部门路由三层触发机制（防"无工作部门凑热闹"）

> 背景：Issue #54「职责明确」延伸——每次编排不应无条件触发全部六大部门，尤其
> "美术/测试常无工作凑热闹"。参考 dongjiagoushi 架构师的 `src/memory/triggers.py`
> 三层触发引擎（语义触发 + 阈值下限 + 显式声明最高优先 + 未命中不拉起），
> 在本仓库落地为 **部门路由三层触发**。

### 7.1 三层触发引擎（routing.py v3.0）

**文件**：`game-studio-agents/config/routing.py`

| 层级 | 规则 | 防误判作用 |
|---|---|---|
| ① 显式声明（最高优先） | `%部门名` / `@部门名` / `[触发:部门名]` 硬匹配 | 命中即触发，不受阈值约束；缺标记不猜测接手部门 |
| ② 语义/关键词（带阈值下限） | 命中部门**强职责关键词**（如"原画/建模"→美术线、"回归/case"→测试线）且次数≥阈值才触发 | 低于阈值 → method=none，静默放行 |
| ③ 未命中 | method=none + confidence=low | 不拉起、不评论凑热闹（关键"下限"） |

### 7.2 关键修复：裸提及部门名不再误触发

**问题**：CI 平台注入的状态标签（如"测试线验收中,美术线验收中"）中的"部门名裸提及"
会让关键词引擎误判命中（"美术线"里的"美术"是美术线强词）→ 无关部门被拉起凑热闹。

**修复**：语义匹配前**剥离"裸部门名"整体**（`美术线`/`测试线`…），显式标记
（%/@/[触发:]）交由显式引擎单独处理。效果：

| 场景 | 是否触发 |
|---|---|
| `请 %测试线 完成回归`（显式声明） | ✅ 触发测试线（high 置信） |
| `测试线验收中、美术线验收中`（裸提及/状态标签） | ❌ 不触发（未命中=静默） |
| `角色原画与 3D 建模规范`（强职责词） | ✅ 触发美术线 |
| `今天天气不错，吃饭了吗`（完全无关） | ❌ 不触发 |

### 7.3 修复 labels 污染路由（对应 dongjiagoushi#74 问题 5）

**文件**：`routing.py` 的 `route_from_env()`
**改动**：不再把 `CNB_ISSUE_LABELS` 拼入语义匹配内容。标签只反映进度状态，
不应作为"分配工作"的触发依据。

### 7.4 测试护栏

**文件**：`game-studio-agents/tests/test_routing.sh`
**覆盖**：三层触发引擎（显式声明最高优先 / 语义阈值 / 未命中静默）、裸提及部门名不触发、
labels 隔离、路由守卫 stage 级 if 拦截。当前 16/16 全绿。

### 7.5 可参考文件清单

| 文件 | 作用 |
|---|---|
| `game-studio-agents/config/routing.py` | ⭐ 部门路由三层触发引擎（核心） |
| `game-studio-agents/tests/test_routing.sh` | ⭐ 三层触发护栏测试 |
| `game-studio-agents/config/game_producer_agent.py` | 编排时按路由只派发命中部门 |
| `.cnb.yml` | 部门 stage 级 if 守卫（grep marker 文件，未命中不拉起） |

> 借鉴来源（dongjiagoushi 仓库，已征得归属方认可、本仓库只做适配不修改对方）：
> - `src/memory/triggers.py` ⭐ 三层触发引擎
> - `local-agent/handle/` ⭐ 自适应 @ 显式硬触发通道
> - `AGENTS.md`「触发强制化」固定规则 ①显性声明触发 ②语义向量触发 ③rules 兜底
