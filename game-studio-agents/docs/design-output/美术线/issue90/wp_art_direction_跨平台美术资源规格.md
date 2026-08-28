# wp_art_direction · 跨平台美术资源规格（Issue #90）

- **工作包**：wp_art_direction 跨平台美术资源规格
- **部门**：美术线
- **主责角色**：tech_artist（技术美术·管线向）组 → art_director（主美·品质向）+ tech_artist + concept_artist（原画·风格向）协作
- **模块**：art_direction / cross-engine-asset
- **产出物类型**：art_doc（跨平台美术资源规格设计文档）
- **场景**：Issue #90「跨平台架构增强」——需在 Web→Cocos→Unity→UE 四级引擎间建立统一的美术资源规格，保障素材复用与跨引擎迁移

---

## 一、跨平台美术资源规格设计原则

### 1.1 核心目标

> 让**同一份源资产**在所有引擎中产出**一致的美术表现**，最大化素材复用，最小化引擎迁移成本。

### 1.2 设计原则

| 原则 | 说明 |
|------|------|
| **中立源优先** | 所有美术资产以中立格式（glTF/PNG/WAV）存储于 `assets/source/`，各引擎只存渲染副本 |
| **分级复用** | 素材按「通用性 × 精度」分级：L0（全引擎通用）/ L1（半通用）/ L2（引擎专属高保真） |
| **确定性输出** | 程序化生成 + 资源管线输入确定性参数 → 输出一致结果（跨引擎 hash 校验） |
| **纹理/模型/材质/动画/音频五维解耦** | 各资源维度独立可替换，降低级联迁移成本 |
| **元数据驱动** | 每份资产携带统一 metadata（asset_id/format/version/tags），支持管线自动检索 |

### 1.3 源资产格式标准

| 资产类型 | 中立格式 | 说明 | 引擎转换目标 |
|---------|---------|------|------------|
| 3D 模型 | `.glb`（glTF 2.0 二进制） | PBR 材质 + 骨骼动画 + 顶点动画 | Cocos `.prefab` / Unity `.prefab` / UE `.uasset` |
| 纹理贴图 | `.png`（无损源）/ `.webp`（压缩分发） | 支持 PBR 通道 | 各引擎专用贴图格式 |
| 2D 立绘 | `.png`（透明背景） | 角色/UI/物品图标 | 各引擎 2D 资源 |
| 骨骼动画 | 内嵌 glTF | 动作数据中立存储 | 各引擎动画资源 |
| 音频 | `.wav`（无损源）/ `.mp3`/`.ogg`（压缩） | 环境/战斗/UI/BGM | 各引擎音频导入 |
| 场景数据 | `.json`（Level Schema） | 中立关卡/场景布局 | 各引擎场景文件 |
| 特效数据 | `.json` + `.png` 序列 | 程序化特效参数 + 贴图序列 | 各引擎粒子/材质 |

---

## 二、美术资源分级体系（L0 / L1 / L2）

### 2.1 分级定义

```
L0（全引擎通用）─→ 适用于 Web/Cocos/Unity/UE 全端
L1（半通用）   ─→ 适用于 Unity/UE 等中高配引擎（2D+3D混合）
L2（引擎专属） ─→ 特定引擎高保真资源（UE Nanite 等）
```

| 级别 | 资产特征 | 精度/规格 | 使用引擎 | 复用策略 |
|------|---------|----------|---------|---------|
| **L0** | 2D 立绘、图标、UI 贴图、基础音频 | 128~512px，低面数（≤5K面），MP3 128kbps | Web / Cocos | 全局共享，零转换 |
| **L1** | 中精度 3D 模型、场景物件、角色（低模） | 5K~30K面，1024px 贴图，FBX/glTF | Unity / Cocos(高配) | 转换后共享，需压缩 |
| **L2** | 高精度 3D 模型、Nanite 场景、4K 贴图 | ≥100K面，4096px+，UE 原生资产 | UE | 引擎专属，不共享 |

### 2.2 各引擎资源规格对照

| 引擎 | 渲染能力 | 模型面数上限 | 贴图规格 | 音频格式 | UI 框架 |
|------|---------|------------|---------|---------|---------|
| Web/React | WebGL/Canvas | L0 ≤5K 面 | 512px | MP3 128kbps | React DOM |
| Cocos | Cocos Renderer | L0-L1 ≤30K 面 | 1024px | OGG/MP3 | Cocos UI |
| Unity | URP/HDRP | L1-L2 ≤100K 面 | 2048-4096px | WAV/OGG | uGUI/UI Toolkit |
| UE5 | Nanite/Lumen | L2 ≥100K 面 | 4096px+ | WAV | UMG |

---

## 三、资源管线设计

### 3.1 管线架构

