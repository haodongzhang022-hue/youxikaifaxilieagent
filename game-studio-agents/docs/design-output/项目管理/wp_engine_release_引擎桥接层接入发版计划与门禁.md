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
