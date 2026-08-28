# wp_engine · C++ 中间件 / ABI 标准化实现（Issue #90）

- **工作包**：wp_engine C++ 中间件/ABI 标准化
- **部门**：程序线
- **主责角色**：engine_dev（组）→ engine_dev + tools_dev + cto 协作
- **模块**：engine / middleware / cabi
- **产出物类型**：engine_impl（引擎中间件实现文档）
- **场景**：Issue #90「跨平台架构增强」——构建引擎无关的 C++ 中间件层，用 C ABI 标准化降低跨引擎迁移成本

---

## 一、C++ 中间件架构设计

### 1.1 核心设计原则

```
┌─────────────────────────────────────────────────────────────────┐
│                    C++ 核心中间件层（Cross-Engine Middleware）   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  C++ 核心库（引擎无关 Pure C++ Core）                    │   │
│  │  · 玩法逻辑（状态机/规则引擎）                           │   │
│  │  · 战斗结算（数值计算/命中判定）                         │   │
│  │  · 程序化生成（噪声/布局/资源分布）                      │   │
│  │  · 叙事数据（对话/任务状态机）                           │   │
│  │  · 数值模型（定点数/配置表）                             │   │
│  └──────────────────────┬──────────────────────────────────┘   │
│                         │ C ABI 导出（extern "C"）              │
│  ┌──────────────────────▼──────────────────────────────────┐   │
│  │  纯 C 接口层（C ABI Boundary）                           │   │
│  │  · 无 C++ 特性（兼容 FFI）                               │   │
│  │  · 显式内存管理（create/destroy）                        │   │
│  │  · 统一错误码（0=成功）                                  │   │
│  │  · 回调机制（事件通知）                                  │   │
│  └──────────────────────┬──────────────────────────────────┘   │
│                         │ 各语言 FFI 包装器                    │
│  ┌──────────────────────▼──────────────────────────────────┐   │
│  │  FFI 包装层（Language Bindings）                         │   │
│  │  · TypeScript（Web/React）→ WASM                         │   │
│  │  · TypeScript（Cocos）→ Native Plugin                    │   │
│  │  · C#（Unity）→ P/Invoke                                 │   │
│  │  · C++（UE）→ 直接编译链接                               │   │
│  │  · Python（原型）→ ctypes                               │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 目录结构

```
middleware/
├── include/                      # 公共头文件
│   ├── cabi_gameplay.h          # 玩法核心 C ABI
│   ├── cabi_combat.h            # 战斗核心 C ABI
│   ├── cabi_procgen.h           # 程序化生成 C ABI
│   ├── cabi_narrative.h         # 叙事数据 C ABI
│   ├── cabi_numeric.h           # 数值计算 C ABI
│   └── cabi_common.h            # 通用错误码/类型
├── src/                          # C++ 核心实现
│   ├── gameplay/                # 玩法逻辑
│   ├── combat/                  # 战斗结算
│   ├── procgen/                 # 程序化生成
│   ├── narrative/               # 叙事数据
│   └── numeric/                 # 定点数
├── bindings/                     # 各语言 FFI 包装器
│   ├── typescript/              # TS 包装（Web+Cocos）
│   ├── csharp/                  # C# 包装（Unity）
│   ├── python/                  # Python 包装
│   └── build_tools/             # 自动生成脚本
├── tests/                        # 单元/集成测试
├── CMakeLists.txt               # CMake 构建配置
└── BUILD.md                     # 构建说明
```

---

## 二、C ABI 接口定义

### 2.1 通用接口规范

```c
// cabi_common.h - 通用 C ABI 规范
#ifndef CABI_COMMON_H
#define CABI_COMMON_H

