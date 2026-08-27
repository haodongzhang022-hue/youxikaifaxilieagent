# ============================================================
# 合并确认 Agent（Merged Confirm Agent）
# 版本: v1.0
# 说明: 针对被打上「已合并」标签但状态仍为 open 的 Issue，
#       由「合并确认员」角色（与评审机制类似但独立于 CodeBuddy）
#       进行工作内容确认：判断当前对话是否还有内容需要推进，
#       还是已适合关闭 / 需要新建 Issue 承接后续任务。
#
#   核心能力（对照用户需求「类似审查机制，探查合并标签 issue 个数」）：
#     1. 探查（probe）：列出仓库中所有「已合并」标签 + open 状态的 Issue，
#        计算数量 N。N > 0 即触发确认工作流。
#     2. 确认（confirm）：对每个待确认 Issue，评估其「是否还有内容需要推进」：
#        - 已合并且无未解决的后续任务 → 建议关闭（CLOSE）；
#        - 已合并但有明确的后续任务 → 建议新建 Issue 承接并关闭原 Issue
#          （REOPEN_AS_NEW，原 Issue 关闭，新 Issue 派发）；
#        - 已合并但存在阻塞 / 待复核 / 依赖未收尾 → 建议保留（KEEP）。
#     3. 决策路由（decision）：把评估结果整理成结构化决策表，供「合并确认员」
#        NPC 读取后在 Issue 评论中输出，并按决策执行关闭 / 新建 / 保留。
#
#   与其余模块解耦：本模块只负责「合并标签 Issue 的确认判定」，
#   不依赖具体岗位/部门/Agent 实现，任何调用方（流水线、编排器、测试）
#   均可独立复用。
# 语言: Python 3 (可运行)
# ============================================================
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# 决策类型
DECISION_CLOSE = "close"            # 建议关闭：已合并且无后续任务
DECISION_NEW_ISSUE = "new_issue"    # 建议新建 Issue 承接后续，并关闭原 Issue
DECISION_KEEP = "keep"              # 建议保留：仍有阻塞/待复核/依赖未收尾

# Issue 状态
ISSUE_OPEN = "open"
ISSUE_CLOSED = "closed"


@dataclass
class MergedIssue:
    """一个带「已合并」标签的 Issue 快照。

    记录探查到的原始信息（标题/描述/标签/评论数/关联 PR），
    以及确认员对它的判定（decision + reason + 建议动作）。
    """
    number: str                                       # Issue 编号
    title: str                                        # 标题
    state: str                                        # open / closed
    body: str = ""                                    # 描述
    labels: List[str] = field(default_factory=list)   # 标签名列表
    comment_count: int = 0                            # 评论数
    merged_label: str = ""                            # 命中的「已合并」标签名
    linked_pr: Optional[str] = None                   # 关联 PR 编号（若能解析）
    # 确认结果
    decision: str = DECISION_KEEP                     # 判定
    reason: str = ""                                  # 判定理由
    suggested_action: str = ""                        # 建议动作（供 NPC 执行）
    checked_at: float = field(default_factory=time.time)


