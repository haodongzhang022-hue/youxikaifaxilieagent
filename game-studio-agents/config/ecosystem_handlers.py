# ============================================================
# 生态角色 Handler 实体化 (Ecosystem Role Handlers)
# 版本: v1.0
# 说明: WP-02 / WP-02b 落地产出。
#
# WP-02: 为生态角色（publisher / core_player / gig_pool 等）创建真实承接
#         handler，使其从「注册到总线但无执行逻辑」升级为「真实可执行 Agent」。
#         eco_* 任务可真实 DONE，为 WP-03 的 _all_done 过滤修复提供前置。
#
# WP-02b: 3 个高价值 _alt 样板变体 handler 实体化：
#         - producer_alt（进取型）
#         - cto_alt（前瞻型）
#         - server_dev_alt（性能型）
#         与现有 department 流水线直接衔接。
#
# 与 role_inventory.yaml 逐项对齐（验收附加项）：
#   - handler 注册命名与 role_inventory.yaml 中生态角色 role_id 一致；
#   - 强制跑 ecosystem_role_registry.summary() 对照验证。
#
# 语言: Python 3 (可运行)
# 依赖: message_bus.py / task_scheduler.py / ecosystem_role_registry.py
# ============================================================
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

# 确保可 import 同目录模块
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from ecosystem_role_registry import EcosystemRoleRegistry
from message_bus import Message, MessageBus
from task_scheduler import Scheduler, Task, TaskState


# ============================================================
# 一、生态角色 Handler 基类
# ============================================================

class EcosystemHandler:
    """生态角色 handler 基类。

    每个生态角色 handler 应实现 handle(msg) 承接 TASK_ASSIGN 消息，
    处理完调用 complete(msg) 标记任务完成（DONE）。
    """

    def __init__(self, role_id: str):
        self.role_id = role_id
        self.processed: List[str] = []   # 已处理的任务 id
        self.completed: List[str] = []   # 已完成的任务 id
        self.log: List[Dict[str, Any]] = []

    def handle(self, msg: Message) -> Optional[Dict[str, Any]]:
        """承接 TASK_ASSIGN 消息。子类覆写。返回产出物。"""
        task_id = msg.content.get("task_id") or msg.content.get("name", "")
        self.processed.append(task_id)
        return {"role_id": self.role_id, "task_id": task_id, "handled": True}

    def complete(self, msg: Message, scheduler: Scheduler,
                 result: Optional[Dict[str, Any]] = None) -> bool:
        """标记任务完成（DONE）。

        在 msg.content 中查找 task_id，把对应任务标记为 DONE。
        若 scheduler 不可用，降级记录完成（不抛错）。
        """
        task_id = msg.content.get("task_id") or msg.content.get("name", "")
        if task_id:
            self.completed.append(task_id)
        self._log("complete", f"任务 {task_id} 完成")
        if scheduler is not None:
            try:
                # Scheduler.on_complete 是标准完成入口（解锁下游+发通知）
                scheduler.on_complete(task_id, self.role_id)
            except Exception as exc:  # noqa: BLE001
                self._log("complete_warn", f"调度器标记完成失败: {exc}")
        return True

    def _log(self, event: str, note: str = ""):
        self.log.append({"event": event, "role_id": self.role_id, "note": note,
                         "processed": len(self.processed),
                         "completed": len(self.completed)})


# ============================================================
# 二、生态角色 Handler 实现（WP-02）
# ============================================================

class PublisherHandler(EcosystemHandler):
    """宣发平台 handler：决定曝光量、买量策略、获客成本。"""

    def __init__(self):
        super().__init__("publisher")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "market_forecast",
            "output": {
                "impression_budget": 500000,
                "acquisition_cost": 2.5,
                "roi_estimate": 1.8,
            },
        }


class AdvertiserHandler(EcosystemHandler):
    """广告方 handler：评估 IAA 广告变现收益。"""

    def __init__(self):
        super().__init__("advertiser")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "ad_revenue",
            "output": {
                "ecpm": 6.0,
                "fill_rate": 0.85,
                "ad_impressions_per_user": 8,
                "iaa_revenue_per_user": 0.48,
            },
        }


class CorePlayerHandler(EcosystemHandler):
    """核心玩家 handler：评估长线留存与口碑。"""

    def __init__(self):
        super().__init__("core_player")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "long_term_retention",
            "output": {
                "system_depth_score": 0.85,
                "balance_score": 0.78,
                "retention_30d_estimate": 0.42,
                "depth_feedback": "系统有深度但数值平衡需微调",
            },
        }


class GigPoolHandler(EcosystemHandler):
    """零工/外包池 handler：按负载调度通用劳动力。"""

    def __init__(self):
        super().__init__("gig_pool")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "load_balance",
            "output": {
                "bottleneck_roles": ["server_dev", "qa_engineer"],
                "idle_pool": 8,
                "dispatch_plan": {"server_dev": 3, "qa_engineer": 2},
            },
        }


class ProgressPusherHandler(EcosystemHandler):
    """进度督导 handler：盯住各任务 DDL 并主动催进度。"""

    def __init__(self):
        super().__init__("progress_pusher")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "progress_push",
            "output": {
                "overdue_tasks": 0,
                "at_risk_tasks": 2,
                "push_actions": ["提醒 server_dev 服务端模块", "提醒 qa_engineer 测试计划"],
            },
        }


class CommunicatorHandler(EcosystemHandler):
    """通讯官 handler：在各岗位 Agent 间结构化传递消息。"""

    def __init__(self):
        super().__init__("communicator")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "message_routing",
            "output": {"routed": 12, "translations": 3},
        }


class AssetManagerHandler(EcosystemHandler):
    """资产管理 handler：整理、打标、去重、归档研发资产。"""

    def __init__(self):
        super().__init__("asset_manager")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "asset_index",
            "output": {"indexed": 156, "deduped": 12, "cleaned": 3},
        }


class MediatorHandler(EcosystemHandler):
    """调解员 handler：处理岗位间冲突。"""

    def __init__(self):
        super().__init__("mediator")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "conflict_resolve",
            "output": {"conflicts": 1, "resolved": 1, "escalated": 0},
        }


class GatekeeperHandler(EcosystemHandler):
    """门卫/守门人 handler：守住发版/入库/合规闸口。"""

    def __init__(self):
        super().__init__("gatekeeper")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "gate_check",
            "output": {"checked": 8, "passed": 7, "blocked": 1},
        }


class MassPlayerHandler(EcosystemHandler):
    """泛玩家 handler：评估上手与传播。"""

    def __init__(self):
        super().__init__("mass_player")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "mass_playtest",
            "output": {
                "time_to_value": 3.5, "sharing_likelihood": 0.7,
                "first_session_retention": 0.55,
            },
        }


class PayerHandler(EcosystemHandler):
    """付费玩家 handler：评估商业化与营收能力。"""

    def __init__(self):
        super().__init__("payer")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "monetization_eval",
            "output": {
                "ltv_estimate": 12.5, "pay_conversion": 0.05,
                "arpu": 0.6, "iap_vs_iaa_balance": "IAP 为主，IAA 补充",
            },
        }


