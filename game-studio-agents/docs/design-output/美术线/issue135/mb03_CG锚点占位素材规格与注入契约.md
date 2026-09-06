# MB-03 · CG 锚点占位素材规格与注入契约（Demo 桩落地 · Issue #135 M-B）

> 承接：美术线（部门级 · 部门头 @分工 拆派 5 角色）
> 上游输入：美术线 WP-03《各引擎高画质 CG 锚点素材与视觉标准》✅（规格级）+ 程序线 MB-01 funnel_demo / MB-02 cloud_stub ✅（逻辑级已合入）
> 程序对接：`FunnelState.play_cg()` 返回 `cg_anchor_playing` 遮罩态，等待美术 MB-03 素材由表现层注入
> 定位：**把 WP-03 的三镜头视觉标准落成 M-B Demo 桩（L0/L1）CG_ANCHOR 环节可直接消费的「占位素材规格 + 表现层注入契约」**
> 阶段合规：MVP 落 L0/L1 预渲染占位（WebM/序列帧最小集）；L3 实时 CG 素材留 UE 阶段储备

---

## 〇、一句话结论

> MB-03 交付 **「三镜头最小可呈现的 CG 锚点占位包 + 可对接 funnel_demo 的素材注入契约」**——
> 引擎逻辑（程序已留 `cg_anchor_playing` 遮罩态）不动，美术把 WP-03 三镜头（苍穹中枢/星核晶体/虚空侵蚀）
> 按 L0/L1 各端规格降为**序列帧/轻量动效占位**，并给出 JSON 注入清单，让 Demo 桩「点增强画质→CG 遮罩→跳云」真正有画面可看。

---

## 一、路由守卫与承接确认

- 路由标记 `.routing_active.txt` = `程序线 美术线` → 美术线 active。
- 程序线 MB-01/02 报告明确登记：**MB-03** 由美术线本轮同步承接（经理级联派发），程序线以 `cg_anchor_playing` 占位态预留接入点。
- 本部门被点名承接 **MB-03**（NORMAL · 部门级）。

| 工作包 | 内容 | 责任部门 | 优先级 | 依赖 | 状态 |
|--------|------|---------|:------:|------|:----:|
| MB-03 | CG 锚点占位素材（WP-03 标准落地，供漏斗②CG遮罩呈现） | **美术线** | NORMAL | WP-03 ✅ + 程序 MB-01/02 ✅ | ✅ DONE |

---

## 二、程序侧 CG_ANCHOR 呈现时序回顾（tech_artist · 对齐程序 MB-01）

程序 `FunnelState` 五环节走通，CG 处于环节③遮罩：
```
LOCAL_LITE →[request_enhance:CG_PLAY]→ CG_ANCHOR
  → play_cg() 返回 "cg_anchor_playing"(遮罩态)
  → CG 播完 jump_cloud：Prewarm(遮罩期后台预热) → Apply(假跳云激活)
→ CLOUD_PLAY →[download 90% 预释放]→ LOCAL_FULL
```
**美术侧关键约束**：CG 遮罩期 = 云实例「后台 Prewarm/Apply」的**等待遮罩**，
即 CG 展示时长需 ≥ 云预热所需时长，避免 CG 播完云还没就绪的裸等。
WP-03 已定 CG 时长 5-15s；MB-03 给 L0/L1 Demo 桩取**固定 8s** 占位（对齐 prewarm 默认 30s 内、视觉护栏≥跳云就绪的可行档）。

### 2.1 遮罩态表现层注入点（供程序/表现层引用）
| 环节 | 程序返回态 | 美术注入内容 | 注入形式 |
|------|-----------|-------------|---------|
| ③ CG 锚点播放 | `cg_anchor_playing` | 三镜头占位 CG（L0 序列帧/轻量 WebM、L1 骨骼动画/预渲染） | 按 `cg_asset_manifest` JSON 清单加载并播放 |
| 过渡到云 | `jump_cloud`（Apply） | 过渡遮罩（传送门/白光/黑屏三选一） | `cg_transition` 特效层 |

> MB-03 只交付「规格 + 注入契约 + 占位序列帧定义」，实际位图/视频帧在本里程碑后由后续素材开发按此规格产出注入；Demo 桩先用**程序内可生成的占位图**（如纯色/渐变 + 镜头语义色块）保证「有画面可看」。

---

## 三、三镜头 L0/L1 占位素材规格（concept_artist · S-3.2）

基于 WP-03 §六 三镜头概念帧规格，落成 L0/L1 Demo 桩可用的**占位序列帧规格**：