```
assets/source/                    # 中立源资产（唯一真相）
├── models/*.glb                  # 3D 模型（含骨骼动画）
├── textures/*.png                # 纹理贴图（PBR 通道）
├── sprites/*.png                 # 2D 立绘/图标
├── audio/*.wav                   # 音频源
├── levels/*.json                 # 场景数据
├── metadata/*.json               # 资产元数据
└── shaders/*.json                # 材质/Shader 参数

        │  资源管线（AssetPipeline）
        ▼
assets/engine/                    # 各引擎渲染副本（自动生成）
├── web/                          # React/WebGL 资源
├── cocos/                        # Cocos Creator 资源
├── unity/                        # Unity 资源
└── unreal/                       # Unreal Engine 资源
```

### 3.2 管线流程

```python
# 管线伪代码
def asset_pipeline(source_path, target_engine):
    """将中立源资产转换为目标引擎渲染副本"""
    metadata = load_metadata(source_path)        # 读取元数据
    asset_type = metadata["asset_type"]          # model/texture/audio/...
    
    # 1. 格式转换
    if asset_type == "model":
        converted = gltf_to_engine(source_path, target_engine)
    elif asset_type == "texture":
        converted = png_to_engine(source_path, target_engine, 
                                  engine_tex_size[target_engine])
    elif asset_type == "audio":
        converted = audio_to_engine(source_path, target_engine)
    elif asset_type == "sprite":
        converted = png_to_sprite(source_path, target_engine)
    
    # 2. 压缩/优化
    optimized = optimize_for_engine(converted, target_engine)
    
    # 3. 生成引擎资源文件
    engine_asset = create_engine_asset(optimized, target_engine)
    
    # 4. hash 校验（跨引擎一致性）
    hash = sha256(source_file)
    verify_engine_hash(engine_asset, hash)
    
    return engine_asset
```

### 3.3 资源转换规则

| 源格式 | Web/React | Cocos | Unity | UE5 |
|--------|----------|-------|-------|-----|
| `.glb` → | WASM 内嵌 / glTF loader | `.prefab` | `.prefab` + FBX 导入 | `.uasset` + FBX 导入 |
| `.png` → | WebP/PNG | PNG/WebP | PNG/TGA | PNG/BC7 |
| `.wav` → | MP3/OGG | OGG/MP3 | WAV/OGG | WAV |
| 动画 → | JSON 骨骼 | 骨骼动画 | Mecanim | Animation Sequence |

### 3.4 程序化生成资产对接

程序化生成核心（C++ 中间件 `cabi_procgen`）输出**中立 JSON 数据**，美术线资源管线将其转换为各引擎原生对象：

```json
// 程序化生成输出 → 美术管线输入
{
  "asset_id": "procgen_tree_oak_01",
  "category": "environment/props/tree",
  "base_mesh": "assets/source/models/tree_oak_base.glb",
  "materials": {
    "trunk": {"type": "pbr", "base_color": "#6B4F3A", "roughness": 0.8},
    "leaves": {"type": "pbr", "base_color": "#2E7D32", "roughness": 0.6}
  },
  "variants": {
    "seed": 42,
    "scale_range": [0.8, 1.2],
    "leaf_density": 0.7
  }
}
```

---

## 四、美术品质基准与校验

### 4.1 品质基准（跨引擎统一）

| 品质维度 | 基准值 | 说明 |
|---------|--------|------|
| base_quality | 65.0 | 基础资源品质（所有引擎达标） |
| art_quality | 72.0 | 美术整体品质（中上水准） |
| art_sens | 0.2 | 泛玩家美术敏感度偏好 |
| performance_budget | 按引擎分级 | Web≤5MB / Cocos≤30MB / Unity≤500MB / UE≥1GB |

### 4.2 跨引擎一致性校验

**一致性校验器**（`tools_dev` 提供）确保同一源资产在四引擎中渲染结果一致：

| 校验项 | 方法 | 容差 |
|--------|------|------|
| 模型顶点数 | glTF 顶点 vs 引擎导入顶点 | ≤2% 偏差 |
| 贴图色彩 | PNG 像素 vs 引擎贴图采样 | ΔE ≤3 |
| 材质参数 | JSON vs 引擎材质属性 | 参数匹配 |
| 动画时长 | glTF 动画 vs 引擎动画 | ≤1帧 偏差 |
| 音频响度 | WAV 响度 vs 引擎播放响度 | ≤1dB |

### 4.3 素材复用率指标

| 指标 | 目标值 | 当前 | 说明 |
|------|--------|------|------|
| L0 素材复用率 | ≥70% | — | 2D/UI/音频在全部引擎共享 |
| L1 素材复用率 | ≥50% | — | 3D 模型在 Unity/UE 间共享 |
| 引擎转换自动化率 | ≥80% | — | 资源管线自动转换比例 |
| 程序化生成覆盖率 | ≥40% | — | 场景/装饰/地形程序化生成占比 |