#ifdef __cplusplus
extern "C" {
#endif

/* ---- 错误码 ---- */
#define CABI_OK                 0   // 成功
#define CABI_ERR_INVALID_ARG    1   // 参数错误
#define CABI_ERR_NULL_PTR       2   // 空指针
#define CABI_ERR_MEMORY         3   // 内存不足
#define CABI_ERR_NOT_INIT       4   // 未初始化
#define CABI_ERR_NOT_FOUND      5   // 资源不存在
#define CABI_ERR_VERSION        6   // 版本不匹配

/* ---- 回调类型 ---- */
typedef void (*cabi_log_callback)(const char* message, int level);
typedef void (*cabi_event_callback)(int event_type, const void* payload, int payload_size);

/* ---- 通用生命周期 ---- */
int cabi_init(cabi_log_callback log_cb);
int cabi_shutdown(void);
int cabi_version(void);

#ifdef __cplusplus
}
#endif
#endif /* CABI_COMMON_H */
```

### 2.2 玩法核心接口（cabi_gameplay.h）

```c
// cabi_gameplay.h - 玩法核心 C ABI
#ifndef CABI_GAMEPLAY_H
#define CABI_GAMEPLAY_H

#ifdef __cplusplus
extern "C" {
#endif

/* ---- 生命周期 ---- */
int cabi_gameplay_init(void);
int cabi_gameplay_shutdown(void);

/* ---- 更新循环 ---- */
int cabi_gameplay_update(float delta_seconds);

/* ---- 状态管理 ---- */
int cabi_gameplay_set_state(int state_id);
int cabi_gameplay_get_state(int* out_state);

/* ---- 事件系统 ---- */
int cabi_gameplay_register_event_callback(cabi_event_callback cb);
int cabi_gameplay_emit_event(int event_type, const void* payload, int payload_size);

/* ---- 数据模型（JSON 序列化） ---- */
int cabi_gameplay_set_data(const char* key, const char* json_data);
int cabi_gameplay_get_data(const char* key, char** out_json, int* out_size);

#ifdef __cplusplus
}
#endif
#endif /* CABI_GAMEPLAY_H */
```

### 2.3 战斗结算接口（cabi_combat.h）

```c
// cabi_combat.h - 战斗核心 C ABI
#ifndef CABI_COMBAT_H
#define CABI_COMBAT_H

#ifdef __cplusplus
extern "C" {
#endif

/* ---- 战斗初始化 ---- */
int cabi_combat_init(void);
int cabi_combat_shutdown(void);

/* ---- 战斗 Tick（30Hz 固定步长） ---- */
int cabi_combat_tick(float accumulated_dt);

/* ---- 技能结算 ---- */
int cabi_combat_cast_skill(int skill_id, int attacker_id, int target_id);

/* ---- 伤害计算（定点数） ---- */
int cabi_combat_calc_damage(const char* skill_config, const char* attacker_stats,
                            const char* target_stats, int* out_damage);

/* ---- 状态效果（Buff/Debuff） ---- */
int cabi_combat_apply_status(int status_id, int target_id, int duration_ms);
int cabi_combat_remove_status(int status_id, int target_id);

/* ---- 掉落表 ---- */
int cabi_combat_roll_loot(int loot_table_id, int seed, char** out_loot_json);

#ifdef __cplusplus
}
#endif
#endif /* CABI_COMBAT_H */
```

### 2.4 程序化生成接口（cabi_procgen.h）

```c
// cabi_procgen.h - 程序化生成 C ABI
#ifndef CABI_PROCGEN_H
#define CABI_PROCGEN_H

#ifdef __cplusplus
extern "C" {
#endif

/* ---- 生成地形 ---- */
int cabi_procgen_terrain(const char* seed, int width, int height,
                         const char* params_json, char** out_heightmap_json);

/* ---- 生成关卡 ---- */
int cabi_procgen_level(const char* seed, const char* level_params,
                       char** out_level_json);

/* ---- 生成资源分布 ---- */
int cabi_procgen_resources(const char* seed, const char* terrain_data,
                           const char* rules_json, char** out_resources_json);

/* ---- 生成建筑/装饰物 ---- */
int cabi_procgen_props(const char* seed, const char* params_json,
                       char** out_props_json);

/* ---- 生成叙事（对话/任务模板） ---- */
int cabi_procgen_narrative(const char* seed, const char* narrative_schema,
                           char** out_narrative_json);

/* ---- 释放结果内存 ---- */
int cabi_procgen_free_result(char* result);

#ifdef __cplusplus
}
#endif
#endif /* CABI_PROCGEN_H */
```

### 2.5 数值计算接口（cabi_numeric.h）

```c
// cabi_numeric.h - 定点数/数值计算 C ABI
#ifndef CABI_NUMERIC_H
#define CABI_NUMERIC_H

