# 引擎桥接层架构（Engine Bridge）

> 面向 **Windows + Cocos Creator + Unreal Engine 5** 引擎环境的统一桥接架构。
> 通过 **MCP（Model Context Protocol）** 和 **引擎插件** 控制引擎，
> 为游戏开发 Agent 系统提供引擎能力访问的标准化接口。

## 一、架构定位

当前 Agent 系统负责游戏开发的**编排与决策**（拆解需求、分配任务、验收产出），
但**不直接接触引擎**。未来的开发环境将迁移到 Windows，并需要借助
Cocos Creator 和 UE5 引擎的**编辑/构建/运行**能力完成实际开发。

引擎桥接层是 Agent 系统与游戏引擎之间的**适配层**：

```
┌─────────────────────────────────────────────────────┐
│               游戏开发 Agent 系统                    │
│  (游戏向经理/六大部门/CodeBuddy/仓库处理专员)         │
└──────────────────────┬──────────────────────────────┘
                       │ EngineCommand（统一命令协议）
                       ▼
┌─────────────────────────────────────────────────────┐
│              引擎桥接层 (Engine Bridge)              │
│                                                     │
│   ┌─────────────┐  ┌─────────────┐  ┌───────────┐  │
│   │ EngineCommand│  │  MCP Client │  │  Plugin   │  │
│   │  (统一语义)  │  │  (协议通道)  │  │  Adapter  │  │
│   └──────┬──────┘  └──────┬──────┘  └─────┬─────┘  │
│          │               │                │         │
│          ▼               ▼                ▼         │
│   ┌─────────────┐  ┌─────────────┐  ┌───────────┐  │
│   │ CocosAdapter │  │  UE5Adapter │  │   Mock    │  │
│   └──────┬──────┘  └──────┬──────┘  └───────────┘  │
└──────────┼────────────────┼─────────────────────────┘
           ▼                ▼
   ┌──────────────┐  ┌──────────────┐
   │ Cocos MCP    │  │ UE5 MCP      │
   │ Server/插件  │  │ Server/插件  │
   └──────┬───────┘  └──────┬───────┘
          ▼                  ▼
   ┌──────────────┐  ┌──────────────┐
   │ Cocos Creator│  │ UE5 编辑器   │
   └──────────────┘  └──────────────┘
```

## 二、核心设计原则

### 1. 统一抽象（EngineCommand）

无论底层是 Cocos 还是 UE5，Agent 都使用**同一套引擎命令**与引擎交互：

| 命令能力 | 语义 | Cocos | UE5 |
|---------|------|-------|-----|
| `scene.load` | 加载场景/关卡 | .scene 文件 | .umap 关卡 |
| `scene.save` | 保存场景/关卡 | .scene 文件 | .umap 关卡 |
| `node.create` | 创建节点/对象 | CC Node | Actor |
| `node.transform` | 设置变换 | Node position | Actor transform |
| `asset.import` | 导入资产 | 资源面板 | Content Browser |
| `material.create` | 创建材质 | Material | Material |
| `play.start` | 进入 Play 模式 | 预览运行 | PIE 模式 |
| `test.run` | 运行自动化测试 | 测试框架 | 自动化测试框架 |
| `blueprint.create` | 创建蓝图 | 不支持 | Blueprint Class |

### 2. MCP 优先，插件补充

- **MCP 优先**：首选通过 MCP 协议与引擎的 MCP Server 通信。
  MCP 提供标准化的工具/资源/事件接口，是最主要的控制通道。
- **插件补充**：MCP 不可用或需要引擎内操作时，通过引擎原生插件
  （Cocos Extension / UE5 Editor Plugin）调用。
- **降级链**：MCP → 插件 → Mock，逐级降级，保证系统始终可用。

### 3. Windows 环境适配

- **路径探测**：从环境变量 + 默认安装路径探测引擎位置
  （`COCOS_CREATOR_PATH` / `UE5_PATH` / `UE_ROOT`）
