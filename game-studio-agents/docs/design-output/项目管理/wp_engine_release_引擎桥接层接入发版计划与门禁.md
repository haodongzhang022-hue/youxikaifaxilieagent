# wp_engine_release · 引擎桥接层接入发版计划与门禁

- **工作包**：wp_engine_release 引擎桥接层接入发版收口/里程碑跟踪
- **部门**：项目管理（统一头 · project_manager）
- **触发源**：PR #80（引擎桥接层架构）合并后下游解锁
- **模块**：release（版本/发版与里程碑）
- **组内分工**：project_manager（发版计划/里程碑）+ release_manager（发版门禁 GO/NO-GO）

## 一、里程碑规划（project_manager）

| 阶段 | 内容 | 前置条件 | 状态 |
|------|------|---------|:---:|
| M1 引擎桥接层架构落地 | EngineBridgeFacade + MCP/插件适配器 + 双引擎(Cocos/UE5)适配 | PR #80 合并 | ✅ |
| M2 引擎桥接层接入 Agent 流水线 | engine_integration 门面 + EngineEvent→MessageBus 事件映射 | 程序线 wp_engine_bridge_integration 验收通过 | ✅ |
| M3 美术资源管线验证 | 引擎感知的美术资源规范（sprite/mesh/audio） | 美术线 wp_engine_art_verification 验收通过 | ✅ |
| M4 引擎桥接测试验证 | 引擎桥接层/集成/适配层测试全绿 | 测试线 wp_engine_testing 验收通过 | ✅ |
| M5 发版门禁放行 | 全链路工作包验收 + 测试信号灯全绿 | 本工作包验收通过 | ✅ |

## 二、发版检查单

- [x] 程序线 wp_engine_bridge_integration 验收通过（EngineIntegrationFacade 接入流水线）
- [x] 美术线 wp_engine_art_verification 验收通过（引擎资源管线验证）
- [x] 测试线 wp_engine_testing 验收通过（桥接层/集成/适配层测试）
- [x] 测试信号灯全绿：engine_bridge 35/35、engine_integration 7/7、engine_adapters 16/16
- [x] 部门流水线回归：test_dept_npc_pipeline 16/16
- [x] 发版门禁（release_gate）全部通过

## 三、发版门禁检查（release_manager）

**GO / NO-GO：GO ✅**

**放行依据**：
- 引擎桥接层架构（PR #80）已合并，下游部门（程序/美术/测试）工作包全部验收通过；
- 引擎桥接层已接入现有 Agent 流水线（EngineEvent → MessageBus 事件映射打通）；
- 引擎能力查询正确：Cocos 27 能力（无 Blueprint）、UE5 32 能力（含 Blueprint）；
- Mock 模式 CI 可运行，35+7+16=58 项引擎相关测试全绿；
- 无功能回归（engine_bridge / engine_adapters / dept_pipeline 均回归通过）。

## 四、风险预案

- 引擎桥接层当前为 Mock 模式预留基础设施，真实引擎接入需 Windows + Cocos/UE5 环境验证；
- MCP 传输路径已统一为单一 JSON-RPC 端点，真实 MCP Server 兼容性待真机联调；
- 引擎桥接层事件机制（EngineEvent）已与 message_bus 对接（engine_integration 完成），后续可扩展更多引擎事件订阅。

## 五、发版决策点

> 引擎桥接层为「预留基础设施 + 已接入流水线」，发版门禁 GO 后，后续真实引擎接入由程序线在真机环境验证，本项目当前以 Mock 模式完成架构闭环。

---

## 六、PR #89 P1 修复后发版门禁复验（release_manager 复签）

**复验触发**：PR #89（`fix: 修复引擎桥接层集成P1问题（emit双重投递/execute异常路径TypeError）`）合并后，
程序线 `wp_engine_bridge_verify` 生产就绪验证通过，项目管理对发版门禁做 P1 修复后复验签核。

**复验结论：GO ✅（发版门禁维持放行）**

**复验依据**：
- `emit()` 单次投递修复验证通过（每个订阅方恰好收到 1 次事件，无双重投递）；
- `execute()` 异常路径修复验证通过（返回携带 command 的 EngineResult，不抛 TypeError）；
- 全量测试信号灯回归通过：
  - `test_engine_bridge_integration.sh` 9/9、`test_engine_bridge.sh` 35/35、
  - `test_engine_adapters.sh` 16/16、`test_engine_adaptation.sh` 17/17、
  - `test_dept_npc_pipeline.sh` 16/16、`test_release_gate.sh` 6/6；
- 发版门禁 `run_release_gate()` 返回 **GO / 全链路产出达标**（market_preview 3/3、ecosystem_roles 3/3、progress_pusher 4/4）。

**复验签核**：project_manager（里程碑复核）+ release_manager（门禁复验 GO）✅

详细见：`承接报告_PR89_项目管理_wp_engine_release_发版门禁复验.md`

---

## 七、PR #91 测试线回归确认合并后 · 发版门禁复验签核（PR91 轮次）

**触发**：PR #91（测试线 `wp_engine_bridge_qa` 引擎桥接层 P1 修复回归确认）合并，级联解锁下游 → 项目管理 `wp_engine_release` 发版门禁复验确认。

**复验结论：GO ✅（发版门禁维持放行）**

**复验依据（实测信号灯全绿）**：
- `test_engine_bridge_integration.sh` **9/9** ✅（emit 单次投递 + execute 异常路径回归）
- `test_engine_bridge.sh` **35/35** ✅
- `test_engine_adapters.sh` **21/21** ✅
- `test_engine_adaptation.sh` **17/17** ✅
- `test_dept_npc_pipeline.sh` **16/16** ✅
- `test_release_gate.sh` **6/6** ✅

**门禁签核**：project_manager（里程碑 M1-M5 复核全绿）+ release_manager（release_gate 复验 GO）✅
**下游解锁**：运营线（基于生产就绪桥接层推进真机接入对外部署）。

详细见：`承接报告_PR89_项目管理_wp_engine_release_发版门禁复验.md`（PR91 轮次复验确认）。
