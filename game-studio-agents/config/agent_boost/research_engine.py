# ============================================================
# Agent 强化层 · 科研探索引擎（Scientific Research Engine）
# 版本: v0.1
# 说明: 为 reference_learner 提供四大科研探索能力：
#       元学习 / 树探索 / 假设求证思维链 / 多Agent博弈
# 来源: 借鉴 dsh-router-standard 的思维模式路由与模式隔离子代理，
#       以及科研方法（MCTS风格树探索、可证伪假设、多视角评审）。
# 语言: 伪代码 / 结构化定义（对接 config/agent_behavior.py）
# ============================================================

"""
科研探索引擎让借鉴从"照搬玩法"升级为"像研究者一样求证、
像棋手一样推演、像评审团一样博弈"。
"""


# ============================================================
# 1. 元学习（Meta-learning）—— 从"如何借鉴"中学习
# ============================================================
class MetaLearner:
    """
    从每次借鉴的复盘结果中，迭代"借鉴策略"（评估权重、阈值、取舍规则）。
    策略更新需人工审核后才全局生效（L2），避免单一案例过度拟合。
    """

    def __init__(self):
        self.strategy = {
            "fit_weights": {          # 契合度评分维度权重
                "game_type": 0.3,
                "audience": 0.2,
                "tech_stack": 0.2,
                "battle_depth": 0.15,
                "learning_curve": 0.15,
            },
            "fit_threshold": 60,      # 契合度及格线
        }
        self.meta_knowledge = []      # 元知识库（"如何评估"）

    def reflect(self, session, actual_feedback):
        """
        借鉴结束后复盘：评估"本次评估是否准确"。
        - session: 本次借鉴的决策单（含 fit_score）
        - actual_feedback: 落地后的实际反馈（玩家好评率、留存等）
        """
        predicted = session.get("fit_score")
        delta = predicted - actual_feedback.get("satisfaction", 0)
        if abs(delta) < 5:
            reflection = {"verdict": "accurate", "delta": delta}
        elif delta > 5:
            reflection = {"verdict": "over_estimated",
                          "delta": delta,
                          "hypothesis": "高估了某些维度权重",
                          "likely_dims": self._find_overweighted_dims(session)}
        else:
            reflection = {"verdict": "under_estimated",
                          "delta": delta,
                          "hypothesis": "低估了某些维度权重",
                          "likely_dims": self._find_underweighted_dims(session)}

        proposal = self._propose_strategy_update(reflection)
        self.meta_knowledge.append({"session_id": session.get("session_id"),
                                    "reflection": reflection,
                                    "proposal": proposal})
        return {"reflection": reflection, "proposal": proposal, "pending_review": True}

    def _find_overweighted_dims(self, session):
        # 定位可能与实际偏差相关的维度（启发式）
        return [dim for dim, w in self.strategy["fit_weights"].items() if w >= 0.25]

    def _find_underweighted_dims(self, session):
        return [dim for dim, w in self.strategy["fit_weights"].items() if w <= 0.15]

    def _propose_strategy_update(self, reflection):
        # 生成策略更新建议（需人工审核）
        if reflection["verdict"] == "over_estimated":
            return [{"key": f"fit_weights.{d}", "action": "decrease", "step": 0.05}
                    for d in reflection["likely_dims"]]
        if reflection["verdict"] == "under_estimated":
            return [{"key": f"fit_weights.{d}", "action": "increase", "step": 0.05}
                    for d in reflection["likely_dims"]]
        return []

    def apply_approved_update(self, updates):
        """人工审核通过后，应用策略更新（L2）。"""
        for u in updates:
            dim = u["key"].split(".")[-1]
            if dim in self.strategy["fit_weights"]:
                if u["action"] == "increase":
                    self.strategy["fit_weights"][dim] += u["step"]
                elif u["action"] == "decrease":
                    self.strategy["fit_weights"][dim] = max(
                        0, self.strategy["fit_weights"][dim] - u["step"])


