# 游戏引擎适配层（Engine Adapter Layer）

> 为 Cocos Creator 与 Unreal Engine 提供统一的引擎抽象，让游戏开发 Agent 体系
> 在 Windows + Cocos + 虚幻引擎的目标环境中正常工作。
> 对应模块：`config/engine_adapters.py`

## 一、设计动机

目标环境是 **Windows + Cocos Creator + Unreal Engine**。游戏资源（美术/音频/场景）
与引擎深度挂钩——Cocos 使用 `assets/` 目录 + TypeScript，Unreal 使用 `Content/` 
目录 + C++/Blueprint。为了不让 Agent 架构绑定到具体引擎，需要一层**引擎抽象**：

- **程序线**：产出与引擎挂钩的构建命令/脚本语言/项目结构
- **美术线**：产出与引擎挂钩的资源格式/导入路径/资源类型
- **测试线**：产出与引擎挂钩的启动命令/测试入口
- **项目管理**：产出与引擎挂钩的发版命令/平台设置

## 二、支持的引擎

| 引擎 | 标识 | 特性 |
|------|------|------|
| Cocos Creator | `cocos_creator` | 轻量 2D/3D、TypeScript、`assets/` 资源目录 |
| Unreal Engine | `unreal_engine` | 重度 3D、C++/Blueprint、`Content/` 资源目录 |
| Custom | `custom` | 预留扩展 |

## 三、核心接口

### 1. EngineAdapter 基类

所有引擎适配器实现以下统一接口：

```python
class EngineAdapter:
    # 基本信息
    engine_type: EngineType
    engine_name: str
    engine_version: str
    
    # 构建与平台
    def build_command(self, target_platform: str = "windows") -> str
    def run_command(self, project_path: str = "") -> str
    def supported_platforms(self) -> List[str]
    
    # 资源管理
    def resource_specs(self) -> List[ResourceSpec]
    def resource_import_path(self, resource_type: str) -> str
    def resource_export_path(self, resource_type: str) -> str
    
    # 项目结构
    def project_structure(self) -> Dict[str, str]
    
    # 脚本语言
    script_languages: List[str]
```

### 2. 使用方式

```python
from engine_adapters import get_engine, build_engine_aware_artifact

# 获取引擎适配器（自动从 CNB_ENGINE 环境变量探测，默认 cocos_creator）
cocos = get_engine("cocos_creator")
unreal = get_engine("unreal_engine")

# 构建命令
cocos.build_command("windows")  # "cocos build --platform windows"
unreal.build_command("windows")  # "RunUAT BuildCookRun -platform=windows"

# 资源规范
for rs in cocos.resource_specs():
    print(rs.resource_type, rs.extension, rs.import_dir)

# 引擎感知产出物
artifact = build_engine_aware_artifact(
    "cocos_creator", "art_asset", {"style": "卡通"}
)
```

### 3. 环境变量

```
CNB_ENGINE=cocos_creator   # 指定目标引擎
CNB_ENGINE=unreal_engine   # 指定 Unreal Engine
```

## 四、与部门 Agent 的集成

`department_agents.py` 中的部门 Agent（ProgramDeptAgent / ArtDeptAgent）已集成引擎感知：

- **ProgramDeptAgent**：client/engine 模块产出会标注引擎信息（名称/版本/构建命令/脚本语言）
- **ArtDeptAgent**：art_direction/audio 模块产出会标注引擎资源格式/导入路径/构建命令

## 五、资源类型对照

| 资源类型 | Cocos Creator | Unreal Engine |
|---------|---------------|---------------|
| sprite/mesh | `assets/textures/*.png` | `Content/Models/*.fbx` |
| audio | `assets/audio/*.mp3` | `Content/Audio/*.wav` |
| animation | `assets/animations/*.anim` | `Content/Animations/*.uasset` |
| prefab/blueprint | `assets/prefabs/*.prefab` | `Content/Blueprints/*.uasset` |
| scene | `assets/scenes/*.scene` | `Content/Maps/*.umap` |
| script | `assets/scripts/*.ts` | `Source/*.cpp` |

## 六、扩展新引擎

1. 继承 `EngineAdapter` 基类；
2. 实现全部接口（基本信息/构建/资源/项目结构/脚本语言）；
3. 在 `_ENGINE_REGISTRY` 中注册；
4. 增加测试信号灯断言。

## 七、测试

```bash
bash game-studio-agents/tests/test_engine_adapters.sh
# 16 项断言全绿
```
