# 程序线 · 承接产出

> 场景：策划线设计产出验收通过后，下游解锁 → 程序线承接实现模块。
> 程序线部门统一头（cto）承接，全程经协作工作台 @分工 留痕（group_audit）。

## 一、承接工作包

| 工作包 | 模块 | 主责角色 | 产出物 |
|--------|------|----------|--------|
| wp_gameplay_impl | gameplay | client_dev + server_dev | 核心循环系统实现方案 |
| wp_numeric_model_impl | numeric_model | server_dev | 经济/数值后端实现方案 |
| wp_narrative_impl | narrative | client_dev + server_dev | 剧情/任务系统实现方案 |
| wp_combat_impl | combat | engine_dev + ai_programmer | 战斗引擎/AI实现方案 |
| wp_level_impl | level | engine_dev + client_dev | 关卡系统实现方案 |

## 二、组内分工表

| 子任务 | 承接角色 | 产出物文件 |
|--------|---------|-----------|
| 核心玩法循环实现 | client_dev + server_dev | wp_gameplay_核心玩法系统实现.md |
| 经济/数值后端实现 | server_dev | wp_numeric_model_数值经济后端实现.md |
| 剧情/任务系统实现 | client_dev + server_dev | wp_narrative_剧情任务系统实现.md |
| 战斗引擎/AI实现 | engine_dev + ai_programmer | wp_combat_战斗引擎与AI实现.md |
| 关卡系统实现 | engine_dev + client_dev | wp_level_关卡系统实现.md |

## 三、跨部门协作

| 协作方向 | 部门 | 协作内容 | 触发时机 |
|---------|------|---------|---------|
| 上游消费 | 策划线 | 消费 5 份设计文档作为实现依据 | 策划产出验收后 |
| 下游解锁 | 美术线 | 承接角色/场景/特效的美术资产 | 程序实现方案确定后 |
| 下游解锁 | 测试线 | 对程序实现做功能/性能验收 | 程序实现交付后 |
| 联动 | 运营线 | 消费数值模型做市场预演 | 数值后端实现后 |
