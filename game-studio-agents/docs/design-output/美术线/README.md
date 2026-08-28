# 美术线 · 承接产出

> 场景：策划线设计 + 程序线实现方案验收通过后，下游解锁 → 美术线承接美术资产。
> 美术线部门统一头（art_director）承接，全程经协作工作台 @分工 留痕（group_audit）。

## 一、承接工作包

| 工作包 | 模块 | 主责角色 | 产出物 | 状态 |
|--------|------|----------|--------|:----:|
| wp_art_direction | art_direction | art_director 总纲 | 美术风格与资源总纲 | ✅ DONE |
| wp_concept_art | narrative + combat | concept_artist | 世界观/角色/怪物原画设定 | ✅ DONE |
| wp_character_model | combat | modeler | 角色/怪物 3D 模型资产 | ✅ DONE |
| wp_animation | combat | animator | 角色动作/战斗动画 | ✅ DONE |
| wp_vfx | combat | vfx_artist | 战斗特效/打击反馈 | ✅ DONE |
| wp_ui_visual | gameplay | ui_ux | 界面视觉/交互规范 | ✅ DONE |
| wp_scene_asset | level | concept_artist + modeler | 场景概念/关卡资产 | ✅ DONE |
| wp_audio | narrative | audio_designer | 剧情/战斗配乐音效 | ✅ DONE |
| wp_review_ux | ui_ux / review 治理 | tech_artist | 评审只读边界在 UI/交互评审中的应用 | ✅ DONE（本轮） |

> 覆盖美术线 8 个设计工作包（含美术风格总纲）+ 本轮评审治理工作包 wp_review_ux，
> 角色覆盖 concept_artist / modeler / animator / vfx_artist / ui_ux / tech_artist / audio_designer
> 全部执行角色 + art_director 主美。

## 二、组内分工表

| 子任务 | 承接角色 | 产出物文件 |
|--------|---------|-----------|
| 美术风格/资源总纲 | art_director | wp_art_direction_美术风格与资源.md |
| 世界观/角色原画 | concept_artist | wp_concept_art_世界观角色原画.md |
| 角色 3D 模型 | modeler | wp_character_model_角色建模资产.md |
| 战斗动画 | animator | wp_animation_战斗动画方案.md |
| 战斗特效 | vfx_artist | wp_vfx_战斗特效方案.md |
| UI 视觉规范 | ui_ux + tech_artist | wp_ui_visual_界面视觉规范.md |
| 场景资产 | concept_artist + modeler | wp_scene_asset_场景资产方案.md |
| 音频设计 | audio_designer | wp_audio_音频设计方案.md |
| 评审只读边界 UI 应用 | tech_artist（单角色直投） | wp_review_ux_评审只读边界UI评审应用.md |

> 分工经协作工作台（CollaborationWorkbench）`delegate` 记录；本轮 wp_review_ux 聚焦单角色
> tech_artist 直投执行，跨角色子任务留痕可审计（group_audit）。

## 三、跨部门协作

| 协作方向 | 部门 | 协作内容 | 触发时机 |
|---------|------|---------|---------|
| 上游消费 | 策划线 | 消费世界观/角色/战斗设计 | 策划产出验收后 |
| 上游消费 | 程序线 | 消费战斗引擎/AI实现约束 + wp_review_role/route（评审只读边界） | 程序实现方案确定后 |
| 下游解锁 | 测试线 | 对美术资源做兼容性/性能验收 + wp_review_qa 评审无推送回归 | 美术资产交付后 |
| 下游解锁 | 项目管理 | 评审→建议→CodeBuddy 推送闭环验收（wp_review_pm） | wp_review_qa 通过后 |
| 联动 | 运营线 | 消费美术品质做市场预演 + wp_review_ops 职责边界文档同步 | 美术品质基准确定后 |

> 推送闭环统一由 `@dongdongxiaozu/youxikaifaxilieagent(CodeBuddy)` 承接，美术线 TA 评审只读不给推送。

## 三、PR #86 下游解锁 · 本轮承接记录

| 工作包 | 状态 | 说明 |
|--------|------|------|
| —（美术线） | ⛔ 无本部门工作包 | PR #86 为测试线承接 wp_art_testing（美术线生态角色模块化验收），美术线为被测对象；下游解锁指向项目管理 wp_release，本轮美术线无工作包，跳过 |

详细见：`承接报告_PR86_跳过.md`
