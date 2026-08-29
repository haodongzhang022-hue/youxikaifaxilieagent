# wp_engine · 引擎感知架构（Cocos/Unity/UE 四阶段选型）

- **工作包**：wp_engine 引擎感知架构（Cocos/Unity/UE 四阶段选型）
- **部门**：程序线
- **主责角色**：engine_dev + cto
- **模块**：engine
- **产出物类型**：tech_impl（技术实现文档 + 代码）
- **场景**：Issue #112「游戏向架构师的开发」——引擎选型需阶段感知，防止阶段错配

---

## 一、核心实现：四阶段感知引擎模块

### 1.1 StageAwareEngine（`config/stage_aware_engine.py`）

**核心思想**：每个架构决策必须绑定「引擎 × 阶段」二维坐标。

| 阶段 | 引擎 | 脚本语言 | 阶段目标 | 边界内 | 边界外 |
|------|------|---------|---------|--------|--------|
| 阶段1 Cocos/MVP | cocos_creator | TS/JS | 极速验证玩法 | UI/动画/点击/本地存档/轻联网 | 复杂寻路/帧同步/深度AI |
| 阶段2 Unity/商业化 | unity | C# | 画面提升+App原生 | UI框架/热更新/实时战斗/养成 | 极致粒子/底层内存/硬核物理 |
| 阶段3 UE/3A | unreal_engine | C++/Blueprint | 极致画质+硬核实时 | 渲染定制/帧同步/大世界 | — |
| 阶段4 资产库 | — | 多语言 | 永不废弃的资产 | 协议/配置表/纯算法 | — |

### 1.2 StageBoundaryGuard（阶段边界护栏）

```python
# 示例：Cocos 阶段检查
guard = StageBoundaryGuard()
result = guard.check('combat_frame_sync', GameStage.STAGE1_COCOS)
# ❌ 过度设计: 模块 'combat_frame_sync' 属于Unreal Engine (3A/重度实时)，
#              当前是Cocos/小程序 (MVP验证期)阶段，阶段不对=错
```

**支持的能力**：
- 模块→适用阶段映射表（17 个模块已登记）
- 越界检测：过度设计（模块属于未来阶段）vs 技术债（模块属于过去阶段）
- 批量检查 + 审计报告

### 1.3 UnityEngineAdapter（新增引擎适配器）

在 `config/engine_adapters.py` 中新增 Unity 引擎适配器：
- `EngineType.UNITY = "unity"` 枚举
- `UnityEngineAdapter` 类（C# 脚本、Unity 构建命令、8 种资源规范）
- 引擎注册表扩展至 3 引擎

### 1.4 引擎能力集

| 引擎 | 能力集 | 独有能力 |
|------|--------|---------|
| Cocos Creator | 10 项 | platform.wechat/douyin、local.storage |
| Unity | 10 项 | assetbundle.load、ai.navmesh、physics.collision |
| UE5 | 12 项 | blueprint.create、physics.advanced、render.pipeline、network.dedicated_server |

---

## 二、跨阶段资产复用策略

| 资产类型 | 阶段1 | 阶段2 | 阶段3 | 复用方式 |
|---------|:---:|:---:|:---:|---------|
| 协议资产 | TS/Python | C#/Go | C++ | 协议定义不变，生成各语言代码 |
| 数值配置表 | JSON | JSON | JSON | Excel→JSON 统一格式 |
| 纯算法 | TS | C# | C++ | 数学逻辑翻译 + 单元测试保留 |

---

## 三、组内分工记录（group_audit）

| 子任务 | 承接角色 | 产出说明 |
|--------|---------|---------|
| 新增UnityEngineAdapter + 四阶段感知引擎模块 | engine_dev | stage_aware_engine.py + engine_adapters.py Unity支持 |
| 架构评审：四阶段引擎边界定义 + 阶段切换策略验证 | cto | 四阶段边界矩阵 + 越界检测 + 阶段切换规则 |

> 分工经协作工作台（CollaborationWorkbench）`delegate` 记录，全程留痕可审计。

---

## 四、测试验证

```bash
bash game-studio-agents/tests/test_stage_aware_engine.sh
# 14/14 通过 🟢
bash game-studio-agents/tests/test_engine_adapters.sh
# 21/21 通过 🟢
```

### 测试覆盖

| 验证项 | 结果 |
|--------|:---:|
| 四阶段枚举完整 | ✅ |
| 阶段选型决策正确 | ✅ |
| 阶段边界检查（阶段不对=错） | ✅ |
| 阶段切换规则（只能向后演进） | ✅ |
| Unity 引擎适配器（新增） | ✅ |
| 3 引擎注册完整 | ✅ |
| 感知引擎模型 | ✅ |

---

## 五、验收通过后解锁下游

- **wp_server**（协议先行）：程序线内部级联解锁
- **wp_client**（逻辑/表现分离）：程序线内部级联解锁
- **美术线 wp_art_direction**：程序线产出到位后级联解锁