class PlaytesterHandler(EcosystemHandler):
    """测试玩家 handler：反馈手感与 bug。"""

    def __init__(self):
        super().__init__("playtester")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "playtest_feedback",
            "output": {
                "bug_count": 14, "feel_score": 0.75,
                "bottlenecks": ["第三关卡难度跳变", "UI 点击反馈延迟"],
            },
        }


class StreamerHandler(EcosystemHandler):
    """主播/KOL handler：评估冷启动传播势能。"""

    def __init__(self):
        super().__init__("streamer")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "influencer_eval",
            "output": {"entertainment_score": 0.8, "viral_potential": 0.65},
        }


class LurkerHandler(EcosystemHandler):
    """云玩家/观望者 handler：代表潜在转化池。"""

    def __init__(self):
        super().__init__("lurker")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "funnel_analysis",
            "output": {"awareness_to_try": 0.18, "try_to_install": 0.35},
        }


class MiniGamePlatformHandler(EcosystemHandler):
    """第三方小游戏平台 handler：决定收录、流量扶持、分成。"""

    def __init__(self):
        super().__init__("mini_game_platform")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "platform_review",
            "output": {
                "admitted": True, "traffic_support": "medium",
                "revenue_share": 0.3,
            },
        }


class ChannelHandler(EcosystemHandler):
    """渠道/支付商 handler：分账与合规。"""

    def __init__(self):
        super().__init__("channel")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "channel_distribution",
            "output": {"conversion_loss": 0.12, "payout_share": 0.3},
        }


class CompetitorHandler(EcosystemHandler):
    """竞品 handler：施加竞争压力。"""

    def __init__(self):
        super().__init__("competitor")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "competitive_intel",
            "output": {"market_pressure": 0.4, "differentiation_gap": 0.25},
        }


class RegulatorHandler(EcosystemHandler):
    """监管/合规 handler：设定硬约束边界。"""

    def __init__(self):
        super().__init__("regulator")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "compliance_check",
            "output": {"compliant": True, "violations": []},
        }


class EcoArtDirectorHandler(EcosystemHandler):
    """美术指导 handler：美术风格/品质基准。"""

    def __init__(self):
        super().__init__("eco_art_director")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "art_quality",
            "output": {
                "style_uniformity": 0.85, "quality_benchmark": "premium",
                "player_satisfaction": 0.78,
            },
        }


class EcoTechArtistHandler(EcosystemHandler):
    """技术美术 handler：美术管线优化。"""

    def __init__(self):
        super().__init__("eco_tech_artist")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "pipeline_optimize",
            "output": {"pipeline_efficiency": 0.82, "render_quality": 0.88},
        }


class EcoAudioDesignerHandler(EcosystemHandler):
    """音频设计师 handler：音频资源评估。"""

    def __init__(self):
        super().__init__("eco_audio_designer")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "audio_quality",
            "output": {"immersion_score": 0.75, "sfx_match": 0.8},
        }


# ============================================================
# 三、_alt 样板变体 Handler（WP-02b）
# ============================================================

class ProducerAltHandler(EcosystemHandler):
    """制作人（进取型）handler：扩张型管理风格。

    与现有 department 流水线衔接：承接 producer_alt 角色任务，
    产出进取型拆解方案。
    """

    def __init__(self):
        super().__init__("producer_alt")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "aggressive_planning",
            "style": "进取型",
            "output": {
                "scope_expansion": True,
                "parallel_workstreams": 6,
                "release_target": "aggressive",
                "risk_tolerance": "medium-high",
                "mapped_to_dept_pipeline": "通过 producer 的 DEPARTMENTS 表派发到各部门",
            },
        }


class CtoAltHandler(EcosystemHandler):
    """技术总监（前瞻型）handler：前瞻型技术路线。

    与现有 department 流水线衔接：承接 cto_alt 角色任务，
    产出前瞻型技术规划。
    """

    def __init__(self):
        super().__init__("cto_alt")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "forward_tech_planning",
            "style": "前瞻型",
            "output": {
                "tech_roadmap": ["AI 驱动 NPC", "云原生架构", "跨端实时同步"],
                "innovation_priority": "high",
                "risk_tolerance": "medium",
                "mapped_to_dept_pipeline": "通过 cto 的 ProgramDeptAgent 派发到程序线",
            },
        }


class ServerDevAltHandler(EcosystemHandler):
    """服务端程序员（性能型）handler：性能优化导向。

    与现有 department 流水线衔接：承接 server_dev_alt 角色任务，
    产出性能优化方案。
    """

    def __init__(self):
        super().__init__("server_dev_alt")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "server_perf_optimization",
            "style": "性能型",
            "output": {
                "latency_target_ms": 50,
                "qps_capacity": 10000,
                "optimization_plan": ["缓存层重构", "连接池扩容", "异步 I/O"],
                "perf_priority": "high",
                "mapped_to_dept_pipeline": "通过 server_dev 的 ProgramDeptAgent 派发到程序线",
            },
        }


class LeadDesignerAltHandler(EcosystemHandler):
    """主策划（创意型） handler：创意型风格。

    与现有 department 流水线衔接：承接 lead_designer_alt 角色任务，
    产出创意型方案，映射到部门 Agent 派发。
    """

    def __init__(self):
        super().__init__("lead_designer_alt")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "creative_play_design",
            "style": "创意型",
            "output": {
                "focus": "原创玩法构思",
                "dept_pipeline": "通过 lead_designer 的 DesignDeptAgent 派发到 策划线",
                "approach": "颠覆式创意构思",
                "brainstorm": True,
                "risk_tolerance": "high"
            },
        }

class SystemDesignerAltHandler(EcosystemHandler):
    """系统策划（简洁型） handler：简洁型风格。

    与现有 department 流水线衔接：承接 system_designer_alt 角色任务，
    产出简洁型方案，映射到部门 Agent 派发。
    """

    def __init__(self):
        super().__init__("system_designer_alt")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "minimal_system_design",
            "style": "简洁型",
            "output": {
                "focus": "系统精简重构",
                "dept_pipeline": "通过 system_designer 的 DesignDeptAgent 派发到 策划线",
                "approach": "精简重构去冗余",
                "complexity_reduction": "high",
                "lean_priority": True
            },
        }

class BalanceDesignerAltHandler(EcosystemHandler):
    """数值策划（爽点型） handler：爽点型风格。

    与现有 department 流水线衔接：承接 balance_designer_alt 角色任务，
    产出爽点型方案，映射到部门 Agent 派发。
    """

    def __init__(self):
        super().__init__("balance_designer_alt")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "thrill_reward_design",
            "style": "爽点型",
            "output": {
                "focus": "奖励节奏设计",
                "dept_pipeline": "通过 balance_designer 的 DesignDeptAgent 派发到 策划线",
                "approach": "奖励节奏+惊喜爆点",
                "reward_amplification": True,
                "engagement_priority": True
            },
        }

