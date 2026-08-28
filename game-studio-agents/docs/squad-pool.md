# 可调配小组池 (SquadPool)

## 设计动机

当**多个部门**（策划线/程序线/美术线/测试线等）有开发/执行需求时，如果每个部门都各自建一个内部小组，会导致：

- **资源浪费**：部门间小组重复建设，同一领域多份编制；
- **调度僵化**：小组被绑定在部门内，无法跨部门共享；
- **不可复用**：任务完成后小组闲置，无法被其他部门再次调用。

**可调配小组池（SquadPool）** 将小组**独立于部门**存在，作为全局共享资源：

```
┌─────────────────────────────────────────┐
│             SquadPool（小组池）            │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐    │
│  │客户端A组 │ │AI逻辑C组│ │引擎D组  │ ... │
│  └─────────┘ └─────────┘ └─────────┘    │
└─────────────────────────────────────────┘
       ▲          ▲          ▲
       │调配       │调配       │调配
   ┌───┴───┐  ┌───┴───┐  ┌───┴───┐
   │程序线   │  │美术线   │  │测试线   │
   └────────┘  └────────┘  └────────┘
```

## 核心能力

| 能力 | 说明 |
|---|---|
| **独立于部门** | 小组不隶属于任何部门编制，是全局共享资源 |
| **按需调配** | 任何部门通过 `dispatch_to_squad()` 按需调用小组 |
| **重复调用** | 小组完成任务后释放回池，可被不同部门反复调度 |
| **多组并行** | 多个小组并存，按领域/技能标签各司其职 |
| **领域寻址** | 按 `domain` / `skill` 自动匹配合适小组 |

## 核心机制

### Squad（小组）

```python
@dataclass
class Squad:
    squad_id: str        # 唯一标识
    name: str            # 小组名称
    domain: str          # 领域（client_dev / ai_dev / engine_dev ...）
    skills: List[str]    # 技能标签（做不一样的事的寻址依据）
    leader: str          # 小组长
    members: List[str]   # 小组成员
    status: str          # IDLE（待命）/ BUSY（执行中）/ READY / BLOCKED
    assign_count: int    # 累计被调配次数（重复调用留痕）
```

### SquadPool（小组池）

```python
class SquadPool:
    def register_squad(squad)          # 注册小组
    def create_squad(name, domain, ...) # 创建并注册
    def acquire(domain/skill, department, task_id)  # 调配
    def release(squad_id)              # 释放回池（重复调用）
    def find(domain/skill/status)      # 查询
    def list_squads()                  # 列出全部
    def summary()                      # 总览
```

### DispatchCapability 集成

```python
cap = DispatchCapability("producer", bus=bus, squad_pool=pool)

# 按领域调配（自动找空闲小组）
r = cap.dispatch_to_squad_by_domain("client_dev", wp, "程序线")

# 按 squad_id 直调
r = cap.dispatch_to_squad("squad_xxx", wp, "程序线")

# 释放小组回池
cap.release_squad("squad_xxx")

# 释放某部门全部占用
cap.release_squads_by_department("程序线")

# 小组池总览
cap.squad_summary()
```

## 与部门内小组的区别

| 维度 | 部门内小组 (game_dev_team) | 可调配小组 (squad_pool) |
|---|---|---|
| 归属 | 绑定在具体部门内 | 独立于部门，全局共享 |
| 生命周期 | 随部门存在 | 任务完成后释放回池 |
| 调用范围 | 仅本部门可用 | 任何部门都可调配 |
| 重复使用 | 任务后销毁 | 释放后可再次被调配 |
| 领域划分 | 部门固定领域 | 多组并存，按领域/技能区分 |

## 预置小组

`create_default_squad_pool()` 提供 5 个常见可调配小组：

| 小组 | domain | 技能 |
|---|---|---|
| 客户端开发A组 | client_dev | client, ui, cocos, unity |
| 服务端开发B组 | server_dev | server, backend, api, database |
| AI 逻辑C组 | ai_dev | ai, behavior_tree, npc, adaptive |
| 引擎适配D组 | engine_dev | engine, cocos, unreal, render |
| 工具链E组 | tools_dev | tools, pipeline, build, scaffold |
