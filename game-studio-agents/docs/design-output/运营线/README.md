# 运营线 · 承接产出

> 场景：策划/程序/美术/测试/项目管理全链路交付后，运营线消费产出做运营包装、市场预演与对外文档同步。
> 运营线部门统一头承接，全程经协作工作台 @分工 留痕（group_audit）。

## 一、承接工作包

| 工作包 | 模块 | 主责角色 | 产出物 | 状态 |
|--------|------|----------|--------|------|
| wp_market_preview | data_ops | data_analyst | 市场预演与生态位诊断 | ✅ DONE |
| wp_ops_strategy | ops | game_operator | 运营策略与用户增长方案 | ✅ DONE |
| wp_ref_learn | ops | reference_learner | 竞品参考学习报告 | ✅ DONE |
| wp_handler_ops | ops | data_analyst + game_operator | 对外文档同步角色变更（仓库处理专员） | ✅ DONE |
| wp_review_ops | ops | data_analyst + game_operator | 评审职责边界对外说明文档同步 | ✅ DONE |

## 二、组内分工表

| 子任务 | 承接角色 | 产出物文件 | 状态 |
|--------|---------|-----------|------|
| 市场预演 | data_analyst | wp_market_preview_市场预演.md | ✅ DONE |
| 运营策略 | game_operator | wp_ops_strategy_运营策略.md | ✅ DONE |
| 借鉴学习 | reference_learner | wp_ref_learn_借鉴学习报告.md | ✅ DONE |
| 对外文档角色变更 | data_analyst + game_operator | wp_handler_ops_对外文档角色变更.md | ✅ DONE |
| 评审职责边界说明 | data_analyst + game_operator | wp_review_ops_评审职责边界说明.md | ✅ DONE |

## 三、跨部门协作

| 协作方向 | 部门 | 协作内容 | 触发时机 |
|---------|------|---------|---------|
| 上游消费 | 策划线 | 消费数值模型做市场预演 | numeric_model 产出后 |
| 上游消费 | 美术线 | 消费美术品质做市场预演 | art_direction 产出后 |
| 联动 | 项目管理 | 发版前市场预演确认 | 发版计划确定后 |
| 上游消费 | 项目管理 | 消费 wp_handler_pm / wp_review_pm 验收报告 | PR #52 合并后 |
| 上游消费 | 测试线 | 消费 wp_handler_qa / wp_review_qa 回归报告 | PR #52 合并后 |
