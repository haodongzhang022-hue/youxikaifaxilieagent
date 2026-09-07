# 🎨 wp_style_index · 可检索风格索引（P2）

> **Issue**：#133「尝试美工增强」 · **工作包**：wp_style_index（P2 可检索风格索引）
> **责任部门**：美术线 · **路由状态**：已激活（.routing_active.txt = 美术线 测试线 项目管理）
> **数据真源**：`game-studio-agents/config/role_presets.yaml`（preset 为唯一真源，本索引只读派生，禁止反向写回）

---

## 〇、工作包定位（承接说明）

对照 ui-ux-pro-max「美工 agent」启发点 ③ 的 **P2**：把 `role_presets.yaml` 里散落的美术风格预设，固化成一份**可检索风格索引**——每条风格含「风格关键词 → 配色 → 视觉签名 → 适用题材/玩法 → 技术栈 → 主责美术角色」，供 `ui_ux` 与主美（`art_director`）在接策划需求时**查库选型**，而非临场发挥。

**承接方**：美术线被游戏向经理点名派发（Issue #133 合并后联动 + `.routing_active.txt` 含美术线）。
**下游依赖**：测试线本轮 QA 验收美术质检门禁；项目管理收口 sign-off（本轮并行，非美术线直接阻塞项）。

**前置依赖（已解锁）**：PR #134 已把 `wp_ui_ux` 产出升级为「可检索 + 可校验」design_system，并加了美术质检门禁（P0/P1）。本 P2 在其之上补「**选型入口层**」——让 20 风格在接需求时能按题材/玩法/技术栈反查。

---

## 一、索引总体结构（三级检索维度）

风格索引按「**查得到 → 选得对 → 落得下**」设计三层检索字段，对齐引擎/质检可消费：

| 层级 | 字段 | 说明 | 检索用途 |
|------|------|------|---------|
| L1 关键词 | `preset_id` / `art_style` / `style_keywords` | 风格唯一键 + 人类可读别名 + 语义关键词 | 按风格名/关键词正向查询 |
| L2 题材×玩法 | `suitable_genres` / `gameplay_fit` / `art_focus` | 适合题材 + 匹配玩法(design_focus) + 美术侧重 | 按策划需求(题材/玩法)反向选型 |
| L3 技术落地 | `tech_stack` / `primary_role` / `verify` | 适配引擎/技术栈 + 主责角色 + 质检挂接 | 落库前查实施者与技术约束 |

### 索引 Schema（供 ui_ux/主美消费，字段全可检索）

```yaml
style_index_entry:
  preset_id: str            # 真源键，如 art_style_inkwash
  art_style: str            # 机器态，如 ink_wash
  display_name: str         # 人类可读，如「原画师（水墨风）」
  style_keywords: [str]     # 检索同义词：水墨/国风/写意/墨韵…
  color_palette: str        # 从真源派生
  visual_signature: str     # 从真源派生（美术质检可挂 visual 校验）
  suitable_genres: [str]    # 题材标签（题材→风格反查用）
  gameplay_fit: [str]       # 匹配 design_focus 玩法向（玩法→风格反查用）
  tech_stack: {dimension, budget, notes}  # 技术栈/资产预算约束
  primary_role: str         # 主责美术角色（锚定 base_role）
  quality_gate: str         # 对接 PR#134 美术质检规则标识
```

---

## 二、风格索引主表（19 风格 · 从 role_presets.yaml 派生）

> 说明：真源 `role_presets.yaml` 共 19 条 `art_style_*` 美术风格预设（issue 分析稿中「20 种」为口径含 UI/UX 双预设的约数；**本索引以真源 19 条为准**，多出的空白位可后续随 preset 增补）。

### 2.1 2D / 插画系

| preset_id | 风格 | 配色 | 视觉签名 | 适合题材(genres) | 主责角色 |
|---|---|---|---|---|---|
| art_style_pixel | 像素 pixel | limited 16-64色 | 复古像素+高饱和霓虹 | 复古/横版/独立/低端机 | concept_artist |
| art_style_inkwash | 水墨 ink_wash | 黑白灰+朱砂点缀 | 东方意境+留白气韵 | 国风/仙侠/武侠/文艺 | concept_artist |
| art_style_watercolor | 水彩绘本 watercolor | 粉彩系低饱和柔和 | 水彩晕染+纸纹+手绘 | 绘本/治愈/休闲/女性向 | concept_artist |
| art_style_flat | 扁平插画 flat | 明亮纯色+大面积留白 | 色块+几何+线性图标 | 休闲/网页/H5/工具 | ui_ux |
| art_style_papercut | 剪纸拼贴 paper_cut | 暖色+纸纹 | 纸质拼贴+缝线+手工 | 亲子/教育/儿童/治愈 | ui_ux |
| art_style_2d5 | 2.5D视差 parallax | 依题材多层明暗 | 多层视差+伪透视+运镜 | 横版/俯视/跑酷/卡牌展示 | concept_artist |
| art_style_handdrawn | 手绘二维 handdrawn_2d | 手绘线条+色彩分离 | 12-24fps 逐帧+动态缓动 | 日式动画/热血动作/2D横版 | animator |
| art_style_silhouette | 剪影黑金 silhouette_dark | 黑白深色+单点亮色 | 剪影轮廓+逆光+高对比 | 独立/氛围叙事/极简风格化 | concept_artist |

### 2.2 写实 / 次世代系

| preset_id | 风格 | 配色/预算 | 视觉签名 | 适合题材 | 主责角色 |
|---|---|---|---|---|---|
| art_style_pbr | 写实PBR realistic_pbr | 自然低饱和 | PBR材质+物理光照+次世代 | 写实/3A/主机/电影化叙事 | concept_artist |

