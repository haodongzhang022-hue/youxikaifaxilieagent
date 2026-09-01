# 07. 思维模式路由强化（Reasoning-Mode Routing Boost）

> 借鉴 dsh-router-standard 的三波段思维模式路由（spec/react/weak + 过渡带回避），
> 为 `reference_learner` 自动路由到最匹配的思维模式，**不换模型**，
> 通过提示词/工具面条件把 GLM 能力往"正确方向"推高上限。

## 1. 核心原理：双吸引子行为策略

论文实测（GLM 5.3 Flash，21 个模式点 × n=2；Issue #126 统一模型）证明：模型沿 persona 轴的行为
**坍缩为三个稳定区**，中间不是连续过渡：

```
spec 带         过渡带(mixed)          react 带
[0, 0.15]       [0.2, 0.45]           [0.5, 1.0]
计划-集体        高熵不稳定              执行者
We 轨迹          随机混搭                 The/Let 轨迹
读优先            回避                   写优先
```

- **spec 吸引子**（计划优先、集体、读优先）→ 适合维护/理解/分析
- **react 吸引子**（执行者、写优先、免仪式）→ 适合构建/产出
- **weak 模式**（模型自分类）→ 适合复合/模糊任务

关键实测：同一模型 spec 条件下维护 99/96、react 条件下绿地构建 10/10；
**条件错配则 91/6**。=> 路由对了，"上帝/幽灵"二象性由条件决定。

## 2. reference_learner 的三波段路由映射

`reference_learner` 的任务横跨理解/迁移/落地，天然需要不同的思维模式：

| 阶段 | 子任务 | 路由模式 | Persona | 首轮核心工具面 |
|---|---|---|---|---|
| L1 理解 | 玩法识别 / 系统拆解 / 数值还原 | **spec** | `You are a helpful software engineer assistant.` + 计划/探索 | read, glob, grep |
| L1 理解 | 心智模型 / 视觉语言提取 | **spec** | spec + 深度探索引导 | read, glob, grep |
| L2 迁移 | 适配评估 / 取舍 | **spec** 或 **weak** | spec / classify-then-act | read, glob, grep |
| L2 迁移 | 融合设计 / 创新点 / 风险审查 | **weak** | 中性 + 分类 | read, write, edit |
| L3 落地 | Mod 构建 / 功能开发 / 视觉改造 | **react** | `hands-on doer，deliver working output fast` | read, write, edit |
| L3 落地 | 模组打包 / 沙盒验证 | **react** | doer（免测试仪式） | read, write, edit |
| 复合 | 端到端借鉴 | **weak** | 中性 + 深度自适应引导 | 全量 |

## 3. 任务分类器（外部路由）

基于论文的 keyword 分类思路，为 `reference_learner` 定制分类器：

```python
REACT_RE = re.compile(
    r'(构建|创建|写一个|生成|做一个|落地|实现|改造|打包|开发|部署|'
    r'build|create|develop|generate|implement|implement mod|deploy)', re.I)

SPEC_RE = re.compile(
    r'(理解|拆解|分析|评估|审查|还原|识别|为什么|怎么|研究|调研|'
    r'understand|analyze|assess|review|evaluate|why|how|research|探索)', re.I)

def classify_task(text):
    react = len(REACT_RE.findall(text))
    spec = len(SPEC_RE.findall(text))
    if react > spec: return 'react'
    if spec > react: return 'spec'
    return 'weak'   # 复合/模糊 → 模型自分类
```

规则：
- 过渡带（mixed）**永不自动选择**，只在显式调试时进入。
- **首请求锁定**：第一个请求就注入 persona 与首轮工具面，之后路径承诺，不中途切换。

## 4. 近场引导 + 深度自适应（来自 dsh-router-standard v19/v20）

在 weak / 复杂任务会话中，对每条真实用户消息追加一条固定引导（近场、缓存友好）：

```text
# 简单任务（快速收敛，P30：零浪费）
Router: 分类该任务（构建 or 修复）并采用匹配风格——构建：直接产出；修复：先查后改。

# 复杂任务（深度探索，P30：深度+12% 且更快收敛）
Router: 分类该任务。构建：直接产出；修复：先查后改。
深入思考架构、边界情况与集成点。不要把推理花在环境或工具上。
信息完备时再产出。每个推理块以一个决策或一个信息需求结尾。
```

复杂判定启发式（`isComplexTask`）：
```python
COMPLEX_RE = re.compile(r'(重构|架构|全面|详细|设计|系统|优化|分析|'
                        r'architecture|refactor|comprehensive|design|system|analyze)', re.I)
def is_complex_task(text):
    return len(text) > 120 or bool(COMPLEX_RE.search(text))
```

## 5. 会话内自优化工具（Agent 可见）

为 `reference_learner` 提供一组"看得见自己的路由"的工具，实现**自我优化闭环**：

| 工具 | 说明 |
|---|---|
| `boost_router_status` | 显示当前会话路由模式、persona、首轮核心工具面、override 状态 |
| `boost_router_mode <spec\|weak\|react\|auto>` | 显式切换路由模式（下一请求生效）；`auto` 回到任务分类 |
| `boost_mode_subagent <mode> <task>` | 在**不同思维模式**的隔离上下文里跑一个子任务，不污染当前轨迹（博弈/对照实验的基础） |

> 这些工具遵循论文结论：**会话中途切换 persona 会使前缀缓存失效**，
> 可靠的模式切换方式是"模式隔离子代理"（fresh context + 自己的 system prompt）。

## 6. 落地实现：`config/agent_boost/routing_preset.yaml`

见配套文件，包含：三波段 persona 模板、核心工具面矩阵、任务分类器、近场引导模板、
`boost_*` 自优化工具定义。该预设封装为可插拔 Mod（见 `08` 与 `04-mod-schema.md`）。

## 7. 上限提升预期

借鉴论文实测数据，对 `reference_learner` 的预期收益：

- **理解/评估类任务（spec 路由）**：从"泛泛而谈"提升到"计划-集体、读优先"的深度拆解，
  减少盲目产出、提升机制还原完整度（对应论文 99/96 vs 91 的维护任务收益）。
- **Mod 落地类任务（react 路由）**：从"过度设计"提升到"直接交付可运行 Mod"，
  减少不必要的仪式与脚手架（对应论文 10/10 vs 6 的绿地构建收益）。
- **复合借鉴（weak + 深度引导）**：复杂借鉴任务决策更充分、收敛更快。

> ⚠️ 路由映射基于统一模型 glm-5.3-flash 单档位验证（默认模型已由 DeepSeek V4 Flash 切换为 GLM 5.3 Flash）。