#ifdef __cplusplus
extern "C" {
#endif

/* ---- 定点数类型 ---- */
typedef int64_t FixedPoint;    // 32bit 整数部分 + 10bit 小数（1/1024 精度）

/* ---- 定点数操作 ---- */
FixedPoint fp_from_float(float f);
FixedPoint fp_from_int(int i);
float fp_to_float(FixedPoint fp);
FixedPoint fp_add(FixedPoint a, FixedPoint b);
FixedPoint fp_sub(FixedPoint a, FixedPoint b);
FixedPoint fp_mul(FixedPoint a, FixedPoint b);
FixedPoint fp_div(FixedPoint a, FixedPoint b);
int fp_compare(FixedPoint a, FixedPoint b);   // -1/0/1

/* ---- 等级成长曲线 ---- */
int cabi_numeric_get_level_exp(int level, int* out_exp);
int cabi_numeric_get_level_stats(int level, const char* stat_name, FixedPoint* out_value);

/* ---- 战斗公式 ---- */
FixedPoint cabi_numeric_calc_atk(FixedPoint base_atk, FixedPoint atk_pct);
FixedPoint cabi_numeric_calc_def(FixedPoint base_def, FixedPoint def_pct);
FixedPoint cabi_numeric_calc_crit(FixedPoint base_crit, FixedPoint crit_rate);

#ifdef __cplusplus
}
#endif
#endif /* CABI_NUMERIC_H */
```

---

## 三、各语言 FFI 包装层设计

### 3.1 TypeScript（Web/React → WASM）

```typescript
// bindings/typescript/wasm/cabi_gameplay.ts
// 通过 Emscripten 将 C++ 编译为 WASM，TS 侧自动生成包装器

import createModule from './wasm_module.js';

export class GameplayCore {
    private module: any;
    
    async init(): Promise<void> {
        this.module = await createModule();
        this.module._cabi_gameplay_init();
    }
    
    update(dt: number): void {
        this.module._cabi_gameplay_update(dt);
    }
    
    setState(stateId: number): void {
        this.module._cabi_gameplay_set_state(stateId);
    }
    
    getState(): number {
        const ptr = this.module._malloc(4);
        this.module._cabi_gameplay_get_state(ptr);
        const state = this.module.HEAP32[ptr / 4];
        this.module._free(ptr);
        return state;
    }
}
```

### 3.2 TypeScript（Cocos → Native Plugin FFI）

```typescript
// bindings/typescript/cocos/native_bridge.ts
// Cocos Creator 通过 Native Plugin 调用 C ABI

import { native } from 'cc';

export class CocosNativeBridge {
    private nativeModule: any;
    
    init(): boolean {
        this.nativeModule = native.reflection.getClass('GameMiddleware');
        return this.nativeModule?.init() ?? false;
    }
    
    loadScene(sceneId: string): boolean {
        return this.nativeModule?.loadScene(sceneId) ?? false;
    }
    
    generateTerrain(seed: string): string {
        return this.nativeModule?.generateTerrain(seed) ?? '{}';
    }
}
```

### 3.3 C#（Unity → P/Invoke）

```csharp
// bindings/csharp/CabiGameplay.cs
using System;
using System.Runtime.InteropServices;

public static class CabiGameplay
{
    private const string DLL_NAME = "game_middleware";
    
    [DllImport(DLL_NAME)]
    public static extern int cabi_gameplay_init();
    
    [DllImport(DLL_NAME)]
    public static extern int cabi_gameplay_shutdown();
    
    [DllImport(DLL_NAME)]
    public static extern int cabi_gameplay_update(float delta_seconds);
    
    [DllImport(DLL_NAME)]
    public static extern int cabi_gameplay_set_state(int state_id);
    
    [DllImport(DLL_NAME)]
    public static extern int cabi_gameplay_get_state(out int out_state);
    
