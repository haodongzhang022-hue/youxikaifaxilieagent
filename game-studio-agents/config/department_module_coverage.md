# 部门角色 module 覆盖表（Department Role → Module Coverage）

> WP-04 落地产出 —— 对齐架构师 CP1 分层实体化方案。
> 说明 `roles.yaml` 声明的六大部门角色，分别由哪个部门 Agent 模块聚合承接执行，
> 以及每个模块对应的行为语义。**事实源**：`roles.yaml`（角色声明）、
> `department_agents.py`（部门 Agent 执行）、`role_inventory.yaml`（角色-实现映射索引）。

## 一、覆盖总览

六大部门角色统一由 **6 个通用部门 Agent**（`department_agents.py`）按 `module` 字段
聚合承接执行。`role_inventory.yaml` 中标注 `implemented` 的部门角色均有真实执行体，
其余 `declared_only` 角色由对应部门 Agent 兜底承接。

| 部门 | 部门 Agent（base_role） | 承接角色 | module | 行为语义 |
|---|---|---|---|---|
| 策划线 | `DesignDeptAgent`（lead_designer） | lead_designer / system_designer / balance_designer / level_designer / narrative_designer / combat_designer | `gameplay` | 核心玩法循环、系统架构设计 |
| 策划线 | `DesignDeptAgent`（lead_designer） | balance_designer 等 | `numeric_model` | 经济/数值模型、成长曲线、市场预演输入 |
| 程序线 | `ProgramDeptAgent`（cto） | cto / client_dev / server_dev / engine_dev / ai_programmer / tools_dev | `client` | 客户端渲染管线、UI 绑定 |
| 程序线 | `ProgramDeptAgent`（cto） | server_dev 等 | `server` | 服务端 API、数据存储 |
| 程序线 | `ProgramDeptAgent`（cto） | engine_dev 等 | `engine` | 引擎核心、性能优化 |
| 程序线 | `ProgramDeptAgent`（cto） | ai_programmer 等 | `ai_logic` | NPC 行为树、自适应难度 |
| 美术线 | `ArtDeptAgent`（art_director） | art_director / concept_artist / modeler / animator / vfx_artist / ui_ux / tech_artist / audio_designer | `art_direction` | 美术风格/品质基准（接入市场预演） |
| 美术线 | `ArtDeptAgent`（art_director） | ui_ux / tech_artist 等 | `ui_ux` | 界面流程、交互设计（可派发 owner） |
| 美术线 | `ArtDeptAgent`（art_director） | audio_designer 等 | `audio` | 音效/背景音乐清单 |
| 测试线 | `QaDeptAgent`（qa_engineer） | qa_engineer / auto_qa | `testing` | 用例执行、缺陷清单、覆盖率/性能评估 |
| 项目管理 | `PmDeptAgent`（project_manager） | project_manager / release_manager | `release` | 里程碑、发版检查单、发版门禁验收 |
| 运营线 | `OpsDeptAgent`（data_analyst） | data_analyst / reference_learner / game_operator | `data_ops` | 数据埋点、运营洞察、市场预演诊断 |

## 二、独立实体化角色（非部门 Agent 兜底）

以下角色有独立实现类，不依赖部门 Agent 聚合：

| 角色 | 实现 | 说明 |
|---|---|---|
| `producer` | `game_producer_agent.GameProducerAgent` | 经理编排，融合制作人+项目经理 |
| `reference_learner` | `reference_learner_agent.ReferenceLearnerAgent` | 参考学习 Agent |
| `progress_pusher` | `progress_pusher.ProgressPusherAgent` | 进度督导 |
| `merged_confirmer` | `merged_confirm_agent.MergedConfirmAgent` | 合并确认 |
| 生态角色（21） | `ecosystem_handlers.py` | WP-02 真实承接 handler |
| `_alt` 样板（3） | `ecosystem_handlers.py` | producer_alt / cto_alt / server_dev_alt |

## 三、角色-模块-行为语义映射明细

### 3.1 策划线（DesignDeptAgent）

| role_id | 状态 | 承接 module | 行为语义 |
|---|---|---|---|
| `producer` | implemented（独立） | —（经理编排） | 愿景定义、里程碑、风险管理 |
| `lead_designer` | implemented | gameplay / numeric_model | 核心玩法、系统架构设计 |
| `system_designer` | declared_only | gameplay | 系统架构、功能设计 |
| `balance_designer` | declared_only | numeric_model | 经济模型、成长曲线、平衡数值 |
| `level_designer` | declared_only | gameplay | 关卡设计 |
| `narrative_designer` | declared_only | gameplay | 叙事/剧情设计 |
| `combat_designer` | declared_only | gameplay | 战斗系统设计 |

### 3.2 程序线（ProgramDeptAgent）

| role_id | 状态 | 承接 module | 行为语义 |
|---|---|---|---|
| `cto` | implemented | client/server/engine/ai_logic | 技术总监，统一技术实现 |
| `client_dev` | declared_only | client | 客户端渲染、UI 绑定 |
| `server_dev` | declared_only | server | 服务端 API、数据存储 |
| `engine_dev` | declared_only | engine | 引擎核心、性能优化 |
| `ai_programmer` | declared_only | ai_logic | NPC 行为树、自适应难度 |
| `tools_dev` | declared_only | client | 工具链开发 |

### 3.3 美术线（ArtDeptAgent）

| role_id | 状态 | 承接 module | 行为语义 |
|---|---|---|---|
| `art_director` | implemented | art_direction/ui_ux/audio | 美术总监，统一风格与品质基准 |
| `concept_artist` | declared_only | art_direction | 概念设定 |
| `modeler` | declared_only | art_direction | 模型制作 |
| `animator` | declared_only | art_direction | 动画 |
| `vfx_artist` | declared_only | art_direction | 特效 |
| `ui_ux` | declared_only | ui_ux | 界面/交互设计 |
| `tech_artist` | declared_only | ui_ux | 技术美术、UI 资产（可派发 owner） |
| `audio_designer` | declared_only | audio | 音效/配乐 |

### 3.4 测试线（QaDeptAgent）

| role_id | 状态 | 承接 module | 行为语义 |
|---|---|---|---|
| `qa_engineer` | implemented | testing | 用例执行、缺陷、覆盖率 |
| `auto_qa` | declared_only | testing | 自动化测试 |

### 3.5 项目管理（PmDeptAgent）

| role_id | 状态 | 承接 module | 行为语义 |
|---|---|---|---|
| `project_manager` | implemented | release | 里程碑、发版检查单、门禁 |
| `release_manager` | declared_only | release | 版本发布 |

### 3.6 运营线（OpsDeptAgent）

| role_id | 状态 | 承接 module | 行为语义 |
|---|---|---|---|
| `data_analyst` | implemented | data_ops | 埋点、洞察、市场诊断 |
| `reference_learner` | implemented | data_ops | 参考学习（独立实现） |
| `game_operator` | declared_only | data_ops | 游戏运营 |

## 四、WP-03 生态任务承接

`run_end_to_end_instantiated.dispatch_ecosystem`（WP-03）为生态角色挂接真实 handler，
让 `eco_*` 任务经 `ecosystem_handlers.py` 真实 DONE 并纳入 `_all_done` 判定。
生态角色 module 承接由 handler 的 `_execute` 提供行为语义（详见 `ecosystem_handlers.py`）。

## 五、查询方式

```bash
# 查看角色-实现映射索引（含部门 module 覆盖）
cd config
python3 role_inventory.py --list
python3 role_inventory.py --gap   # 差距索引（强制 registry.summary() 对照）
```
