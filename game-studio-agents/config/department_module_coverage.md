# 部门角色 Module 覆盖表

> 对齐架构师 [MEDIUM] 风险规避：明确「部门 Agent 角色吞噬」问题——66+ 角色差异靠 module 字段区分，非真实独立 Agent 行为，角色语义被稀释。本表作为「角色 → 部门 Agent → module → 行为语义」的单一映射索引，供架构师 / 经理 / 审查员快速核对。

## 一、六大部门 Agent → 角色 → module 映射

| 部门 | 部门 Agent 类 | base_role | 承载角色 | module 分支 | 行为语义 |
|---|---|---|---|---|---|
| 策划线 | `DesignDeptAgent` | lead_designer | lead_designer / system_designer / balance_designer / level_designer | `gameplay` | 核心玩法循环 / 系统架构设计 |
| 策划线 | `DesignDeptAgent` | lead_designer | （同上） | `numeric_model` | 数值模型 / 经济产出 / 成长曲线，经 market_input_bridge 转译市场预演 |
| 程序线 | `ProgramDeptAgent` | cto | cto / client_dev / server_dev / engine_dev / ai_programmer / tools_dev | `client` | 客户端渲染管线 / UI 绑定 |
| 程序线 | `ProgramDeptAgent` | cto | （同上） | `server` | 服务端 API / 数据存储 |
| 程序线 | `ProgramDeptAgent` | cto | （同上） | `engine` | 引擎核心 / 性能优化 |
| 程序线 | `ProgramDeptAgent` | cto | （同上） | `ai_logic` | NPC 行为树 / 自适应难度 |
| 美术线 | `ArtDeptAgent` | art_director | art_director / concept_artist / modeler / animator / vfx_artist / ui_ux / tech_artist / audio_designer | `art_direction` | 美术风格 / 资源规格 |
| 美术线 | `ArtDeptAgent` | art_director | （同上） | `ui_ux` | UI/UX 布局 / 交互设计 |
| 美术线 | `ArtDeptAgent` | art_director | （同上） | `audio` | 音频 / 配音规格 |
| 测试线 | `QaDeptAgent` | qa_engineer | qa_engineer / auto_qa | — | 功能 / 性能 / 自动化测试 |
| 项目管理 | `PmDeptAgent` | project_manager | project_manager / release_manager | — | 版本 / 里程碑 / 发版门禁 |
| 运营线 | `OpsDeptAgent` | data_analyst | data_analyst / reference_learner / game_operator | — | 数据洞察 / 埋点 / 市场生态位 |

## 二、独立实体化角色（非部门聚合）

| 角色 | 实现文件 | 类 | 承接方式 |
|---|---|---|---|
| producer | `game_producer_agent.py` | `GameProducerAgent` | 制作人 + 项目经理融合岗位 |
| reference_learner | `reference_learner_agent.py` | `ReferenceLearnerAgent` | 独立 Agent，参考学习 |
| progress_pusher | `progress_pusher.py` | `ProgressPusherAgent` | 独立 Agent，进度督导 |
| merged_confirmer | `merged_confirm_agent.py` | `MergedConfirmAgent` | 独立 Agent，合并确认 |

## 三、生态角色 handler 承接（WP-02）

| 圈层 | 角色 | handler 类 | 行为 |
|---|---|---|---|
| 协作支持圈 | communicator | `CommunicatorHandler` | 协作通讯 |
| 协作支持圈 | progress_pusher | `ProgressPusherHandler` | 进度盯守 |
| 协作支持圈 | asset_manager | `AssetManagerHandler` | 资产管理 |
| 协作支持圈 | mediator | `MediatorHandler` | 冲突调解 |
| 协作支持圈 | gig_pool | `GigPoolHandler` | 零工池 |
| 协作支持圈 | gatekeeper | `GatekeeperHandler` | 门卫 |
| 玩家圈 | mass_player | `MassPlayerHandler` | 大众玩家反馈 |
| 玩家圈 | core_player | `CorePlayerHandler` | 核心玩家反馈 |
| 玩家圈 | payer | `PayerHandler` | 付费玩家反馈 |
| 玩家圈 | playtester | `PlaytesterHandler` | 试玩反馈 |
| 玩家圈 | streamer | `StreamerHandler` | 直播反馈 |
| 玩家圈 | lurker | `LurkerHandler` | 潜水观察 |
| 外部市场圈 | publisher | `PublisherHandler` | 发行 / 市场预演 |
| 外部市场圈 | mini_game_platform | `MiniGamePlatformHandler` | 小游戏平台 |
| 外部市场圈 | advertiser | `AdvertiserHandler` | 广告投放 |
| 外部市场圈 | channel | `ChannelHandler` | 渠道分发 |
| 外部市场圈 | competitor | `CompetitorHandler` | 竞品分析 |
| 外部市场圈 | regulator | `RegulatorHandler` | 合规监管 |
| 美术圈 | eco_art_director | `EcoArtDirectorHandler` | 生态美术方向 |
| 美术圈 | eco_tech_artist | `EcoTechArtistHandler` | 生态技术美术 |
| 美术圈 | eco_audio_designer | `EcoAudioDesignerHandler` | 生态音频 |

## 四、_alt 变体实体化样板（WP-02b）

| 变体 | 对应基础角色 | handler 类 | 风格 | 行为 |
|---|---|---|---|---|
| producer_alt | producer | `ProducerAltHandler` | 进取型 | 制作人进取规划 |
| cto_alt | cto | `CtoAltHandler` | 前瞻型 | 技术前瞻规划 |
| server_dev_alt | server_dev | `ServerDevAltHandler` | 性能型 | 服务端性能优化 |

> 剩余 25 个 `_alt` 变体按此样板批量补充，按部门分组：策划线 6 / 程序线 5 / 美术线 8 / 测试线 2 / 项目管理 2 / 运营线 2。

## 五、注册/装配口径

- `DEPARTMENTS`（`game_producer_agent.py`）为部门角色**事实源**，列明各部门承载角色。
- 部门 Agent 通过 `DEPT_AGENT_CLASS` 映射实例化，仅六部门有对应 Agent 类。
- 生态角色经 `EcosystemRoleRegistry` 注册到 message_bus，由 `ecosystem_handlers.py` 的 handler 真实承接。
- `_alt` 变体来自 roles.yaml，经 handler 独立承接，与 department 流水线直接衔接。
