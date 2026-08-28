# 测试线 · 承接产出

> 场景：策划线设计 + 程序线实现 + 美术线资产验收通过后，下游解锁 → 测试线验收测试。
> 测试线部门统一头（qa_engineer）承接，全程经协作工作台 @分工 留痕（group_audit）。

## 一、承接工作包

| 工作包 | 模块 | 主责角色 | 产出物 |
|--------|------|----------|--------|
| wp_acceptance_test | 全链路 | qa_engineer + auto_qa | 全链路验收测试方案 |
| wp_perf_test | 全链路 | auto_qa | 性能测试方案 |
| wp_regression_test | 全链路 | qa_engineer | 回归测试方案 |
| wp_review_qa | 评审治理 | qa_engineer | 验收评审无推送权限边界回归 |
| wp_handler_qa | 仓库处理专员回归 | qa_engineer + auto_qa | 仓库处理专员触发链路回归验证 |
| wp_art_testing | 美术线生态角色模块化验收 | qa_engineer + auto_qa | 美术线生态角色接入模块化验收（16 项断言） |

## 二、组内分工表

| 子任务 | 承接角色 | 产出物文件 |
|--------|---------|-----------|
| 功能验收测试 | qa_engineer | wp_acceptance_test_功能验收测试.md |
| 自动化回归 | auto_qa | wp_regression_test_自动化回归方案.md |
| 性能验收 | auto_qa | wp_perf_test_性能验收方案.md |
| 评审只读边界回归 | qa_engineer | wp_review_qa_验收评审无推送权限边界回归.md |
| 仓库处理专员触发链路回归 | qa_engineer + auto_qa | wp_handler_qa_仓库处理专员触发链路回归.md |
| 美术线生态角色模块化验收 | qa_engineer + auto_qa | wp_art_testing_美术线生态角色模块化验收.md |

## 三、跨部门协作

| 协作方向 | 部门 | 协作内容 | 触发时机 |
|---------|------|---------|---------|
| 上游消费 | 策划线 | 消费设计文档做测试依据 | 策划产出验收后 |
| 上游消费 | 程序线 | 消费实现方案做测试依据 | 程序产出验收后 |
| 上游消费 | 美术线 | 消费美术资产做兼容性验收 | 美术产出验收后 |
| 上游消费 | 程序线 | 消费 wp_handler_program 验证报告做回归依据 | PR#52 合并后 |
| 上游消费 | 程序线/美术线 | 消费评审只读边界（wp_review_role/route/ux）做权限回归 | PR#56 合并后 |
| 下游解锁 | 项目管理 | 发版里程碑收口 + 评审闭环验收 | 测试验收通过后 |
| 被测对象 | 美术线 | 消费美术线生态角色产出做模块化验收（wp_art_testing） | PR#84 合并后 |
| 下游解锁 | 项目管理 | wp_art_testing 验收通过后解锁 wp_release 发版门禁 | 本包验收通过后 |

## 四、引擎适配专项（PR #82 合并后下游解锁）

| 工作包 | 模块 | 主责角色 | 产出物 | 状态 |
|--------|------|----------|--------|:----:|
| wp_engine_adaptation_qa | 双引擎适配底座验收 | qa_engineer + auto_qa | wp_engine_adaptation_qa_双引擎适配底座验收回归.md | ⛔ 打回（程序线 PR#87 未合入） |