# ============================================================
# 2. 树探索（Tree Search）—— 多分支推演 + 剪枝
# ============================================================
class TreeSearch:
    """
    对一个借鉴机制，分叉成多落地分支，每个分支评估收益/成本/风险，
    按置信度排序 + 剪枝，收敛到最优分支并保留备选。
    """

    def __init__(self, max_depth=2, prune_threshold=0.4):
        self.max_depth = max_depth
        self.prune_threshold = prune_threshold

    def explore(self, root_question, branch_generator, evaluator):
        """
        - branch_generator(question) -> list[Branch]
        - evaluator(branch) -> {score, reason, sub_branches?}
        """
        root = {"question": root_question, "branches": [], "depth": 0}
        self._expand(root, branch_generator, evaluator)
        self._prune(root)
        ranked = sorted(root["branches"], key=lambda b: -b["score"])
        return {
            "root_question": root_question,
            "branches": ranked,
            "recommended": ranked[0]["id"] if ranked else None,
            "backup": ranked[1]["id"] if len(ranked) > 1 else None,
            "depth": root["depth"],
            "confidence": ranked[0]["score"] / 100 if ranked else 0,
        }

    def _expand(self, node, branch_generator, evaluator, depth=0):
        if depth >= self.max_depth:
            return
        for branch in branch_generator(node["question"]):
            result = evaluator(branch)
            entry = {"id": branch.get("id"), "label": branch.get("label"),
                     "score": result.get("score", 0),
                     "reason": result.get("reason", ""),
                     "pruned": False, "sub_branches": []}
            node["branches"].append(entry)
            if result.get("sub_branches"):
                self._expand({"question": f"{node['question']} -> {branch['label']}",
                              "branches": entry["sub_branches"],
                              "depth": depth + 1},
                             branch_generator, evaluator, depth + 1)
            node["depth"] = max(node["depth"], depth + 1)

    def _prune(self, node):
        # 剪掉低分分支（相对最优的 prune_threshold 以下）
        if not node["branches"]:
            return
        best = max(b["score"] for b in node["branches"])
        for b in node["branches"]:
            if b["score"] < best * self.prune_threshold:
                b["pruned"] = True
            self._prune({"branches": b["sub_branches"], "depth": 0})


# ============================================================
# 3. 假设求证思维链（Hypothesis-Verification CoT）
# ============================================================
class HypothesisVerifier:
    """
    对每个借鉴决策先提可证伪假设，再收集证据求证，最终收敛结论。
    """

    HYPOTHESIS_TEMPLATE = (
        "对借鉴点 {mech}，我假设：\n"
        "  H1: {mech} 与自有游戏契合（因为 {reason1}）\n"
        "  H2: {mech} 与自有游戏不契合（因为 {reason2}）\n\n"
        "收集证据：\n"
        "  {evidence_list}\n\n"
        "验证：\n"
        "  {verification}\n\n"
        "收敛结论：{conclusion}"
    )

    def __init__(self):
        self.evidence_sources = ["player_feedback", "operational_data",
                                 "competitor", "technical"]

    def verify(self, mechanism, hypotheses, evidence):
        """
        - hypotheses: [{"id":"H1","claim":"契合","supporters":[...]}]
        - evidence: [{"text":..., "supports":["H1"], "source":...}]
        """
        scores = {h["id"]: 0 for h in hypotheses}
        for ev in evidence:
            for hid in ev.get("supports", []):
                scores[hid] += ev.get("weight", 1)

        best_h = max(hypotheses, key=lambda h: scores.get(h["id"], 0))
        total = sum(scores.values()) or 1
        confidence = scores.get(best_h["id"], 0) / total
        unverified = [h["id"] for h in hypotheses
                      if not scores.get(h["id"])]

        return {
            "winner": best_h["id"],
            "confidence": confidence,
            "scores": scores,
            "unverified_hypotheses": unverified,
            "evidence_count": len(evidence),
            "note": ("有未验证假设，证据不足" if unverified
                     else "假设均已验证"),
        }

    def build_chain(self, mechanism, hypotheses, evidence):
        """生成可读的假设求证思维链文本。"""
        result = self.verify(mechanism, hypotheses, evidence)
        evidence_lines = "\n".join(
            f"  E{i+1}: {ev['text']} (来源:{ev.get('source')}, 支持:{','.join(ev.get('supports',[]))})"
            for i, ev in enumerate(evidence))
        return self.HYPOTHESIS_TEMPLATE.format(
            mech=mechanism,
            reason1=hypotheses[0].get("reason", ""),
            reason2=hypotheses[1].get("reason", ""),
            evidence_list=evidence_lines,
            verification=f"  最佳假设 {result['winner']} 置信度 {result['confidence']:.2f}",
            conclusion=f"采纳 {result['winner']}，以匹配的落地形态实施",
        )