---

## 五、美术风格在跨平台中的一致性

### 5.1 风格基准（跨引擎不变项）

「赛博星核 × 失落文明」风格在四引擎中**保持一致**：

| 风格维度 | 统一标准 | Web | Cocos | Unity | UE |
|---------|---------|-----|-------|-------|-----|
| 色彩体系 | 冷蓝 #1E3A5F + 暖金 #D4A017 + 虚空紫 #6B21A8 | ✅ 全平台统一 | ✅ | ✅ | ✅ |
| 光照方向 | 全局统一（主光角度/强度/色温） | WebGL 近似 | Cocos 近似 | 物理光照 | 物理光照 |
| 材质语言 | 锈蚀金属/发泡岩石/能量晶体 三套标准 | 简化 PBR | PBR | 完整 PBR | Nanite PBR |
| 粒子质感 | 星核高光粒子 + 虚空侵蚀腐蚀纹理 | Canvas 粒子 | Cocos 粒子 | VFX Graph | Niagara |

### 5.2 引擎差异下的风格实现策略

| 引擎 | 风格实现方式 | 降级策略 |
|------|------------|---------|
| Web | 2D 立绘 + CSS 3D + WebGL 简化渲染 | 静态立绘替代 3D 场景 |
| Cocos | 2D + 3D 混合，中低面数模型 | L0 素材 + 简化特效 |
| Unity | 完整 3D + PBR + URP | 高质量光照 + L1 素材 |
| UE5 | Nanite 几何 + Lumen 光照 + 高级材质 | 最高保真 + L2 素材 |

---

## 六、资源规格与美术角色的协同

### 6.1 各角色职责

| 角色 | 跨平台资源规格职责 | 产出 |
|------|------------------|------|
| **art_director** | 风格基准统一 + 跨引擎品质把控 | 风格基线 + 品质标准 |
| **tech_artist** | 资源管线实现 + 格式转换 + 性能优化 | 管线设计 + 转换规则 + 校验器 |
| **concept_artist** | 2D 源立绘 + 场景概念图（L0 级） | 立绘 PNG + 概念图 |
| **modeler** | 3D 模型（L1/L2 级） | glTF 模型 + 骨骼 |
| **animator** | 通用动画（glTF 内嵌） | 骨骼动画数据 |
| **vfx_artist** | 特效参数（JSON）+ 贴图序列 | 特效数据 + 粒子贴图 |
| **audio_designer** | 通用音频（WAV/MP3） | 音频资产 |

### 6.2 角色间协作流程

```
concept_artist（概念设计）
    │  设计稿 → PNG 立绘 + 概念图（L0）
    ▼
modeler（建模）
    │  概念图 → 3D 模型 → .glb（L1/L2）
    ▼
animator（动画）
    │  模型 → 骨骼动画 → glTF 内嵌
    ▼
vfx_artist（特效）
    │  特效参数 JSON + 粒子贴图（L0）
    ▼
tech_artist（管线）
    │  统一转换 → 各引擎资源副本
    ▼
各引擎渲染

art_director（品质把关）
    │  全流程品质基准校验
    ▼
最终交付
```

---

## 七、跨部门协作依赖

| 协作方向 | 部门 | 协作内容 |
|---------|------|---------|
| 上游消费 | @策划线 | 消费 wp_gameplay 素材复用策略 + wp_combat 战斗视觉反馈 + wp_narrative 叙事资源清单 |
| 上游消费 | @程序线 | 消费 wp_client 资源层接口 + wp_engine C ABI 资产格式 + wp_ai_logic 程序化生成中立数据 |
| 下游解锁 | @测试线 | 对美术资源做跨引擎兼容性/性能验收 |
| 协同 | @运营线 | 消费美术品质基准做市场预演 |

---

## 八、交付物清单

| 交付物 | 位置 | 说明 |
|--------|------|------|
| 中立资产格式规范 | `assets/source/` Schema | 与中间件 `02-middleware-design.md` 对齐 |
| 资源管线设计 | 本文档 §三 | 转换/优化/hash 校验流程 |
| 素材分级体系 | 本文档 §二 | L0/L1/L2 分级 |
| 各引擎资源规格表 | 本文档 §2.2 | 四引擎资源参数对照 |
| 一致性校验规则 | 本文档 §4.2 | 跨引擎渲染一致性校验 |
| 风格一致性方案 | 本文档 §五 | 四引擎风格统一策略 |

> 全程机制驱动：美术线部门统一头承接 → CollaborationWorkbench 组内分工（art_director/tech_artist/concept_artist/modeler/animator/vfx_artist）→ group_audit 留痕 → REVIEW_RESULT 上报。
