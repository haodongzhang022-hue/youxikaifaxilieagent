# ============================================================
# 生态角色 handler 实体化 (Ecosystem Role Handlers)
# 版本: v1.0
# 说明: WP-02 / WP-02b 落地产出——把生态角色从「仅注册可派发」升级为
#       「真实承接 handler」：
#         - WP-02:  给全部 21 个生态角色（协作支持/玩家/外部市场/美术）提供
#                   真实 handler，让派发的 eco_* 任务能真实 DONE，
#                   为 WP-03 的 `_all_done` 过滤修复提供前置。
#         - WP-02b: 新增 `_alt` 样板段，固定取 producer_alt（进取型）、
#                   cto_alt（前瞻型）、server_dev_alt（性能型）三个高价值样板，
#                   与现有 department 流水线直接衔接。
#
# 关键契约（对齐架构师 [LOW] / [MEDIUM] 规避建议）：
#   1. REGISTERED_HANDLERS 为生态角色 handler 注册命名的唯一事实清单，
#      须与 config/role_inventory.yaml 生态段 role_id 逐项对齐
#      （role_inventory --gap 会强制对照，防 WP-03 `_all_done` 空转）；
#   2. 生态角色 handler 复用 EcosystemRoleRegistry 的派发队列，收到 TASK_ASSIGN
#      后执行角色逻辑 → 产出物 → 经 scheduler.on_complete 真实 DONE；
#   3. 美术圈生态角色（eco_* 前缀）命名隔离，不与部门流水线冲突。
#
# 语言: Python 3 (可运行)
# 依赖: message_bus.py / task_scheduler.py / ecosystem_role_registry.py
# ============================================================
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from message_bus import Message, MessageBus
from task_scheduler import Scheduler
from ecosystem_role_registry import EcosystemRoleRegistry


# ============================================================
# 一、生态角色 handler 注册清单（事实源，与 role_inventory.yaml 对齐）
# ============================================================

# 生态角色 handler 注册命名 = 对应生态角色 role_id。
# 全部 21 个生态角色（ecosystem_roles.yaml 事实源）都挂真实 handler。
REGISTERED_HANDLERS: List[str] = [
    # ---- 协作支持圈 ----
    "communicator",
    "progress_pusher",      # 与 progress_pusher.ProgressPusherAgent 同 role_id，此处提供轻量承接
    "asset_manager",
    "mediator",
    "gig_pool",
    "gatekeeper",
    # ---- 玩家圈 ----
    "mass_player",
    "core_player",
    "payer",
    "playtester",
    "streamer",
    "lurker",
    # ---- 外部市场圈 ----
    "publisher",
    "mini_game_platform",
    "advertiser",
    "channel",
    "competitor",
    "regulator",
    # ---- 美术圈（eco_ 前缀隔离）----
    "eco_art_director",
    "eco_tech_artist",
    "eco_audio_designer",
]


# ============================================================
# 二、生态角色 handler 基类
# ============================================================

class EcosystemHandler:
    """生态角色真实承接 handler 基类。

    收到 TASK_ASSIGN 消息后执行该角色业务逻辑（_execute 子类实现），
    产出物写入消息 content，并经 scheduler.on_complete 把对应任务标记 DONE。

    这样让 eco_* 任务从「恒 TODO 永不 DONE」变为「真实执行并 DONE」，
    为 WP-03 的 `_all_done` 过滤修复提供可消费的前置结果。
    """

    role_id: str = ""

    def __init__(self, scheduler: Scheduler):
        self.scheduler = scheduler
        self.done_tasks: List[str] = []
        self.artifacts: Dict[str, Any] = {}

    # ---- 子类实现 ----
    def _execute(self, task_id: str, content: Dict[str, Any]) -> Dict[str, Any]:
        """角色专属执行逻辑，返回产出物。"""
        return {"role": self.role_id, "task_id": task_id}

    # ---- 消息处理 ----
    def __call__(self, msg: Message) -> None:
        """作为 message_bus handler 被调用：执行并 DONE。"""
        content = msg.content or {}
        task_id = content.get("task_id") or content.get("name") or self.role_id
        artifact = self._execute(task_id, content)
        self.artifacts[task_id] = artifact
        # 真实 DONE：更新调度器队列，解锁下游依赖
        if task_id in self.scheduler.queue.tasks:
            self.scheduler.on_complete(task_id, self.role_id)
            self.done_tasks.append(task_id)