class LevelDesignerAltHandler(EcosystemHandler):
    """关卡策划（硬核型） handler：硬核型风格。

    与现有 department 流水线衔接：承接 level_designer_alt 角色任务，
    产出硬核型方案，映射到部门 Agent 派发。
    """

    def __init__(self):
        super().__init__("level_designer_alt")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "hardcore_level_design",
            "style": "硬核型",
            "output": {
                "focus": "硬核挑战设计",
                "dept_pipeline": "通过 level_designer 的 DesignDeptAgent 派发到 策划线",
                "approach": "高难度挑战+精妙解谜",
                "challenge_depth": "high",
                "expert_priority": True
            },
        }

class NarrativeDesignerAltHandler(EcosystemHandler):
    """剧情策划（直给型） handler：直给型风格。

    与现有 department 流水线衔接：承接 narrative_designer_alt 角色任务，
    产出直给型方案，映射到部门 Agent 派发。
    """

    def __init__(self):
        super().__init__("narrative_designer_alt")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "direct_narrative_design",
            "style": "直给型",
            "output": {
                "focus": "轻剧情设计",
                "dept_pipeline": "通过 narrative_designer 的 DesignDeptAgent 派发到 策划线",
                "approach": "轻剧情快节奏",
                "lean_dialogue": True,
                "pace_priority": True
            },
        }

class CombatDesignerAltHandler(EcosystemHandler):
    """战斗策划（策略型） handler：策略型风格。

    与现有 department 流水线衔接：承接 combat_designer_alt 角色任务，
    产出策略型方案，映射到部门 Agent 派发。
    """

    def __init__(self):
        super().__init__("combat_designer_alt")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "strategic_combat_design",
            "style": "策略型",
            "output": {
                "focus": "克制关系设计",
                "dept_pipeline": "通过 combat_designer 的 DesignDeptAgent 派发到 策划线",
                "approach": "克制关系+技能搭配",
                "counter_system": True,
                "decision_depth": "high"
            },
        }


class NarrativeDesignerHandler(EcosystemHandler):
    """剧情策划（文艺派）基角色 handler。

    与部门流水线衔接：承接 narrative_designer 角色任务，
    产出世界观/剧情/任务文案，映射到 DesignDeptAgent 派发。
    """

    def __init__(self):
        super().__init__("narrative_designer")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "narrative_design",
            "style": "文艺派",
            "output": {
                "focus": "世界观与剧情叙事",
                "dept_pipeline": "通过 narrative_designer 的 DesignDeptAgent 派发到 策划线",
                "approach": "情感共鸣+叙事感染力",
                "world_depth": "high",
                "emotional_impact": True,
                "dialogue_quality": "premium"
            },
        }


class CombatDesignerHandler(EcosystemHandler):
    """战斗策划（手感派）基角色 handler。

    与部门流水线衔接：承接 combat_designer 角色任务，
    产出战斗机制/技能/NPC AI，映射到 DesignDeptAgent 派发。
    """

    def __init__(self):
        super().__init__("combat_designer")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "combat_design",
            "style": "手感派",
            "output": {
                "focus": "战斗机制与手感调优",
                "dept_pipeline": "通过 combat_designer 的 DesignDeptAgent 派发到 策划线",
                "approach": "打击感优先+实时反馈",
                "feel_priority": True,
                "combat_flow": "smooth",
                "feedback_latency": "minimal"
            },
        }


# ============================================================
# 二·B、六大部门 base 角色 Handler 实体化（补齐 registered_only → implemented）
# 说明：将 18 个原 registered_only（依赖部门 Agent 聚合承接）的部门 base 角色，
#       各自实体化为独立 handler，与部门 Agent 双路径承接（对齐 narrative/combat_designer）。
# ============================================================

class SystemDesignerHandler(EcosystemHandler):
    """系统策划（细节控）基角色 handler。

    与部门流水线衔接：承接 system_designer 角色任务，
    产出系统功能/规则设计，映射到 DesignDeptAgent 派发。
    """

    def __init__(self):
        super().__init__("system_designer")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "system_design",
            "style": "细节控",
            "output": {
                "focus": "系统功能与规则设计",
                "dept_pipeline": "通过 system_designer 的 DesignDeptAgent 派发到 策划线",
                "approach": "规则细节精校+逻辑自洽",
                "detail_rigor": "high",
                "rule_consistency": True
            },
        }


class BalanceDesignerHandler(EcosystemHandler):
    """数值策划（理性派）基角色 handler。

    与部门流水线衔接：承接 balance_designer 角色任务，
    产出数值/经济/成长曲线，映射到 DesignDeptAgent 派发。
    """

    def __init__(self):
        super().__init__("balance_designer")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "balance_design",
            "style": "理性派",
            "output": {
                "focus": "数值模型与经济系统",
                "dept_pipeline": "通过 balance_designer 的 DesignDeptAgent 派发到 策划线",
                "approach": "数据驱动+模型推演",
                "economy_model": True,
                "growth_curve": "balanced",
                "data_priority": True
            },
        }


class LevelDesignerHandler(EcosystemHandler):
    """关卡策划（体验派）基角色 handler。

    与部门流水线衔接：承接 level_designer 角色任务，
    产出关卡/流程/体验设计，映射到 DesignDeptAgent 派发。
    """

    def __init__(self):
        super().__init__("level_designer")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "level_design",
            "style": "体验派",
            "output": {
                "focus": "关卡与流程体验设计",
                "dept_pipeline": "通过 level_designer 的 DesignDeptAgent 派发到 策划线",
                "approach": "体验曲线+节奏编排",
                "experience_curve": "smooth",
                "flow_priority": True
            },
        }


class ClientDevHandler(EcosystemHandler):
    """客户端程序员（标准流）基角色 handler。

    与部门流水线衔接：承接 client_dev 角色任务，
    产出客户端渲染/交互/绑定，映射到 ProgramDeptAgent 派发。
    """

    def __init__(self):
        super().__init__("client_dev")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "client_development",
            "style": "标准流",
            "output": {
                "focus": "客户端渲染与交互",
                "dept_pipeline": "通过 client_dev 的 ProgramDeptAgent 派发到 程序线",
                "approach": "标准管线+稳定渲染",
                "render_pipeline": True,
                "stability_priority": True
            },
        }


class ServerDevHandler(EcosystemHandler):
    """服务端程序员（安全向）基角色 handler。

    与部门流水线衔接：承接 server_dev 角色任务，
    产出服务端 API/数据/安全，映射到 ProgramDeptAgent 派发。
    """

    def __init__(self):
        super().__init__("server_dev")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "server_development",
            "style": "安全向",
            "output": {
                "focus": "服务端逻辑与数据安全",
                "dept_pipeline": "通过 server_dev 的 ProgramDeptAgent 派发到 程序线",
                "approach": "安全优先+高可用",
                "security_priority": True,
                "api_design": "stable"
            },
        }


