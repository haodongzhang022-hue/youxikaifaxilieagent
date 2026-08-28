# wp_client · 多引擎客户端适配层实现（Issue #90）

- **工作包**：wp_client 多引擎客户端适配层
- **部门**：程序线
- **主责角色**：client_dev（组）→ cocos_dev + ue_dev + client_dev 协作
- **模块**：client / multi-engine-adapter
- **产出物类型**：client_impl（客户端实现文档）
- **场景**：Issue #90「跨平台架构增强」——需在 Web→Cocos→Unity→UE 四级引擎间实现客户端统一适配层

---

## 一、适配层架构设计

### 1.1 三层客户端适配架构

```
┌──────────────────────────────────────────────────────────────┐
│  客户端逻辑层（Engine-Agnostic Client Logic）                 │
│  · 游戏状态管理（纯数据驱动）                                 │
│  · 输入抽象（IInputAdapter）                                  │
│  · 场景/UI 数据绑定（DataBinding）                            │
│  · 资源缓存管理（AssetCacheManager）                          │
├──────────────────────────────────────────────────────────────┤
│  引擎适配接口层（Client Engine Adapter Interface）            │
│  · IClientAdapter 基类（生命周期/渲染/输入/网络统一入口）     │
│  · 统一命令协议（基于 engine_bridge EngineCommand）           │
│  · 引擎能力探测（Capability Discovery）                       │
├──────────────────────────────────────────────────────────────┤
│  引擎实现层（Web / Cocos / Unity / UE）                       │
│  · ReactWebAdapter（Web 引流）                               │
│  · CocosAdapter（小程序轻量）                                │
│  · UnityAdapter（完整客户端）                                │
│  · UE5Adapter（高保真客户端）                                │
└──────────────────────────────────────────────────────────────┘
```

### 1.2 核心接口定义

```python
# 客户端引擎适配器接口（所有引擎实现需实现）
class IClientAdapter:
    """客户端引擎适配器统一接口"""
    
    # ---- 生命周期 ----
    def initialize(self, config: dict) -> bool: ...
    def shutdown(self) -> None: ...
    
    # ---- 渲染层 ----
    def create_scene(self, scene_data: dict) -> str: ...       # 返回 scene_id
    def load_scene(self, scene_id: str) -> bool: ...
    def unload_scene(self, scene_id: str) -> bool: ...
    
    # ---- 输入层 ----
    def bind_input(self, input_action: str, handler: callable) -> None: ...
    def unbind_input(self, input_action: str) -> None: ...
    
    # ---- 资源层 ----
    def load_asset(self, asset_id: str, asset_type: str) -> Any: ...
    def preload_asset(self, asset_ids: list[str]) -> bool: ...
    
    # ---- UI 层 ----
    def show_panel(self, panel_id: str, data: dict = None) -> None: ...
    def hide_panel(self, panel_id: str) -> None: ...
    
    # ---- 网络层 ----
    def connect_server(self, endpoint: str) -> bool: ...
    def disconnect_server(self) -> None: ...
    def send_message(self, msg_type: str, payload: dict) -> None: ...
```

### 1.3 引擎能力差异适配

| 能力维度 | React/Web | Cocos | Unity | UE5 |
|---------|-----------|-------|-------|-----|
| 渲染 | Canvas/WebGL | Cocos Renderer | Built-in/URP/HDRP | Nanite/Lumen |
| 输入 | 键鼠/触屏 | 触屏/键鼠 | 键鼠/手柄 | 键鼠/手柄/VR |
| 资源格式 | WASM/JSON | .prefab/.scene | .prefab/.unity | .uasset |
| UI 框架 | React DOM | Cocos UI | uGUI/UI Toolkit | UMG |
| 网络 | WebSocket | WebSocket | Socket/HTTP | Socket/HTTP |
| 性能预算 | 轻量（≤5MB） | 中量（≤30MB） | 完整（≤500MB） | 高保真（≥1GB） |