class MergedConfirmAgent:
    """合并确认 Agent 核心逻辑。

    工作流：
      1. probe(issues) —— 输入仓库 Issue 列表，筛出「已合并标签 + open」的候选；
      2. confirm(candidates) —— 对每个候选做确认判定（基于规则启发式）；
      3. decide() —— 汇总决策表，输出结构化结果供「合并确认员」NPC 使用。
    """

    # 匹配的「已合并」标签关键词（支持模糊匹配，如「安全加固已合并」「经理编排已合并」）
    MERGED_LABEL_KEYWORDS = ("已合并", "已合入", "merged")

    def __init__(self, log_fn: Any = None) -> None:
        self._log = log_fn or (lambda *a, **k: None)
        self._candidates: List[MergedIssue] = []
        self._decided: List[MergedIssue] = []

    # ---------- 1. 探查：筛出「已合并标签 + open」的 Issue ----------
    def probe(self, issues: List[Dict[str, Any]]) -> List[MergedIssue]:
        """从传入的 Issue 列表筛出「带已合并标签且 open」的候选。

        issues 形如：[{number, title, state, body, labels:[{name}], comment_count}]
        """
        candidates = []
        for it in issues:
            state = it.get("state", "").lower()
            if state != ISSUE_OPEN:
                continue
            labels = [lb.get("name", "") if isinstance(lb, dict) else str(lb)
                      for lb in it.get("labels", [])]
            merged_label = self._find_merged_label(labels)
            if not merged_label:
                continue
            mi = MergedIssue(
                number=str(it.get("number", "")),
                title=it.get("title", ""),
                state=state,
                body=it.get("body", ""),
                labels=labels,
                comment_count=it.get("comment_count", 0),
                merged_label=merged_label,
                linked_pr=self._extract_linked_pr(it.get("body", "")),
            )
            candidates.append(mi)

        self._candidates = candidates
        self._log("probe", f"探查到 {len(candidates)} 个「已合并标签 + open」Issue")
        return candidates

    def _find_merged_label(self, labels: List[str]) -> Optional[str]:
        """在标签列表中匹配「已合并」相关标签（大小写不敏感）。"""
        lb_lower = {lb.lower() for lb in labels}
        for lb in labels:
            for kw in self.MERGED_LABEL_KEYWORDS:
                if kw.lower() in lb.lower():
                    return lb
        return None

    @staticmethod
    def _extract_linked_pr(body: str) -> Optional[str]:
        """从 Issue 描述中尝试解析关联 PR 编号（如 PR #15 / pulls/15）。"""
        if not body:
            return None
        m = re.search(r"(?:PR\s*#|pulls/)(\d+)", body)
        return f"#{m.group(1)}" if m else None

    # ---------- 2. 确认：对每个候选做判定 ----------
    def confirm(self, candidates: Optional[List[MergedIssue]] = None) -> List[MergedIssue]:
        """对候选做确认判定，产出决策。

        判定规则（启发式）：
          - 若评论数 >= 1 且描述中无「下一阶段/待联动/继续/待推进」等后续关键词
            → 判定 CLOSE（已合并且无后续任务）；
          - 若描述或标签中明确含「下一阶段/待联动/待推进」等后续关键词
            → 判定 NEW_ISSUE（有后续任务，需新建 Issue 承接）；
          - 若评论数较多（>= 5）且仍在 open，可能仍有讨论在推进
            → 判定 KEEP（保守保留，避免误关）。
        """
        targets = candidates if candidates is not None else self._candidates
        decided = []
        for mi in targets:
            decision, reason, action = self._evaluate(mi)
            mi.decision = decision
            mi.reason = reason
            mi.suggested_action = action
            decided.append(mi)
        self._decided = decided
        return decided

    def _evaluate(self, mi: MergedIssue):
        """单个 Issue 的确认判定（启发式规则）。"""
        title = mi.title or ""
        body = mi.body or ""
        joined = f"{title} {body}".lower()

        # —— 下游已承接信号：仅当命中「明确承接语义 + 具体 Issue 锚点（#编号）」才判定已派发 → CLOSE ——
        # 「已由 #xx 承接」「解锁自 #3」「下游工作包 #7」「#xx 承接」等明确承接才落地；
        # 「该需求由 #100 提出」「已完成，关联 #55」（来源/关联引用）不判定为下游已承接；
        # 「已由负责人正在讨论」「承接中」「Ref:（未带编号）」等未落地表述也不判定。
        downstream_handled_re = re.compile(
            r'(?:已由)\s*#\d+(?:/\s*#?\d+)*\s*(?:承接|派发|落地|负责|跟进|处理)'
            r'|(?:解锁自)\s*#\d+'
            r'|(?:下游工作包)\s*#\d+'
            r'|#\d+\s*(?:承接|派发|落地)',
            re.IGNORECASE)
        has_downstream = bool(downstream_handled_re.search(joined))

        # 阻塞 / 待复核：仅「状态前缀(待/未/仍/还有)+主题词」组合才算未完成 → KEEP
        # 「已通过评审」「已修复 bug」等已完成表述不再误判为 KEEP。
        block_patterns = [
            r'(?:待|未|仍|还有)(?:评审|复核|修复|处理|解决|返工|人工|确认|收尾)',
            r'(?:仍有|还有)(?:阻塞|卡住|问题)',
            r'(?:被驳回|待人工|需要人工)',
        ]
        block_keywords = ["阻塞", "卡住", "返工"]
        has_block = (any(re.search(pt, joined) for pt in block_patterns)
                     or any(kw.lower() in joined for kw in block_keywords))

        # —— 否定前缀 / 完成态剥离（Bug A 防护）——
        # 「无后续任务」「没有后续推进」「后续任务已完成落地」等否定/完成态表述
        # 不应触发 NEW_ISSUE，应判 CLOSE。先剥离否定与完成态语境再判后续关键词。
        stripped = re.sub(
            r'(?:无|没有|不需要|不再|未|尚未)\s*(?:后续|下一阶段|下一步|待推进|待实施|后续任务|后续推进)',
            ' ', joined)
        stripped = re.sub(
            r'(?:后续任务|后续推进|后续待办|待收尾|下一阶段|下一步|待推进|待实施)\s*(?:已完成|已落地|已收尾|已实施|已实现|已推进完|已完工|已结束)',
            ' ', stripped)

        # 后续推进关键词（命中且无下游承接 → 判定 NEW_ISSUE）
        # 注意：不再用宽泛的「后续」（「后续方案/后续讨论」等模糊表述易误判），
        #       只用能表达「明确未派发后续任务」的精准关键词。
        #       裸版本号 v0.9/v1.0/v2 也会被「已上线」等完成态提及，不再单独判 NEW，
        #       改为「阶段前缀 + 版本号」组合正则才判 NEW。
        next_keywords = [
            "下一阶段", "待联动", "待推进", "待实施", "继续完善", "继续推进",
            "待收尾", "下一步", "下一阶段v", "待派发",
            "待合并", "待合入", "待验收", "待回归", "后续任务", "后续推进",
            "有待推进", "后续待办", "下一轮", "二期",
        ]
        next_version_re = re.compile(
            r'(?:下一阶段|待联动|待推进|待实施|二期)\s*v?\d+(?:\.\d+)*', re.IGNORECASE)
        has_next_version = bool(next_version_re.search(stripped))
        # 后续未派发才判定 NEW_ISSUE；若已带编号被下游承接则不算"未派发的后续"
        has_next = (any(kw.lower() in stripped for kw in next_keywords)
                    or has_next_version) and not has_downstream

        # 模糊讨论中（无明确承接对象/目标/排期）→ 保守 KEEP，不新建 Issue 不关闭
        vague_discussion_patterns = [
            r'(?:正在|仍在|还在)(?:讨论|研究|探讨|规划|筹备)',
            r'(?:待|尚待|还需)(?:讨论|研究|确认|明确)',
            r'(?:负责人|相关方)(?:正在|仍在)(?:讨论|推进|跟踪)',
            r'(?:讨论中|研究中|探讨中)',
        ]
        has_vague_discussion = any(re.search(pt, stripped) for pt in vague_discussion_patterns)

        # 评论数多且 open，可能仍在推进 → 保守 KEEP
        active_discussion = mi.comment_count >= 5 and not has_downstream

        if has_block:
            return (DECISION_KEEP,
                    f"Issue #{mi.number} 命中阻塞/待复核关键词，可能仍有依赖或阻塞未收尾",
                    "保留 Issue，交由对应负责人继续推进，暂不关闭")
        # 下游已承接优先于模糊讨论：既有明确承接锚点又提及「正在讨论」，优先判定 CLOSE
        if has_downstream:
            return (DECISION_CLOSE,
                    f"Issue #{mi.number} 已合并（标签「{mi.merged_label}」），后续任务已由下游 Issue 承接",
                    "关闭 Issue（工作已完成，后续已派发到新 Issue）")
        if has_vague_discussion and not has_next:
            return (DECISION_KEEP,
                    f"Issue #{mi.number} 仍处于模糊讨论/规划阶段（无明确承接对象或排期）",
                    "保留 Issue，待讨论收敛后再评估关闭或新建承接")
        if has_next:
            return (DECISION_NEW_ISSUE,
                    f"Issue #{mi.number} 已合并但描述/标签明确有「下一阶段/待联动/待推进」等后续任务且未派发",
                    "新建 Issue 承接后续任务，并关闭原 Issue（保留合并记录）")
        if active_discussion:
            return (DECISION_KEEP,
                    f"Issue #{mi.number} 评论数较多（{mi.comment_count}）且状态仍 open，可能仍有讨论在推进",
                    "保留 Issue，待讨论收敛后再评估是否关闭")
        # 已合并且无明确后续 → 关闭
        return (DECISION_CLOSE,
                f"Issue #{mi.number} 已合并（标签「{mi.merged_label}」），且无后续推进/阻塞信号",
                "关闭 Issue（工作已完成，无待推进内容）")

    # ---------- 3. 汇总决策 ----------
    def decide(self) -> Dict[str, Any]:
        """输出结构化决策表，供「合并确认员」NPC 在 Issue 评论中使用。

        调用顺序约定：probe() → confirm() → decide()。
        若未 confirm() 但已存在候选，此处自动补齐 confirm()，
        确保 probed_count 与 decided 语义一致（probed_count>0 时 decided 不会为空）。
        """
        if not self._decided and self._candidates:
            # 未显式 confirm 但有候选：自动补齐确认，避免 probed/decided 自相矛盾
            self.confirm()
        return {
            "probed_count": len(self._candidates),
            "decided": [
                {
                    "number": mi.number,
                    "title": mi.title,
                    "merged_label": mi.merged_label,
                    "linked_pr": mi.linked_pr,
                    "decision": mi.decision,
                    "reason": mi.reason,
                    "suggested_action": mi.suggested_action,
                }
                for mi in self._decided
            ],
            "close_count": sum(1 for m in self._decided if m.decision == DECISION_CLOSE),
            "new_issue_count": sum(1 for m in self._decided if m.decision == DECISION_NEW_ISSUE),
            "keep_count": sum(1 for m in self._decided if m.decision == DECISION_KEEP),
            "checked_at": time.time(),
        }

    # ---------- 汇总统计 ----------
    def summary(self) -> Dict[str, Any]:
        return {
            "candidates": [{"number": m.number, "title": m.title,
                            "merged_label": m.merged_label} for m in self._candidates],
            "probed_count": len(self._candidates),
        }