### 3.1 镜头 A「苍穹中枢」· 大场景俯冲（5s）
| 维度 | L0 网页 | L1 Cocos 小程序 |
|------|--------|----------------|
| 呈现形式 | 720p 渐变背景 + 冷蓝主调 + 星轨粒子 SVG 动效 | 1080×1920 竖版静态过场 + 缓动 zoom |
| 序列帧 | 12 帧关键帧（俯冲→环绕→定格） | 8 帧关键帧（竖版裁剪） |
| 色彩 | 冷蓝 #2A4A8A 主 + 暖金 #FFD700 核心光 | 同 L0，竖版构图 |
| 占位兜底 | 冷蓝→暖金径向渐变 + 环形星轨线条 | 同上 |

### 3.2 镜头 B「星核能量晶体」· 特写（4s）
| 维度 | L0 网页 | L1 Cocos 小程序 |
|------|--------|----------------|
| 呈现形式 | 暖金发光圆核 + 呼吸脉冲(透明度正弦) | 竖版晶体剪影 + 辉光脉冲 |
| 序列帧 | 10 帧关键帧（缓推→自转→脉冲） | 8 帧关键帧 |
| 色彩 | 暖金 #FFD700 中心 + 冷蓝 #3A6AC8 环境 | 同 L0 |
| 占位兜底 | 暖金圆形渐变 + 脉动光圈 | 同上 |

### 3.3 镜头 C「虚空侵蚀边界」· 战斗张力（4-6s，取 5s）
| 维度 | L0 网页 | L1 Cocos 小程序 |
|------|--------|----------------|
| 呈现形式 | 暗紫底 + 蓝色护盾光弧 + 粒子涌 | 竖版暗紫渐变 + 蓝紫冷热对抗色带 |
| 序列帧 | 12 帧（粒子涌→护盾展开→定格） | 8 帧关键帧 |
| 色彩 | 暗紫 #5B2A6E 主 + 蓝 #4A9CFF 盾光 + 暖金点缀 | 同 L0 |
| 占位兜底 | 暗紫→蓝光径向渐变 + 护盾弧线 | 同上 |

> 每镜头占位素材用**程序可程序化生成的纯色/渐变 + 语义图形**即可，不给后续素材开发设门槛，
> 只锁「构图/色彩/时长」三要素与 WP-03 母版一致（画质承诺认知链护栏）。

---

## 四、占位素材注入契约（tech_artist · S-3.3）

### 4.1 cg_asset_manifest JSON（供表现层加载 CG）
```json
{
  "manifest_version": "1.0",
  "milestone": "M-B_Demo_L0L1",
  "player": "placeholder",
  "total_duration_s": 14,
  "cg_segments": [
    {"id":"cg_A_shenqiong","anchor":"苍穹中枢","duration_s":5,
     "engines":{"web_l0":{"media":"placeholder_gradient","bg":"#2A4A8A","glow":"#FFD700","frames":12,"present":"svg_dolly"},
                "cocos_l1":{"media":"placeholder_vertical","bg":"#2A4A8A","glow":"#FFD700","frames":8}}},
    {"id":"cg_B_xinghe","anchor":"星核晶体","duration_s":4,
     "engines":{"web_l0":{"media":"placeholder_glow","core":"#FFD700","env":"#3A6AC8","frames":10,"present":"pulse"},
                "cocos_l1":{"media":"placeholder_vertical","core":"#FFD700","env":"#3A6AC8","frames":8}}},
    {"id":"cg_C_xukong","anchor":"虚空侵蚀","duration_s":5,
     "engines":{"web_l0":{"media":"placeholder_particle","bg":"#5B2A6E","shield":"#4A9CFF","frames":12,"present":"shield_pulse"},
                "cocos_l1":{"media":"placeholder_vertical","bg":"#5B2A6E","shield":"#4A9CFF","frames":8}}}
  ],
  "transition": {
    "type":"portal", "bg_cover":"#FFFFFF",
    "portal_color":"#FFD700", "duration_ms":1200,
    "fallback":{"type":"blackfade","duration_ms":600}
  }
}
```
> 表现层加载此清单，按引擎分支取对应 `media` 占位类型渲染 CG_ANCHOR 遮罩；
> 真 CG 位图/视频就绪后仅替换 `media` 字段即可，契约不变（跨引擎同构）。

### 4.2 过渡遮罩（portal 优先）
- 对齐 WP-03 §3.2 传送门方案：能量传送门亮起 → 白光扩散遮盖 → 新画质展开，1-1.5s。
- 兜底：黑屏淡入（对齐程序超时降级护栏，≤2s）。
- L0 用序列帧/纯色盖白、L1 用骨骼动效盖白；L2/L3 实时粒子/着色器留对应引擎。

---

## 五、CG 遮罩期性能预算（tech_artist · S-3.4）

