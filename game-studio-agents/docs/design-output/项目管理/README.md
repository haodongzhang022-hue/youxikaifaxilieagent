# 项目管理 · 承接产出

> 场景：测试线验收通过后，下游解锁 → 项目管理执行发版里程碑 + 评审-修复闭环验收。
> 项目管理部门统一头（project_manager）承接，全程经协作工作台 @分工 留痕（group_audit）。

## 一、承接工作包

| 工作包 | 模块 | 主责角色 | 产出物 |
|--------|------|----------|--------|
| wp_release_plan | release | project_manager | 发版计划与里程碑 |
| wp_release_gate | release | release_manager | 发版门禁检查 |
| wp_handler_pm | 评审-修复闭环验收 | release_manager + project_manager | 评审-修复闭环验收 |
| wp_review_pm | 评审治理闭环验收 | release_manager + project_manager | 评审→建议→CodeBuddy 推送闭环验收 |

## 二、组内分工表

| 子任务 | 承接角色 | 产出物文件 |
|--------|---------|-----------|
| 发版计划/里程碑 | project_manager | wp_release_plan_发版计划.md |
| 发版门禁检查 | release_manager | wp_release_gate_发版门禁.md |
| 评审-修复闭环验收 | release_manager + project_manager | wp_handler_pm_评审修复闭环验收.md |
| 评审→建议→CodeBuddy 推送闭环验收 | release_manager + project_manager | wp_review_pm_评审建议CodeBuddy推送闭环验收.md |

## 三、跨部门协作

| 协作方向 | 部门 | 协作内容 | 触发时机 |
|---------|------|---------|---------|
| 上游消费 | 全部 | 消费全链路验收结果 | 测试验收通过后 |
| 上游消费 | 测试线 | 消费 wp_handler_qa / wp_review_qa 验收报告 | 测试验收通过后 |
| 联动 | 运营线 | 发版前市场预演确认 | 发版计划确定后 |
| 下游解锁 | 运营线 | wp_handler_ops / wp_review_ops | 本部门验收通过后 |
