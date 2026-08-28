# 美术线 · Issue #90 跨平台架构增强产出

> 场景：策划线设计 + 程序线实现方案验收通过后，下游解锁 → 美术线承接跨平台美术资源工作包。
> 美术线部门统一头（art_director）承接，全程经协作工作台 @分工 留痕（group_audit）。

## 产出物清单

| 工作包 | 主责角色 | 产出文件 |
|--------|---------|---------|
| wp_art_direction | tech_artist（组）→ art_director + tech_artist + concept_artist | wp_art_direction_跨平台美术资源规格.md |
| wp_ui_ux | ui_ux（组）→ ui_ux + tech_artist | wp_ui_ux_多端UIUX适配.md |
| wp_audio | audio_designer（角色级直投） | wp_audio_通用音频资源.md |

## 核心设计要点

1. **中立资产格式**：glTF/PNG/WAV 中立源 + 各引擎渲染副本，最大化素材复用
2. **素材分级体系**：L0（全引擎通用）/ L1（半通用）/ L2（引擎专属），复用策略明确
3. **资源管线**：中立源 → 格式转换 → 引擎副本，hash 校验保证跨端一致
4. **多端 UI 适配**：逻辑/适配/实现三层分离，设计令牌全端统一
5. **通用音频**：WAV 中立源 + 各引擎压缩分发，响度/延迟跨端统一

## 上游输入对接

- 策划线：wp_gameplay（素材复用策略）+ wp_combat（战斗视觉/听觉反馈）+ wp_narrative（叙事资源）
- 程序线：wp_client（UI/资源适配层接口）+ wp_engine（C ABI 中立格式）+ wp_ai_logic（程序化生成数据）
- 架构师：multi-engine-pipeline（中立资产格式 + 中间件设计）

## 下游解锁

- **测试线**（wp_testing）：对美术资源做跨引擎兼容性/性能验收
- **项目管理**（wp_release）：多引擎版本/里程碑发布
- **运营线**（wp_data_ops）：消费美术品质做多端市场预演
