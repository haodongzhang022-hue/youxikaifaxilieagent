# wp_release · 发版计划与里程碑（Issue #90 跨平台架构增强）

- **工作包**：wp_release 多引擎版本/里程碑
- **部门**：项目管理 | **统一头**：项目管理（小组）
- **主责角色**：project_manager（项目经理·协调型）+ release_manager（版本管理·严格门禁）
- **流水线位**：第 5 位（策划→程序→美术→测试 → **项目管理** → 运营）
- **上游依赖**：测试线 wp_testing ✅（跨平台回归/性能测试 4 份方案验收通过）
- **产出物类型**：release_plan（发版计划）+ gate_report（版本门禁）

---

## 一、多引擎发版里程碑规划

针对 Issue #90 四级引擎流水线（React→Cocos→Unity→UE），制定分阶段里程碑：

| 里程碑 | 阶段 | 内容 | 前置条件 | 引擎范围 |
|--------|------|------|---------|---------|
| M1 | 引擎无关核心冻结 | C++ 中间件 C ABI 接口冻结 + 中立资产格式 Schema | 程序线 wp_engine/wp_ai_logic ✅ | 引擎无关 |
| M2 | Web 引流验证 | React Web 端玩法跑通 + 分享传播链路 | M1 + wp_client React 适配 ✅ | React |
| M3 | 小程序轻量验证 | Cocos 小程序打包 + Python 原型快速迭代 | M2 + wp_client Cocos 适配 ✅ | Cocos |
| M4 | 完整 App 内容 | Unity 完整地图 + 内容/玩法升级 | M3 + wp_client Unity 适配 ✅ | Unity |
| M5 | 高保真护城河 | UE 高保真效果 + 跨引擎迁移成本验证 | M4 + wp_client UE 适配 ✅ | UE |

**核心原则**：迁移是「换渲染器」而非「重写游戏」——C ABI 中间件 + 程序化生成（同 seed 同输出）保证四端一致。

---

## 二、发版检查单（多引擎门禁）

- [x] 策划线：wp_gameplay/wp_numeric_model/wp_combat/wp_narrative 验收通过
- [x] 程序线：wp_client/wp_server/wp_engine/wp_ai_logic 验收通过
- [x] 美术线：wp_art_direction/wp_ui_ux/wp_audio 验收通过
- [x] 测试线：wp_testing 跨平台回归/一致性/兼容性/性能 4 份方案验收通过
- [ ] 运营线：wp_data_ops 多端数据埋点/分析（本部门验收后解锁）
- [ ] 跨引擎一致性回归（同 seed → 四端 hash 一致）实测通过
- [ ] 发版门禁（release_gate）全部通过

---

## 三、跨引擎迁移成本与风险管控

| 风险 | 等级 | 规避方案 |
|------|------|---------|
| C++ 开发成本高 | MEDIUM | AI 辅助 + Python 原型先行 |
| Unity 原生 C++ 集成复杂 | HIGH | 限制 C++ 到核心逻辑 + Native Plugin |
| 跨引擎行为不一致 | HIGH | 一致性校验器 + 跨引擎回归测试（测试线方案）|
| Python→C++ AI 转译质量 | HIGH | 测试门禁 + 人工审查 |

---

## 四、发版决策点（人类 CP）

> 按 FRAMEWORK_UPGRADE.md 政策，跨平台架构发版最终拍板归**人类 CP**。
> 项目管理版本门禁 GO 后，提交人类 CP 最终确认。
