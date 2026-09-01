# 管线注册表与编排核心

> 版本: v1.0  
> 对齐 Issue #126：管线注册表 + 编排核心实现说明

---

## 一、管线注册表（Pipeline Registry）

### 1.1 数据模型

每个管线通过 `PipelineDef` 定义，包含：

| 字段 | 说明 | 示例 |
|------|------|------|
| `pipeline_id` | 唯一标识 | `pipeline.character_animation.unity` |
| `name` | 中文名 | `Unity角色动作管线` |
| `engine` | 引擎层级 | `react` / `cocos` / `unity` / `unreal` |
| `domain` | 专业方向 | `character_animation` / `ai_trigger` / ... |
| `status` | 状态 | `active` / `deprecated` / `draft` |
| `inputs` | 输入要求 | `["绑定模型", "动作需求", "风格规范"]` |
| `workflow` | 工作流步骤 | `["K动画", "Animation Clip", "状态机", "集成验证"]` |
| `outputs` | 产出物 | `[".anim", ".controller"]` |
| `tools` | 工具链 | `["Unity Animator", "Timeline"]` |
| `quality_gates` | 质量门禁 | `["动作流畅度", "性能基准"]` |
| `dependencies` | 前置依赖 | `["pipeline.skeleton_binding.unity"]` |

### 1.2 管线数量

| 引擎 | 管线数 | 专业方向 |
|------|--------|---------|
| L0 React | 8 | 角色动作/AI/特效/数值/难度/玩法/骨骼/导演台 |
| L1 Cocos | 8 | 角色动作/AI/特效/数值/难度/玩法/骨骼/导演台 |
| L2 Unity | 12 | 角色动作/AI/特效/数值/难度/玩法/骨骼/模型生成/模型上色/法线/材质/导演台 |
| L3 Unreal | 12 | 同 Unity |
| **合计** | **40** | 12 个专业方向 |

### 1.3 专业方向维度

| 方向 | 引擎覆盖 | 说明 |
|------|---------|------|
| `character_animation` | 4 | 角色动作/动画 |
| `ai_trigger` | 4 | AI触发器/行为逻辑 |
| `scene_vfx` | 4 | 场景特效 |
| `numeric_design` | 4 | 数值策划 |
| `difficulty_optimization` | 4 | 难度优化 |
| `gameplay_optimization` | 4 | 玩法优化 |
| `skeleton_binding` | 4 | 骨骼绑定 |
| `model_generation` | 2 | 模型生成（Tripo等） |
| `model_painting` | 2 | 模型上色 |
| `normal_mapping` | 2 | 法线贴图 |
| `texture_material` | 2 | 纹理材质 |
| `director_booth` | 4 | 导演台（过场/叙事） |

---

## 二、管线编排器（Pipeline Orchestrator）

### 2.1 核心能力

| 能力 | 方法 | 说明 |
|------|------|------|
| 管线解析 | `resolve_pipeline(engine, domain)` | 按引擎×方向精确匹配管线 |
| 需求推荐 | `suggest_pipeline(description, engine)` | 根据自然语言描述推荐管线 |
| 管线派发 | `dispatch(engine, domain, context)` | 创建执行记录，检查依赖 |
| 状态控制 | `start/complete/fail/unblock` | 管线状态机控制 |
| 依赖管理 | 自动检测前置依赖 | 依赖未就绪 → `BLOCKED` |
| 执行追踪 | `list_executions(engine, domain)` | 按引擎/方向过滤执行记录 |

### 2.2 管线状态机

```
PENDING → READY → IN_PROGRESS → COMPLETED
           ↑         │            │
           │         ▼            ▼
           └── BLOCKED          FAILED
                                CANCELLED
```

### 2.3 需求推荐

通过关键词匹配（专业方向关键词表），结合引擎提示，推荐最匹配的管线。

```python
# 示例
suggestions = orchestrator.suggest_pipeline("做一个 Unity 的角色动作和骨骼绑定", "unity")
# 返回: [Unity角色动作管线 (score=3), Unity骨骼绑定管线 (score=2)]
```

---

## 三、与现有系统集成

### 3.1 接入点

| 现有模块 | 接入方式 |
|---------|---------|
| `game_producer_agent.py` | 拆包时根据 `engine` + `domain` 标注 `pipeline_id` |
| `department_agents.py` | 部门 Agent 根据 `pipeline_id` 调派专业管线 |
| `pipeline_registry.py` | 作为管线定义的数据源 |
| `pipeline_orchestrator.py` | 作为管线调度与执行核心 |
| `middleware/` | 管线核心逻辑走 C ABI 中间件 |

### 3.2 调用示例

```python
from pipeline_registry import PipelineRegistry
from pipeline_orchestrator import PipelineOrchestrator

# 1. 查看管线矩阵
reg = PipelineRegistry()
print(reg.report())

# 2. 按引擎查询
unity_pipes = reg.by_engine("unity")

# 3. 派发管线
orch = PipelineOrchestrator()
ex = orch.dispatch("unity", "character_animation", {"style": "卡通"})
orch.start(ex.execution_id)
# ... 执行 ...
orch.complete(ex.execution_id, {"clips": 12})
```

---

## 四、测试

```bash
# 管线注册表自测
python3 config/pipeline_registry.py

# 管线编排器自测
python3 config/pipeline_orchestrator.py
```

**断言覆盖**：
- 管线总数 ≥ 40
- 四引擎各有对应管线
- 导演台覆盖 4 引擎
- 骨骼绑定覆盖 ≥ 4 引擎
- 模型生成/上色/法线/材质覆盖 2 引擎
- 依赖检测（骨骼绑定 → 角色动作）
- 需求推荐匹配

---

> 状态: `done`  
> 依赖: 无（纯数据 + 逻辑模块）  
> 下一步: 接入 game_producer_agent / department_agents
