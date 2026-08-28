# 美术线 · 引擎资源管线验证报告（wp_engine_art_verification）

> 承接：PR #79 合并后解锁 · 美术线引擎资源验证工作包
> 主责：art_director（美术线统一头） · 协办：tech_artist / audio_designer
> 依赖：程序线 `wp_engine_adaptation_fix`（audio_resource_extension 修复）

## 一、验证目标

基于游戏引擎适配层（`config/engine_adapters.py`），验证 **Cocos Creator** 与 **Unreal Engine**
双引擎的美术资源管线产出正确性，重点验证程序线修复后的 `audio_resource_extension` 字段。

## 二、验证内容与结果

### 2.1 引擎资源规范（engine_adapters.py）

| 引擎 | 资源类型 | 扩展名 | 导入目录 | 验证结果 |
|------|---------|--------|---------|:---:|
| **Cocos Creator** | sprite | `.png` | `assets/textures` | ✅ |
| | audio | `.mp3` | `assets/audio` | ✅ |
| | animation | `.anim` | `assets/animations` | ✅ |
| | prefab | `.prefab` | `assets/prefabs` | ✅ |
| | scene | `.scene` | `assets/scenes` | ✅ |
| | script | `.ts` | `assets/scripts` | ✅ |
| **Unreal Engine** | mesh | `.fbx` | `Content/Models` | ✅ |
| | material | `.uasset` | `Content/Materials` | ✅ |
| | audio | `.wav` | `Content/Audio` | ✅ |
| | animation | `.uasset` | `Content/Animations` | ✅ |
| | blueprint | `.uasset` | `Content/Blueprints` | ✅ |
| | script | `.cpp` | `Source/` | ✅ |

### 2.2 audio_resource_extension Bug 修复验证

**Bug 原问题**：`department_agents.py` 中 `audio_resource_extension` 取 `engine.resource_specs()[0].extension`，
即**第一个资源规格**的扩展名：
- Cocos Creator 第一个规格为 sprite（`.png`）→ **错误**（应 `.mp3`）
- Unreal Engine 第一个规格为 mesh（`.fbx`）→ **错误**（应 `.wav`）

**修复后**：改为按 `resource_type == "audio"` 筛选：
```python
"audio_resource_extension": next(
    (rs.extension for rs in engine.resource_specs() if rs.resource_type == "audio"),
    ""
)
```

| 引擎 | 修复前（Bug） | 修复后（正确） | 验证 |
|------|:---:|:---:|:---:|
| Cocos Creator | `.png` ❌ | `.mp3` ✅ | ✅ |
| Unreal Engine | `.fbx` ❌ | `.wav` ✅ | ✅ |

### 2.3 ArtDeptAgent 引擎感知产出验证

通过 ArtDeptAgent 执行 `audio` 模块工作包，验证引擎感知字段正确：

**Cocos Creator（默认引擎）**：
```
engine: Cocos Creator
engine_type: cocos_creator
audio_resource_extension: .mp3  ✅
audio_import_dir: assets/audio   ✅
build_command: cocos build --platform windows  ✅
```

**Unreal Engine（CNB_ENGINE=unreal_engine）**：
```
engine: Unreal Engine
engine_type: unreal_engine
audio_resource_extension: .wav  ✅
audio_import_dir: Content/Audio  ✅
build_command: RunUAT BuildCookRun -platform=windows -project=Game.uproject  ✅
```

### 2.4 回归测试验证

| 测试脚本 | 断言数 | 结果 |
|---------|:---:|:---:|
| `test_engine_adapters.sh` | 16/16 | 🟢 通过 |
| `test_art_testing.sh` | 9/9 | 🟢 通过 |
| `test_engine_bridge.sh` | 35/35 | 🟢 通过 |

## 三、结论

**✅ 验证通过** —— 引擎资源管线产出正确，`audio_resource_extension` Bug 已修复生效。

- Cocos Creator 音频资源扩展名正确返回 `.mp3`；
- Unreal Engine 音频资源扩展名正确返回 `.wav`；
- ArtDeptAgent 引擎感知产出字段完整（engine / engine_type / audio_resource_extension / audio_import_dir / build_command）；
- 回归测试全绿，无影响既有美术生态角色接入链路。

## 四、产出物清单

| 产出物 | 路径 | 说明 |
|--------|------|------|
| 引擎资源管线验证报告 | `docs/design-output/美术线/wp_engine_art_verification_引擎资源管线验证.md` | 本文档 |
