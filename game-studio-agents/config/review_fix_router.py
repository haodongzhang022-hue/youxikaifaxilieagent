# ============================================================
# 评审-修复闭环：上下文路由机制（Review-Fix Loop Router）
# 版本: v1.0
# 说明: 让「评审发现 bug → CodeBuddy 修复」闭环能**路由到原对话上下文**，
#       而非每次当作全新任务处理（上下文用上，问题更好解决）。
#
#   核心能力（对照「评审-修复闭环护栏」机制改进方向）：
#     1. 上下文路由（全局ID + sessionID）：提交 PR / 工作包时注册原对话上下文，
#        评审打回时按全局ID定位到原对话（sessionID），继承完整上下文与历史
#        评审-修复记录来修复 —— 信息细节不丢失，修复效果更强。
#     2. 降级显性化（哈希校验兜底）：当上下文路由不可用（如原对话已失效/未
#        注册 sessionID）时，**降级到哈希校验**做确定性兜底匹配；但降级**必须
#        显性输出说明**（route_fallback 告警 + 原因 + 丢失的信息），禁止静默
#        降级 —— 否则一旦崩了不修，会一直用哈希、丢失太多上下文信息细节，
#        导致修复效果持续变弱。
#
#   与其余模块解耦：本模块只负责「评审-修复闭环」的上下文路由与降级判定，
#   不依赖具体岗位/部门/Agent 实现，任何调用方（流水线、编排器、测试）均
#   可独立复用，避免分支耦合冲突。
# 语言: Python 3 (可运行)
# ============================================================
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# 路由模式
ROUTE_SESSION = "session_route"   # 上下文路由：全局ID + sessionID 定位原对话
ROUTE_HASH = "hash_fallback"      # 降级：哈希校验兜底（丢失对话上下文细节）


@dataclass
class ReviewFixContext:
    """一次评审-修复闭环的上下文（全局ID + sessionID 定位原对话）。

    保存提交时注册的原始上下文，以及历次评审-修复记录（history），
    使后续修复能继承完整的上下文细节，而非降级成哈希做无上下文匹配。
    """
    global_id: str                                  # 全局ID：PR / 工作包唯一标识
    session_id: str                                 # sessionID：原对话会话标识
    payload: Dict[str, Any] = field(default_factory=dict)   # 提交时的上下文内容
    history: List[Dict[str, Any]] = field(default_factory=list)  # 历次评审-修复记录
    created_at: float = field(default_factory=time.time)