    [DllImport(DLL_NAME)]
    public static extern int cabi_combat_calc_damage(
        string skill_config, string attacker_stats, string target_stats,
        out int out_damage);
}
```

### 3.4 C++（UE → 直接编译链接）

```cpp
// bindings/ue5/GameMiddleware.h
#pragma once
#include "cabi_gameplay.h"
#include "cabi_combat.h"
#include "cabi_procgen.h"

class FGameMiddleware
{
public:
    static FGameMiddleware& Get()
    {
        static FGameMiddleware Instance;
        return Instance;
    }
    
    void Init()
    {
        // UE 直接 include 头文件 + 链接静态库
        cabi_gameplay_init();
        cabi_combat_init();
    }
    
    void Update(float DeltaSeconds)
    {
        cabi_gameplay_update(DeltaSeconds);
    }
    
    // ... 其他中间件调用
};
```

### 3.5 Python（原型 → ctypes）

```python
# bindings/python/cabi_gameplay.py
import ctypes
from ctypes import c_int, c_float, c_char_p, c_void_p, POINTER

class GameMiddleware:
    """Python 绑定（用于原型开发）"""
    
    def __init__(self, lib_path: str = "libgame_middleware.so"):
        self.lib = ctypes.CDLL(lib_path)
        
        # 配置函数签名
        self.lib.cabi_gameplay_init.restype = c_int
        self.lib.cabi_gameplay_update.restype = c_int
        self.lib.cabi_gameplay_update.argtypes = [c_float]
        self.lib.cabi_gameplay_set_state.restype = c_int
        self.lib.cabi_gameplay_set_state.argtypes = [c_int]
    
    def init(self) -> int:
        return self.lib.cabi_gameplay_init()
    
    def update(self, dt: float) -> int:
        return self.lib.cabi_gameplay_update(dt)
    
    def set_state(self, state_id: int) -> int:
        return self.lib.cabi_gameplay_set_state(state_id)
```

---

## 四、构建与工具链

### 4.1 CMake 构建配置

```cmake
# CMakeLists.txt
cmake_minimum_required(VERSION 3.16)
project(game_middleware CXX C)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# 核心库
add_library(game_middleware STATIC
    src/gameplay/GameplayCore.cpp
    src/combat/CombatCore.cpp
    src/procgen/ProcgenCore.cpp
    src/narrative/NarrativeCore.cpp
    src/numeric/FixedPoint.cpp
)

# 导出 C ABI（动态库）
add_library(game_middleware_abi SHARED
    src/cabi_gameplay.cpp
    src/cabi_combat.cpp
    src/cabi_procgen.cpp
    src/cabi_narrative.cpp
    src/cabi_numeric.cpp
)

target_link_libraries(game_middleware_abi PRIVATE game_middleware)

# 各平台构建目标
# - Linux:  .so
# - macOS:  .dylib
# - Windows: .dll
# - WASM:   Emscripten
if(EMSCRIPTEN)
    set_target_properties(game_middleware_abi PROPERTIES
        OUTPUT_NAME "game_middleware"
        SUFFIX ".wasm")
endif()
```

### 4.2 自动代码生成工具链

```python
# bindings/build_tools/generate_bindings.py
"""从 C ABI 头文件自动生成各语言 FFI 包装器"""

import re
import subprocess
from pathlib import Path

def parse_c_header(header_path: Path) -> dict:
    """解析 C 头文件，提取函数签名"""
    funcs = []
    with open(header_path) as f:
        content = f.read()
    
    # 匹配 C 函数声明
    pattern = r'\bint\s+(\w+)\((.*?)\)'
    for match in re.finditer(pattern, content):
        name = match.group(1)
        args = match.group(2).strip()
        funcs.append({'name': name, 'args': args})
    
    return {'funcs': funcs}

def generate_csharp(funcs: list, namespace: str = 'GameMiddleware'):
    """生成 C# P/Invoke 包装器"""
    lines = [f'using System.Runtime.InteropServices;', '']
    lines.append(f'public static class {namespace} {{')
    for f in funcs:
        lines.append(f'    [DllImport("game_middleware")]')
        lines.append(f'    public static extern int {f["name"]}({f["args"]});')
        lines.append('')
    lines.append('}')
    return '\n'.join(lines)

def generate_ts(funcs: list, module_name: str = 'game_middleware'):
    """生成 TypeScript WASM 包装器"""
    # ... 实现
    pass

