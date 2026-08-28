# wp_art_testing · 美术线生态角色接入验收回归

> 承接 Issue #32 `wp_art_testing` 工作包（测试线·qa_engineer）。
> 对美术线生态角色接入（wp_art_direction / wp_ui_ux / wp_audio）做全链路验收回归。

## 一、验收范围

| 工作包 | 验收项 | 验证方式 |
|--------|--------|---------|
| `wp_art_direction` | 美术品质进入市场预演 | `market_simulator.py` 输出 `art_satisfaction` / `art_quality` |
| `wp_ui_ux` | UI/UX 角色可被派发 | `ArtDeptAgent` 承接 `ui_ux` 工作包产出交互规范 |
| `wp_audio` | 音频角色可被派发 + 音频入市场预演 | `market_simulator.py` 输出 `audio_immersion` / `audio_quality`；`eco_audio_designer` 已注册 |
| 全链路 | 依赖链正确解锁 | `DispatchCapability` 派发链：wp_art_direction → wp_ui_ux/wp_audio → wp_art_testing |

## 二、验收标准

1. **wp_art_direction**：`market_simulator` 包含 `art_satisfaction` 指标，`art_quality` 进入市场预演；
2. **wp_ui_ux**：`ArtDeptAgent` 执行 `ui_ux` 工作包验收通过，产出交互规范，可派发给 `tech_artist`；
3. **wp_audio**：`market_simulator` 包含 `audio_immersion` 指标，`eco_audio_designer` 已注册；
4. **全链路**：`wp_art_testing` 依赖（wp_ui_ux + wp_audio）满足后可从派发能力模块追踪。

## 三、测试信号灯

```bash
bash game-studio-agents/tests/test_art_testing.sh
# 9 项断言全绿
```

## 四、引擎适配联动

本工作包同时验证了引擎适配层（`config/engine_adapters.py`）——
美术资源（sprite/audio/animation/prefab）的格式与导入路径与
Cocos Creator / Unreal Engine 深度挂钩。

```bash
bash game-studio-agents/tests/test_engine_adapters.sh
# 16 项断言全绿
```