class ReviewFixRouter:
    """评审-修复闭环的上下文路由机制。

    流程：
      1. register_context(global_id, session_id, payload)
         —— 提交 PR / 工作包时注册原对话上下文（可路由）；
      2. route_review(global_id, review)
         —— 评审打回时，优先路由到原对话上下文（session_route）；
            路由不可用时降级到哈希校验（hash_fallback），**必须显性输出降级说明**。
      3. record_fix(global_id, fix) —— 把一次修复记录追加到上下文历史。
    """

    def __init__(self) -> None:
        self._contexts: Dict[str, ReviewFixContext] = {}  # global_id -> 上下文
        self._fallbacks: Dict[str, Dict[str, Any]] = {}   # global_id -> 降级记录
        self._log_fn = lambda *a, **k: None

    def set_logger(self, log_fn: Any) -> None:
        """注入日志回调（便于测试/编排器统一收集告警）。"""
        self._log_fn = log_fn

    # ---------- 1. 注册上下文（提交时） ----------
    def register_context(self, global_id: str, session_id: str,
                         payload: Dict[str, Any]) -> None:
        """提交 PR / 工作包时注册原对话上下文，使该 global_id 可走上下文路由。"""
        self._contexts[global_id] = ReviewFixContext(
            global_id=global_id, session_id=session_id, payload=payload)

    def has_context(self, global_id: str) -> bool:
        return global_id in self._contexts

    def get_context(self, global_id: str) -> Optional[ReviewFixContext]:
        return self._contexts.get(global_id)

    # ---------- 2. 评审打回 → 路由 ----------
    def route_review(self, global_id: str, review: Dict[str, Any]
                     ) -> Tuple[Optional[ReviewFixContext], str, bool]:
        """评审打回 → 路由到上下文。

        返回 (context, route_mode, degraded)：
          - context：命中的原对话上下文；路由不可用时为 None；
          - route_mode：ROUTE_SESSION（上下文路由）或 ROUTE_HASH（降级哈希校验）；
          - degraded：本次是否发生降级（True = 降级到哈希校验）。
        降级到哈希校验时，本方法**必输出显性降级说明**（route_fallback 告警 +
        原因 + 丢失的信息），绝不静默降级。
        """
        ctx = self._contexts.get(global_id)
        if ctx is not None:
            # 上下文路由成功：全局ID + sessionID 定位到原对话，继承完整上下文。
            ctx.history.append({"ts": time.time(), "type": "review", "data": review})
            return ctx, ROUTE_SESSION, False

        # 降级到哈希校验兜底：显性说明降级原因与丢失的信息细节。
        fb = self._hash_fallback(global_id, review)
        self._fallbacks[global_id] = fb
        # —— 显性降级说明（禁止静默降级）——
        self._log_fn(
            "route_fallback",
            f"评审打回 {global_id} 无法路由到原对话上下文（无 sessionID 注册记录），"
            f"已降级为哈希校验兜底。降级原因: {fb['reason']}。"
            f"本次丢失的上下文信息: {fb['lost_info']}。"
            f"降级后修复仅依赖 {fb['mode']}，信息细节少于上下文路由，效果可能变弱；"
            f"请尽快恢复上下文注册以避免持续丢失上下文。")
        return None, ROUTE_HASH, True

    def _hash_fallback(self, global_id: str, review: Dict[str, Any]) -> Dict[str, Any]:
        """哈希校验兜底：基于 global_id + 评审内容做确定性匹配。

        ⚠️ 这只是无上下文时的降级匹配：**不携带任何对话历史/上下文细节**，
        仅能按内容哈希稳定识别「同一份评审」，无法理解修复对象的背景与来龙去脉，
        因此信息量显著少于上下文路由，修复效果会变弱。降级必须显性说明。
        """
        digest = hashlib.sha256(
            (global_id + "|" + json.dumps(review, sort_keys=True, ensure_ascii=False)
             ).encode("utf-8")).hexdigest()[:16]
        return {
            "mode": ROUTE_HASH,
            "digest": digest,
            "reason": "未注册 sessionID，原对话上下文不可路由",
            "lost_info": "对话历史、提交时上下文、历次评审-修复记录（history）",
        }

    def is_degraded(self, global_id: str) -> bool:
        return global_id in self._fallbacks

    def get_fallback(self, global_id: str) -> Optional[Dict[str, Any]]:
        return self._fallbacks.get(global_id)

    # ---------- 3. 记录修复 ----------
    def record_fix(self, global_id: str, fix: Dict[str, Any]) -> None:
        """把一次修复记录追加到上下文历史（仅上下文路由可积累；哈希降级无历史）。"""
        ctx = self._contexts.get(global_id)
        if ctx is not None:
            ctx.history.append({"ts": time.time(), "type": "fix", "data": fix})
        else:
            # 降级场景无上下文可积累历史：显性提示（与 route_review 的降级说明呼应）。
            self._log_fn(
                "record_fix_no_context",
                f"修复 {global_id} 时无上下文可记录历史（哈希降级中），"
                f"本次修复信息不会沉淀，无法被后续上下文路由复用。")

    # ---------- 闭环健康判别（区分「正常待评审」与「真正闭环中断」） ----------
    LOOP_PENDING_REVIEW = "pending_review"   # 正常待评审：修复已 push，新评审下一轮才产生
    LOOP_INTERRUPTED = "interrupted"         # 真正闭环中断：须满足至少一个硬性信号
    LOOP_OK = "ok"                           # 闭环正常：已有评审结论

    def classify_loop_state(self, global_id: str, has_newest_review: bool = False,
                            push_success: bool = True, review_timeout: bool = False,
                            rounds_over_limit: bool = False) -> str:
        """判别评审闭环当前处于「正常待评审」还是「真正闭环中断」。

        规则（对应「评审修复闭环护栏」第七章判别规则，防误报）：
          - 真正中断：须满足**至少一个硬性信号**——
            ① push 失败（403 权限缺失，修复根本没推上去）；
            ② push 成功但长时间无后续评审 run 跟进（review_timeout）；
            ③ 评审长期停留"需修改"且超轮次上限未收敛（rounds_over_limit）。
          - 正常待评审：push 成功且已触发新一轮评审事件，但**最新 head 评审结论尚未
            产生**（has_newest_review=False）——这是修复 push 后、新评审在下一轮才产生的
            **正常状态**，禁止仅因"暂无最新评审结论"就误判中断。
          - 闭环正常：最新 head 已有评审结论（has_newest_review=True）且无硬性中断信号。
        """
        # 先判硬性中断信号（任一命中即为真正中断，优先于"暂无评审结论"）。
        if not push_success or review_timeout or rounds_over_limit:
            return self.LOOP_INTERRUPTED
        # 无硬性中断信号 + 已有最新评审结论 → 闭环正常。
        if has_newest_review:
            return self.LOOP_OK
        # push 成功、无硬性中断信号、仅"最新 head 暂无评审结论" → 正常待评审（不误报）。
        return self.LOOP_PENDING_REVIEW

    # ---------- 诊断 ----------
    def summary(self) -> Dict[str, Any]:
        """路由机制运行概况：上下文路由 vs 降级哈希校验的使用统计。"""
        session_ids = {c.session_id for c in self._contexts.values()}
        return {
            "context_registered": len(self._contexts),
            "session_ids": sorted(session_ids),
            "hash_fallback_count": len(self._fallbacks),
            "degraded": sorted(self._fallbacks.keys()),
        }


# ============================================================
# 自测（python review_fix_router.py 可运行）
# ============================================================
if __name__ == "__main__":
    logs = []

    def _log(tag, msg):
        logs.append((tag, msg))

    r = ReviewFixRouter()
    r.set_logger(_log)

    # 场景1：上下文路由（全局ID + sessionID 定位原对话）
    r.register_context("PR-23", "session_abc123", {"module": "server", "role": "cto"})
    ctx, mode, degraded = r.route_review("PR-23", {"issue": "负载均衡"})
    assert mode == ROUTE_SESSION and not degraded and ctx is not None
    r.record_fix("PR-23", {"fix": "负载均衡修复"})
    assert len(ctx.history) == 2  # 1 review + 1 fix

    # 场景2：路由不可用 → 降级到哈希校验，**必须显性输出降级说明**
    ctx2, mode2, degraded2 = r.route_review("PR-99", {"issue": "无上下文"})
    assert mode2 == ROUTE_HASH and degraded2 and ctx2 is None
    assert any(tag == "route_fallback" for tag, _ in logs), "必须显性输出降级说明"
    assert r.is_degraded("PR-99")

    print("上下文路由: PR-23 命中 session_abc123，history=%d 条" % len(ctx.history))
    print("降级显性化: PR-99 降级哈希校验，显性说明=%s" %
          any(tag == "route_fallback" for tag, _ in logs))
    print("汇总:", r.summary())
    print("评审-修复闭环上下文路由自测通过 ✅")
