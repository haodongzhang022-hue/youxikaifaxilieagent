# 跨引擎中间件（Cross-Engine Middleware）

> 对齐 Issue #90「跨平台架构增强」· wp_engine C++中间件/ABI 标准化
> 核心命题：**让各引擎退化成「渲染器」，迁移变成「换渲染器」而非「重写游戏」**

## 设计原则

- **C ABI 标准化**：纯 C 头文件，Python/TS/C#/C++ 全部可直接 FFI 调用
- **确定性程序化生成**：同一种子 seed → 完全一致的输出（跨引擎 hash 校验）
- **定点数精度**：32bit 整数 + 10bit 小数，跨端 bit 级一致
- **引擎无关核心**：玩法/战斗/数值/叙事均为纯逻辑，不依赖任何引擎 API

## 目录结构

```
middleware/
├── include/               # C ABI 公共头文件（跨语言 FFI 契约）
│   ├── cabi_common.h     # 通用错误码/回调/JSON 帮助
│   ├── cabi_gameplay.h   # 玩法状态机 + 事件系统
│   ├── cabi_combat.h     # 战斗结算 + 掉落
│   ├── cabi_procgen.h    # 程序化生成（地形/关卡/资源/装饰/叙事）
│   └── cabi_numeric.h    # 定点数 + 数值公式
├── src/                   # C++ 核心实现（引擎无关 Pure C++）
│   ├── common/           # 通用生命周期
│   ├── gameplay/         # 玩法核心
│   ├── combat/           # 战斗核心
│   ├── procgen/          # 程序化生成核心
│   └── numeric/          # 定点数
├── bindings/              # 各语言 FFI 绑定
│   ├── python/           # ctypes 绑定 + 纯 Python 参考实现
│   └── typescript/       # Web/React WASM 绑定
└── CMakeLists.txt         # 构建配置
```

## 快速验证（无需 C 编译器）

当前环境无 C 编译器时，可用 Python 绑定验证确定性核心：

```bash
PYTHONPATH=. python3 -m middleware.bindings.python.consistency
```

预期输出：`ALL CONSISTENCY CHECKS PASSED`（全部生成器种子确定性 OK）。

## 构建（需 C++17 + CMake 3.16+）

```bash
cd middleware
mkdir -p build && cd build
cmake .. && make
ctest   # 运行 C++ 核心自测
```

产物：
- `libgame_middleware.a` — C++ 核心静态库
- `libgame_middleware_abi.so` — C ABI 动态库（供各语言 FFI）

## 确定性保证

| 生成器 | 同 seed 输出 | golden hash（golden_seed） |
|--------|-------------|--------------------------|
| terrain | ✅ 一致 | 9d21290196fb |
| level | ✅ 一致 | 55b61ed84f88 |
| resources | ✅ 一致 | e0468607b364 |
| props | ✅ 一致 | 2084f4ebdb29 |
| narrative | ✅ 一致 | bf78ceb41b2a |
| loot | ✅ 一致 | ffd089fa98e5 |

> 跨引擎一致性：各引擎（React WASM / Cocos / Unity / UE）调用同一 C ABI 核心，
> 对同 seed 产出相同 hash，即为「换渲染器」的迁移根基。

## 四引擎适配器（middleware/adapters）

在核心之上，为四个引擎各建一层**适配器**，让各引擎真正消费 C++ 核心：

```
┌─────────────────────────────────────────────────────┐
│                  C++ 中间件核心 (C ABI)              │
│   玩法 / 战斗 / 数值 / 程序化生成（引擎无关）          │
└──────────────────────┬──────────────────────────────┘
                       │ 统一 C ABI 契约
     ┌─────────┬───────┴───────┬──────────┐
     ▼         ▼               ▼          ▼
 React(WASM) Cocos(Native)  Unity(P/Invoke) Unreal(原生C++)
  web 引流    小程序分享       完整地图        护城河高保真
```

| 适配器 | 语言 | 集成方式 | 职责 |
|--------|------|---------|------|
| `adapters/react/reactAdapter.ts` | TS | Emscripten WASM | 网页端逻辑玩法 + 引流 |
| `adapters/cocos/cocosAdapter.ts` | TS | Native Plugin FFI | 小程序快速分享/轻量 |
| `adapters/unity/UnityAdapter.cs` | C# | P/Invoke Native Plugin | 完整地图 App 客户端 |
| `adapters/unreal/UnrealAdapter.h` | C++ | 原生源码集成 | 最高质量/护城河 |

**核心原则**：各引擎只做「渲染」，逻辑全部走中间件 C++ 核心 → 迁移即换渲染器。

## 四引擎一致性测试

```bash
PYTHONPATH=. python3 middleware/adapters/tests/test_adapters.py
```

验证：种子确定性 / 跨种子差异 / golden hash 基准 / 四适配器契约。