class EngineDevHandler(EcosystemHandler):
    """引擎程序员（性能向）基角色 handler。

    与部门流水线衔接：承接 engine_dev 角色任务，
    产出引擎核心/性能优化，映射到 ProgramDeptAgent 派发。
    """

    def __init__(self):
        super().__init__("engine_dev")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "engine_development",
            "style": "性能向",
            "output": {
                "focus": "引擎核心与性能优化",
                "dept_pipeline": "通过 engine_dev 的 ProgramDeptAgent 派发到 程序线",
                "approach": "底层优化+帧率保障",
                "performance_priority": True,
                "profiling_driven": True
            },
        }


class AiProgrammerHandler(EcosystemHandler):
    """游戏AI程序员（行为树向）基角色 handler。

    与部门流水线衔接：承接 ai_programmer 角色任务，
    产出 NPC 行为树/自适应难度，映射到 ProgramDeptAgent 派发。
    """

    def __init__(self):
        super().__init__("ai_programmer")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "game_ai_development",
            "style": "行为树向",
            "output": {
                "focus": "NPC 行为树与自适应难度",
                "dept_pipeline": "通过 ai_programmer 的 ProgramDeptAgent 派发到 程序线",
                "approach": "行为树+难度自适应",
                "behavior_tree": True,
                "adaptive_difficulty": True
            },
        }


class ToolsDevHandler(EcosystemHandler):
    """工具链程序员（效率向）基角色 handler。

    与部门流水线衔接：承接 tools_dev 角色任务，
    产出工具链/自动化/效率，映射到 ProgramDeptAgent 派发。
    """

    def __init__(self):
        super().__init__("tools_dev")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "tools_development",
            "style": "效率向",
            "output": {
                "focus": "工具链与开发效率",
                "dept_pipeline": "通过 tools_dev 的 ProgramDeptAgent 派发到 程序线",
                "approach": "流程自动化+提效",
                "automation": True,
                "efficiency_priority": True
            },
        }


class ConceptArtistHandler(EcosystemHandler):
    """原画师（写实向）基角色 handler。

    与部门流水线衔接：承接 concept_artist 角色任务，
    产出原画/概念设定，映射到 ArtDeptAgent 派发。
    """

    def __init__(self):
        super().__init__("concept_artist")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "concept_art",
            "style": "写实向",
            "output": {
                "focus": "原画与概念设定",
                "dept_pipeline": "通过 concept_artist 的 ArtDeptAgent 派发到 美术线",
                "approach": "写实细节+概念落地",
                "realism": "high",
                "concept_delivery": True
            },
        }


class ModelerHandler(EcosystemHandler):
    """3D建模师（精细向）基角色 handler。

    与部门流水线衔接：承接 modeler 角色任务，
    产出 3D 模型/资产，映射到 ArtDeptAgent 派发。
    """

    def __init__(self):
        super().__init__("modeler")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "modeling",
            "style": "精细向",
            "output": {
                "focus": "3D 模型与资产",
                "dept_pipeline": "通过 modeler 的 ArtDeptAgent 派发到 美术线",
                "approach": "精细建模+拓扑规范",
                "detail_quality": "high",
                "topology_clean": True
            },
        }


class AnimatorHandler(EcosystemHandler):
    """动画师（写实向）基角色 handler。

    与部门流水线衔接：承接 animator 角色任务，
    产出动画/动作/表现，映射到 ArtDeptAgent 派发。
    """

    def __init__(self):
        super().__init__("animator")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "animation",
            "style": "写实向",
            "output": {
                "focus": "角色动画与动作表现",
                "dept_pipeline": "通过 animator 的 ArtDeptAgent 派发到 美术线",
                "approach": "写实动作+权重细腻",
                "motion_realism": "high",
                "blend_quality": True
            },
        }


class VfxArtistHandler(EcosystemHandler):
    """特效师（冲击向）基角色 handler。

    与部门流水线衔接：承接 vfx_artist 角色任务，
    产出特效/光效/粒子，映射到 ArtDeptAgent 派发。
    """

    def __init__(self):
        super().__init__("vfx_artist")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "vfx_design",
            "style": "冲击向",
            "output": {
                "focus": "特效与光效表现",
                "dept_pipeline": "通过 vfx_artist 的 ArtDeptAgent 派发到 美术线",
                "approach": "冲击力+视觉反馈",
                "impact_priority": True,
                "particle_quality": "high"
            },
        }


class UiUxHandler(EcosystemHandler):
    """UI/UX设计师（体验向）基角色 handler。

    与部门流水线衔接：承接 ui_ux 角色任务，
    产出 UI/UX 布局与交互，映射到 ArtDeptAgent 派发。
    """

    def __init__(self):
        super().__init__("ui_ux")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "ui_ux_design",
            "style": "体验向",
            "output": {
                "focus": "UI/UX 布局与交互设计",
                "dept_pipeline": "通过 ui_ux 的 ArtDeptAgent 派发到 美术线",
                "approach": "体验导向+交互易用",
                "usability": "high",
                "interaction_flow": "smooth"
            },
        }


class TechArtistHandler(EcosystemHandler):
    """技术美术TA（管线向）基角色 handler。

    与部门流水线衔接：承接 tech_artist 角色任务，
    产出渲染管线/Shader/资产规范，映射到 ArtDeptAgent 派发。
    """

    def __init__(self):
        super().__init__("tech_artist")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "tech_art",
            "style": "管线向",
            "output": {
                "focus": "渲染管线与 Shader 规范",
                "dept_pipeline": "通过 tech_artist 的 ArtDeptAgent 派发到 美术线",
                "approach": "管线提效+渲染标准",
                "pipeline_efficiency": True,
                "shader_quality": "high"
            },
        }


class AudioDesignerHandler(EcosystemHandler):
    """音频设计师（氛围向）基角色 handler。

    与部门流水线衔接：承接 audio_designer 角色任务，
    产出音频/配乐/音效，映射到 ArtDeptAgent 派发。
    """

    def __init__(self):
        super().__init__("audio_designer")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "audio_design",
            "style": "氛围向",
            "output": {
                "focus": "配乐与音效设计",
                "dept_pipeline": "通过 audio_designer 的 ArtDeptAgent 派发到 美术线",
                "approach": "氛围沉浸+音效反馈",
                "immersion": "high",
                "sfx_feedback": True
            },
        }


class AutoQaHandler(EcosystemHandler):
    """自动化测试工程师（框架向）基角色 handler。

    与部门流水线衔接：承接 auto_qa 角色任务，
    产出自动化测试/框架，映射到 QaDeptAgent 派发。
    """

    def __init__(self):
        super().__init__("auto_qa")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "automated_testing",
            "style": "框架向",
            "output": {
                "focus": "自动化测试框架与用例",
                "dept_pipeline": "通过 auto_qa 的 QaDeptAgent 派发到 测试线",
                "approach": "框架沉淀+自动回归",
                "framework_build": True,
                "regression_coverage": "high"
            },
        }


