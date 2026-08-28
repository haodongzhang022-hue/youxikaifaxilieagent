# 测试线 · 引擎桥接层与适配层测试验证（wp_engine_testing）

> 承接：PR #80 合并后下游解锁 · 测试线引擎桥接与适配层测试验证工作包
> 主责：qa_engineer（测试线统一头） · 协办：auto_qa
> 依赖：程序线 `wp_engine_bridge_integration` ✅、美术线 `wp_engine_art_verification` ✅

## 一、验证目标

对 PR #80（引擎桥接层架构）合并后由程序线交付的引擎桥接层（`config/engine_bridge/`）与
引擎适配层（`config/engine_adapters.py`）进行全面测试验证，确认：

1. 引擎桥接层（EngineBridge）核心架构正确性；
2. 引擎桥接层接入 Agent 流水线（EngineIntegrationFacade）正确性；
3. 双引擎适配层（Cocos Creator / Unreal Engine 5）资源管线正确性；
4. 引擎事件 → MessageBus 事件映射链路正确性；
5. 部门 NPC 流水线执行链路完整性（无回归）。

## 二、组内分工表（经协作工作台 @分工 · group_audit）

| 子任务 | 承接角色 | 内容 | 状态 |
|--------|---------|------|:---:|
| 引擎桥接层功能测试 | qa_engineer | 引擎桥接层核心架构测试（35 项断言） | ✅ DONE |
| 引擎桥接集成测试 | auto_qa | 引擎桥接层接入 Agent 流水线测试（7 项断言） | ✅ DONE |
| 双引擎适配层测试 | auto_qa | 双引擎适配层资源管线测试（16 项断言） | ✅ DONE |
| 部门流水线回归 | qa_engineer | 部门 NPC 流水线链路回归（16 项断言） | ✅ DONE |

## 三、测试执行与结果

### 3.1 引擎桥接层测试（test_engine_bridge.sh）

| 测试模块 | 覆盖范围 | 断言数 | 结果 |
|---------|---------|:---:|:---:|
| 引擎桥接层可导入 | EngineBridgeFacade/BridgeConfig/EngineCommand 等 | 1 | 🟢 |
| 引擎命令协议 | EngineCommand 构造/序列化/能力映射 | 4 | 🟢 |
| Windows 环境探测 | get_windows_environment（Cocos/UE5/通用） | 6 | 🟢 |
| 引擎适配器工厂 | create_engine_adapter（cocos/ue5/mock/不支持） | 5 | 🟢 |
| 引擎适配器能力 | Cocos/UE5 能力集差异 | 3 | 🟢 |
| MCP 客户端 Mock | 连接/调用/命令执行/工具列表 | 5 | 🟢 |
| 插件适配器 Mock | 发现/调用/错误处理 | 6 | 🟢 |
| 命令集快捷方法 | load_scene/create_node/set_transform/run_test | 4 | 🟢 |
| **合计** | | **35** | **🟢 全绿** |

### 3.2 引擎桥接层集成测试（test_engine_bridge_integration.sh）

| 测试模块 | 覆盖范围 | 断言数 | 结果 |
|---------|---------|:---:|:---:|
| 集成模块可导入 | EngineIntegrationFacade | 1 | 🟢 |
| 集成门面初始化 | Mock 模式初始化 | 1 | 🟢 |
| 引擎命令执行 | load_scene/create_node/play | 1 | 🟢 |
| 事件映射 | EngineEvent → MessageBus | 1 | 🟢 |
| 引擎能力查询 | Cocos/UE5 能力集 | 1 | 🟢 |
| 能力检查 | engine_capability_check 全通过 | 1 | 🟢 |
| 状态报告 | 含集成信息 | 1 | 🟢 |
| **合计** | | **7** | **🟢 全绿** |

### 3.3 双引擎适配层测试（test_engine_adapters.sh）

| 测试模块 | 覆盖范围 | 断言数 | 结果 |
|---------|---------|:---:|:---:|
| 引擎适配器工厂 | get_engine_adapter（cocos/ue5/unknown） | 3 | 🟢 |
| 资源规格 | 双引擎资源类型/扩展名/导入路径 | 4 | 🟢 |
| 引擎感知产出 | 美术资源产出引擎感知正确 | 5 | 🟢 |
| 音频资源格式 | Cocos→.mp3 / UE→.wav | 2 | 🟢 |
| 资源导入路径 | 正确映射 | 1 | 🟢 |
| 产出物序列化 | 两引擎产出物均含资源规格 | 1 | 🟢 |
| **合计** | | **16** | **🟢 全绿** |

### 3.4 部门流水线回归（test_dept_npc_pipeline.sh）

| 测试模块 | 覆盖范围 | 断言数 | 结果 |
|---------|---------|:---:|:---:|
| 六大部门 NPC 角色 | .cnb/settings.yml 注册完整 | 7 | 🟢 |
| 部门执行链路 | issue.open + pull_request.merged 含 6 部门执行阶段 | 4 | 🟢 |
| 组内/跨部门协作指令 | 部门执行阶段含协作指令 | 2 | 🟢 |
| .cnb.yml 流水线 | 部门 npc:go 执行阶段 | 3 | 🟢 |
| **合计** | | **16** | **🟢 全绿** |

### 3.5 辅助回归

| 测试脚本 | 断言数 | 结果 |
|---------|:---:|:---:|
| test_dispatch_capability.sh | 16/16 | 🟢 |
| test_role_collaboration.sh | 33/33 | 🟢 |
| test_agent_identity.sh | 18/18 | 🟢 |
| test_art_testing.sh | 9/9 | 🟢 |

## 四、验证结论

**✅ 全部通过**

1. **引擎桥接层架构正确**：EngineBridgeFacade 统一入口可用，MCP 客户端/插件适配器 Mock 模式功能正常；
2. **Agent 流水线接入正确**：EngineIntegrationFacade 已接入 ProgramDeptAgent，引擎事件正确映射到 MessageBus；
3. **双引擎适配正确**：Cocos Creator 与 Unreal Engine 5 资源管线产出正确，audio_resource_extension 修复生效；
4. **部门流水线无回归**：六大部门 NPC 流水线执行链路完整，协作指令齐全；
5. **辅助回归全绿**：派发能力、协作工作台、身份自适应、美术线生态角色均无回归。

## 五、产出物清单

| 产出物 | 路径 | 说明 |
|--------|------|------|
| 引擎桥接与适配层测试验证报告 | `docs/design-output/测试线/wp_engine_testing_引擎桥接与适配层测试验证.md` | 本文档 |
