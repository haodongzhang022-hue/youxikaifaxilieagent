# ============================================================
# 框架自升级闭环 · 共享记忆接线 (Framework Upgrade Memory)
# 版本: v1.0
# 说明: wp_server（程序线·cto）的落地产出。
#       把 loc://memory.framework_upgrade.* 与 game-architect-team/src/
#       shared_memory.py 的 SharedMemory 对接接线，补齐 UPG 编号递增规则，
#       让框架升级记录按「触发→评估→人类 CP 拍板→落地走 PR→留痕」闭环
#       沉淀进共享记忆（只增不改只追加）。
#
# 三条核心能力：
#   1. FrameworkUpgradeMemory：连接 SharedMemory，注册 framework_upgrade 空间；
#   2. UPG 编号递增规则：自动生成 UPG-001 / UPG-002 / ...（从共享记忆读取
#      已有记录最大值，保证跨实例不重复）；
#   3. 四环节闭环留痕：触发→评估→决策→落地，每个环节可独立追加记录。
#
# 对接说明（评审改进①）：
#   - SharedMemory 原生使用 loc://memory.<space>.<kind>.<seq> 格式，
#     framework_upgrade 空间直接复用该格式，无需修改 SharedMemory 内核；
#   - 本模块作为「集成桥」，把 policy 文档中定义的写入位置
#     loc://memory.framework_upgrade.{content|task|skill}.<seq> 映射到
#     SharedMemory.add_record() / revise() 的真实调用。
#
# 语言: Python 3 (可运行)
# 依赖: ../../game-architect-team/src/shared_memory.py（共享记忆实现）
# ============================================================
from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional

# ---- 接入 SharedMemory（从 game-architect-team/src 导入）----
_SHARED_MEMORY_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "game-architect-team", "src"))
if _SHARED_MEMORY_DIR not in sys.path:
    sys.path.insert(0, _SHARED_MEMORY_DIR)
from shared_memory import SharedMemory, SharedMemoryRecord

# ============================================================
# 常量
# ============================================================

# framework_upgrade 功能空间名（对齐 FRAMEWORK_UPGRADE.md 5.3 节）
FRAMEWORK_UPGRADE_SPACE = "framework_upgrade"

# 可写该空间的 agent（程序线 cto / server_dev）
ALLOWED_WRITERS = ["cto", "server_dev", "producer", "data_analyst"]

# 升级记录字段（对齐 FRAMEWORK_UPGRADE.md 5.1 节）
UPGRADE_FIELDS = [
    "upgrade_id", "trigger", "scope", "risk", "priority",
    "decision", "implemented", "timestamp", "status",
]

# 默认权限：同空间可读写；外空间只读
_DEFAULT_ACL = "rw"

# ============================================================
# UPG 编号规则
# ============================================================

def next_upg_id(memory: SharedMemory) -> str:
    """生成下一个 UPG 编号（UPG-XXX，自动递增）。

    规则（评审改进②）：
      1. 扫描共享记忆 framework_upgrade 空间中全部 content 记录，
         取已有 upgrade_id 的 max 数值；
      2. 不存在记录 → 从 UPG-001 开始；
      3. 存在记录 → max+1（如已有 UPG-001、UPG-003，下一个是 UPG-004）；
      4. 跨实例安全：任何实例调用都能从共享记忆读到已有最大值，
         不依赖本地状态，保证唯一不重复。
    """
    max_num = 0
    # 扫描全部 active 记录，不依赖关键词匹配，保证不漏
    for r in memory._records.values():
        if r.space != FRAMEWORK_UPGRADE_SPACE:
            continue
        if r.kind != "content":
            continue
        upg_id = r.content.get("upgrade_id", "")
        if upg_id and upg_id.startswith("UPG-"):
            try:
                num = int(upg_id.split("-")[1])
                max_num = max(max_num, num)
            except (ValueError, IndexError):
                continue
    return f"UPG-{max_num + 1:03d}"


# ============================================================
# 框架升级记忆桥
# ============================================================