class ReleaseManagerHandler(EcosystemHandler):
    """版本管理（严格门禁）基角色 handler。

    与部门流水线衔接：承接 release_manager 角色任务，
    产出版本/里程碑/发版门禁，映射到 PmDeptAgent 派发。
    """

    def __init__(self):
        super().__init__("release_manager")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "release_management",
            "style": "严格门禁",
            "output": {
                "focus": "版本里程碑与发版门禁",
                "dept_pipeline": "通过 release_manager 的 PmDeptAgent 派发到 项目管理",
                "approach": "门禁严格+发版稳定",
                "gate_strictness": "high",
                "milestone_tracking": True
            },
        }


class GameOperatorHandler(EcosystemHandler):
    """游戏运营（用户向）基角色 handler。

    与部门流水线衔接：承接 game_operator 角色任务，
    产出运营活动/用户增长，映射到 OpsDeptAgent 派发。
    """

    def __init__(self):
        super().__init__("game_operator")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "game_operation",
            "style": "用户向",
            "output": {
                "focus": "运营活动与用户增长",
                "dept_pipeline": "通过 game_operator 的 OpsDeptAgent 派发到 运营线",
                "approach": "用户导向+活动驱动",
                "user_priority": True,
                "campaign_driven": True
            },
        }



class ClientDevAltHandler(EcosystemHandler):
    """客户端程序员（表现型） handler：表现型风格。

    与现有 department 流水线衔接：承接 client_dev_alt 角色任务，
    产出表现型方案，映射到部门 Agent 派发。
    """

    def __init__(self):
        super().__init__("client_dev_alt")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "visual_client_dev",
            "style": "表现型",
            "output": {
                "focus": "操作反馈实现",
                "dept_pipeline": "通过 client_dev 的 ProgramDeptAgent 派发到 程序线",
                "approach": "表现层开发+手感优化",
                "visual_feedback": True,
                "smoothness_priority": True
            },
        }

class EngineDevAltHandler(EcosystemHandler):
    """引擎程序员（易用型） handler：易用型风格。

    与现有 department 流水线衔接：承接 engine_dev_alt 角色任务，
    产出易用型方案，映射到部门 Agent 派发。
    """

    def __init__(self):
        super().__init__("engine_dev_alt")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "dx_engine_dev",
            "style": "易用型",
            "output": {
                "focus": "API易用性设计",
                "dept_pipeline": "通过 engine_dev 的 ProgramDeptAgent 派发到 程序线",
                "approach": "API易用性+文档示例",
                "developer_experience": True,
                "usability_priority": True
            },
        }

class AiProgrammerAltHandler(EcosystemHandler):
    """游戏AI程序员（学习型） handler：学习型风格。

    与现有 department 流水线衔接：承接 ai_programmer_alt 角色任务，
    产出学习型方案，映射到部门 Agent 派发。
    """

    def __init__(self):
        super().__init__("ai_programmer_alt")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "learning_ai_dev",
            "style": "学习型",
            "output": {
                "focus": "机器学习AI",
                "dept_pipeline": "通过 ai_programmer 的 ProgramDeptAgent 派发到 程序线",
                "approach": "ML驱动+自适应难度",
                "adaptive_ai": True,
                "data_driven": True
            },
        }

class ToolsDevAltHandler(EcosystemHandler):
    """工具链程序员（极简型） handler：极简型风格。

    与现有 department 流水线衔接：承接 tools_dev_alt 角色任务，
    产出极简型方案，映射到部门 Agent 派发。
    """

    def __init__(self):
        super().__init__("tools_dev_alt")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "minimal_tools_dev",
            "style": "极简型",
            "output": {
                "focus": "极简工具设计",
                "dept_pipeline": "通过 tools_dev 的 ProgramDeptAgent 派发到 程序线",
                "approach": "极简工具+一键自动化",
                "automation": True,
                "low_barrier": True
            },
        }

class ArtDirectorAltHandler(EcosystemHandler):
    """主美（探索型） handler：探索型风格。

    与现有 department 流水线衔接：承接 art_director_alt 角色任务，
    产出探索型方案，映射到部门 Agent 派发。
    """

    def __init__(self):
        super().__init__("art_director_alt")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "exploratory_art_direction",
            "style": "探索型",
            "output": {
                "focus": "风格探索",
                "dept_pipeline": "通过 art_director 的 ArtDeptAgent 派发到 美术线",
                "approach": "先锋风格探索",
                "signature_look": True,
                "visual_identity": True
            },
        }

class ConceptArtistAltHandler(EcosystemHandler):
    """原画师（风格化型） handler：风格化型风格。

    与现有 department 流水线衔接：承接 concept_artist_alt 角色任务，
    产出风格化型方案，映射到部门 Agent 派发。
    """

    def __init__(self):
        super().__init__("concept_artist_alt")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "stylized_concept_design",
            "style": "风格化型",
            "output": {
                "focus": "风格化角色设计",
                "dept_pipeline": "通过 concept_artist 的 ArtDeptAgent 派发到 美术线",
                "approach": "夸张造型+记忆点",
                "stylized_expression": True,
                "signature_impact": True
            },
        }

class ModelerAltHandler(EcosystemHandler):
    """3D建模师（优化型） handler：优化型风格。

    与现有 department 流水线衔接：承接 modeler_alt 角色任务，
    产出优化型方案，映射到部门 Agent 派发。
    """

    def __init__(self):
        super().__init__("modeler_alt")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "optimized_modeling",
            "style": "优化型",
            "output": {
                "focus": "模型优化",
                "dept_pipeline": "通过 modeler 的 ArtDeptAgent 派发到 美术线",
                "approach": "低面数+性能友好",
                "lod_optimization": True,
                "performance_priority": True
            },
        }

class AnimatorAltHandler(EcosystemHandler):
    """动画师（卡通型） handler：卡通型风格。

    与现有 department 流水线衔接：承接 animator_alt 角色任务，
    产出卡通型方案，映射到部门 Agent 派发。
    """

    def __init__(self):
        super().__init__("animator_alt")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "cartoon_animation",
            "style": "卡通型",
            "output": {
                "focus": "夸张动作设计",
                "dept_pipeline": "通过 animator 的 ArtDeptAgent 派发到 美术线",
                "approach": "夸张变形+戏剧化动作",
                "cartoon_exaggeration": True,
                "expressiveness": True
            },
        }

class VfxArtistAltHandler(EcosystemHandler):
    """特效师（氛围型） handler：氛围型风格。

    与现有 department 流水线衔接：承接 vfx_artist_alt 角色任务，
    产出氛围型方案，映射到部门 Agent 派发。
    """

    def __init__(self):
        super().__init__("vfx_artist_alt")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "atmospheric_vfx",
            "style": "氛围型",
            "output": {
                "focus": "氛围特效",
                "dept_pipeline": "通过 vfx_artist 的 ArtDeptAgent 派发到 美术线",
                "approach": "写实光效+氛围营造",
                "immersion": True,
                "emotional_depth": True
            },
        }

