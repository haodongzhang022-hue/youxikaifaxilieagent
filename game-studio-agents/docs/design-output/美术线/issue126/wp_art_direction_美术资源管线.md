# wp_art_direction · 美术资源管线（骨骼绑定/K动画/模型/贴图/材质/特效）

- **工作包**：wp_art_direction 美术资源管线
- **部门**：美术线
- **主责角色**：art_director（主美）+ concept_artist（原画）+ modeler（建模）+ animator（动画）+ vfx_artist（特效）+ tech_artist（技术美术）
- **模块**：art_direction
- **产出物类型**：art_doc（美术设计文档）
- **场景**：Issue #126「游戏团队深化，匹配引擎」——美术资源按四引擎层级差异化构建管线
- **前置依赖**：wp_gameplay ✅ / wp_numeric_model ✅ / wp_narrative ✅ / wp_combat ✅（策划线已全部验收通过）
- **对齐契约**：架构师 `art-line-contract.md`（引擎四层级资产管线契约）

---

## 一、美术资源管线总纲（art_director）

### 1.1 四引擎层级美术管线矩阵

**核心原则**：美术复杂度匹配引擎能力上限，同一世界观在不同引擎层级下美术深度不同。

| 维度 | L0 纯网页(React) | L1 Cocos | L2 Unity | L3 UE |
|------|-----------------|----------|----------|-------|
| 美术形态 | 2D/序列帧为主 | 2D+低模3D | 标准3D+动画 | 高模+PBR+物理 |
| 骨骼方案 | 无/序列帧 | Spine 2D / DragonBone | Humanoid | 完整骨骼+IK |
| 模型规格 | 100 tris(icon级) | 1K~5K tris | 30K~80K tris | 50K+ tris + Nanite |
| 贴图规格 | 256px | 512~1024px | 2048px PBR | 4096px PBR全套 |
| 渲染管线 | CSS/Canvas 2D | 2D/3D混合 | 标准渲染管线 | 全功能渲染 |
| 动画导演台 | CSS Timeline | Cocos Animation | Unity Timeline | UE Sequencer |
| 材质语言 | CSS样式/WebGL | 2D Shader | Standard Shader | PBR/Substance |
| 特效方案 | Canvas粒子 | 2D/3D粒子组件 | Particle System | Niagara/Cascade |

### 1.2 美术风格统一（跨引擎）

**「星穹守望者」** 统一风格：**赛博星核 × 失落文明**（对齐 wp_narrative 世界观）

- **色彩体系**：冷蓝主调（苍穹中枢）+ 暖金点缀（星核能量）+ 暗紫渲染（虚空侵蚀）
- **造型语言**：棱角+曲线混合（遗迹几何感 + 星械流线感）
- **材质语言**：锈蚀金属 / 发泡岩石 / 能量晶体（跨引擎共用一套）
- **光照方向**：统一光源方向，半现实光照 + 体积光强化

### 1.3 美术品质基准（art_quality）

| 维度 | L0 | L1 | L2 | L3 |
|------|:--:|:--:|:--:|:--:|
| base_quality | 50 | 60 | 68 | 78 |
| art_quality | 55 | 65 | 72 | 85 |
| art_sens | 0.15 | 0.18 | 0.22 | 0.28 |

> 美术品质进入市场预演沙盒（art_quality 维度博弈），L2 为商业化基准线 72.0。

---

## 二、骨骼绑定方案（animator · 对齐 art-line-contract）

### 2.1 跨引擎骨骼命名统一规范

统一命名约定（全引擎共用）：

```
bone_root → bone_spine → bone_chest
bone_shoulder_L/R → bone_arm_L/R → bone_forearm_L/R → bone_hand_L/R
bone_thigh_L/R → bone_leg_L/R → bone_foot_L/R
```

### 2.2 骨骼源格式与引擎映射

| 源格式 | L0 React | L1 Cocos | L2 Unity | L3 UE |
|--------|---------|----------|----------|-------|
| Spine | 序列帧 | Spine Runtime | 导入骨骼动画 | 转换FBX |
| DragonBone | — | DragonBone Runtime | 导入 | 转换FBX |
| FBX | — | 转换Spine | Humanoid Rig | 完整骨架 |
| glTF | 骨骼JSON | 转换 | Avatar Mask | Skeletal Mesh |
| Mixamo | — | 转换Spine | Humanoid 映射 | 重定向 |

### 2.3 骨骼绑定工作流

```
模型资产 → 骨骼创建 → 权重分配 → 约束设置 → 蒙皮测试 → 动画就绪
```

**四引擎差异**：
- **L0**：无骨骼，直接序列帧/精灵图
- **L1**：Spine/DragonBone 2D骨骼，IK约束，槽位插槽
- **L2**：Humanoid Avatar，T-Pose 校准，骨骼 Mask 分层
- **L3**：完整 Skeletal Mesh，Control Rig + 物理约束，IK 全程

