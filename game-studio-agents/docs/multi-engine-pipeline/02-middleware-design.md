# 跨引擎中间件详细设计

> 本文件聚焦跨引擎中间件各子模块的详细设计，包括接口契约、数据规范、实现要点。

---

## 一、中立资产格式规范

### 1.1 3D 模型：glTF 2.0

- **源格式**：`.glb`（二进制 glTF），支持 PBR 材质、骨骼动画、顶点动画
- **纹理**：PNG (无损源) / WebP (压缩分发)
- **转换**：`gltf-transform` + 自研转换器，支持各引擎专用格式导出
- **验证**：Schema 校验 + 渲染一致性检查

### 1.2 关卡/场景数据：JSON Schema

```json
{
  "$schema": "https://example.com/level-schema.json",
  "level_id": "LVL_001",
  "name": "新手村",
  "dimensions": {"width": 100, "depth": 80},
  "spawn_points": [
    {"x": 10, "y": 2, "z": 10, "rotation_y": 0}
  ],
  "terrain": {
    "type": "procedural",
    "seed": 42,
    "params": {"height_range": [0, 12], "fractal_octaves": 5}
  },
  "props": [
    {"prefab_id": "tree_oak_01", "x": 15, "z": 20, "scale": 1.2}
  ],
  "npc": [],
  "enemies": [],
  "triggers": []
}
```

### 1.3 资产元数据

每份资产携带统一元数据，支持标签检索和智能复用：

```json
{
  "asset_id": "asset_tree_oak_01",
  "asset_type": "model",
  "category": "environment/props/tree",
  "format": "gltf",
  "version": "1.0.0",
  "author": "procedural",
  "tags": ["tree", "oak", "nature", "forest"],
  "optimizations": {
    "low_poly": true,
    "draw_calls": 1,
    "texture_size": 256
  },
  "licenses": {"usage": "internal", "commercial": false}
}
```

### 1.4 目录规范

```
assets/
├── source/                    # 中立源资产（唯一真相）
│   ├── models/*.glb
│   ├── textures/*.png
│   ├── audio/*.wav
│   ├── animations/*.fbx
│   ├── levels/*.json
│   └── metadata/*.json
├── generated/                 # 程序化生成产物
│   ├── terrain/               # 按 seed 组织的生成地形
│   ├── buildings/
│   └── props/
└── engine/                    # 各引擎渲染副本（由 pipeline 自动生成）
    ├── cocos/                 # 构建时生成
    ├── unity/                 # 构建时生成
    └── unreal/                # 构建时生成
```

---

## 二、C ABI 中间层设计

### 2.1 核心原则

1. **纯 C 头文件** — 无 C++ 特性，保证跨语言 FFI 兼容
2. **显式内存管理** — 提供 create/destroy 接口，由宿主管理生命周期
3. **错误码统一** — 所有函数返回 `int`，0 = 成功，非 0 = 错误码
4. **回调机制** — 宿主可注册回调（事件通知/日志/自定义行为）

### 2.2 接口清单（初始版）

```c
// cabi_gameplay.h
#ifndef CABI_GAMEPLAY_H
#define CABI_GAMEPLAY_H

#ifdef __cplusplus
extern "C" {
#endif

/* ---- 生命周期 ---- */
int cabi_gameplay_init(void);
int cabi_gameplay_shutdown(void);

/* ---- 更新循环 ---- */
int cabi_gameplay_update(float delta_time);

/* ---- 状态管理 ---- */
int cabi_gameplay_set_state(int state_id);
int cabi_gameplay_get_state(void);

/* ---- 事件系统 ---- */
typedef void (*cabi_event_callback)(int event_type, void* payload, int payload_size);
int cabi_gameplay_register_event_callback(cabi_event_callback cb);
int cabi_gameplay_emit_event(int event_type, void* payload, int payload_size);

/* ---- 数据模型 ---- */
int cabi_gameplay_set_data(const char* key, const void* data, int size);
int cabi_gameplay_get_data(const char* key, void* out_buf, int* in_out_size);

/* ---- 程序化生成 ---- */
int cabi_procgen_generate(const char* gen_type, const char* seed_str, 
                          const char* params_json, char** out_result_json);
int cabi_procgen_free_result(char* result);

/* ---- 日志 ---- */
typedef void (*cabi_log_callback)(const char* message, int level);
int cabi_set_log_callback(cabi_log_callback cb);

#ifdef __cplusplus
}
#endif

#endif /* CABI_GAMEPLAY_H */
```

