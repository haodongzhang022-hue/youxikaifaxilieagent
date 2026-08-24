# ============================================================
# 游戏借鉴学习 Agent · 可运行实现（ReferenceLearnerAgent）
# 版本: v0.1
# 说明: 基于通用内核 agent_core.BaseAgent 落地 reference_learner 岗位，
#       对接升级后的通用基础设施：
#         - agent_core.BaseAgent   通用生命周期 / 状态机 / 决策 / 消息收发
#         - message_bus.MessageBus 事件驱动消息总线（协作）
#         - task_scheduler.Scheduler 任务队列 / 优先级 / 依赖调度
#       并复用强化层 agent_behavior.CapabilityBoost：
#         思维模式路由 / 科研探索（树探索·假设求证·博弈） / 探索规划 / 相似度校准
# 语言: Python 3 (可运行)
# ============================================================
from __future__ import annotations

from typing import Any, Dict, List, Optional

from agent_core import BaseAgent
from message_bus import Message, MessageBus
from task_scheduler import Scheduler, Task
from agent_behavior import CapabilityBoost


# ============================================================
# reference_learner 业务状态机（与 roles.yaml 对齐）
# ============================================================

# IDLE → INPUT_PENDING → ANALYSIS → ASSESS → DECIDE →
#        BUILD_MOD → SANDBOX_VERIFY → REVIEW_COMMIT → ARCHIVING → IDLE
BUSINESS_STATES = [
    "INPUT_PENDING", "ANALYSIS", "ASSESS", "DECIDE",
    "BUILD_MOD", "SANDBOX_VERIFY", "REVIEW_COMMIT", "ARCHIVING",
]