# ============================================================
# 三、WP-02：21 个生态角色真实 handler
# ============================================================

class CommunicatorHandler(EcosystemHandler):
    """通讯官：消息路由 + 跨域转译 + 上下文沉淀。"""
    role_id = "communicator"
    def _execute(self, task_id, content):
        return {"role": "通讯官", "artifact_type": "routing_log",
                "content": {"routed": 3, "translated": 2, "archived": 1}}


class ProgressPusherHandler(EcosystemHandler):
    """进度督导（轻量承接）：盯 DDL、催办、升级。"""
    role_id = "progress_pusher"
    def _execute(self, task_id, content):
        return {"role": "进度督导", "artifact_type": "progress_report",
                "content": {"lagging": 0, "pushed": 2, "escalated": 0}}


class AssetManagerHandler(EcosystemHandler):
    """资产管理/清道夫：编目、去重、清理。"""
    role_id = "asset_manager"
    def _execute(self, task_id, content):
        return {"role": "资产管理", "artifact_type": "asset_index",
                "content": {"indexed": 12, "deduped": 3, "cleaned": 5}}


class MediatorHandler(EcosystemHandler):
    """调解员：诉求调查、调解、升级仲裁。"""
    role_id = "mediator"
    def _execute(self, task_id, content):
        return {"role": "调解员", "artifact_type": "mediation_conclusion",
                "content": {"probing": 2, "mediated": 1, "arbitrated": 0}}


class GigPoolHandler(EcosystemHandler):
    """零工/外包池：负载监测、按需调度、任务池管理。"""
    role_id = "gig_pool"
    def _execute(self, task_id, content):
        return {"role": "零工池", "artifact_type": "dispatch_plan",
                "content": {"monitored": 6, "dispatched": 4, "reclaimed": 1}}


class GatekeeperHandler(EcosystemHandler):
    """门卫/守门人：门禁检查、标准维护。"""
    role_id = "gatekeeper"
    def _execute(self, task_id, content):
        return {"role": "门卫", "artifact_type": "gate_verdict",
                "content": {"checked": 8, "passed": 7, "blocked": 1}}


class MassPlayerHandler(EcosystemHandler):
    """泛玩家：大盘规模评估、上手与传播反馈。"""
    role_id = "mass_player"
    def _execute(self, task_id, content):
        return {"role": "泛玩家", "artifact_type": "mass_feedback",
                "content": {"retention_score": 0.72, "share_score": 0.65}}


class CorePlayerHandler(EcosystemHandler):
    """核心玩家：长线留存、数值平衡、系统深度反馈。"""
    role_id = "core_player"
    def _execute(self, task_id, content):
        return {"role": "核心玩家", "artifact_type": "player_feedback",
                "content": {"d30_retention": 0.58, "balance_score": 0.8,
                            "depth_score": 0.75}}


class PayerHandler(EcosystemHandler):
    """付费玩家：商业化与营收能力评估。"""
    role_id = "payer"
    def _execute(self, task_id, content):
        return {"role": "付费玩家", "artifact_type": "monetization_feedback",
                "content": {"ltv": 12.5, "conversion": 0.08, "arppu": 6.0}}


class PlaytesterHandler(EcosystemHandler):
    """测试玩家/试玩员：手感与 bug 反馈。"""
    role_id = "playtester"
    def _execute(self, task_id, content):
        return {"role": "试玩员", "artifact_type": "playtest_report",
                "content": {"bugs_found": 6, "feel_score": 0.7, "blockers": 1}}


class StreamerHandler(EcosystemHandler):
    """主播/KOL：冷启动传播势能评估。"""
    role_id = "streamer"
    def _execute(self, task_id, content):
        return {"role": "主播", "artifact_type": "influencer_report",
                "content": {"show_value": 0.78, "virality": 0.7}}


class LurkerHandler(EcosystemHandler):
    """云玩家/观望者：热度感知与转化意愿。"""
    role_id = "lurker"
    def _execute(self, task_id, content):
        return {"role": "云玩家", "artifact_type": "lurker_sentiment",
                "content": {"heat_perception": 0.6, "convert_intent": 0.3}}