# ============================================================
# 自测（python merged_confirm_agent.py 可运行）
# ============================================================
if __name__ == "__main__":
    logs = []
    def _log(tag, msg): logs.append((tag, msg))

    a = MergedConfirmAgent(log_fn=_log)

    # 模拟一组仓库 Issue（含已合并标签 + open / closed / 无标签等）
    issues = [
        {
            "number": "14", "state": "open",
            "title": "安全改进",
            "body": "安全加固已合并，鉴权回归已完成，下游工作包已由 #24 承接",
            "labels": [{"name": "安全加固已合并"}],
            "comment_count": 4,
        },
        {
            "number": "10", "state": "open",
            "title": "对比借鉴开源项目",
            "body": "经理编排已合并，v0.7 已联动完成，下游已由 #16/#19 承接",
            "labels": [{"name": "经理编排已合并"}, {"name": "v0.7待联动"}],
            "comment_count": 9,
        },
        {
            "number": "8", "state": "open",
            "title": "补充各个岗位的各个角色的内容",
            "body": "预设体系已合并，下一阶段v0.8 已由 #19 承接",
            "labels": [{"name": "预设体系已合并"}],
            "comment_count": 10,
        },
        {
            "number": "1", "state": "open",
            "title": "先探查当前游戏开发一般工作岗位",
            "body": "生态角色体系已合并，下一阶段：生态角色接入流水线 已由 #27 承接",
            "labels": [{"name": "生态角色体系已合并"}],
            "comment_count": 7,
        },
        {
            "number": "24", "state": "closed",
            "title": "安全加固下游",
            "body": "已完成",
            "labels": [{"name": "下游工作包"}],
            "comment_count": 1,
        },
        {
            "number": "29", "state": "open",
            "title": "跨仓库调用agent团队协助的能力的设置",
            "body": "跨仓库调用能力已合并，但仍有下一阶段待推进，未派发完成",
            "labels": [{"name": "跨仓库已合并"}, {"name": "下一阶段"}],
            "comment_count": 3,
        },
        {
            "number": "30", "state": "open",
            "title": "讨论中的功能",
            "body": "已合并，已由负责人正在讨论后续方案",
            "labels": [{"name": "已合并"}],
            "comment_count": 2,
        },
    ]

    candidates = a.probe(issues)
    print(f"探查: 命中 {len(candidates)} 个「已合并标签 + open」Issue")
    for c in candidates:
        print(f"  #{c.number} {c.title}  标签={c.merged_label}")

    decided = a.confirm()
    result = a.decide()
    print(f"\n确认判定:")
    for d in result["decided"]:
        print(f"  #{d['number']} [{d['decision']}] {d['reason']}")

    print(f"\n统计: close={result['close_count']} new_issue={result['new_issue_count']} keep={result['keep_count']}")

    # 断言
    assert result["probed_count"] == 6, "应探查到 6 个候选（#14/#10/#8/#1 合并 + #29 下一阶段 + #30 模糊讨论）"
    assert any(d["number"] == "14" and d["decision"] == "close" for d in result["decided"]), \
        "#14 应判定 close（下游已由 #24 承接）"
    assert any(d["number"] == "10" and d["decision"] == "close" for d in result["decided"]), \
        "#10 应判定 close（下游已由 #16/#19 承接）"
    assert any(d["number"] == "8" and d["decision"] == "close" for d in result["decided"]), \
        "#8 应判定 close（下游已由 #19 承接）"
    assert any(d["number"] == "1" and d["decision"] == "close" for d in result["decided"]), \
        "#1 应判定 close（下游已由 #27 承接）"
    assert any(d["number"] == "29" and d["decision"] == "new_issue" for d in result["decided"]), \
        "#29 应判定 new_issue（有下一阶段但未派发）"
    assert any(d["number"] == "30" and d["decision"] == "keep" for d in result["decided"]), \
        "#30 应判定 keep（模糊讨论中，不新建不关闭）"
    print("\n合并确认 Agent 自测通过 ✅")