def generate_python(funcs: list, lib_name: str = 'libgame_middleware'):
    """生成 Python ctypes 包装器"""
    # ... 实现
    pass
```

### 4.3 一致性校验器

```python
# tests/consistency_verifier.py
"""跨引擎一致性校验：验证各引擎对同一输入的输出一致"""

import hashlib
import json

class ConsistencyVerifier:
    """跨引擎一致性校验器"""
    
    def verify_seed_determinism(self, gen_func, seed: str, params: dict):
        """验证同一种子输出一致"""
        results = []
        for i in range(10):
            result = gen_func(seed, params)
            results.append(self._hash_data(result))
        return len(set(results)) == 1, results[0]
    
    def verify_cross_engine(self, engine_adapter, test_case):
        """验证跨引擎行为一致"""
        # 在多个引擎上运行同一测试用例
        outputs = []
        for engine in ['react', 'cocos', 'unity', 'ue5']:
            output = engine_adapter.run_test(engine, test_case)
            outputs.append(output)
        # 校验输出一致性
        return self._compare_outputs(outputs)
    
    def _hash_data(self, data):
        """序列化并哈希数据"""
        json_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()
```

---

## 五、核心模块实现要点

### 5.1 玩法核心（GameplayCore）

```cpp
// src/gameplay/GameplayCore.cpp
#include "GameplayCore.h"

GameplayCore::GameplayCore()
    : current_state_(STATE_IDLE)
    , accumulator_(0.0f)
    , tick_interval_(1.0f / 30.0f)  // 30Hz 固定 Tick
{
}

int GameplayCore::Update(float dt) {
    accumulator_ += dt;
    while (accumulator_ >= tick_interval_) {
        ProcessTick();               // 处理逻辑 Tick
        accumulator_ -= tick_interval_;
    }
    return CABI_OK;
}

void GameplayCore::ProcessTick() {
    // 1. 处理事件队列
    ProcessEvents();
    // 2. 推进状态机
    AdvanceStateMachine();
    // 3. 更新实体状态
    UpdateEntities();
    // 4. 发送状态变更事件
    EmitEvents();
}
```

### 5.2 战斗结算（CombatCore）

```cpp
// src/combat/CombatCore.cpp
#include "CombatCore.h"

FixedPoint CombatCore::CalcDamage(const SkillConfig& skill,
                                  const UnitStats& attacker,
                                  const UnitStats& target) {
    // 基础攻击力 × 技能倍率 - 目标防御力
    FixedPoint base = attacker.atk * skill.multiplier;
    FixedPoint def_factor = target.def / (target.def + FixedPoint(100));
    FixedPoint final = base * (FixedPoint(1) - def_factor);
    
    // 暴击判定（种子随机）
    if (RollCritical(attacker.crit_rate)) {
        final = final * FixedPoint(1, 5);  // 150% 暴击伤害
    }
    
    return final;
}

bool CombatCore::RollCritical(FixedPoint crit_rate) {
    // 使用统一随机种子管理，保证多端一致
    uint32_t roll = rng_.Next();
    return FixedPoint(roll % 1000) < crit_rate * FixedPoint(1000);
}
```

### 5.3 程序化生成（ProcgenCore）

```cpp
// src/procgen/ProcgenCore.cpp
#include "ProcgenCore.h"

std::string ProcgenCore::GenerateTerrain(const std::string& seed,
                                          int width, int height) {
    uint32_t seed_value = std::hash<std::string>{}(seed);
    pcg32 rng(seed_value);
    
    std::vector<std::vector<float>> heightmap(height, std::vector<float>(width));
    
    for (int y = 0; y < height; y++) {
        for (int x = 0; x < width; x++) {
            // Perlin/Simplex 噪声
            heightmap[y][x] = noise_.Generate2D(x, y, rng);
        }
    }
    
    // 序列化为中立 JSON 格式
    return SerializeHeightmap(heightmap, seed);
}
```

### 5.4 叙事数据（NarrativeCore）

```cpp
// src/narrative/NarrativeCore.cpp
#include "NarrativeCore.h"

