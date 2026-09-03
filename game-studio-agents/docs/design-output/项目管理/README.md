# 项目管理 · 承接产出

> 项目管理部门统一头承接，经协作工作台 @分工 留痕（group_audit），由 project_manager / release_manager 执行。

## 一、承接工作包

| 工作包 | 模块 | 主责角色 | 产出物 |
|--------|------|----------|--------|
| wp_review_pm | review 闭环治理验收 | project_manager | wp_review_pm_评审建议CodeBuddy推送闭环验收.md |
| wp_handler_pm | handler 角色职责治理验收 | project_manager | wp_handler_pm_仓库处理专员职责边界闭环验收.md |
| wp_release_plan | release | project_manager | wp_release_plan_发版计划.md |
| wp_release_gate | release | release_manager | wp_release_gate_发版门禁.md |
| wp_release | release 发版质量门禁验收放行 | project_manager + release_manager | 承接报告_REVIEW_RESULT_wp_release.md |
| wp_engine_adaptation_pm | engine_adaptation 项目管理架构里程碑验收 | project_manager + release_manager | 承接报告_PR86_项目管理_wp_engine_adaptation_pm.md |

## 二、PR #86 下游解锁 · 本轮承接记录

| 工作包 | 状态 | 说明 |
|--------|------|------|
| wp_release | ✅ 已交付 | 发版质量门禁验收放行（GO），前序流水线已完成 |
| wp_engine_adaptation_pm | ✅ DONE | 双引擎适配底座项目管理架构里程碑验收，测试线 wp_engine_adaptation_qa 验收通过后解锁，经 @分工 拆派 project_manager + release_manager 完成 |

详细见：`承接报告_PR86_项目管理_wp_engine_adaptation_pm.md`
## 二、PR #89 下游解锁 · 本轮承接记录

| 工作包 | 状态 | 说明 |
|--------|------|------|
| wp_engine_release（发版门禁复验） | ✅ DONE | PR89 P1 修复后发版门禁复验签核（GO），程序线 wp_engine_bridge_verify 生产就绪验证通过后解锁，经 @分工 拆派 project_manager + release_manager 完成 |

详细见：`承接报告_PR89_项目管理_wp_engine_release_发版门禁复验.md`

## 三、组内分工表

| 子任务 | 承接角色 | 产出物文件 |
|--------|---------|-----------|
| 评审→建议→CodeBuddy 推送闭环验收 | project_manager | wp_review_pm_评审建议CodeBuddy推送闭环验收.md |
| 仓库处理专员职责边界与闭环验收 | project_manager | wp_handler_pm_仓库处理专员职责边界闭环验收.md |
| 发版计划/里程碑 | project_manager | wp_release_plan_发版计划.md |
| 发版门禁检查 | release_manager | wp_release_gate_发版门禁.md |
| 发版质量门禁验收放行 | project_manager + release_manager | 承接报告_REVIEW_RESULT_wp_release.md |
| 双引擎适配底座里程碑验收 | project_manager + release_manager | 承接报告_PR86_项目管理_wp_engine_adaptation_pm.md |

## 四、跨部门协作

| 协作方向 | 部门 | 协作内容 | 触发时机 |
|---------|------|---------|---------|
| 上游消费 | 测试线/程序线/美术线 | 消费回归结论做验收依据 | 测试验收通过后 |
| 上游消费 | 测试线 | 消费 wp_engine_adaptation_qa 验收结论做引擎适配里程碑依据 | 测试线验收通过后 |
| 上游消费 | 程序线 | 消费 PR #87 wp_engine_adaptation_integration 合入状态 | 引擎适配集成合入后 |
| 下游解锁 | 运营线 | wp_review_ops + wp_handler_ops 对外同步 | PM 验收通过后 |
| 前置依赖 | 程序线 | PR #87 wp_engine_adaptation_integration 合入 | 解锁 PM 工作包前置条件 |

## 二、PR #113 下游解锁 · 本轮承接记录