---

## 二、多端客户端适配实现方案

### 2.1 React/Web 适配器（L1 引流层）

```typescript
// src/adapters/ReactWebAdapter.ts
import { IClientAdapter } from './IClientAdapter';

export class ReactWebAdapter implements IClientAdapter {
    private canvas!: HTMLCanvasElement;
    private ws!: WebSocket;
    
    async initialize(config: EngineConfig): Promise<boolean> {
        // 初始化 WebGL 上下文
        this.canvas = document.createElement('canvas');
        const gl = this.canvas.getContext('webgl2');
        if (!gl) throw new Error('WebGL2 not supported');
        
        // 连接服务端（WebSocket 或 HTTP）
        this.ws = new WebSocket(config.serverEndpoint);
        return true;
    }
    
    async loadScene(sceneId: string): Promise<boolean> {
        // 通过 WASM 加载 C++ 中间件生成的中立场景数据
        const sceneData = await loadJSON(`/assets/generated/scenes/${sceneId}.json`);
        // 渲染到 Canvas
        this.renderScene(sceneData);
        return true;
    }
    
    // ... 其他接口实现
}
```

### 2.2 Cocos Creator 适配器（L2 轻量层）

```typescript
// assets/scripts/adapters/CocosAdapter.ts
import { _decorator, Component } from 'cc';
import { IClientAdapter } from './IClientAdapter';

export class CocosAdapter implements IClientAdapter {
    initialize(config: EngineConfig): Promise<boolean> {
        // Cocos 项目初始化
        return Promise.resolve(true);
    }
    
    loadScene(sceneName: string): Promise<boolean> {
        // 调用 Cocos director.loadScene
        director.loadScene(sceneName);
        return Promise.resolve(true);
    }
    
    // ... 其他接口实现
}
```

### 2.3 Unity 适配器（L3 完整层）

```csharp
// Assets/Scripts/Adapters/UnityAdapter.cs
using System;
using System.Collections.Generic;

public class UnityAdapter : IClientAdapter
{
    public void Initialize(Dictionary<string, object> config)
    {
        // Unity 场景初始化
    }
    
    public void LoadScene(string sceneName)
    {
        UnityEngine.SceneManagement.SceneManager.LoadScene(sceneName);
    }
    
    // ... 其他接口实现
}
```

### 2.4 UE5 适配器（L4 护城河层）

```cpp
// Source/Game/Adapters/UE5Adapter.h
#pragma once
#include "CoreMinimal.h"
#include "IClientAdapter.h"

class UE5Adapter : public IClientAdapter
{
public:
    virtual bool Initialize(const FEngineConfig& Config) override;
    virtual bool LoadScene(const FString& SceneName) override;
    virtual void ShowPanel(const FString& PanelId) override;
    
private:
    UWorld* CurrentWorld = nullptr;
};
```

---

## 三、多端一致性保障

### 3.1 客户端状态同步

```
┌─────────────────────────────────────────────────┐
│  客户端状态管理（引擎无关）                      │
│  · GameStateStore（Redux 风格单向数据流）        │
│  · 场景状态 / UI 状态 / 玩家状态分离             │
│  · 服务端权威 → 客户端投影（Server-Authoritative）│
├─────────────────────────────────────────────────┤
│  状态快照（Snapshot）                           │
│  · 每 100ms 发送一次状态快照                     │
│  · 客户端预测 + 服务端回滚（Rollback）           │
├─────────────────────────────────────────────────┤
│  跨端同步                                       │
│  · 多端登录共享玩家进度                          │
│  · 离线逻辑（轻量端可离线推进）                 │
└─────────────────────────────────────────────────┘
```

### 3.2 UI/UX 多端适配