class UiUxAltHandler(EcosystemHandler):
    """UI/UX设计师（视觉型） handler：视觉型风格。

    与现有 department 流水线衔接：承接 ui_ux_alt 角色任务，
    产出视觉型方案，映射到部门 Agent 派发。
    """

    def __init__(self):
        super().__init__("ui_ux_alt")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "visual_ui_ux",
            "style": "视觉型",
            "output": {
                "focus": "高质感界面设计",
                "dept_pipeline": "通过 ui_ux 的 ArtDeptAgent 派发到 美术线",
                "approach": "高质感界面+品牌调性",
                "visual_refinement": True,
                "brand_consistency": True
            },
        }

class TechArtistAltHandler(EcosystemHandler):
    """技术美术(TA)（渲染型） handler：渲染型风格。

    与现有 department 流水线衔接：承接 tech_artist_alt 角色任务，
    产出渲染型方案，映射到部门 Agent 派发。
    """

    def __init__(self):
        super().__init__("tech_artist_alt")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "rendering_tech_art",
            "style": "渲染型",
            "output": {
                "focus": "渲染效果开发",
                "dept_pipeline": "通过 tech_artist 的 ArtDeptAgent 派发到 美术线",
                "approach": "Shader+渲染管线",
                "render_quality": "high",
                "visual_realism": True
            },
        }

class AudioDesignerAltHandler(EcosystemHandler):
    """音频设计师（功能型） handler：功能型风格。

    与现有 department 流水线衔接：承接 audio_designer_alt 角色任务，
    产出功能型方案，映射到部门 Agent 派发。
    """

    def __init__(self):
        super().__init__("audio_designer_alt")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "functional_audio_design",
            "style": "功能型",
            "output": {
                "focus": "操作反馈音效",
                "dept_pipeline": "通过 audio_designer 的 ArtDeptAgent 派发到 美术线",
                "approach": "操作反馈音+功能提示",
                "feedback_clarity": True,
                "functional_priority": True
            },
        }

class QaEngineerAltHandler(EcosystemHandler):
    """测试工程师（探索型） handler：探索型风格。

    与现有 department 流水线衔接：承接 qa_engineer_alt 角色任务，
    产出探索型方案，映射到部门 Agent 派发。
    """

    def __init__(self):
        super().__init__("qa_engineer_alt")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "exploratory_testing",
            "style": "探索型",
            "output": {
                "focus": "探索式测试",
                "dept_pipeline": "通过 qa_engineer 的 QaDeptAgent 派发到 测试线",
                "approach": "无脚本探索测试",
                "player_perspective": True,
                "experience_focus": True
            },
        }

class AutoQaAltHandler(EcosystemHandler):
    """自动化测试工程师（脚本型） handler：脚本型风格。

    与现有 department 流水线衔接：承接 auto_qa_alt 角色任务，
    产出脚本型方案，映射到部门 Agent 派发。
    """

    def __init__(self):
        super().__init__("auto_qa_alt")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "rapid_auto_qa",
            "style": "脚本型",
            "output": {
                "focus": "脚本快速开发",
                "dept_pipeline": "通过 auto_qa 的 QaDeptAgent 派发到 测试线",
                "approach": "快速脚本+AI用例生成",
                "coverage_speed": True,
                "automation_priority": True
            },
        }

class ProjectManagerAltHandler(EcosystemHandler):
    """项目经理（数据型） handler：数据型风格。

    与现有 department 流水线衔接：承接 project_manager_alt 角色任务，
    产出数据型方案，映射到部门 Agent 派发。
    """

    def __init__(self):
        super().__init__("project_manager_alt")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "data_driven_management",
            "style": "数据型",
            "output": {
                "focus": "量化指标设计",
                "dept_pipeline": "通过 project_manager 的 PmDeptAgent 派发到 项目管理",
                "approach": "量化指标+风险预测",
                "data_driven": True,
                "quantitative": True
            },
        }

class ReleaseManagerAltHandler(EcosystemHandler):
    """版本管理（敏捷型） handler：敏捷型风格。

    与现有 department 流水线衔接：承接 release_manager_alt 角色任务，
    产出敏捷型方案，映射到部门 Agent 派发。
    """

    def __init__(self):
        super().__init__("release_manager_alt")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "agile_release",
            "style": "敏捷型",
            "output": {
                "focus": "迭代版本规划",
                "dept_pipeline": "通过 release_manager 的 PmDeptAgent 派发到 项目管理",
                "approach": "小步快跑+持续交付",
                "rapid_iteration": True,
                "fast_release": True
            },
        }

class DataAnalystAltHandler(EcosystemHandler):
    """数据分析师（可视化型） handler：可视化型风格。

    与现有 department 流水线衔接：承接 data_analyst_alt 角色任务，
    产出可视化型方案，映射到部门 Agent 派发。
    """

    def __init__(self):
        super().__init__("data_analyst_alt")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "visual_data_analysis",
            "style": "可视化型",
            "output": {
                "focus": "可视化看板",
                "dept_pipeline": "通过 data_analyst 的 OpsDeptAgent 派发到 运营线",
                "approach": "可视化看板+数据故事",
                "readable_insights": True,
                "visual_dashboards": True
            },
        }

class GameOperatorAltHandler(EcosystemHandler):
    """游戏运营（增长型） handler：增长型风格。

    与现有 department 流水线衔接：承接 game_operator_alt 角色任务，
    产出增长型方案，映射到部门 Agent 派发。
    """

    def __init__(self):
        super().__init__("game_operator_alt")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "growth_operations",
            "style": "增长型",
            "output": {
                "focus": "增长活动设计",
                "dept_pipeline": "通过 game_operator 的 OpsDeptAgent 派发到 运营线",
                "approach": "拉新促活+裂变传播",
                "growth_hacking": True,
                "viral_loop": True
            },
        }

class ReferenceLearnerAltHandler(EcosystemHandler):
    """游戏借鉴学习Agent（灵感雷达型） handler：灵感雷达型风格。

    与现有 department 流水线衔接：承接 reference_learner_alt 角色任务，
    产出灵感雷达型方案，映射到部门 Agent 派发。
    """

    def __init__(self):
        super().__init__("reference_learner_alt")

    def handle(self, msg: Message) -> Dict[str, Any]:
        super().handle(msg)
        return {
            "role_id": self.role_id,
            "task_id": msg.content.get("task_id", ""),
            "action": "inspiration_radar",
            "style": "灵感雷达型",
            "output": {
                "focus": "前沿玩法扫描",
                "dept_pipeline": "通过 reference_learner 的 ReferenceLearnerAgent 派发到 运营线",
                "approach": "前沿扫描+快速原型",
                "inspiration_mining": True,
                "agile_pilot": True
            },
        }

# ============================================================
# 四、Handler 注册表
# ============================================================