### 2.3 各语言 FFI 包装器

| 语言 | 调用方式 | 生成方式 |
|------|---------|---------|
| TypeScript (React) | WASM (Emscripten) | 手动 + AI 生成 |
| TypeScript (Cocos) | Native Plugin FFI | 手动 + AI 生成 |
| C# (Unity) | P/Invoke | 自动生成 (SWIG/cbindgen) |
| C++ (UE) | 直接 include + 链接 | 零包装 |
| Python (原型) | ctypes/cffi | 自动生成 |

---

## 三、程序化生成核心设计

### 3.1 生成器架构

```python
# procgen_core.py 的抽象接口
class BaseGenerator:
    """所有程序化生成器的基类（引擎无关）"""
    
    def __init__(self, seed: int):
        self.seed = seed
        self.rng = random.Random(seed)
    
    def generate(self, params: dict) -> dict:
        """生成数据，返回中立 JSON 数据"""
        raise NotImplementedError
    
    def validate(self, data: dict) -> bool:
        """校验生成结果是否符合规范"""
        raise NotImplementedError
    
    def export(self, data: dict) -> dict:
        """导出为中立资产格式（glTF/JSON/PNG）"""
        raise NotImplementedError
```

### 3.2 内置生成器清单

| 生成器 | 输出 | 依赖 |
|--------|------|------|
| `TerrainGen` | 高度图 + 纹理 (PNG) | Perlin/Simplex 噪声 |
| `LevelGen` | 关卡数据 (JSON) | 房间布局算法 |
| `PropGen` | 物品/装饰物 (glTF) | 模型组合算法 |
| `BuildingGen` | 建筑模型 (glTF) | 模块化拼接 |
| `NarrativeGen` | 剧情/对话 (JSON) | 模板 + LLM 可选 |
| `TextureGen` | 贴图 (PNG) | 过程纹理算法 |
| `AnimationGen` | 动画曲线 (FBX) | 程序化动画 |

### 3.3 确定性保证

- 同一种子 + 相同参数 → 相同输出
- 随机数使用 `seeded RNG`（如 PCG/XorShift），不用系统随机
- 生成器版本控制：输出数据包含 `generator_version` 字段
- 回归测试：已知种子的输出快照比对

---

## 四、玩法逻辑层设计

### 4.1 状态机

```
[Idle] ──start──→ [Playing] ──pause──→ [Paused]
   ▲                  │                  │
   │                  ▼                  │
   └───exit──── [GameOver] ←──────┘
```

- 状态枚举统一编号，跨语言一致
- 状态转换通过事件总线触发
- 每个状态的可转换目标在配置中声明

### 4.2 事件总线

```cpp
// gameplay_core.h 核心事件定义
enum GameEventType {
    EVENT_STATE_CHANGE = 1,
    EVENT_PLAYER_JOIN = 2,
    EVENT_ITEM_PICKUP = 3,
    EVENT_COMBAT_START = 4,
    EVENT_COMBAT_END = 5,
    EVENT_LEVEL_COMPLETE = 6,
    EVENT_LEVEL_FAILED = 7,
    EVENT_SCORE_CHANGED = 8,
    EVENT_AI_TRIGGER = 9,
    // ... 扩展预留
};
```

### 4.3 数据模型

- **实体-组件模型 (ECS)**：所有游戏实体由组件组合而成
- **数据驱动**：实体定义来自 JSON，代码不硬编码数值
- **序列化**：支持保存/加载，格式 JSON

---

## 五、迁移工具链设计

### 5.1 资产转换管线

```python
# 转换管线伪代码
def convert_asset(asset_id, source_format, target_engines):
    """将中立源资产转换为各引擎渲染副本"""
    
    source_path = find_source(asset_id)      # assets/source/
    meta = load_metadata(asset_id)           # 元数据
    
    for engine in target_engines:
        converter = get_converter(source_format, engine)
        result = converter.convert(source_path, meta)
        verify_consistency(source_path, result)  # hash 校验
        write_to_engine_dir(engine, result)      # assets/engine/{engine}/
    
    update_manifest(asset_id, target_engines)

def convert_all():
    """批量转换全部资产"""
    for asset_id in get_all_asset_ids():
        convert_asset(asset_id, ...)
```