class FrameworkUpgradeMemory:
    """框架升级共享记忆桥。

    把 FRAMEWORK_UPGRADE.md 定义的 loc://memory.framework_upgrade.*
    写入位置与 SharedMemory 对接，提供四环节闭环的便捷 API：
      - record_trigger(): 记录触发信号
      - record_evaluation(): 记录评估报告
      - record_decision(): 记录人类 CP 拍板结果
      - record_implementation(): 记录落地执行与 PR
      - record_upgrade(): 一条命令完整留痕（便捷封装）
    全部遵循「只增不改只追加」，写入后不可删改。
    """

    def __init__(self, memory: Optional[SharedMemory] = None):
        self.memory = memory or SharedMemory()
        # 设置空间 ACL
        for writer in ALLOWED_WRITERS:
            self.memory.set_acl(FRAMEWORK_UPGRADE_SPACE, writer, "rw")

    # ---- 内部工具：把升级记录写入共享记忆 ----
    def _add(self, kind: str, content: Dict[str, Any],
             owner: str = "cto") -> SharedMemoryRecord:
        """向 framework_upgrade 空间追加一条记录（只增）。

        内部实现，外部请优先使用公开方法 add_record()。
        """
        return self.memory.add_record(
            FRAMEWORK_UPGRADE_SPACE, kind, content,
            owner=owner, acl_check=owner)

    def add_record(self, kind: str, content: Dict[str, Any],
                   owner: str = "cto") -> SharedMemoryRecord:
        """公开接口：向 framework_upgrade 空间追加一条记录（只增）。

        Args:
            kind:    记录类型（content / task / skill）
            content: 记录内容（字典）
            owner:   记录者（默认 cto）

        Returns:
            新写入的 SharedMemoryRecord。
        """
        return self._add(kind, content, owner=owner)

    def _revise(self, mem_id: str, new_content: Dict[str, Any],
                owner: str = "cto", weight_delta: float = 0.3) -> SharedMemoryRecord:
        """修订（追加新版本，原记录标 superseded 保留）。"""
        return self.memory.revise(
            mem_id, new_content, weight_delta=weight_delta, acl_check=owner)

    # ---- 环节 1：记录触发信号 ----
    def record_trigger(self, trigger: str, details: Dict[str, Any],
                       upg_id: str = "", owner: str = "cto") -> SharedMemoryRecord:
        """记录框架升级触发信号。

        Args:
            trigger: 触发条件（新调研 P0 / 评审反复≥3次 / 用户诉求 /
                     10轮超限 / 多源叠加）
            details: 触发详情（影响面初判 / 相关 Issue / PR 链接等）
            upg_id:  关联的升级标识（如 UPG-001），可选
            owner:   记录者（默认 cto）
        """
        content = {
            "type": "trigger",
            "trigger": trigger,
            "details": details or {},
        }
        if upg_id:
            content["upgrade_id"] = upg_id
        return self._add("content", content, owner=owner)

    # ---- 环节 2：记录评估报告 ----
    def record_evaluation(self, upg_id: str,
                          impact: Dict[str, Any],
                          feasibility: Dict[str, Any],
                          risk: Dict[str, Any],
                          priority: str,
                          owner: str = "cto") -> SharedMemoryRecord:
        """记录升级评估报告（影响面 / 可行性 / 风险 / 优先级）。

        Args:
            upg_id:      升级标识（如 UPG-001）
            impact:      影响面评估结果
            feasibility: 可行性评估结果
            risk:        风险评估结果（含缓解措施）
            priority:    P0 / P1 / P2
            owner:       记录者（默认 cto）
        """
        content = {
            "type": "evaluation",
            "upgrade_id": upg_id,
            "impact": impact or {},
            "feasibility": feasibility or {},
            "risk": risk or {},
            "priority": priority,
        }
        return self._add("content", content, owner=owner)

    # ---- 环节 3：记录人类 CP 拍板结果 ----
    def record_decision(self, upg_id: str, decision: str,
                        reason: str = "",
                        owner: str = "producer") -> SharedMemoryRecord:
        """记录人类 CP 拍板结果。

        Args:
            upg_id:   升级标识（如 UPG-001）
            decision: 批准 / 打回 / 搁置
            reason:   拍板原因（可选）
            owner:    记录者（默认 producer）
        """
        content = {
            "type": "decision",
            "upgrade_id": upg_id,
            "decision": decision,
            "reason": reason or "",
        }
        return self._add("content", content, owner=owner)

    # ---- 环节 4：记录落地执行 ----
    def record_implementation(self, upg_id: str,
                              tasks: List[str],
                              pr_links: List[str],
                              version: str,
                              status: str = "active",
                              owner: str = "cto") -> SharedMemoryRecord:
        """记录落地执行与留痕。

        Args:
            upg_id:    升级标识（如 UPG-001）
            tasks:     落地子任务列表
            pr_links:  关联 PR 链接列表
            version:   框架版本号（如 v0.7）
            status:    active / superseded
            owner:     记录者（默认 cto）
        """
        content = {
            "type": "implementation",
            "upgrade_id": upg_id,
            "tasks": tasks or [],
            "pr_links": pr_links or [],
            "version": version,
            "status": status,
        }
        return self._add("content", content, owner=owner)

    # ---- 便捷封装：一条命令完整闭环留痕 ----
    def record_upgrade(self, trigger: str,
                       impact: Dict[str, Any],
                       feasibility: Dict[str, Any],
                       risk: Dict[str, Any],
                       priority: str,
                       decision: str,
                       reason: str,
                       tasks: List[str],
                       pr_links: List[str],
                       version: str,
                       owner: str = "cto",
                       upg_id: Optional[str] = None) -> SharedMemoryRecord:
        """完整记录一次框架升级闭环（触发→评估→决策→落地→留痕）。

        一次调用自动完成全部环节的留痕，返回最终的完整升级记录。
        若未显式传 upg_id，则由 next_upg_id() 自动生成递增编号。
        """
        upg_id = upg_id or next_upg_id(self.memory)

        # 环节 1：触发
        self.record_trigger(trigger, {}, upg_id=upg_id, owner=owner)
        # 环节 2：评估
        self.record_evaluation(upg_id, impact, feasibility, risk, priority,
                               owner=owner)
        # 环节 3：决策（人类 CP 拍板）
        self.record_decision(upg_id, decision, reason, owner=owner)
        # 环节 4：落地
        self.record_implementation(upg_id, tasks, pr_links, version,
                                   owner=owner)

        # 返回完整的升级记录（作为最终 content 记录）
        complete = {
            "type": "upgrade",
            "upgrade_id": upg_id,
            "trigger": trigger,
            "scope": impact,
            "risk": risk,
            "priority": priority,
            "decision": decision,
            "decision_reason": reason,
            "implemented": {
                "tasks": tasks,
                "pr_links": pr_links,
                "version": version,
            },
            "status": "active",
        }
        return self._add("content", complete, owner=owner)

    # ---- 查询 ----
    def query_upgrades(self, keyword: str = "",
                       topk: int = 10000) -> List[SharedMemoryRecord]:
        """查询 framework_upgrade 空间的升级记录。

        Args:
            keyword: 查询关键词（可选）
            topk: 返回记录上限，默认 10000 避免 SharedMemory.query 默认
                  topk=10 截断导致审计/幂等判定覆盖不全。
        """
        return self.memory.query(FRAMEWORK_UPGRADE_SPACE, kind="content",
                                 keyword=keyword, topk=topk)

    def get_upgrade(self, upg_id: str) -> Optional[SharedMemoryRecord]:
        """按 upgrade_id 查询完整升级记录（type=upgrade）。"""
        for r in self.query_upgrades(keyword=upg_id):
            content = r.content
            if content.get("type") == "upgrade" and \
               content.get("upgrade_id") == upg_id:
                return r
        return None

    def get_all_records(self) -> List[SharedMemoryRecord]:
        """获取全部记录（含历史版本）。"""
        return list(self.memory._records.values())

    def stats(self) -> Dict[str, Any]:
        """统计 framework_upgrade 空间的记录数。"""
        return self.memory.stats()


