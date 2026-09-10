# 🏛️ Issue #133「尝试美工增强」收尾 · 路由幻影部门缺陷修复 + 门禁 sign-off

> 触发：人类在 Issue #133 评论「好的，做一下收尾，134 已经合并了」→ `@CodeBuddy`
> 岗位壳：CodeBuddy（代码质量审查 + 残留工作收敛）→ 项目管理（收口 sign-off）协同
> 关联：PR #134（美术线 UI/UX 产出升级 design_system + 美术质检门禁 P0/P1）已合入 main
> 结论：**发现并修复收尾缺陷 → 全链路闭环 GO**

## 〇、收尾时发现的真实缺陷（非流程噪音）

按"先盘残留工作，再下判断"的岗位壳铁律，收尾审查中发现一处**机制缺陷**：

| 项 | 现象 | 复现 |
|----|------|------|
| 缺陷 | 评论触发（`issue.comment@npc`）时，`routing.py route` 输出**幻影部门** `程序线 美术线 测试线 项目管理` | Issue #133 收尾评论下实跑 |
| 期望 | 评论「好的，做一下收尾，134已经合并了」无强职责关键词 → **不得拉起任何部门** | — |

**根因（环境态污染）**：
- 平台在评论事件下仍注入 **Issue 原始正文** `CNB_ISSUE_DESCRIPTION`（Issue #133 正文含"美术线承接 wp_style_index → 测试线 QA 验收 → 项目管理收口 → 运营线同步"等历史链路词）；
- `route_from_env()` 以事件名匹配数据源，`issue.comment@npc` 命中 `"issue" in event` 分支 → 把 **Issue 历史正文当本轮工作内容**做语义匹配 → 语义误触发。

**旁证（同源隐患）**：`scripts/change-aware-test.sh` 亦读取 `CNB_ISSUE_DESCRIPTION`，在本机实测中导致 test_routing 用例外源失败——同一"环境态污染"类缺陷。

## 一、修复方案（最小改动 + 可回归）

| # | 改动 | 说明 |
|---|------|------|
| 1 | `game-studio-agents/config/routing.py` | `route_from_env()` 支持权威上下文：`CNB_ROUTING_CONTENT`（本轮真实触发内容，如评论正文）优先；`CNB_ROUTING_EVENT` 覆盖事件判定；评论事件下**清空 Issue/PR 历史正文**，仅保留评论内容 |
| 2 | `scripts/routing-marker.sh`（新增） | 路由决策**统一入口**：按事件定位权威内容（`CNB_COMMENT_BODY` / `CNB_NPC_TRIGGER_CONTENT` → 回退事件正文），注入 `CNB_ROUTING_CONTENT/EVENT` 并清空 PR 残留，再写 marker |
| 3 | `.cnb.yml`（2 处） | `issue.open` / `pull_request.merged` 的路由决策 stage 由内联 `routing.py marker` 改为复用 `bash scripts/routing-marker.sh`，消除"改一处漏一处" |
| 4 | `game-studio-agents/tests/test_routing.sh` | 新增第 10 节（环境态污染回归）+ 第 11 节（统一入口护栏）；并隔离用例外源环境态 |

**修复后实测**：

| 场景 | 修复前 | 修复后 |
|------|--------|--------|
| 评论「做一下收尾，134已合并」 | `程序线 美术线 测试线 项目管理`（幻影） | 空（无部门被误拉起）✅ |
| `issue.open` 服务端 bug | 程序线 | 程序线 ✅ |
| `pull_request.merged` 美术改动 | 美术线 | 美术线 ✅ |

## 二、回归验证（本地实测）

| 回归 | 结果 |
|------|------|
| `tests/test_routing.sh` | **20 通过 / 0 失败**（含新增 2 类护栏） |
| `tests/test_ui_ux.sh`（美术质检门禁 6 规则） | **16 通过 / 0 失败** |
| `tests/test_art_testing.sh` | **9 通过 / 0 失败** |
| `tests/test_producer_agent.sh` | **24 通过 / 0 失败** |
| `scripts/change-aware-test.sh --all` 全量 | **17 模块通过 / 0 失败** ✅ |

## 三、门禁 sign-off（release_manager 视角）

| 验收项 | 判据 | 结论 |
|--------|------|:----:|
| 美术质检门禁 6 规则 | 合规放行 + 6 类违规拦截（P0/P1 PR #134） | ✅ 复核 16/16 |
| 路由器不产生幻影部门 | 评论触发无强职责词 → active 为空 | ✅ 20/20 |
| 既有链路不回归 | issue.open / PR merged 路由、部门 stage 守卫 | ✅ 全量 17/17 |
| 护栏可回归 | 新增护栏固化"环境态污染"防回退 | ✅ |

## 四、Issue #133 收尾结论

| 里程碑 | 阶段 | 状态 |
|--------|------|:----:|
| P0 · ui_ux 产出升级可检索可校验 design_system | 落地 | ✅ 完成（PR #134 合入） |
| P1 · 美术质检门禁 6 规则 | 落地 | ✅ 完成（sign-off） |
| P2 · 可检索风格索引 wp_style_index | 落地 | ✅ 完成（美术线交付） |
| 测试侧 QA 验收 | 验收 | ✅ 完成（测试线 GO） |
| 收尾缺陷 · 路由环境态污染 | 修复 | ✅ 本轮修复（含回归护栏） |
| **Issue #133 收口** | 闭环 | ✅ **可关闭** |

**残留工作审查**：无未闭环 PR；P0/P1/P2 全量落地 main；本次发现的机制缺陷已就地修复并固化断言。
**处置结论**：Issue #133 职责范围内已无残留工作 → **建议关闭**（关闭动作由人工/具备权限角色执行）。

---
*全程机制驱动：评论 @CodeBuddy → 岗位壳审查残留工作 → 定位并修复环境态污染缺陷 → 全量回归 20/20 + 17 模块全绿 → 门禁 sign-off + Issue 收口结论。*