### 5.2 代码转换器

```python
# 代码转换管线
def generate_code(source_language, target_language, source_code, engine_spec):
    """生成目标语言的代码"""
    
    # 1. 提取核心逻辑（依赖分析）
    core_logic = extract_core(source_code)
    
    # 2. 转换为目标语言
    if target_language == "cpp":
        code = ai_translate_python_to_cpp(core_logic)
    elif target_language == "csharp":
        code = generate_csharp_wrapper(core_logic)  # 通过 C ABI
    elif target_language == "typescript":
        code = generate_ts_wrapper(core_logic)      # 通过 WASM
    
    # 3. 生成测试用例
    tests = generate_tests(source_code, code)
    
    # 4. 校验一致性
    result = verify_behavior(source_code, code, tests)
    
    return {"code": code, "tests": tests, "verified": result}
```

### 5.3 一致性校验器

```python
class ConsistencyVerifier:
    """跨引擎一致性校验"""
    
    def verify_asset(self, source_path, engine_path, algorithm="sha256"):
        """资产一致性校验：对比源资产与渲染副本"""
        source_hash = hash_file(source_path, algorithm)
        engine_hash = hash_file(engine_path, algorithm)
        return source_hash == engine_hash
    
    def verify_data_schema(self, json_data, schema):
        """数据结构校验：验证 JSON 符合 Schema"""
        return validate_json_schema(json_data, schema)
    
    def verify_gameplay_behavior(self, test_cases, engine_under_test):
        """行为回归校验：测试用例在各引擎上行为一致"""
        results = []
        for test in test_cases:
            result = run_test(engine_under_test, test)
            results.append(result)
        return all(results)
    
    def generate_report(self):
        """生成一致性报告（人可读）"""
        ...
```

---

## 六、开发顺序建议

### 第 1 周：规范先行
1. 中立资产格式 Schema（JSON Schema 定义）
2. C ABI 头文件设计
3. 资产目录结构 + 元数据规范

### 第 2-3 周：核心实现
4. C ABI 核心库（C++ 实现 + C 头文件）
5. 程序化生成 TerrainGen MVP
6. 资产转换管线（glTF→各引擎）

### 第 4-5 周：跨引擎打通
7. React→Cocos 迁移 Demo
8. Cocos→Unity 迁移 Demo
9. Unity→UE 迁移 Demo（C++ 核心直接集成）

### 第 6 周：工程化
10. 一致性校验器 + 回归测试
11. AI 转译管线初版
12. 文档完善 + 脚手架

---

## 七、与现有模块的接口契约

### 7.1 与 `engine_adapters.py` 的关系

```python
# 现有 engine_adapters.py 提供引擎适配
# 新中间件层在其之上提供引擎无关的核心能力

from engine_adapters import get_engine, EngineAdapter

class CrossEngineMiddleware:
    """跨引擎中间件入口"""
    
    def __init__(self):
        self.asset_pipeline = AssetPipeline()
        self.procgen = ProcgenCore()
        self.gameplay = GameplayCore()
        self.migration = MigrationTools()
    
    def get_engine_adapter(self, engine_type):
        """获取指定引擎的适配器（复用现有模块）"""
        return get_engine(engine_type)
```

### 7.2 与 `engine_bridge/` 的关系

```python
# 现有 engine_bridge 提供引擎连接能力（MCP/插件）
# 中间件层在其之上提供引擎无关的核心逻辑

from engine_bridge import EngineBridgeFacade

class MiddlewareWithBridge:
    """中间件 + 引擎桥接的组合"""
    
    def __init__(self):
        self.middleware = CrossEngineMiddleware()
        self.bridge = EngineBridgeFacade(...)
    
    def execute_in_engine(self, engine, operation, *args):
        """通过桥接层在指定引擎中执行中间件操作"""
        # 中间件输出中立数据
        data = self.middleware.generate(...)
        # 通过桥接层注入到引擎
        self.bridge.execute_engine_operation(engine, operation, data)
```

---

> 状态: `in_progress`  
> 依赖: 现有 engine_adapters.py / engine_bridge/  
> 下一步: 按开发顺序开始实现 P0 模块