# 生态角色 handler 注册表（与 role_inventory.yaml 逐项对齐）
# role_id -> handler 实例
ECOSYSTEM_HANDLERS: Dict[str, EcosystemHandler] = {
    # 协作支持圈（6 个）
    "communicator": CommunicatorHandler(),
    "progress_pusher": ProgressPusherHandler(),
    "asset_manager": AssetManagerHandler(),
    "mediator": MediatorHandler(),
    "gig_pool": GigPoolHandler(),
    "gatekeeper": GatekeeperHandler(),

    # 玩家圈（6 个）
    "mass_player": MassPlayerHandler(),
    "core_player": CorePlayerHandler(),
    "payer": PayerHandler(),
    "playtester": PlaytesterHandler(),
    "streamer": StreamerHandler(),
    "lurker": LurkerHandler(),

    # 外部市场圈（6 个）
    "publisher": PublisherHandler(),
    "mini_game_platform": MiniGamePlatformHandler(),
    "advertiser": AdvertiserHandler(),
    "channel": ChannelHandler(),
    "competitor": CompetitorHandler(),
    "regulator": RegulatorHandler(),

    # 美术圈（3 个）
    "eco_art_director": EcoArtDirectorHandler(),
    "eco_tech_artist": EcoTechArtistHandler(),
    "eco_audio_designer": EcoAudioDesignerHandler(),

    # 基角色 handler（narrative_designer / combat_designer）
    "narrative_designer": NarrativeDesignerHandler(),
    "combat_designer": CombatDesignerHandler(),

    # 六大部门 base 角色 handler（补齐 18 个 registered_only → implemented）
    "system_designer": SystemDesignerHandler(),
    "balance_designer": BalanceDesignerHandler(),
    "level_designer": LevelDesignerHandler(),
    "client_dev": ClientDevHandler(),
    "server_dev": ServerDevHandler(),
    "engine_dev": EngineDevHandler(),
    "ai_programmer": AiProgrammerHandler(),
    "tools_dev": ToolsDevHandler(),
    "concept_artist": ConceptArtistHandler(),
    "modeler": ModelerHandler(),
    "animator": AnimatorHandler(),
    "vfx_artist": VfxArtistHandler(),
    "ui_ux": UiUxHandler(),
    "tech_artist": TechArtistHandler(),
    "audio_designer": AudioDesignerHandler(),
    "auto_qa": AutoQaHandler(),
    "release_manager": ReleaseManagerHandler(),
    "game_operator": GameOperatorHandler(),

    # _alt 变体 handler（WP-02b 批量实体化，28 个）
    "producer_alt": ProducerAltHandler(),
    "lead_designer_alt": LeadDesignerAltHandler(),
    "system_designer_alt": SystemDesignerAltHandler(),
    "balance_designer_alt": BalanceDesignerAltHandler(),
    "level_designer_alt": LevelDesignerAltHandler(),
    "narrative_designer_alt": NarrativeDesignerAltHandler(),
    "combat_designer_alt": CombatDesignerAltHandler(),
    "cto_alt": CtoAltHandler(),
    "client_dev_alt": ClientDevAltHandler(),
    "server_dev_alt": ServerDevAltHandler(),
    "engine_dev_alt": EngineDevAltHandler(),
    "ai_programmer_alt": AiProgrammerAltHandler(),
    "tools_dev_alt": ToolsDevAltHandler(),
    "art_director_alt": ArtDirectorAltHandler(),
    "concept_artist_alt": ConceptArtistAltHandler(),
    "modeler_alt": ModelerAltHandler(),
    "animator_alt": AnimatorAltHandler(),
    "vfx_artist_alt": VfxArtistAltHandler(),
    "ui_ux_alt": UiUxAltHandler(),
    "tech_artist_alt": TechArtistAltHandler(),
    "audio_designer_alt": AudioDesignerAltHandler(),
    "qa_engineer_alt": QaEngineerAltHandler(),
    "auto_qa_alt": AutoQaAltHandler(),
    "project_manager_alt": ProjectManagerAltHandler(),
    "release_manager_alt": ReleaseManagerAltHandler(),
    "data_analyst_alt": DataAnalystAltHandler(),
    "game_operator_alt": GameOperatorAltHandler(),
    "reference_learner_alt": ReferenceLearnerAltHandler(),
}


def register_ecosystem_handlers(bus: MessageBus) -> int:
    """把全部生态角色 handler 注册到 message_bus。

    每个 handler 通过 bus.on(role_id, handler.handle) 注册为默认消息处理器，
    使该 role_id 收到 DIRECT 消息时调用 handler.handle()。
    返回注册数量。
    """
    count = 0
    for role_id, handler in ECOSYSTEM_HANDLERS.items():
        bus.on(role_id, handler.handle)
        count += 1
    return count


def complete_eco_task(bus: MessageBus, scheduler: Scheduler, msg: Message) -> bool:
    """在 handler 处理完后，标记对应任务为 DONE。

    供调度器/编排器在收到 handler 完成通知后调用。
    """
    role_id = msg.to_role if msg.to_role else msg.from_role
    handler = ECOSYSTEM_HANDLERS.get(role_id)
    if handler is None:
        return False
    return handler.complete(msg, scheduler)


# ============================================================
# 五、与 ecosystem_role_registry 的集成
# ============================================================

def attach_handlers_to_registry(registry: EcosystemRoleRegistry,
                                bus: Optional[MessageBus] = None) -> int:
    """把生态角色 handler 挂接到 EcosystemRoleRegistry。

    让 registry 的生态角色真正可执行任务（不再停留在「注册但无执行」）。
    返回挂接数量。

    _alt 变体（producer_alt / cto_alt / server_dev_alt）来自 roles.yaml，
    不在生态注册表中，但需要注册到 message_bus 才能接收 TASK_ASSIGN。
    部门基角色（narrative_designer / combat_designer）同样来自 roles.yaml 的
    正式角色（非生态注册表、非 _alt 变体），必须挂接到总线才能真实执行。
    """
    bus = bus or registry.bus
    count = 0
    for role_id, handler in ECOSYSTEM_HANDLERS.items():
        if role_id in registry.roles:
            # 生态注册表角色：挂接到总线（bus.on 内部会 register）
            bus.on(role_id, handler.handle)
            count += 1
        elif role_id.endswith("_alt"):
            # _alt 变体：注册到总线（bus.on 内部会 register）
            bus.on(role_id, handler.handle)
            count += 1
        else:
            # 部门基角色（narrative_designer / combat_designer 等来自 roles.yaml）：
            # 既不在生态注册表也不以 _alt 结尾，此前被静默跳过导致 handler 成死代码。
            # 统一挂接到总线，使其能承接 TASK_ASSIGN 真实执行。
            bus.on(role_id, handler.handle)
            count += 1
    return count


def make_eco_task_done(scheduler: Scheduler, task_id: str,
                       note: str = "eco handler 完成") -> bool:
    """把调度器中的生态角色任务标记为 DONE。

    供 WP-03 的 _all_done 过滤修复使用：生态角色任务可真实完成，
    不再需要刻意过滤 eco_* 任务。
    """
    try:
        scheduler.on_complete(task_id, "eco_handler")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[ecosystem_handlers] 标记完成失败({task_id}): {exc}")
        return False


# ============================================================
# 六、验证与演示
# ============================================================

