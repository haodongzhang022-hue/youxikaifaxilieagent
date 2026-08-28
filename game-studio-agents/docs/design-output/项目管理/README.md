# 项目管理 · 承接产出

> 场景：PR #76 合并后，测试线 wp_handler_qa 验收通过 → 游戏向经理解锁下游 → 项目管理验收评审-修复闭环与仓库处理专员职责边界。
> 项目管理部门统一头承接，经协作工作台 @分工 留痕（group_audit），由 project_manager 执行。

## 一、承接工作包

| 工作包 | 模块 | 主责角色 | 产出物 |
|--------|------|----------|--------|
| wp_review_pm | review 闭环治理验收 | project_manager | wp_review_pm_评审建议CodeBuddy推送闭环验收.md |
| wp_handler_pm | handler 角色职责治理验收 | project_manager | wp_handler_pm_仓库处理专员职责边界闭环验收.md |
| wp_release_plan | release | project_manager | wp_release_plan_发版计划.md |
| wp_release_gate | release | release_manager | wp_release_gate_发版门禁.md |

## 二、组内分工表

| 子任务 | 承接角色 | 产出物文件 |
|--------|---------|-----------|
| 评审→建议→CodeBuddy 推送闭环验收 | project_manager | wp_review_pm_评审建议CodeBuddy推送闭环验收.md |
| 仓库处理专员职责边界与闭环验收 | project_manager | wp_handler_pm_仓库处理专员职责边界闭环验收.md |
| 发版计划/里程碑 | project_manager | wp_release_plan_发版计划.md |
| 发版门禁检查 | release_manager | wp_release_gate_发版门禁.md |

## 三、跨部门协作

| 协作方向 | 部门 | 协作内容 | 触发时机 |
|---------|------|---------|---------|
| 上游消费 | 测试线/程序线/美术线 | 消费回归结论做验收依据 | 测试验收通过后 |
| 下游解锁 | 运营线 | wp_review_ops + wp_handler_ops 对外同步 | PM 验收通过后 |

---

## 补充承接：wp_release 发版质量门禁验收放行（PR #84 级联解锁）

> 场景：测试线 wp_art_testing（美术线生态角色模块化验收）验收通过 → 游戏向经理解锁下游
> → 项目管理承接 **wp_release 发版质量门禁验收放行**。
> 经协作工作台 @分工 拆派 project_manager + release_manager，全程留痕（group_audit）。

| 工作包 | 模块 | 主责角色 | 产出物 | 状态 |
|--------|------|----------|--------|------|
| wp_release | release 发版质量门禁验收放行 | project_manager + release_manager | 发版门禁验收放行（GO）+ 发版计划 | ✅ DONE |

- 组内分工：wp_release__sub1（project_manager）发版门禁验收放行、wp_release__sub2（release_manager）门禁复核；
- 发版门禁验收结论 **GO**（market_preview 3/3、ecosystem_roles 3/3、progress_pusher 4/4，release_gate 10/10）；
- 下游解锁：运营线 `wp_market_preview`。
