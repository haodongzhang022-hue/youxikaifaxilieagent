# wp_ui_ux · 多端 UI/UX 适配方案（Issue #90）

- **工作包**：wp_ui_ux 多端 UI/UX 适配
- **部门**：美术线
- **主责角色**：ui_ux（UI/UX设计师·体验向）组 → ui_ux + tech_artist（技术美术·管线向）协作
- **模块**：ui_ux / cross-platform-ui
- **产出物类型**：ui_asset（多端 UI/UX 适配设计文档）
- **场景**：Issue #90「跨平台架构增强」——需在 Web/Cocos/Unity/UE 四引擎间实现 UI/UX 的跨端适配

---

## 一、多端 UI 适配设计目标

### 1.1 核心目标

> 同一套 UI 逻辑与视觉语言，在 Web（鼠标/触屏）→ Cocos（触屏）→ Unity（键鼠/手柄/触屏）→ UE（键鼠/手柄/VR）四端保持**一致的用户体验**，同时最大化代码复用。

### 1.2 适配原则

| 原则 | 说明 |
|------|------|
| **逻辑/视图分离** | UI 业务逻辑（数据绑定/状态管理）与渲染（引擎 UI 框架）完全解耦 |
| **统一设计令牌** | 色彩/字体/间距/圆角等设计令牌（Design Token）全端统一 |
| **响应式布局** | 基于 Flexbox/Grid 思想的响应式布局，自适应不同分辨率与宽高比 |
| **多输入支持** | 同时支持键鼠/触屏/手柄三种输入模式，交互状态统一 |
| **渐进增强** | Web/Cocos 提供基础交互，Unity/UE 增强触觉反馈/动效 |

---

## 二、UI 架构分层

### 2.1 三层 UI 架构