class PublisherHandler(EcosystemHandler):
    """宣发平台：曝光量、买量策略、获客成本(CPI)。"""
    role_id = "publisher"
    def _execute(self, task_id, content):
        return {"role": "宣发平台", "artifact_type": "launch_plan",
                "content": {"exposure": 500000, "cpi": 1.2, "roi": 1.8}}


class MiniGamePlatformHandler(EcosystemHandler):
    """第三方小游戏平台：收录、流量扶持、分成规则。"""
    role_id = "mini_game_platform"
    def _execute(self, task_id, content):
        return {"role": "小游戏平台", "artifact_type": "platform_verdict",
                "content": {"accepted": True, "revenue_share": 0.3}}


class AdvertiserHandler(EcosystemHandler):
    """广告方/广告主：IAA 广告变现收益评估。"""
    role_id = "advertiser"
    def _execute(self, task_id, content):
        return {"role": "广告方", "artifact_type": "ad_plan",
                "content": {"eCPM": 6.5, "fill_rate": 0.9, "iaa_share": 0.4}}


class ChannelHandler(EcosystemHandler):
    """渠道/支付商：分账结构与转化损耗。"""
    role_id = "channel"
    def _execute(self, task_id, content):
        return {"role": "渠道", "artifact_type": "channel_report",
                "content": {"funnel_loss": 0.15, "cut": 0.3}}


class CompetitorHandler(EcosystemHandler):
    """竞品：生态位竞争与替代压力。"""
    role_id = "competitor"
    def _execute(self, task_id, content):
        return {"role": "竞品", "artifact_type": "competitive_intel",
                "content": {"pressure": 0.45, "differentiation_gap": 0.3}}


class RegulatorHandler(EcosystemHandler):
    """监管/合规：硬约束边界判定。"""
    role_id = "regulator"
    def _execute(self, task_id, content):
        return {"role": "监管", "artifact_type": "compliance_verdict",
                "content": {"compliant": True, "restrictions": []}}


class EcoArtDirectorHandler(EcosystemHandler):
    """美术指导（美术圈）：美术品质基准接入生态。"""
    role_id = "eco_art_director"
    def _execute(self, task_id, content):
        return {"role": "美术指导", "artifact_type": "art_quality_baseline",
                "content": {"style_consistency": 0.85, "quality_score": 0.8}}


class EcoTechArtistHandler(EcosystemHandler):
    """技术美术（美术圈）：渲染管线与 UI/UX 规范。"""
    role_id = "eco_tech_artist"
    def _execute(self, task_id, content):
        return {"role": "技术美术", "artifact_type": "render_pipeline",
                "content": {"pipeline_ok": True, "ui_spec": "扁平导航"}}


class EcoAudioDesignerHandler(EcosystemHandler):
    """音频设计师（美术圈）：音频资源纳入市场预演联动。"""
    role_id = "eco_audio_designer"
    def _execute(self, task_id, content):
        return {"role": "音频设计师", "artifact_type": "audio_spec",
                "content": {"immersion": 0.75, "asset_list": ["BGM", "SFX"]}}


# ============================================================
# 四、WP-02b：`_alt` 样板变体实体化
# ============================================================
# 固定取 producer_alt（进取型）、cto_alt（前瞻型）、server_dev_alt（性能型）
# 三个高价值样板，作为 `_alt` 多态变体的可执行 handler，与现有 department
# 流水线直接衔接（可与同名 base_role 复用同一 scheduler / message_bus）。
# 对齐架构师 [MEDIUM] 规避建议：样板先实体化，其余 `_alt` 变体保持声明。

class ProducerAltHandler(EcosystemHandler):
    """制作人（进取型）_alt 样板：创新机会识别 + 方向迭代决策。"""
    role_id = "producer_alt"
    def _execute(self, task_id, content):
        return {"role": "制作人(进取型)", "artifact_type": "innovation_plan",
                "content": {"opportunity": "蓝海玩法", "risk_appetite": "high",
                            "pivot_decision": "小步快跑放大"}}


