# 程序线 · Issue #90 跨平台架构增强产出

> 场景：Issue #90「跨平台架构增强」派发程序线 4 个工作包，产出跨平台技术实现文档。
> 部门流水线顺序：策划 → 程序 → 美术 → 测试 → 项目管理 → 运营

## 产出物清单

| 工作包 | 主责角色 | 产出文件 |
|--------|---------|---------|
| wp_client | client_dev（组）→ cocos_dev + ue_dev + client_dev | wp_client_多引擎客户端适配层.md |
| wp_server | server_dev | wp_server_多端共享服务端.md |
| wp_engine | engine_dev（组）→ engine_dev + tools_dev + cto | wp_engine_C++中间件ABI标准化.md |
| wp_ai_logic | ai_programmer | wp_ai_logic_程序化生成引擎无关AI.md |

## 核心设计要点

1. **C ABI 标准化**：纯 C 接口层，支持 Python/TS/JS/C#/C++ 5 语言直接调用
2. **引擎无关客户端适配层**：IClientAdapter 统一接口，4 引擎实现可替换
3. **多端共享服务端**：服务端权威 + 统一协议，4 平台连同一服务
4. **程序化生成确定性**：同一种子 → 相同输出（跨引擎 hash 一致）
5. **引擎无关 NPC AI**：行为树 JSON 驱动 + 黑板 + 感知系统
6. **跨端一致性保障**：定点数计算 + 统一随机种子 + 服务端权威

## 对接的策划设计文档

- `wp_gameplay_跨平台核心玩法架构.md` → wp_client / wp_engine
- `wp_numeric_model_跨平台数值模型.md` → wp_server / wp_engine
- `wp_combat_引擎无关战斗机制.md` → wp_client / wp_engine / wp_ai_logic
- `wp_narrative_跨平台叙事框架.md` → wp_client / wp_server

## 对接的架构师设计文档

- `multi-engine-pipeline/01-architecture.md` → 四级引擎流水线 + 跨引擎中间件
- `multi-engine-pipeline/02-middleware-design.md` → C ABI 接口 + 中立资产格式 + 程序化生成

## 下游解锁

- **美术线**（wp_art_direction / wp_ui_ux / wp_audio）：跨平台资源规格产出
- **测试线**（wp_testing）：跨平台回归/性能测试