# ============================================================
# 演示 / 自测
# ============================================================

def demo():
    print("=" * 60)
    print("框架自升级闭环 · 共享记忆接线（wp_server）")
    print("=" * 60)

    fmu = FrameworkUpgradeMemory()

    # 1. UPG 编号规则：空空间 → 从 UPG-001 开始
    upg_1 = next_upg_id(fmu.memory)
    print(f"\n[UPG 编号] 初始编号: {upg_1}")

    # 2. 完整闭环留痕
    rec = fmu.record_upgrade(
        trigger="框架自升级闭环缺失（P0 缺口）",
        impact={"scope": "框架治理", "modules": ["docs/FRAMEWORK_UPGRADE.md"]},
        feasibility={"tech": "兼容", "migration": "低"},
        risk={"level": "低", "mitigation": "回退到旧版本文档"},
        priority="P0",
        decision="批准",
        reason="框架演进需要统一沉淀通道",
        tasks=["定义触发条件", "定义评估流程", "定义决策机制", "定义留痕方式"],
        pr_links=["https://cnb.cool/dongdongxiaozu/youxikaifaxilieagent/-/pulls/49"],
        version="v0.6.4",
    )
    print(f"\n[闭环留痕] 记录 {rec.mem_id} 写入，UPG 编号: {rec.content['upgrade_id']}")

    # 3. 再次生成编号：应递增为 UPG-002
    upg_2 = next_upg_id(fmu.memory)
    print(f"[UPG 编号] 递增后编号: {upg_2}")

    # 4. 查询
    records = fmu.query_upgrades(keyword="framework")
    print(f"\n[查询] framework_upgrade 空间 content 记录数: {len(records)}")

    for r in records:
        c = r.content
        print(f"  - {r.mem_id} type={c.get('type')} upg={c.get('upgrade_id', '-')}")

    # 5. 统计
    stats = fmu.stats()
    print(f"\n[统计] 总记录: {stats['total_records']}, active: {stats['active']}")

    # 6. 只增不改只追加验证
    print("\n[不可变性] 验证只增不改只追加...")
    old_count = len(fmu.get_all_records())
    # 追加一条新记录
    fmu.record_trigger("用户提出新架构诉求", {"detail": "需要支持多租户"},
                       owner="cto")
    new_count = len(fmu.get_all_records())
    assert new_count > old_count, "追加后记录数应增加"
    # 旧记录仍在且不可删改
    assert rec.mem_id in [r.mem_id for r in fmu.get_all_records()], "旧记录不可删"
    print(f"  ✅ 追加后 {old_count} → {new_count}，旧记录保留")

    print("\n✅ 框架自升级闭环 · 共享记忆接线验证通过")


if __name__ == "__main__":
    demo()