class ReferenceLearnerAgent(BaseAgent):
    """
    游戏借鉴学习 Agent。

    职责（roles.yaml → reference_learner）：
      - 理解目标游戏机制并拆解还原
      - 评估借鉴机制与自有游戏的适配度并做取舍
      - 以创意工坊模组（Mod）方式落地
      - 维护借鉴知识库与玩法雷达

    强化层（CapabilityBoost）调用时机：
      - 分析前  → plan_exploration  决定探索模式（渠道/类型/深度）
      - 决策时  → tree_search / review_decision 科研探索与多 Agent 博弈
      - 构建后  → calibrate_similarity 相似度档位控制与多轮校准
      - 复盘时  → reflect_learning 元学习迭代借鉴策略
    """

    def __init__(self, role_id: str = "reference_learner",
                 bus: Optional[MessageBus] = None,
                 scheduler: Optional[Scheduler] = None,
                 boost: Optional[CapabilityBoost] = None):
        super().__init__(role_id, bus)
        self.scheduler = scheduler or Scheduler(bus=self.bus)
        self.boost = boost or CapabilityBoost()
        self.biz_state = "IDLE"                 # 借鉴落地业务状态
        self.decisions: List[Dict[str, Any]] = []   # 决策历史
        self.mod_versions: List[Dict[str, Any]] = []  # 已构建 Mod 版本

    # ---------- 覆写 BaseAgent 钩子 ----------
    def on_boot(self):
        """加载借鉴知识库与玩法雷达基线。"""
        self.knowledge.add_doc("借鉴知识库", {"note": "已评估/已落地/已放弃"})
        self.knowledge.add_doc("竞品玩法库", {"note": "玩法雷达候选"})
        self.knowledge.add_doc("自有游戏基线", {"mods": [], "version": "baseline"})

    def heartbeat(self):
        """心跳：玩法雷达定期扫描（简化：打印当前状态）。"""
        pass

    # ---------- 借鉴落地主流程（业务状态机） ----------
    def handle_task(self, msg: Message):
        """处理主业务消息：驱动借鉴落地状态机。"""
        if msg.type == "TASK_ASSIGN":
            self._start_reference(msg.content.get("task_id"),
                                  msg.content.get("inputs", {}))

        elif msg.type == "REVIEW_RESULT":
            self._on_review(msg.content)

        elif msg.type == "STATUS_REPORT":
            self.reply(msg, "STATUS_REPORT", self.report())

        elif msg.type == "NOTIFICATION":
            self._log("notification", str(msg.content))

    # ---------- 借鉴落地各阶段 ----------
    def _start_reference(self, task_id: str, inputs: Dict[str, Any]):
        """收到借鉴任务 → 探索规划 → 分析 → 评估。"""
        request = inputs.get("request", inputs.get("title", ""))
        self.biz_state = "INPUT_PENDING"
        self._transition("PLANNING")
        self._log("reference", f"收到借鉴任务 {task_id}: {request}")

        # 1) 探索规划（校验：渠道×信息类型×深度）
        exploration = self.boost.plan_exploration(request)
        self._log("exploration", f"探索模式={exploration['mode_preset']}")

        self.biz_state = "ANALYSIS"
        # 2) 理解拆解（产出机制分析报告）
        analysis = self._analyze(inputs)
        self._log("analysis", f"机制分析: {analysis.get('mechanism', '')}")

        self.biz_state = "ASSESS"
        # 3) 适配评估（契合度评分 + 取舍）
        assessment = self._assess(analysis)
        self._log("assess", f"契合度={assessment.get('fit_score')}")

        # 契合度过低则放弃
        if assessment.get("fit_score", 0) < 60:
            self.biz_state = "IDLE"
            self._log("assess", "契合度不足，放弃借鉴")
            return

        # 4) 决策（科研探索：树探索 + 多 Agent 博弈）
        self.biz_state = "DECIDE"
        decision = self._decide(assessment)
        self.decisions.append(decision)
        self._log("decide", f"决策={decision.get('action')}")

        # 5) 构建 Mod
        self.biz_state = "BUILD_MOD"
        mod = self._build_mod(decision, inputs)
        self._log("build_mod", f"Mod 构建: {mod.get('mod_id')}")

        # 6) 相似度校准（校准：档位控制 + 多轮迭代）
        calib = self.boost.calibrate_similarity(mod, assessment.get("target", {}),
                                                preset=self._similarity_preset(decision))
        self._log("calibration", f"校准状态={calib.get('status')}")

        # 7) 沙盒验证
        self.biz_state = "SANDBOX_VERIFY"
        verified = self._sandbox_verify(mod)
        self._log("sandbox", f"沙盒验证={'通过' if verified else '打回'}")

        if not verified:
            self.biz_state = "BUILD_MOD"   # 打回重建
            self._log("sandbox", "验证失败，打回重建")
            return

        # 8) 提交审核（发 REVIEW_REQUEST 给制作人）
        self.biz_state = "REVIEW_COMMIT"
        self._request_review(mod)
        self._log("review", f"已提交审核: {mod.get('mod_id')}")

    def _analyze(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """机制理解拆解：还原玩法循环 / 数值 / 视觉语言。"""
        return {
            "mechanism": inputs.get("mechanism", inputs.get("title", "未知机制")),
            "system_breakdown": ["玩法循环", "数值曲线", "视觉语言"],
            "source": inputs.get("source", "待补充"),
        }

    def _assess(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """适配评估：契合度评分（元学习策略权重）+ 取舍矩阵。"""
        weights = self.boost.meta.strategy["fit_weights"]
        # 简化评分：基于可用信息给出确定性打分
        base = {"game_type": 0.8, "audience": 0.7, "tech_stack": 0.6,
                "battle_depth": 0.7, "learning_curve": 0.7}
        fit_score = int(sum(base[k] * w for k, w in weights.items()) / sum(weights.values()) * 100)
        return {
            "analysis": analysis,
            "fit_score": fit_score,
            "decision_matrix": {"keep": 0.6, "trim": 0.3, "adapt": 0.1, "drop": 0.0},
            "target": {"mechanics": 0.5, "numeric": 0.5, "visual": 0.5,
                       "code": 0.5, "mindset": 0.5},   # 自有游戏基线
        }

    def _decide(self, assessment: Dict[str, Any]) -> Dict[str, Any]:
        """科研决策：树探索多分支推演 + 多 Agent 博弈评审。"""
        # 树探索：对落地方式分叉推演
        tree = self.boost.tree.explore(
            root_question="借鉴机制应如何落地？",
            branch_generator=lambda q: [
                {"id": "keep", "label": "整体搬", "score": 0.8},
                {"id": "trim", "label": "裁剪后搬", "score": 0.9},
                {"id": "adapt", "label": "改造融合", "score": 0.7},
                {"id": "drop", "label": "放弃", "score": 0.1},
            ],
            evaluator=lambda b: {"score": b["score"] * 100,
                                 "reason": f"{b['label']} 适配评估"},
        )
        self._log("tree_search", f"推荐分支={tree.get('recommended')} 置信度={tree.get('confidence')}")

        # 多 Agent 博弈评审
        verdicts = {
            "advocate": {"verdict": "support", "confidence": 0.8},
            "reviewer": {"verdict": "conditional_support", "confidence": 0.7,
                         "conditions": ["需裁剪部分数值"]},
            "skeptic": {"verdict": "oppose", "confidence": 0.3,
                        "conditions": ["注意版权雷同风险"]},
        }
        debate = self.boost.review_decision("借鉴落地", verdicts)
        self._log("debate", f"博弈评审={debate.get('action')} 置信度={debate.get('weighted_confidence')}")

        return {
            "mechanism": assessment["analysis"]["mechanism"],
            "strategy": tree.get("recommended", "trim"),
            "action": debate.get("action", "有条件采纳"),
            "confidence": debate.get("weighted_confidence", 0.5),
            "conditions": debate.get("conditions", []),
            "fit_score": assessment["fit_score"],
        }

    def _build_mod(self, decision: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
        """以创意工坊模组（Mod）方式落地借鉴。"""
        import uuid
        mod = {
            "mod_id": f"mod_{uuid.uuid4().hex[:8]}",
            "name": inputs.get("mod_name", f"{decision['mechanism']}_mod"),
            "strategy": decision["strategy"],
            "manifest": {
                "author": self.role_id,
                "target_mechanism": decision["mechanism"],
                "similarity_goal": self._similarity_preset(decision),
            },
            # 各维度相似度打分（供校准引擎检测）
            "mechanics": 0.7, "numeric": 0.6, "visual": 0.5,
            "code": 0.65, "mindset": 0.5,
        }
        self.mod_versions.append(mod)
        return mod

    def _similarity_preset(self, decision: Dict[str, Any]) -> str:
        """根据决策选择相似度档位（默认 high=7成参考）。"""
        strategy = decision.get("strategy")
        if strategy == "keep":
            return "full_clone"
        if strategy == "drop":
            return "anti_pattern"
        if strategy == "adapt":
            return "code_only"
        return "high"

    def _sandbox_verify(self, mod: Dict[str, Any]) -> bool:
        """沙盒隔离验证：功能可用性 / 回滚测试。"""
        # 简化：manifest 完整且策略明确视为通过
        return bool(mod.get("manifest") and mod.get("strategy"))

    def _request_review(self, mod: Dict[str, Any]):
        """提交审核：发 APPROVAL_REQUEST 给制作人（L2 人机共治）。"""
        self.send("APPROVAL_REQUEST", "producer",
                  {"mod_id": mod["mod_id"], "mod": mod, "await": "human_review"})

    # ---------- 审核结果回调 ----------
    def _on_review(self, content: Dict[str, Any]):
        """收到审核结果：通过则归档知识库，打回则重建。"""
        mod_id = content.get("mod_id")
        if content.get("approved"):
            self.biz_state = "ARCHIVING"
            self._archive(mod_id)
            self._log("review", f"Mod {mod_id} 已通过并归档")
            self.biz_state = "IDLE"
        else:
            self.biz_state = "BUILD_MOD"
            self._log("review", f"Mod {mod_id} 被打回，重建")

    def _archive(self, mod_id: str):
        """归档知识库 + 元学习复盘。"""
        self.knowledge.learn({"mod_id": mod_id}, "publish_mod",
                             {"status": "archived"})
        # 元学习：复盘本次借鉴，迭代评估策略
        reflection = self.boost.reflect_learning(
            {"session_id": mod_id, "fit_score": 80}, {"satisfaction": 75})
        self._log("meta_learning", f"元学习复盘={reflection.get('reflection', {}).get('verdict')}")

    # ---------- 调度对接 ----------
    def enqueue_reference_task(self, name: str, payload: Dict[str, Any],
                               priority: str = "NORMAL") -> Task:
        """把借鉴任务交给调度器派发（对接 task_scheduler）。"""
        task = Task(name=name, owner=self.role_id, priority=priority, payload=payload)
        self.scheduler.enqueue(task)
        return task

    # ---------- 汇报 ----------
    def report(self) -> Dict[str, Any]:
        return {
            "agent_id": self.role_id,
            "biz_state": self.biz_state,
            "state": self.state,
            "decisions": len(self.decisions),
            "mod_versions": len(self.mod_versions),
            "log_len": len(self.log),
        }


# ============================================================
# 演示
# ============================================================

def demo():
    print("=" * 60)
    print("游戏借鉴学习 Agent (ReferenceLearnerAgent) 演示")
    print("=" * 60)

    bus = MessageBus()
    agent = ReferenceLearnerAgent(role_id="reference_learner", bus=bus)
    agent.boot()

    # 模拟制作人下发借鉴任务
    from message_bus import build_task_assign
    msg = build_task_assign(
        "producer", "reference_learner", "rl_001",
        {"request": "借鉴某动作游戏的核心战斗循环，注意不要踩版权雷同的坑",
         "mechanism": "完美闪避反击循环", "title": "动作游戏战斗循环借鉴",
         "mod_name": "dodge_counter_mod"})
    bus.publish(msg)
    bus.process_all()

    print(f"\n处理完成后状态: {agent.state} / biz_state={agent.biz_state}")
    print("\n借鉴决策历史:")
    for d in agent.decisions:
        print(f"  - {d['mechanism']} → 策略={d['strategy']}, 动作={d['action']}, 置信度={d['confidence']}")

    print("\nMod 版本:")
    for m in agent.mod_versions:
        print(f"  - {m['mod_id']} ({m['name']}) strategy={m['strategy']}")

    print("\nAgent 运行日志:")
    for entry in agent.log:
        print(f"  [{entry['event']}] {entry['note']}")

    print("\n交付到总线上的消息数:", len(bus.delivered))
    for m in bus.delivered:
        print(f"  - {m.type} from {m.from_role} to {m.to_role}")


if __name__ == "__main__":
    demo()