- **进程管理**：支持启动/停止/查找引擎编辑器进程
- **MCP 端点**：默认 `http://127.0.0.1:12345/mcp`（Cocos）和
  `http://127.0.0.1:54321/mcp`（UE5），可从环境变量覆盖

### 4. 测试优先

- **Mock 模式**：所有引擎操作都有可测试的 Mock 实现
- **测试信号灯**：35 项断言覆盖命令协议/环境探测/MCP/插件/适配器/门面
- **CI 集成**：`test_engine_bridge.sh` 已接入流水线

## 三、模块结构

```
game-studio-agents/config/engine_bridge/
├── __init__.py         # 模块入口，导出公共接口 + 演示
├── protocol.py         # 引擎命令协议（EngineCommand/EngineCapability/EngineResult）
├── mcp_client.py       # MCP 客户端（连接引擎 MCP Server）
├── plugin_adapter.py   # 引擎插件适配器（发现/调用插件）
├── engine_adapter.py   # 引擎适配器基类 + Mock 适配器 + 工厂
├── cocos_adapter.py    # Cocos Creator 适配器
├── ue5_adapter.py      # Unreal Engine 5 适配器
├── environment.py      # Windows 环境适配（路径/版本/端点探测）
├── errors.py           # 异常体系
└── bridge.py           # 统一门面（EngineBridgeFacade）
```

## 四、使用方式

```python
from engine_bridge import EngineBridgeFacade, BridgeConfig

# 创建桥接（Mock 模式用于测试）
bridge = EngineBridgeFacade(BridgeConfig(use_mock=True, engines=["cocos", "ue5"]))
bridge.init()

# 加载场景
result = bridge.load_scene("assets/scenes/Main.scene")
if result.success:
    print("场景加载成功")

# 创建节点
bridge.create_node("Player", "Root")

# 进入 Play 模式
bridge.play()

# 查询能力
caps = bridge.capabilities("cocos")
if bridge.has_capability(EngineCapability.SCENE_LOAD, "cocos"):
    print("Cocos 支持场景加载")
```

## 五、Agent 集成方式

各 Agent 通过 `EngineBridgeFacade` 获得引擎能力：

- **程序线**（client_dev/engine_dev）：直接控制引擎执行代码修改、场景操作
- **美术线**（tech_artist/art_director）：通过引擎设置材质、导入资源、预览效果
- **测试线**（qa_engineer/auto_qa）：通过引擎运行自动化测试、收集测试结果
- **游戏向经理**：通过引擎查询项目状态、触发构建

每个 Agent 只需持有 `EngineBridgeFacade` 实例，无需关心底层是 Cocos 还是 UE5。

## 六、当前状态与后续规划

### ✅ 已完成（本架构阶段）
- 统一引擎命令协议（EngineCommand + 27/32 能力定义）
- Windows 目标环境探测（模拟 Windows + Cocos + UE5）
- MCP 客户端（HTTP 传输，Mock 模式可用）
- 插件适配器（插件发现/调用，Mock 模式可用）
- Cocos/UE5 适配器（MCP 优先 + 插件降级）
- 统一门面（EngineBridgeFacade）
- 35 项测试信号灯 + CI 集成

### 🔜 待引擎环境就绪后
- 实现引擎 MCP Server 插件（Cocos Extension / UE5 Plugin）
- 真实 MCP 协议对接（HTTP/SSE 传输）
- 真实插件通道对接（Editor.Message / EditorUtility）
- Windows 进程管理与编辑器自动化
- 引擎事件流对接（场景变更/编译完成/测试结果）
- 构建/打包流水线对接

## 七、测试

```bash
# 运行引擎桥接层测试
bash game-studio-agents/tests/test_engine_bridge.sh

# 运行引擎桥接层演示
python3 game-studio-agents/config/engine_bridge/__init__.py
```