# ============================================================
# 4. 多 Agent 博弈（Multi-agent Debate）
# ============================================================
class DebateCoordinator:
    """
    用不同思维模式/不同 persona 的多个 Agent 对同一借鉴决策辩论、评审、投票。
    借鉴 dsh-router-standard 的"模式隔离子代理"：每个博弈 Agent 在隔离上下文跑。
    """

    DEFAULT_WEIGHTS = {
        "advocate": 0.3,   # 辩手 (react 模式)
        "reviewer": 0.3,   # 评审 (spec 模式)
        "skeptic": 0.2,    # 怀疑者 (weak 模式)
    }

    ROLES = {
        "advocate": {
            "mode": "react",
            "persona": "执行者，直接产出，论证'值得落地'，列收益与实现路径",
            "default_verdict": "support",
        },
        "reviewer": {
            "mode": "spec",
            "persona": "计划-集体，读优先，评估可行性/结构/路线图契合",
            "default_verdict": "conditional_support",
        },
        "skeptic": {
            "mode": "weak",
            "persona": "中性+分类，找风险/反例/边界情况/合规漏洞",
            "default_verdict": "oppose",
        },
    }

    def __init__(self, weights=None):
        self.weights = weights or dict(self.DEFAULT_WEIGHTS)
        self.role_mode_map = {r: v["mode"] for r, v in self.ROLES.items()}

    def spawn_debaters(self, decision):
        """
        生成博弈 Agent 配置（模式隔离）。返回各角色要独立评估的问题。
        """
        return {
            role: {
                "mode": cfg["mode"],
                "persona": cfg["persona"],
                "question": self._question_for(role, decision),
                "isolated": True,   # 模式隔离，独立 system prompt
            }
            for role, cfg in self.ROLES.items()
        }

    def _question_for(self, role, decision):
        prompts = {
            "advocate": f"论证借鉴决策「{decision}」值得落地：列出收益、亮点、实现路径。",
            "reviewer": f"评估借鉴决策「{decision}」的可行性、结构完整性与路线图契合度。",
            "skeptic": f"质疑借鉴决策「{decision}」：找出风险、反例、边界情况与合规漏洞。",
        }
        return prompts[role]

    def arbitrate(self, decision, verdicts):
        """
        仲裁加权综合三方意见，产出最终决策与置信度。
        - verdicts: {"advocate": {"verdict":"support","confidence":0.8}, ...}
        """
        # verdict 归一化分值
        score_map = {"support": 1.0, "conditional_support": 0.6,
                     "neutral": 0.5, "oppose": 0.0}
        total_weight = 0
        weighted = 0
        conditions = []
        for role, v in verdicts.items():
            w = self.weights.get(role, 0)
            total_weight += w
            weighted += w * score_map.get(v.get("verdict"), 0.5)
            if v.get("conditions"):
                conditions.extend(v["conditions"])

        confidence = weighted / total_weight if total_weight else 0.5
        if confidence >= 0.75:
            action = "采纳落地"
        elif confidence >= 0.5:
            action = "有条件采纳" + (f"（条件: {'; '.join(conditions)}）" if conditions else "")
        else:
            action = "建议不落地 / 需重新设计"

        return {
            "decision": decision,
            "participants": [{"role": r, **v} for r, v in verdicts.items()],
            "weighted_confidence": round(confidence, 2),
            "action": action,
            "conditions": conditions,
        }

    def adjust_weight(self, role, weight):
        """高风险决策可加大怀疑者权重（人机共治）。"""
        self.weights[role] = weight