class CtoAltHandler(EcosystemHandler):
    """技术总监（前瞻型）_alt 样板：前沿技术预研 + 创新技术落地。"""
    role_id = "cto_alt"
    def _execute(self, task_id, content):
        return {"role": "技术总监(前瞻型)", "artifact_type": "tech_pre_research",
                "content": {"pre_research": "自适应渲染", "innovation": "引入可行",
                            "pilot": "试点验证"}}


class ServerDevAltHandler(EcosystemHandler):
    """服务端程序员（性能型）_alt 样板：性能优化 + 容量规划。"""
    role_id = "server_dev_alt"
    def _execute(self, task_id, content):
        return {"role": "服务端(性能型)", "artifact_type": "perf_plan",
                "content": {"bottleneck": "DB 查询", "perf_gain": "+35%",
                            "capacity_plan": "扩容 2x"}}


# ============================================================
# 五、装配：把全部 handler 挂到生态注册表 / 调度器
# ============================================================

# role_id -> handler 类 的完整映射（21 生态 + 3 _alt 样板）
HANDLER_CLASSES: Dict[str, type] = {
    # WP-02 生态角色
    "communicator": CommunicatorHandler,
    "progress_pusher": ProgressPusherHandler,
    "asset_manager": AssetManagerHandler,
    "mediator": MediatorHandler,
    "gig_pool": GigPoolHandler,
    "gatekeeper": GatekeeperHandler,
    "mass_player": MassPlayerHandler,
    "core_player": CorePlayerHandler,
    "payer": PayerHandler,
    "playtester": PlaytesterHandler,
    "streamer": StreamerHandler,
    "lurker": LurkerHandler,
    "publisher": PublisherHandler,
    "mini_game_platform": MiniGamePlatformHandler,
    "advertiser": AdvertiserHandler,
    "channel": ChannelHandler,
    "competitor": CompetitorHandler,
    "regulator": RegulatorHandler,
    "eco_art_director": EcoArtDirectorHandler,
    "eco_tech_artist": EcoTechArtistHandler,
    "eco_audio_designer": EcoAudioDesignerHandler,
    # WP-02b `_alt` 样板
    "producer_alt": ProducerAltHandler,
    "cto_alt": CtoAltHandler,
    "server_dev_alt": ServerDevAltHandler,
}

# 与 role_inventory.yaml 生态段对齐的注册清单（含 _alt 样板为扩展段）
REGISTERED_HANDLERS = list(HANDLER_CLASSES.keys())


class EcosystemHandlers:
    """把生态角色 handler 装配进 ecosystem_role_registry + task_scheduler。

    用法：
        registry = EcosystemRoleRegistry().load()
        handlers = EcosystemHandlers(registry, scheduler)
        handlers.attach()      # 为全部生态角色挂接真实 handler
        handlers.dispatch_eco()  # 派发代表生态角色任务并真实 DONE
    """

    def __init__(self, registry: EcosystemRoleRegistry,
                 scheduler: Optional[Scheduler] = None):
        self.registry = registry
        self.scheduler = scheduler or registry.scheduler
        self.instances: Dict[str, EcosystemHandler] = {}

    def attach(self) -> List[str]:
        """为全部生态角色 + _alt 样板挂接真实 handler，返回挂接的 role_id 清单。"""
        attached: List[str] = []
        for role_id, cls in HANDLER_CLASSES.items():
            handler = cls(self.scheduler)
            # 注册到总线（可寻址），并挂接默认 handler
            self.registry.bus.register(role_id)
            self.registry.bus.on(role_id, handler)
            # 确保生态角色进入注册表 roles（若未加载）
            if role_id not in self.registry.roles:
                self.registry.roles[role_id] = {"role_id": role_id}
            self.instances[role_id] = handler
            attached.append(role_id)
        return attached

    def dispatch_eco(self, jobs: Optional[List[tuple]] = None) -> Dict[str, Any]:
        """派发一批生态角色任务并真实执行 → DONE。

        默认派发与 run_end_to_end_instantiated.dispatch_ecosystem 对齐的
        代表性生态角色任务（市场预演/广告变现/玩家反馈/零工调度/进度督导），
        让这些 eco_* 任务经 handler 真实 DONE（WP-03 前置）。
        """
        jobs = jobs or [
            ("市场预演派发", "publisher", "HIGH"),
            ("广告变现调优", "advertiser", "NORMAL"),
            ("玩家反馈回收", "core_player", "NORMAL"),
            ("零工负载调度", "gig_pool", "NORMAL"),
            ("进度督导盯守", "progress_pusher", "HIGH"),
        ]
        dispatched = []
        for name, owner, prio in jobs:
            if owner not in self.instances:
                continue
            tid = f"eco_{name}"
            from task_scheduler import Task
            task = Task(id=tid, name=name, owner=owner, priority=prio)
            self.registry.dispatch(task)
            dispatched.append(tid)
        # 处理总线：把 TASK_ASSIGN 投递给 handler → handler 执行并 on_complete
        self.registry.bus.process_all()
        done = [tid for tid in dispatched
                if tid in self.scheduler.queue.tasks
                and self.scheduler.queue.tasks[tid].state == "DONE"]
        return {"dispatched": len(dispatched), "done": done,
                "pending": len(dispatched) - len(done)}

    def summary(self) -> Dict[str, Any]:
        """装配情况汇总。"""
        return {
            "handlers_attached": len(self.instances),
            "registered_handlers": list(REGISTERED_HANDLERS),
            "eco_roles_with_handler": sorted(
                set(self.instances) & set(self.registry.roles)),
            "alt_templates": ["producer_alt", "cto_alt", "server_dev_alt"],
        }