```
┌─────────────────────────────────────────────────────────────┐
│  UI 逻辑层（Engine-Agnostic UI Logic）                       │
│  · 数据模型（ViewModel/状态管理）                            │
│  · 路由/导航（URL-based）                                    │
│  · 交互状态机（点击/悬停/拖拽/键盘）                          │
│  · 无障碍逻辑（对比度/焦点管理）                              │
├─────────────────────────────────────────────────────────────┤
│  UI 适配层（UI Engine Adapter）                              │
│  · 渲染接口（RenderPanel / RenderComponent）                │
│  · 输入抽象（IInputAdapter → 键鼠/触屏/手柄）                 │
│  · 动画抽象（Tween / Spring / Easing 接口）                  │
│  · 字体/图标加载抽象                                          │
├─────────────────────────────────────────────────────────────┤
│  引擎 UI 实现层（Web / Cocos / Unity / UE）                  │
│  · React DOM（Web）                                          │
│  · Cocos UI（小程序）                                        │
│  · uGUI / UI Toolkit（Unity）                                │
│  · UMG（UE）                                                 │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 引擎 UI 框架对照

| 维度 | Web/React | Cocos | Unity | UE5 |
|------|-----------|-------|-------|-----|
| UI 框架 | React DOM / Tailwind | Cocos UI | uGUI / UI Toolkit | UMG |
| 渲染方式 | DOM/Canvas | 引擎内渲染 | 引擎内渲染 | 引擎内渲染 |
| 布局系统 | Flexbox/Grid | Cocos Widget | RectTransform | UMG Slot |
| 样式方案 | CSS/Tailwind | 组件属性 | UGUI Style | UMG Style |
| 动画 | CSS Transition / Framer | Cocos Animation | Animator | UMG Animation |
| 字体 | Web Font | TTF/OTF | TTF/OTF | TTF/OTF |

---

## 三、设计令牌（Design Token）统一

### 3.1 视觉设计令牌（全端统一）

```json
// design-tokens.json — 中立 UI 设计令牌（全端共享）
{
  "colors": {
    "primary": {"value": "#1E3A5F", "usage": "界面背景/框架"},
    "accent": {"value": "#D4A017", "usage": "按钮/关键元素"},
    "warning": {"value": "#6B21A8", "usage": "危险/负面反馈"},
    "text_main": {"value": "#E0E6F0", "usage": "主要文字"},
    "text_aux": {"value": "#8899AA", "usage": "辅助文字"}
  },
  "typography": {
    "font_cn": "思源黑体",
    "font_en": "Orbitron",
    "heading_size": [20, 24, 32],
    "body_size": [14, 16],
    "caption_size": [12]
  },
  "spacing": {"xs": 4, "sm": 8, "md": 16, "lg": 24, "xl": 32},
  "radius": {"sm": 4, "md": 8, "lg": 12},
  "shadow": {"level1": "0 1px 2px rgba(0,0,0,0.2)", "level2": "0 4px 8px rgba(0,0,0,0.3)"}
}
```

### 3.2 多端适配转换

| 设计令牌 | Web/CSS | Cocos | Unity | UE5 |
|---------|---------|-------|-------|-----|
| 颜色 | CSS `var(--primary)` | Color 组件 | ColorBlock | SlateBrush |
| 字体 | `font-family` | Label TTF | TMP Font | SlateFontInfo |
| 间距 | CSS `gap/margin` | Layout 组件 | RectTransform offsets | UMG Slot padding |
| 圆角 | CSS `border-radius` | Sprite 9-slice | Image 9-slice | UMG BorderBrush |
| 阴影 | CSS `box-shadow` | 自制 shadow | Outline + Shadow | Slate Brush Shadow |

---

## 四、多端交互适配

### 4.1 输入方式映射

| 交互动作 | Web（键鼠） | Cocos（触屏） | Unity（键鼠+手柄） | UE（键鼠+手柄） |
|---------|-----------|--------------|-------------------|---------------|
| 点击/确认 | Mouse Click | Touch Tap | Mouse / A键 | Mouse / Space |
| 悬停 | Mouse Hover | Long Press | Mouse Hover | Mouse Hover |
| 返回 | Esc / Back | System Back | Esc | Esc |
| 快捷操作 | 数字键 / Tab | 无 | 数字键 / 手柄键 | 数字键 / 手柄键 |
| 拖拽 | Mouse Drag | Touch Drag | Mouse Drag | Mouse Drag |
| 滚动 | Mouse Wheel | Touch Swipe | Mouse Wheel | Mouse Wheel |

### 4.2 触控目标优化

| 平台 | 最小触控目标 | 建议目标尺寸 | 悬停替代 |
|------|------------|------------|---------|
| Web（桌面） | 32px | 36-44px | 悬停高亮 |
| Web（移动） | 44px | 48-56px | 点击反馈 |
| Cocos | 44px | 48-60px | 长按预览 |
| Unity | 36px | 40-48px | 悬停/手柄选中 |
| UE | 36px | 40-48px | 悬停/手柄选中 |

### 4.3 响应式布局断点

| 断点 | 宽高比 | 适配策略 |
|------|--------|---------|
| 手机竖屏 | 9:16 | 单列布局，导航底部 Tab |
| 手机横屏 | 16:9 | 双列布局，侧边导航 |
| 平板 | 4:3 | 网格布局 |
| 桌面 | 16:9 | 完整四宫格布局 |
| 超宽屏 | 21:9 | 扩展侧边栏 |

---

## 五、核心界面多端适配

### 5.1 战斗 HUD

| 元素 | Web | Cocos | Unity | UE |
|------|-----|-------|-------|-----|
| 左下体力 | 静态圆环 | 静态圆环 | 动态圆环 + 受击红闪 | 动态圆环 + 受击红闪 + 震动 |
| 右下技能 | 3+1 按钮 | 3+1 按钮 | 3+1 按钮 + 冷却遮罩 | 3+1 按钮 + 冷却遮罩 |
| 中央怒气条 | 细进度条 | 细进度条 | 发光进度条 | 发光进度条 + 满气特效 |
| 左上任务提示 | 文本浮动 | 文本浮动 | 可拖拽面板 | 可拖拽面板 |
| 玩家生命条 | 简化 | 简化 | 完整 HUD | 完整 HUD |

### 5.2 主界面（四宫格）

| 元素 | Web | Cocos | Unity | UE |
|------|-----|-------|-------|-----|
| 继续旅程 | 大按钮 | 大按钮 | 全屏入口 | 全屏入口 + 3D 场景 |
| 星械工坊 | 按钮 + 预览 | 按钮 + 2D预览 | 3D 预览 | 3D 高保真预览 |
| 氏族社交 | 列表 | 列表 | 列表 + 头像 | 列表 + 3D 头像 |
| 设置 | 弹窗 | 弹窗 | 全屏面板 | 全屏面板 |

### 5.3 背包/星械界面

| 维度 | Web | Cocos | Unity | UE |
|------|-----|-------|-------|-----|
| 列表布局 | 网格 | 网格 | 网格 + 排序 | 网格 + 排序 |
| 物品详情 | 侧边详情 | 弹窗详情 | 侧边详情 + 3D模型 | 3D 模型交互 |
| 品质色 | CSS 颜色 | Sprite 颜色 | 材质颜色 | 材质颜色 |

---

## 六、动效与反馈适配

### 6.1 动效分级

| 动效类型 | Web | Cocos | Unity | UE |
|---------|-----|-------|-------|-----|
| 点击反馈（0.95缩放） | CSS Transform | Cocos Scale | Image Scale | UMG Scale |
| 悬停高亮 | CSS Hover | 长按高亮 | Color Tint | Brush Tint |
| 面板弹出 | CSS Transition | Cocos Tween | DOTween | UMG Animation |
| 受击红闪（150ms） | CSS Filter | Sprite Color | Image Color | Brush Color |
| 技能冷却遮罩 | CSS Mask | Sprite Fill | Image Fill | UMG ProgressBar |
| 拖拽吸附 | CSS Drag | Touch Drag | EventSystem | UMG Drag |

### 6.2 动效预算

| 引擎 | 同时动效数 | 动画时长上限 | 性能策略 |
|------|----------|------------|---------|
| Web | ≤4 | ≤0.3s | CSS GPU 加速 |
| Cocos | ≤6 | ≤0.4s | Tween 合批 |
| Unity | ≤8 | ≤0.5s | DOTween 池化 |
| UE | ≤10 | ≤0.5s | UMG 缓存 |

---

## 七、无障碍（A11y）适配

| 无障碍项 | Web | Cocos | Unity | UE |
|---------|-----|-------|-------|-----|
| 对比度 | ≥4.5:1 | ≥4.5:1 | ≥4.5:1 | ≥4.5:1 |
| 焦点管理 | Tab 导航 | 无（触屏） | 手柄焦点 | 手柄焦点 |
| 屏幕阅读 | ARIA / SR | 无 | 自定义 | 自定义 |
| 色盲模式 | CSS Filter | 配色切换 | 配色切换 | 配色切换 |
| 文字缩放 | CSS rem | 字号设置 | TMP 字号 | UMG 字号 |

---

## 八、UI 资源规格

### 8.1 通用资源规范

| 资源类型 | 中立格式 | 规格 | 用途 |
|---------|---------|------|------|
| UI 贴图 | PNG | 128-1024px | 按钮/图标/背景 |
| 图标集 | SVG → PNG | 24/48/72px | 功能图标 |
| 字体 | TTF/OTF | 思源黑体 + Orbitron | 中文/英文 |
| 动效数据 | JSON | 参数化 | 跨端动效 |
| 音效 | WAV/MP3 | UI 交互音 | 点击/悬停/反馈 |

### 8.2 分辨率适配策略

```
安全区适配 → 避开刘海/圆角/底部导航
UI 缩放策略 → 基于参考分辨率等比缩放 + 边距自适应
像素密度 → 1x/2x/3x 三套图，自动选择
```

---

## 九、跨部门协作依赖

| 协作方向 | 部门 | 协作内容 |
|---------|------|---------|
| 上游消费 | @策划线 | 消费 wp_gameplay 系统界面需求 + wp_combat 战斗 UI 交互 |
| 上游消费 | @程序线 | 消费 wp_client 引擎 UI 适配层接口 + wp_engine UI 数据通道 |
| 下游解锁 | @测试线 | 对多端 UI 做可用性/兼容性验收 |
| 协同 | @运营线 | 消费 UI 体验品质做市场预演 |

---

## 十、交付物清单

| 交付物 | 说明 |
|--------|------|
| 设计令牌（Design Tokens） | 全端统一视觉变量（JSON） |
| UI 架构分层设计 | 逻辑/适配/实现三层分离 |
| 多端交互映射表 | 输入方式/触控/响应式适配 |
| 核心界面适配方案 | 战斗 HUD/主界面/背包 四端规格 |
| 动效分级方案 | 各端动效实现 + 性能预算 |
| 无障碍适配清单 | A11y 各端支持矩阵 |

> 全程机制驱动：美术线部门统一头承接 → CollaborationWorkbench 组内分工（ui_ux + tech_artist）→ group_audit 留痕 → REVIEW_RESULT 上报。
