# 双引擎适配层架构文档（wp_engine_adaptation）

> 对齐架构师建议：面向「Windows + Cocos Creator + Unreal Engine + DeepSeek harness + 云端 cnb.cool」环境，补齐 4 处 P1 缺漏 + 2 处 P2 补强。

## 背景

项目未来将在 **Windows 环境**下用 **Cocos Creator** 与 **Unreal Engine** 双引擎进行开发，使用 **DeepSeek harness** 作本地 Agent 运行时，并与**云端 cnb.cool** 协同。当前框架是**引擎无关的纯编排逻辑**（六大部门 + 生态角色 + task_scheduler/message_bus），可无缝迁移。但存在 4 处 P1 + 2 处 P2 架构缺漏，若不补，会导致「本地引擎产出无法纳入云端编排」「本地/云端双环境分歧」（即 wp_audio 那类「声明改动未落地/幻觉」）。

## 分层架构

```
┌─ 云端编排层（cnb.cool，现有不动）─────────────────────────┐
│  task_scheduler / message_bus / 六大部门 / 评审门禁      │
└───────────────▲───────────────────────────────────┬────┘
       云端派单 / 验收回传                      │
┌───────────────┴───────────────────────────────────▼────┐
│  双环境同步层（engine_sync.py，P1-3/P1-4 核心）          │
│  · 产物契约：Cocos/UE 资源格式 + 构建产物清单            │
│  · 同步通道：本地→云端 上传 / 云端→本地 派单落地        │
│  · 同源校验：hash/版本 一致性护栏（防跨环境分歧）        │
└───────────────▲───────────────────────────────────┬────┘
       本地执行 / 资源产出                      │
┌───────────────┴───────────────────────────────────▼────┐
│  本地 Windows 执行层（deepseek_harness.py，P1-2/P2-6）  │
│  · DeepSeek 本地 Agent 运行时                          │
│  · Cocos Creator 工具链 / UE5 工具链                    │
│  · 本地资源管线（.prefab/.uasset 等）                   │
└──────────────────────────────────────────────────────────┘
```

## 模块清单

| 模块 | 对应缺漏 | 核心能力 |
|------|---------|---------|
| `config/engine_adapters.py` | P1-1 / P2-5 | 双引擎技术栈契约（脚本语言/资源目录/构建命令/资源类型）、构建产物契约、resolve_engine 自适应 |
| `config/engine_sync.py` | P1-3 / P1-4 | 产物清单（含 hash）、同源校验、双向同步计划、一致性护栏报告 |
| `config/deepseek_harness.py` | P1-2 / P2-6 | 本地 Agent 运行时上下文、接收派单、执行计划、本地执行、回传云端 |
| `config/roles.yaml` | P1-1 | 新增 `cocos_dev` / `ue_dev` 岗位（含 engine 字段） |
| `config/department_agents.py` | P1-1 | 程序线/美术线 Agent 引擎感知（资源格式契约） |
| `config/role_inventory.yaml` | P1-1 | 同步登记 cocos_dev / ue_dev 实现映射 |

## 一、双引擎技术栈契约（P1-1 / P2-5）

`engine_adapters.py` 为两类引擎提供统一抽象：

| 维度 | Cocos Creator | Unreal Engine |
|------|--------------|---------------|
| 引擎标识 | `cocos` | `unreal` |
| 脚本语言 | TypeScript / JavaScript | C++ / Blueprint |
| 资源目录 | `assets/` | `Content/` |
| 构建命令 | `cocos build --platform windows` | `RunUAT BuildCookRun -platform=windows -project={project}` |
| 资源类型 | .prefab / .scene / .anim / .png | .uasset / .umap / .cpp/.h |

核心 API：
- `get_engine_spec(engine)`：返回指定引擎技术栈契约
- `resolve_engine(hint)`：从 CNB_ENGINE 环境变量/参数解析目标引擎（支持「虚幻」别名）
- `build_artifact_manifest(engine, modules)`：生成构建产物清单
- `artifact_contract(engine, kind)`：查询资源落地格式
- `engine_aware_artifact(engine, dept, wp)`：部门产出标注引擎契约

岗位落地：`roles.yaml` 新增 `cocos_dev`（engine: cocos）与 `ue_dev`（engine: unreal），带完整职责、任务、协作与状态机。

## 二、双环境同步层（P1-3 / P1-4）

`engine_sync.py` 打通本地引擎环境与云端编排的产物双向同步，核心是**同源 hash 校验护栏**，直接回应「声明改动未落地」事故。

| 能力 | 说明 |
|------|------|
| `build_manifest(engine, local_root, items)` | 生成本地产出物产物清单（每项含 SHA-256 hash） |
| `verify_manifest(manifest, local_root)` | 同源校验：比对记录 hash 与实际 hash，输出 MATCH / MISSING / MISMATCH |
| `consistency_report()` | 一致性护栏报告（人可读） |
| `sync_plan(engine, direction, items)` | 生成本地→云端 上传 / 云端→本地 落地 同步计划 |

**同源校验三类结果**：
- `MATCH`：一致
- `MISSING`：本地缺失（「声明未落地」的典型，直接拦截验收）
- `MISMATCH`：内容分歧（hash 不一致）

## 三、DeepSeek 本地 Agent 运行时（P1-2 / P2-6）

`deepseek_harness.py` 把 DeepSeek 定义为「本地 Agent 运行时」（不只是推理模型），明确它是本地进程 / 工具调用面 / 与 cnb.cool API 的桥。

| 能力 | 说明 |
|------|------|
| `build_context(agent_role, engine, workspace)` | 构建本地运行时上下文（角色/引擎/工作区/工具链） |
| `receive_dispatch(ctx, message)` | 从 cnb.cool 接收 TASK_ASSIGN 派单，解析工作包 |
| `plan_execution(ctx, work_package)` | 结合目标引擎生成执行计划（工具调用面） |
| `execute_locally(ctx, plan)` | 调用本地引擎工具链执行，产出产物清单 |
| `report_back(ctx, plan, result)` | 把产物 + 同源校验要求回传云端 |

**本地/云端协同闭环**：
```
云端 TASK_ASSIGN 派单
  → DeepSeek harness 本地接收
  → 调用 Cocos/UE 工具链执行
  → 本地产出 + 产物清单
  → 同源校验（防分歧）
  → 回传云端验收
```

## 四、验收

测试信号灯 `tests/test_engine_adaptation.sh`（17 项断言全绿）覆盖：
- 双引擎技术栈契约（Cocos/UE）
- 资源管线分叉（.scene/.umap）
- 构建产物契约
- resolve_engine 自适应
- 同源校验（一致/缺失/分歧三场景）
- 双向同步计划
- DeepSeek 运行时（接收/执行/回传）
- roles.yaml 岗位（cocos_dev/ue_dev）
- 部门 Agent 引擎感知

## 关联

Ref: #32（承接架构师建议，落地 wp_engine_adaptation 双引擎适配）