| 工作包 | 状态 | 说明 |
|--------|------|------|
| wp_release_stage_gate（stage_gate 纳入发版门禁） | ✅ DONE | PR #113 合并后游戏向经理派发，把 stage_gate 阶段边界审查纳入发版门禁 + 里程碑排布 M1-M5，经 @分工 拆派 project_manager + release_manager 完成 |

详细见：`PR113_stage_gate/承接报告_wp_release_stage_gate.md`

## 三、PR #115 下游解锁 · 本轮承接记录

| 工作包 | 状态 | 说明 |
|--------|------|------|
| wp_pm_squad_confirm（开发小组闭环接入确认） | ✅ DONE | 验证 `_run_dev_team_loop()` 在 PmDeptAgent._execute 正确接入 + release_pm 小组自动调配/释放闭环，测试全绿，经 @分工 拆派 project_manager + release_manager 完成 |

详细见：`PR115_wp_pm_squad_confirm/承接报告_PR115_项目管理_wp_pm_squad_confirm.md`

## 四、组内分工表（新增 PR#115）

| 子任务 | 承接角色 | 产出物文件 |
|--------|---------|-----------|
| 验证 _run_dev_team_loop 在 _execute 接入 | project_manager | PR115_wp_pm_squad_confirm/承接报告_PR115_项目管理_wp_pm_squad_confirm.md |
| 验证 release_pm 小组自动调配/释放 | release_manager | PR115_wp_pm_squad_confirm/承接报告_PR115_项目管理_wp_pm_squad_confirm.md |

## 五、跨部门协作记录（新增 PR#115）

| 协作方向 | 部门 | 协作内容 | 触发时机 |
|---------|------|---------|---------|
| 上游消费 | 程序线 | 消费 PR #115 交付的 dev_team_loop + squad_pool 工具链 | PR #115 合并后 |
| 上游消费 | 游戏向经理 | 消费 `MODULE_SQUAD_DOMAIN` release→release_pm 映射 | 经理拆包自动标注后 |

## 六、PR #130 下游解锁 · 本轮承接记录（wp_release 发版收口闭环）

> PR #129（管线矩阵驱动发布评审，Issue#128 wp_pipeline_release）+ 收口修复 PR #130 合并 → 下游路由标记指向项目管理承接 **wp_release 发版收口闭环**。

| 工作包 | 状态 | 说明 |
|--------|------|------|
| wp_release（发版收口闭环） | ✅ DONE | 管线矩阵驱动发布评审真正达成闭环（真实部门状态驱动门禁/部门回报口径自洽/producer 消费 pipeline_status/topo_sort 收敛 4 点修复核对），发版收口验收放行 GO。经 @分工 拆派 project_manager + release_manager 完成 |

详细见：`PR130_closure/承接报告_wp_release_发版收口闭环.md`
审计流水：`PR130_closure/wp_release_closure_group_audit.json`

## 七、组内分工表（新增 PR#130）

| 子任务 | 承接角色 | 内容 | 产出物文件 |
|--------|---------|------|-----------|
| wp_release_closure__sub1 | project_manager | 发版收口闭环验收（真实部门状态驱动门禁/口径自洽/producer 消费核对） | PR130_closure/承接报告_wp_release_发版收口闭环.md |
| wp_release_closure__sub2 | release_manager | 发版门禁收口复核（release_gate/pipeline_release GO-NO-GO 收口一致 + 回归全绿） | PR130_closure/承接报告_wp_release_发版收口闭环.md |

## 八、跨部门协作记录（新增 PR#130）

| 协作方向 | 部门 | 协作内容 | 触发时机 |
|---------|------|---------|---------|
| 上游消费 | 程序线 | 消费 PR #129/#130 管线矩阵驱动发布评审核心代码合并状态 | PR #130 合并后 |
| 上游消费 | 测试线/策划线/美术线 | 消费各线验收回归全绿做发版收口门禁依据 | 各线验收通过后 |
| 下游解锁 | 运营线 | wp_release 发版收口验收通过后解锁运营线下游 | PM 验收后 |