### 2.4 风险与规避

| 风险 | 等级 | 规避方案 |
|------|:----:|---------|
| 骨骼跨引擎映射丢失 | **HIGH** | 统一命名 + Spine/FBX/glTF/Mixamo 映射表 + 验证工具 |
| 权重分配不均 | MEDIUM | 自动权重 + 手动细化（肩/髋/手指重点） |
| 骨骼命名冲突 | MEDIUM | 命名规范 + Lint 校验工具 |

---

## 三、K动画方案（animator · 对齐 wp_combat 战斗节奏）

### 3.1 战斗动画关键帧规格（对齐 wp_combat）

| 动画类型 | L0 | L1 | L2 | L3 |
|---------|:--:|:--:|:--:|:--:|
| 攻击前摇 | 0.1s | 0.12s | 0.15s | 0.18s（含蓄力） |
| 攻击后摇 | 0.05s | 0.08s | 0.12s | 0.15s（可取消） |
| 闪避无敌帧 | 0.2s | 0.25s | 0.3s | 0.3s |
| 受击停顿 | 50ms | 60ms | 60ms | 80ms |
| 弹反窗口 | — | 0.15s | 0.2s | 0.25s |

### 3.2 K动画关键帧工作流

```
概念姿态 → 基础动作 → 关键帧K帧 → 中间帧补全 → 曲线调优 → 引擎集成
```

**四引擎适配**：
- **L0**：序列帧动画（CSS keyframes / Canvas sprite）
- **L1**：Spine 骨骼动画关键帧 + 曲线
- **L2**：Unity Animation Clip + BlendTree + 动画状态机
- **L3**：UE AnimSequence + AnimBlueprint + 动画蒙太奇

### 3.3 动画状态机

```
Idle ↔ Move ↔ Attack ↔ Skill ↔ Hit ↔ Death
（每个状态含进入/退出过渡，跨引擎行为一致）
```

---

## 四、模型生成/上色/法线贴图/纹理/材质（modeler · 对齐 art-line-contract）

### 4.1 模型生成（Tripo 等 AI 工具）

| 引擎层级 | 生成方式 | 拓扑要求 | 面数预算 |
|---------|---------|---------|---------|
| L0 | 不适用（2D为主） | — | — |
| L1 | 2D图集/低模 | 三角面≤1K | 1K~5K tris |
| L2 | Tripo生成+人工优化 | 四边面优先 | 30K~80K tris |
| L3 | Tripo生成+高模烘焙 | 全四边面 | 50K+ tris + Nanite |

### 4.2 模型上色（PBR 工作流）

```
基础色 → AO烘焙 → 金属度/粗糙度 → 法线贴图 → 自发光 → PBR验证
```

| 参数 | L0 | L1 | L2 | L3 |
|------|:--:|:--:|:--:|:--:|
| 贴图分辨率 | 256px | 512~1024px | 2048px | 4096px |
| 材质通道 | 无 | 2D diffuse | PBR (albedo/normal/metallic/roughness) | PBR全套+Detail |
| 自发光 | — | 2D特效 | 自发光贴图 | Emission + Bloom |

### 4.3 法线贴图

| 引擎层级 | 烘焙方式 | 精度 | 输出 |
|---------|---------|:----:|------|
| L0 | — | — | 无 |
| L1 | 2D光照贴图 | 512px | 精灵光照 |
| L2 | 高模到低模烘焙 | 2048px | Normal Map |
| L3 | 高模烘焙+细节叠加 | 4096px | Normal + Detail Normal |

### 4.4 纹理与材质规格

**glTF 中立源格式** → 各引擎转换：

| 材质类型 | L0 | L1 | L2 | L3 |
|---------|:--:|:--:|:--:|:--:|
| 金属 | CSS渐变 | 2D Sprite | Standard Shader | PBR + Metalness |
| 岩石 | CSS图案 | 2D Tilemap | Standard Shader | PBR + Parallax |
| 能量晶体 | CSS发光 | 2D Glow | Unlit + Emission | Subsurface + Bloom |
| 半透明 | CSS opacity | 2D Alpha | Transparent | Translucent + IOR |

---

## 五、场景特效方案（vfx_artist · 对齐 art-line-contract）

### 5.1 特效预算矩阵

| 维度 | L0 | L1 | L2 | L3 |
|------|:--:|:--:|:--:|:--:|
| 粒子数/特效 | ≤100 | ≤200 | ≤500 | ≤2000（含GPU粒子） |
| 同屏特效数 | ≤5 | ≤10 | ≤20 | ≤40 |
| 后处理 | 无 | 2D Bloom | Bloom/AO/DOF | Full Post-Fx |
| 体积光 | 无 | 2D径向渐变 | 3D体积光 | 光线追踪阴影 |