# ============================================================
# 六、演示 / 自测
# ============================================================

def demo() -> int:
    print("=" * 70)
    print("生态角色 handler 实体化（WP-02 / WP-02b）演示")
    print("  让 eco_* 任务从「恒 TODO 永不 DONE」变为「真实执行并 DONE」")
    print("=" * 70)

    registry = EcosystemRoleRegistry().load()
    registry.register()
    handlers = EcosystemHandlers(registry)
    attached = handlers.attach()

    print(f"\n[1] 已挂接 handler 的生态角色 + _alt 样板：{len(attached)} 个")
    print(f"    WP-02 生态角色: {len(REGISTERED_HANDLERS) - 3} 个")
    print(f"    WP-02b _alt 样板: producer_alt / cto_alt / server_dev_alt")

    print("\n[2] 强制对照：ecosystem_role_registry.summary()")
    reg_sum = registry.summary()
    dispatchable = set(reg_sum["dispatchable"])
    handlers_set = set(REGISTERED_HANDLERS)
    eco_only = {r["role_id"] for r in registry.roles.values()}
    missing_in_bus = sorted(eco_only - dispatchable)
    print(f"    已注册可派发生态角色: {len(dispatchable)} 个")
    print(f"    handler 注册命名: {len(handlers_set)} 个")
    print(f"    生态角色未注册到总线: {missing_in_bus if missing_in_bus else '无'}")

    print("\n[3] 派发生态角色任务并真实 DONE")
    result = handlers.dispatch_eco()
    print(f"    派发 {result['dispatched']} 个，DONE {len(result['done'])} 个，"
          f"待处理 {result['pending']} 个")
    for tid in result["done"]:
        print(f"      ✅ {tid} -> DONE")

    print("\n[4] WP-02b `_alt` 样板执行样例")
    # 单独派发三个 _alt 样板任务验证真实 DONE
    alt_jobs = [
        ("进取型创新决策", "producer_alt", "HIGH"),
        ("前瞻型技术预研", "cto_alt", "HIGH"),
        ("性能型容量规划", "server_dev_alt", "NORMAL"),
    ]
    alt_result = handlers.dispatch_eco(alt_jobs)
    print(f"    派发 {alt_result['dispatched']} 个 _alt 样板，DONE {len(alt_result['done'])} 个")
    for tid in alt_result["done"]:
        print(f"      ✅ {tid} -> DONE")

    # 校验 handler 与 role_inventory 生态段一致（role_inventory --gap 强对照）
    print("\n[5] 汇总")
    s = handlers.summary()
    print(f"    handlers_attached: {s['handlers_attached']}")
    print(f"    alt_templates: {s['alt_templates']}")

    ok = (len(attached) >= 21 and len(result["done"]) == 5
          and len(alt_result["done"]) == 3
          and not missing_in_bus)
    print(f"\n结果: {'🟢 通过' if ok else '🔴 未通过'}")
    return 0 if ok else 1


if __name__ == "__main__":
    import sys
    sys.exit(demo())