### 2.3 卡通 / 风格化 3D 系

| preset_id | 风格 | 配色/预算 | 视觉签名 | 适合题材 | 主责角色 |
|---|---|---|---|---|---|
| art_style_lowpoly | 低多边形 low_poly | 低面(1000-5000) | 几何块面+柔和光影 | 休闲/移动端/极简 | modeler |
| art_style_cel | 日系卡渲 cel_shading | 高饱和粒子+描边 | 描边卡渲+速度线 | 日系/二次元/卡通 | vfx_artist |
| art_style_toon | 手绘Toon handpainted_toon | 中低面(2000-8000) | 手工上色+柔光+圆润 | 卡通/休闲/家庭/移动端 | modeler |
| art_style_chibi | Q萌 Q版 chibi_q | 低面(1500-5000) | 大头短身+夸张表情 | Q版/休闲/派对/收集/社交 | modeler |
| art_style_voxel | 体素 voxel | 单位体素(8-64³) | 体素块+可破坏+高饱和 | 沙盒/生存/创造/像素复古 | modeler |

### 2.4 主题 / 氛围暗黑系

| preset_id | 风格 | 配色 | 视觉签名 | 适合题材 | 主责角色 |
|---|---|---|---|---|---|
| art_style_cyberpunk | 赛博朋克 cyberpunk | 霓虹紫/青/洋红高对比 | 故障+全息霓虹+高反差 | 科幻/赛博朋克/近未来 | concept_artist |
| art_style_steampunk | 蒸汽朋克 steampunk | 黄铜/深棕/墨绿+蒸汽白 | 齿轮+黄铜蒸汽+维多利亚 | 蒸汽朋克/幻想机械/架空 | concept_artist |
| art_style_gothic | 哥特暗黑 gothic_dark | 暗紫/深红/漆黑+冷白高光 | 尖拱+蜡烛光晕+暗黑华丽 | 暗黑/哥特/恐怖/奇幻 | concept_artist |
| art_style_noir | 黑色电影 film_noir | 黑白灰+暗红点缀 | 硬光+斜线光栅+烟雾 | 侦探/悬疑/犯罪/都市 | concept_artist |
| art_style_retro_arcade | 复古街机 retro_arcade | 荧光(青/品红/绿)+CRT | CRT扫描+像素闪烁+街机框 | 复古/街机/竞速/怀旧 | vfx_artist |

---

## 三、反向检索矩阵（策划需求 → 风格选型）

策划线接到需求（题材 + 玩法侧重 design_focus）时，主美/UI 依下表**查库选型**，不再临场发挥：

| 策划需求标签 | 推荐风格（按匹配度排序） | 玩法侧重 |
|---|---|---|
| 国风/仙侠/武侠/文艺 | inkwash → watercolor | narrative/survival |
| 科幻/赛博/近未来 | cyberpunk → pbr → flat | shooter/open_world |
| 蒸汽朋克/幻想机械 | steampunk → gothic | survival/tower_defense |
| 暗黑/哥特/恐怖 | gothic → noir → silhouette | narrative/roguelike |
| 侦探/悬疑/犯罪 | noir → silhouette → gothic | narrative/puzzle |
| 复古/街机/怀旧 | retro_arcade → pixel | racing/party |
| 像素/独立/低端机 | pixel → voxel → retro_arcade | roguelike/survival |
| 沙盒/创造 | voxel → lowpoly | survival/open_world |
| 休闲/移动端/极简 | lowpoly → flat → papercut | casual/party |
| 亲子/教育/儿童 | papercut → toon → chibi | puzzle/party |
| 治愈/女性向/温情 | watercolor → papercut → toon | narrative/casual |
| Q版/派对/社交 | chibi → toon → flat | party |
| 日系/二次元 | cel → handdrawn → flat | moba/rhythm |
| 3A/写实/电影化 | pbr | shooter/open_world/narrative |
| 2D横版/热血动作 | handdrawn → cel → pixel | combat/racing |

**索引用法**：① 题材标签正向命中 → 得 1~3 候选风格；② 叠加玩法 design_focus 二次过滤；③ 命中多风格时按性能预算(低端机/移动端)与技术栈取舍；④ 定稿风格 → 落 `art_style` → 触发该风格对应 `ui_ux`/`art_director` 产线（PR#134 design_system）→ 质检校验。

---

## 四、主责角色与质检挂接

- **主审/选型**：`art_director`（主美定风格方向）；`ui_ux`（UI 层风格套用）。
- **数据维护**：`tech_artist`（风格→引擎技术栈映射 + 索引与 role_presets 真源一致性校验）。
- **质检挂接**：索引内 `color_palette`/`visual_signature` 派生自真源，对齐 PR#134 美术质检门禁 6 规则（hex 真实 / type_scale / icon 禁 emoji / 断点 / 对比度 / asset_upload），供本轮测试线 QA 复核美术质检门禁时可检索对照。

---

## 五、检索查询协议（供 ui_ux/主美/策划拉取）

对外暴露查询接口（纯只读，服务 `game-studio-agents/config` 内既有消费方）：

```python
# 伪代码：按题材/玩法查风格 → 返回候选风格列表
style_index.lookup(genres=["国风"], gameplay=["narrative"])
#  → [art_style_inkwash, art_style_watercolor]
style_index.lookup(preset_id="art_style_cyberpunk")
#  → 单条全字段（配色/签名/技术栈/主责/质检标识）
```

**产出物落库路径**：`game-studio-agents/docs/design-output/美术线/issue133/wp_style_index_可检索风格索引.md`