### 5.2 特效类型与引擎映射

**JSON 中立定义** → 各引擎适配：

| 特效类型 | L0 | L1 | L2 | L3 |
|---------|:--:|:--:|:--:|:--:|
| 技能释放 | Canvas粒子 | Particle 2D | Particle System | Niagara |
| 命中反馈 | CSS震屏 | 2D Flash | Camera Shake | Physical Animation |
| 环境氛围 | CSS渐变 | 2D 光效 | 体积雾 | 大气散射 |
| 虚空侵蚀 | CSS滤镜 | 2D 腐蚀贴图 | 特效材质 | Niagara 顶点动画 |

### 5.3 特效规格（分引擎适配）

**L0**：Canvas 2D 粒子 + CSS animation，特效复用 CSS 类
**L1**：Cocos ParticleSystem + Sprite 帧动画，spine 角色特效叠加
**L2**：Unity Particle System 模块化配置，自定义 Shader 特效
**L3**：UE Niagara 系统 + GPU 粒子，物理模拟 + Mesh 发射器

---

## 六、动画导演台（Cutscene Director · tech_artist + animator · 对齐架构师）

### 6.1 导演台能力梯度（四引擎）

| 能力 | L0 | L1 | L2 | L3 |
|------|:--:|:--:|:--:|:--:|
| 时间轴 | CSS Timeline | Cocos Animation | Unity Timeline | UE Sequencer |
| 镜头调度 | CSS transform | 2D 摄像机 | CineMachine | Camera Sequencer |
| 角色表演 | 2D过渡 | Spine动画 | Animation Clip | Control Rig |
| 灯光控制 | CSS filter | 2D灯光 | 3D灯光 | UE Lighting |
| 音效同步 | Web Audio | AudioClip | AudioSource | AudioCue |

### 6.2 导演台工作流

```
分镜脚本 → 镜头蓝图 → 轨道编排 → 角色表演 → 灯光 → 音效 → 成片
```

### 6.3 接入 IPresentationAdapter

```
CutsceneDirector → IPresentationAdapter → 引擎具体实现
├─ L0: ReactTimelineAdapter
├─ L1: CocosAnimationAdapter
├─ L2: UnityTimelineAdapter
└─ L3: SequencerAdapter
```

---

## 七、渲染管线/资源优化（tech_artist · 对齐架构师 art-line-contract）

### 7.1 渲染管线性能预算

| 指标 | L0 | L1 | L2 | L3 |
|------|:--:|:--:|:--:|:--:|
| 帧率目标 | 60fps | 60fps | 60fps | 60fps |
| DrawCall 预算 | ≤50 | ≤100 | ≤200 | ≤500（含GPU Culling） |
| 显存占用 | ≤50MB | ≤200MB | ≤800MB | ≤4GB |
| 加载预算 | ≤1s | ≤2s | ≤5s | ≤10s |

### 7.2 资源优化策略

- **L0**：CSS sprite 合并、Canvas 合批、按需加载
- **L1**：图集打包、音频压缩、贴图Mipmap、资源异步加载
- **L2**：AssetBundle 分包、LOD 分级、GPU Instancing、Addressable 管理
- **L3**：Nanite 自动 LOD、World Partition、流式加载、Shader 合并

### 7.3 C ABI 资产接口需求（供程序线后续实现）

定义 `cabi_asset.h` 系列接口（模型/动画/贴图/法线/骨骼映射/特效/完整性校验），程序线后续实现。

---

## 八、产出物清单

| 子任务 | 承接角色 | 产出说明 |
|--------|---------|---------|
| 美术资源管线总纲 | art_director | 四引擎层级美术管线定义、品质基准、风格约束 ✅ |
| 角色/场景概念设计 | concept_artist | 角色概念设计 + 四引擎层级原画规格适配 ✅ |
| 骨骼绑定/K动画 | animator | 四引擎骨骼命名统一 + K动画关键帧工作流 ✅ |
| 模型/上色/贴图/材质 | modeler | glTF中立源 + PBR上色 + 法线烘焙 + 纹理材质规格 ✅ |
| 场景特效方案 | vfx_artist | 四引擎特效预算与规格，JSON中立定义 ✅ |
| 动画导演台+渲染优化 | tech_artist | 导演台四引擎适配 + 渲染管线性能预算 ✅ |

**跨部门协作**：
- 上游：消费策划线 wp_gameplay / wp_numeric_model / wp_narrative / wp_combat（已解锁）
- 跨仓：对齐架构师 art-line-contract（引擎四层级资产管线契约）
- 下游：程序线实现 cabi_asset.h 接口，测试线做四引擎兼容性/性能验收

---

*产出类型：art_doc（美术设计文档）*
*生成：美术线 · wp_art_direction · Issue #126*
*状态：✅ DONE*
