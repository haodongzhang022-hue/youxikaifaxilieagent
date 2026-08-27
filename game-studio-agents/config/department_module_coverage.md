# 部门角色 module 覆盖表（角色 → 行为语义映射）

> 状态: v1.0 (Issue #55, WP-04 策划线产出)
> 说明: 明确六大部门 Agent 按 `module` 字段兜底的角色及其行为语义，
>       解决"66+ 角色差异靠 module 区分、角色语义被稀释"的问题。
> 权威事实源: `config/role_inventory.yaml`（角色-实现映射索引）

## 一、六大部门 Agent 兜底角色

| 部门 | 部门键 | 兜底角色 (role_id) | 行为语义 |
|---|---|---|---|
| 策划线 | design | lead_designer, system_designer, balance_designer, level_designer | 系统/数值/关卡设计，产出设计案 |
| 程序线 | program | cto, client_dev, server_dev, engine_dev, ai_programmer, tools_dev | 服务端/客户端/引擎/AI/工具开发，产出代码 |
| 美术线 | art | art_director, concept_artist, modeler, animator, vfx_artist, ui_ux, tech_artist, audio_designer | 概念/建模/动画/特效/UI/TA/音频，产出美术资产 |
| 测试线 | qa | qa_engineer, auto_qa | 功能/自动化测试，产出测试报告 |
| 项目管理 | pm | project_manager, release_manager | 排期/风险/版本管理，产出计划与门禁 |
| 运营线 | ops | data_analyst, reference_learner, game_operator | 数据分析/竞品借鉴/运营策略，产出运营方案 |

## 二、已实体化独立实现（非 module 兜底）

| 角色 | 实现类 | 文件 |
|---|---|---|
| producer | GameProducerAgent | game_producer_agent.py |
| reference_learner | ReferenceLearnerAgent | reference_learner_agent.py |
| progress_pusher | ProgressPusherAgent | progress_pusher.py |
| merged_confirmer | MergedConfirmAgent | merged_confirm_agent.py |
| publisher / core_player / advertiser / gig_pool | EcosystemHandler | ecosystem_handlers.py |
| producer_alt / server_dev_alt / data_analyst_alt | AltVariantHandler | alt_variants.py |

## 三、仅声明未兜底（差距，见 role_inventory --gap）

- narrative_designer, combat_designer 及其 `_alt` 变体：**无 module 兜底、无独立实现**（纯声明）
- 其余生态角色（communicator/mediator/gatekeeper/asset_manager/mass_player 等）：仅注册可派发，无 handler

> ⚠️ 以上差距由 `tests/test_role_inventory.sh` 护栏持续暴露，作为后续实体化 backlog。

## 四、P1 backlog：批量补充 `_alt` 变体（25 个，按同模式分批）

> 已实体化样板：producer_alt / server_dev_alt / data_analyst_alt（AltVariantHandler 独立承接）
> 剩余 25 个 `_alt` 变体待按同模式批量补充，按部门分组：

| 部门 | 待补充变体 | 数量 |
|---|---|---|
| 策划线 | lead_designer_alt, system_designer_alt, balance_designer_alt, level_designer_alt, narrative_designer_alt, combat_designer_alt | 6 |
| 程序线 | cto_alt, client_dev_alt, engine_dev_alt, ai_programmer_alt, tools_dev_alt | 5 |
| 美术线 | art_director_alt, concept_artist_alt, modeler_alt, animator_alt, vfx_artist_alt, ui_ux_alt, tech_artist_alt, audio_designer_alt | 8 |
| 测试线 | qa_engineer_alt, auto_qa_alt | 2 |
| 项目管理 | project_manager_alt, release_manager_alt | 2 |
| 运营线 | reference_learner_alt, game_operator_alt | 2 |

> 补充方式：每个变体在 `alt_variants.py` 中新增独立行为 handler（风格差异化执行），
> 并将 `role_inventory.yaml` 对应角色状态更新为 implemented。