| 端 | CG 播放帧率 | 占位过渡 GPU | 切换过渡时长 | 全链路（点增强→CG 首帧） |
|----|:--:|:--:|:--:|:--:|
| L0 网页 | 24fps | 无（纯色/渐变+SVG） | ≤1.5s | ≤2s |
| L1 Cocos | 30fps | ≤5% | ≤1.5s | ≤2s |
| L2 Unity | 30fps | ≤10%（储备） | ≤2s | ≤1.5s |
| L3 UE | 实时 60fps | ≤15%（储备） | ≤2s | ≤1s |

> L0/L1 Demo 桩用**程序化占位**（无位图/视频解码开销），全链路 ≤2s 可达，满足 WP-02 §3.3 首帧护栏。

---

## 六、CG 遮罩期 UI 与音效最小呈现（对齐 WP-03 §八/§九）

### 6.1 遮罩期 UI 覆盖（ui_ux · 最小集）
- CG_ANCHOR 期间右下角出现**轻量「增强画质」微提示**（金色呼吸描边，非弹窗强推），对齐 WP-03 §8.1。
- 过渡完成后 Toast「完整版已就绪，画质已升级」。
- **视觉护栏**：不遮挡 CG 主体；过渡 ≤2s，超时降级黑屏淡入。

### 6.2 遮罩期音效（audio_designer · 最小集）
- 每镜头配 2-3s 情绪垫乐占位（对齐 WP-03 §9 风格：镜头A 交响庄严 / 镜头B 神秘晶体 / 镜头C 紧张）。
- 过渡音效：传送门开启嗡鸣→金属"洞开"（0.8-1.2s）。
- L0 MP3 128kbps / L1 AAC 128kbps 占位。

---

## 七、角色分工与产出物（group_audit）

| 子任务 | 承接角色 | 产出 |
|--------|---------|------|
| MB-03 总纲 + 三镜头覆盖核对 + 与 WP-03 衔接 | art_director | §〇/§一 + 全文档主美审校 |
| 三镜头 L0/L1 占位序列帧规格 | concept_artist | §三 三镜头素材规格表 |
| CG 占位序列帧节奏/时长对齐 funnel_demo 过渡时序 | animator | §三 时序 + §五 性能预算节奏 |
| CG 遮罩过渡特效占位规格（传送门/白光最小集） | vfx_artist | §四.2 过渡遮罩 + manifest transition |
| 注入契约 JSON + 表现层接入 funnel_demo play_cg + 性能预算 | tech_artist | §四 cg_asset_manifest + §五 |

- 协作工作台留痕：`mb03_group_audit.json`（DELEGATE SPLIT → 5 子任务派发 → 各角色 SUB_ACCEPT/SUB_COMPLETE → DONE，11 事件）

---

## 八、跨部门协作记录（request_peer）

| 协作方向 | 部门 | 协作内容 | 状态 |
|---------|------|---------|:----:|
| 下游消费 | 程序线 MB-01/02 | 消费 `funnel_demo.play_cg()` / `cloud_stub` CG 遮罩接入点，素材按 `cg_asset_manifest` 注入 | ✅ 已对齐（本轮并行）|
| 上游消费 | 美术线 WP-03 | 复用三镜头视觉标准 + 过渡遮罩三套方案 + 各端规格 | ✅ 已解锁 |
| 下游输出 | 项目管理 WP-04 / 经理 G2 门禁 | MB-03 完成，待经理验收 G2 单版体验门禁 | 🔗 供 G2 验收 |

---

## 九、阶段护栏校验

| 内容 | 阶段归属 | 合规判断 |
|------|---------|:--------:|
| 三镜头 L0/L1 占位素材规格 + 注入契约 | MVP Demo 桩可落 | ✅ 本阶段内 |
| 程序化占位（纯色/渐变/语义图形） | Demo 桩现在可用 | ✅ 本阶段内 |
| 真 CG 位图/视频帧 | 后续素材开发按契约注入 | 🔗 契约就绪、素材后续补 |
| L2/L3 实时 CG + 无缝切换 | UE 阶段储备 | ✅ 本包只给规格不硬做 |

> **护栏结论**：MB-03 交付**占位素材规格 + 注入契约**，Demo 桩以程序化占位「有画面可看」，
> 不产 L3 实时 CG / 真云渲染素材，符合「阶段不对就算错」铁律。

---

## 十、结论

1. MB-03 把 WP-03 三镜头视觉标准落到 M-B Demo 桩可消费的**占位素材规格 + 注入契约**
2. 程序 `cg_anchor_playing` 遮罩态与美术 `cg_asset_manifest` 清单对接，契约跨引擎同构、素材可就绪替换
3. 阶段护栏成立：Demo 桩程序化占位可跑通，L3 实时 CG / 无缝切换留 UE 储备
4. 供经理 **G2 单版体验门禁**验收（MB-01/02/03 齐备）

*产出：美术线 art_director + concept_artist + animator + vfx_artist + tech_artist 协作产出（group_audit 留痕 11 事件）。*
