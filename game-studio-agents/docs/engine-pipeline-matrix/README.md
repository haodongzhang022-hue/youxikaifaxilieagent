# 引擎分层 × 专业方向 管线矩阵

> **核心命题**：替代「统一笼统式」输出，为不同引擎层级建立专业方向管线。

## 文档索引

| # | 文档 | 说明 |
|---|------|------|
| 0 | [00-overview.md](./00-overview.md) | 管线矩阵总览（背景/模型/四引擎管线定义/实施路径） |
| 1 | [01-pipeline-registry.md](./01-pipeline-registry.md) | 管线注册表 + 编排核心实现说明 |
| 2 | [02-director-booth.md](./02-director-booth.md) | 导演台能力设计（借鉴视频创作流程） |
| 3 | [03-pipeline-deep-dive.md](./03-pipeline-deep-dive.md) | 专业管线深入设计（角色动作/AI/特效/美术/导演台） |

## 核心模块

| 模块 | 文件 | 职责 |
|------|------|------|
| 管线注册表 | `config/pipeline_registry.py` | 40 条管线定义（四引擎×12专业方向） |
| 管线编排器 | `config/pipeline_orchestrator.py` | 管线调度/依赖管理/状态机/需求推荐 |

## 快速验证

```bash
# 管线注册表自测
python3 config/pipeline_registry.py

# 管线编排器自测（含派发/依赖/推荐）
python3 config/pipeline_orchestrator.py

# 测试信号灯
bash tests/test_pipeline_matrix.sh
```

## 管线矩阵速览

| 方向 | React | Cocos | Unity | UE |
|------|-------|-------|-------|-----|
| 角色动作 | ✅ | ✅ | ✅ | ✅ |
| AI触发器 | ✅ | ✅ | ✅ | ✅ |
| 场景特效 | ✅ | ✅ | ✅ | ✅ |
| 数值策划 | ✅ | ✅ | ✅ | ✅ |
| 难度优化 | ✅ | ✅ | ✅ | ✅ |
| 玩法优化 | ✅ | ✅ | ✅ | ✅ |
| 骨骼绑定 | ✅ | ✅ | ✅ | ✅ |
| 模型生成 | — | — | ✅ | ✅ |
| 模型上色 | — | — | ✅ | ✅ |
| 法线贴图 | — | — | ✅ | ✅ |
| 纹理材质 | — | — | ✅ | ✅ |
| 导演台 | ✅ | ✅ | ✅ | ✅ |

> **合计 40 条管线**。每条独立注册、独立追踪、独立优化，能力持续积累。