int NarrativeCore::LoadNarrative(const char* json_data) {
    // 解析叙事 JSON Schema
    auto narrative = nlohmann::json::parse(json_data);
    
    // 初始化对话状态机
    dialogue_state_ = DialogueState::INACTIVE;
    
    // 注册触发条件
    for (const auto& trigger : narrative["triggers"]) {
        triggers_.push_back(ParseTrigger(trigger));
    }
    
    return CABI_OK;
}

int NarrativeCore::AdvanceDialogue(const char* choice_id) {
    // 根据选择推进对话
    auto choice = choices_.find(choice_id);
    if (choice == choices_.end()) {
        return CABI_ERR_NOT_FOUND;
    }
    
    // 更新对话状态
    current_dialogue_ = choice->second.next_dialogue;
    
    // 触发相关事件
    EmitEvent(EVENT_DIALOGUE_CHANGED, current_dialogue_.c_str());
    
    return CABI_OK;
}
```

### 5.5 定点数实现（FixedPoint）

```cpp
// src/numeric/FixedPoint.h
#pragma once
#include <cstdint>

class FixedPoint {
private:
    static constexpr int FRACTION_BITS = 10;   // 10bit 小数精度
    static constexpr int64_t SCALE = 1 << FRACTION_BITS;  // 1024
    
    int64_t value_;
    
public:
    FixedPoint() : value_(0) {}
    FixedPoint(int64_t value) : value_(value * SCALE) {}
    FixedPoint(float f) : value_(static_cast<int64_t>(f * SCALE)) {}
    
    FixedPoint operator+(const FixedPoint& other) const {
        return FixedPoint::FromRaw(value_ + other.value_);
    }
    
    FixedPoint operator*(const FixedPoint& other) const {
        return FixedPoint::FromRaw((value_ * other.value_) >> FRACTION_BITS);
    }
    
    float ToFloat() const { return static_cast<float>(value_) / SCALE; }
    
    static FixedPoint FromRaw(int64_t raw) {
        FixedPoint fp;
        fp.value_ = raw;
        return fp;
    }
};
```

---

## 六、开发排期与里程碑

| 阶段 | 任务 | 预估周期 |
|------|------|---------|
| P0-1 | 中立资产格式 Schema 定义 | 3 天 |
| P0-2 | C ABI 头文件设计 + 核心库骨架 | 5 天 |
| P0-3 | 程序化生成 TerrainGen MVP | 5 天 |
| P1-1 | 玩法核心 C++ 实现 | 7 天 |
| P1-2 | 战斗结算 C++ 实现 | 7 天 |
| P1-3 | 各语言 FFI 包装器生成工具 | 5 天 |
| P1-4 | 一致性校验器 + 回归测试 | 4 天 |
| P2-1 | React→Cocos 迁移 Demo | 5 天 |
| P2-2 | Cocos→Unity 迁移 Demo | 7 天 |
| P2-3 | Unity→UE 迁移 Demo | 5 天 |

---

## 七、交付物与验收标准

| 交付物 | 路径 | 验收标准 |
|--------|------|---------|
| C ABI 头文件 | `middleware/include/*.h` | 覆盖玩法/战斗/生成/叙事/数值 |
| C++ 核心库 | `middleware/src/` | 编译通过 + 单测通过 |
| FFI 包装器 | `middleware/bindings/` | 5 语言调用验证通过 |
| 一致性校验器 | `middleware/tests/` | 跨引擎 seed 一致性测试通过 |
| CMake 构建 | `middleware/CMakeLists.txt` | Linux/WASM/Windows 三平台构建通过 |
| 绑定生成工具 | `middleware/bindings/build_tools/` | 从头文件自动生成包装器 |

**验收指标**：
- 同一 seed 在 4 引擎产出完全一致的地图数据（hash 一致）
- 定点数战斗结算偏差 = 0（跨端一致）
- C ABI 接口可供 Python/TS/JS/C#/C++ 全部直接调用
- WASM 体积 ≤ 2MB（Web 端加载性能可接受）

---

> 产出：engine_dev + tools_dev + cto 协作，基于策划线 wp_gameplay/wp_combat/wp_numeric_model 设计 + 架构师中间件设计文档。