| 平台 | UI 适配策略 | 资源规格 |
|------|-----------|---------|
| Web | 响应式布局，触摸优先 | 低分辨率图（512px） |
| Cocos | 自适应屏幕，动态分辨率 | 中分辨率图（1024px） |
| Unity | 多分辨率适配，SafeArea 处理 | 高分辨率图（2048px） |
| UE5 | 平台原生分辨率，全屏适配 | 4K 高保真图 |

### 3.3 资源加载与缓存

```typescript
// 多端统一资源缓存策略
interface AssetCacheConfig {
    memoryCacheSize: number;     // 内存缓存上限（MB）
    diskCacheSize: number;       // 磁盘缓存上限（MB）
    preloadList: string[];       // 预加载资源清单
    versionCheck: boolean;       // 版本校验
}

// 加载优先级：
// 1. 内存缓存（LRU）
// 2. 磁盘缓存（IndexedDB / LocalStorage / FileSystem）
// 3. 远程加载（CDN + 版本号）
```

---

## 四、客户端开发管线

### 4.1 多引擎共享代码策略

| 代码层 | 语言 | 共享策略 |
|--------|------|---------|
| 纯逻辑层（数值/规则/状态机） | C++ | 全部引擎共享（通过 C ABI 调用） |
| 数据模型层（JSON Schema） | JSON | 全部引擎共享 |
| 引擎适配层 | 各引擎语言 | 各引擎独立实现 |
| UI 表现层 | 各引擎语言 | 各引擎独立实现 |

### 4.2 开发流程

```
[设计规范] → [C++ 核心实现] → [C ABI 导出] → [各引擎适配器] → [多端回归验证]
     │             │              │                │                 │
     └───── 策划设计输入 ──── 程序实现 ──────── 客户端适配 ──── 测试验证 ──┘
```

### 4.3 分支管理

```
main
├── feature/client/react     # React/Web 客户端
├── feature/client/cocos     # Cocos Creator 客户端  
├── feature/client/unity     # Unity 客户端
├── feature/client/ue        # UE5 客户端
└── feature/client/shared    # 客户端共享代码（C++ / JSON）
```

---

## 五、接口契约（与 C++ 中间件对接）

### 5.1 C ABI 调用规范

```c
// 客户端通过 C ABI 调用中间件核心逻辑
// cabi_gameplay.h - 玩法核心
int cabi_gameplay_update(float dt);          // 客户端每帧调用
int cabi_gameplay_set_state(int state_id);   // 设置游戏状态
int cabi_gameplay_emit_event(int type, void* payload, int size);  // 发送事件

// cabi_procgen.h - 程序化生成
int cabi_procgen_generate(const char* type, const char* seed,
                          const char* params, char** result);
```

### 5.2 客户端事件流

```
[引擎事件] → [EngineBridgeFacade] → [ClientAdapter] → [GameStateStore] → [UI 更新]
     │              │                     │                │                 │
   Cocos/UE5    统一命令协议          引擎无关接口         状态管理          渲染更新
```

---

## 六、交付物与验收标准

| 交付物 | 路径 | 验收标准 |
|--------|------|---------|
| IClientAdapter 接口定义 | `client/adapters/IClientAdapter.ts` | 覆盖生命周期/渲染/输入/资源/UI/网络 |
| ReactWebAdapter 实现 | `client/adapters/react/` | 可加载中立 JSON 场景数据 |
| CocosAdapter 实现 | `client/adapters/cocos/` | 可通过 EngineBridge 控制场景加载 |
| UnityAdapter 实现 | `client/adapters/unity/` | 可调用 C ABI 中间件 |
| UE5Adapter 实现 | `client/adapters/ue5/` | 可原生集成 C++ 核心 |

**验收指标**：
- 多端加载同一中立场景数据，渲染结果一致
- 输入映射覆盖全部战斗动作（7 种操作 × 4 引擎）
- 资源缓存命中率 ≥ 90%（重复场景切换）

---

> 产出：程序线 client_dev 组协作产出，基于策划线 wp_gameplay 三层架构 + 架构师多引擎流水线设计。