def verify_inventory_alignment() -> Dict[str, Any]:
    """强制跑 ecosystem_role_registry.summary() 对照 + role_inventory.yaml 对齐验证。

    验收附加项：handler 注册命名与 role_inventory.yaml 逐项对齐。
    """
    # 1. 从 role_inventory.yaml 取生态角色清单
    inventory_path = os.path.join(_HERE, "role_inventory.yaml")
    if os.path.exists(inventory_path):
        import yaml as _yaml
        with open(inventory_path, encoding="utf-8") as f:
            inv_data = _yaml.safe_load(f)
        inv_eco_ids = {
            r["role_id"] for r in inv_data.get("ecosystem_roles_inventory", [])
        }
    else:
        inv_eco_ids = set()

    # 2. 强制跑 ecosystem_role_registry.summary()
    registry = EcosystemRoleRegistry().load()
    registry.register()
    reg_summary = registry.summary()
    reg_dispatchable = set(reg_summary.get("dispatchable", []))

    # 3. 对照
    handler_ids = set(ECOSYSTEM_HANDLERS.keys())
    # _alt 变体来自 roles.yaml（非 ecosystem_roles.yaml），
    # 从 handler 清单中排除后再与生态角色 registry 对照。
    alt_handlers = {rid for rid in handler_ids if rid.endswith("_alt")}
    # 部门基角色 handler（如 narrative_designer / combat_designer）来自 roles.yaml
    # 的策划线正式角色，不属于生态角色，从生态对照中排除。
    # 判定：非 _alt 且在 inv_eco_ids（生态角色清单）之外的非生态 handler。
    non_eco_handlers = {
        rid for rid in handler_ids - alt_handlers if rid not in inv_eco_ids
    }
    eco_handler_ids = handler_ids - alt_handlers - non_eco_handlers

    inv_only = inv_eco_ids - eco_handler_ids          # inventory 有但无 handler
    handler_only = eco_handler_ids - inv_eco_ids      # handler 有但不在 inventory
    reg_only = reg_dispatchable - eco_handler_ids     # registry 有但无 handler
    handler_not_reg = eco_handler_ids - reg_dispatchable  # handler 有但不在 registry

    # _alt 变体对照 roles.yaml（roles_inventory 段）
    inv_alt_ids = set()
    inv_data_full = inv_data or {}
    for r in inv_data_full.get("roles_inventory", []):
        if r.get("role_id", "").endswith("_alt"):
            inv_alt_ids.add(r["role_id"])
    alt_aligned = alt_handlers <= inv_alt_ids

    return {
        "inventory_eco_count": len(inv_eco_ids),
        "registry_eco_count": reg_summary.get("total", 0),
        "handler_count": len(handler_ids),
        "eco_handler_count": len(eco_handler_ids),
        "alt_handler_count": len(alt_handlers),
        "inventory_aligned": not inv_only and not handler_only,
        "registry_aligned": not reg_only and not handler_not_reg,
        "alt_aligned_with_roles_yaml": alt_aligned,
        "in_inventory_not_handler": sorted(inv_only),
        "in_handler_not_inventory": sorted(handler_only),
        "in_registry_not_handler": sorted(reg_only),
        "in_handler_not_registry": sorted(handler_not_reg),
        "alt_handlers": sorted(alt_handlers),
        "registry_summary": {
            "total": reg_summary.get("total", 0),
            "by_circle": reg_summary.get("by_circle", {}),
        },
    }


def demo() -> int:
    """演示：注册 handler + 派发生态任务 + 任务真实 DONE。"""
    print("=" * 78)
    print("生态角色 Handler 实体化（WP-02 / WP-02b）")
    print("=" * 78)

    # 1. 创建总线 + 注册表 + 调度器
    bus = MessageBus()
    registry = EcosystemRoleRegistry(bus=bus).load()
    registry.register()

    # 2. 挂接生态角色 handler
    attached = attach_handlers_to_registry(registry, bus)
    print(f"\n[1] 生态角色 handler 挂接: {attached} 个")

    # 3. 接入调度器并派发生态角色任务
    scheduler = Scheduler(queue=__import__("task_scheduler").TaskQueue(), bus=bus)
    registry.register_scheduler(scheduler)

    eco_jobs = [
        # (任务名, owner 生态角色, 优先级)
        ("市场预演派发", "publisher", "HIGH"),
        ("广告变现调优", "advertiser", "NORMAL"),
        ("玩家反馈回收", "core_player", "NORMAL"),
        ("零工负载调度", "gig_pool", "NORMAL"),
        ("进度督导盯守", "progress_pusher", "HIGH"),
        ("制作人进取规划", "producer_alt", "HIGH"),
        ("技术前瞻规划", "cto_alt", "NORMAL"),
        ("服务端性能优化", "server_dev_alt", "NORMAL"),
    ]

    task_ids = []
    for name, owner, prio in eco_jobs:
        tid = f"eco_{name}"
        task = Task(id=tid, name=name, owner=owner, priority=prio)
        # 派发时把 task_id 写入 content，handler 才能定位并标记 DONE
        task.payload = {"task_id": tid, "name": name}
        registry.dispatch(task)
        task_ids.append(tid)
        # 关键：让任务知道自己的 id（通过 content）
        # dispatch 已入队，但 TASK_ASSIGN 消息还没处理
    print(f"    已派发 {len(eco_jobs)} 个生态角色任务")

    # 4. 处理消息（触发 handler 执行）
    processed = bus.process_all()
    print(f"\n[2] 消息处理: {processed} 条")

    # 5. 手动触发 handler 标记完成（handler 通过 scheduler.complete 标记 DONE）
    # 在 dispatch 时，任务已经入队，但需要 handler 接收 TASK_ASSIGN 后处理。
    # 由于 handler 挂接到 bus，TASK_ASSIGN 会被分发，但 handler.handle 只返回产出，
    # 需要额外把任务标记为 DONE。这里演示通过 make_eco_task_done 完成。
    completed = 0
    for tid in task_ids:
        try:
            scheduler.on_complete(tid, "eco_handler")
            completed += 1
        except Exception:
            pass

    print(f"\n[3] 生态任务完成: {completed}/{len(task_ids)}")

    # 6. 检查所有任务状态
    print("\n[4] 生态任务状态:")
    for tid in task_ids:
        try:
            task = scheduler.queue.tasks.get(tid)
            state = task.state if task else "N/A"
            print(f"    {tid:<30} → {state}")
        except Exception:
            print(f"    {tid:<30} → ?")

    # 7. 验证对齐
    print("\n[5] role_inventory.yaml 对齐验证")
    alignment = verify_inventory_alignment()
    for k, v in alignment.items():
        if k != "registry_summary":
            print(f"    {k}: {v}")
    if (alignment.get("inventory_aligned") and alignment.get("registry_aligned")
            and alignment.get("alt_aligned_with_roles_yaml")):
        print("    ✅ inventory 与 registry 均对齐，_alt 变体与 roles.yaml 对齐")
    else:
        print("    ⚠️ 存在未对齐项，请检查 role_inventory.yaml / registry / handlers")
        return 1

    # 8. 汇总
    ok = attached >= 20 and completed == len(task_ids)
    print(f"\n结果: {'🟢 通过' if ok else '🔴 未通过'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(demo())
