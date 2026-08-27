# ============================================================
# 框架升级记录沉淀与复盘审计 (Framework Upgrade Ops)
# 版本: v1.0
# 说明: wp_data_ops（运营线·data_analyst）的落地产出。
#       按框架自升级闭环政策（FRAMEWORK_UPGRADE.md），把升级记录
#       沉淀进共享记忆（只增不改只追加），并对已有记录做复盘审计：
#         - 沉淀：把 UPG-001 及后续升级记录写入 shared memory，
#                 遵循「触发→评估→决策→落地」四环节闭环；
#         - 审计：对共享记忆中的升级记录做完整性/闭环性/版本追溯审计，
#                 验证是否满足政策要求（只增不改、可回溯、版本清晰）。
#
# 依赖: framework_upgrade_memory.py（共享记忆接线桥）
#       game-architect-team/src/shared_memory.py（共享记忆）
#
# 语言: Python 3 (可运行)
# ============================================================
from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional

# ---- 接入 SharedMemory 与 FrameworkUpgradeMemory ----
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)
_ARCH_DIR = os.path.abspath(
    os.path.join(_BASE_DIR, "..", "..", "game-architect-team", "src"))
if _ARCH_DIR not in sys.path:
    sys.path.insert(0, _ARCH_DIR)

from framework_upgrade_memory import (
    FrameworkUpgradeMemory,
)


# ============================================================
# 一、升级记录沉淀（运营线·data_analyst）
# ============================================================

# 已知升级记录清单（只增不改，历史记录固定不可删改）
# 每条记录对应 FRAMEWORK_UPGRADE.md「六、升级记录」表中的一行。
# 新升级发生时在此追加，而不是修改已有记录。
_KNOWN_UPGRADES: List[Dict[str, Any]] = [
    {
        "upgrade_id": "UPG-001",
        "trigger": "框架自升级闭环缺失（P0 缺口）",
        "scope": {
            "modules": ["docs/FRAMEWORK_UPGRADE.md"],
            "roles": ["cto", "server_dev", "data_analyst", "qa_engineer"],
            "pipelines": ["评审-修复闭环", "任务调度依赖链"],
        },
        "risk": {"level": "低", "mitigation": "回退到旧版本文档，不影响现有功能"},
        "priority": "P0",
        "decision": "批准",
        "decision_reason": "框架演进需要统一沉淀通道，避免升级散落无痕迹",
        "implemented": {
            "tasks": [
                "定义框架自升级闭环政策（触发/评估/决策/留痕）",
                "实现 FrameworkUpgradeMemory 共享记忆接线",
                "实现 UPG 编号递增规则",
                "实现四环节闭环留痕 API",
            ],
            "pr_links": [
                "https://cnb.cool/dongdongxiaozu/youxikaifaxilieagent/-/pulls/49",
                "https://cnb.cool/dongdongxiaozu/youxikaifaxilieagent/-/pulls/51",
            ],
            "version": "v0.6.4",
        },
        "status": "active",
        "audit": "闭环完整",
    },
]


def seed_known_upgrades(memory: Optional[FrameworkUpgradeMemory] = None) -> Dict[str, Any]:
    """把已知升级记录沉淀进共享记忆（幂等：只追加不重复）。

    Args:
        memory: FrameworkUpgradeMemory 实例（缺省时自动创建）。

    Returns:
        {"seeded": int, "skipped": int, "records": [mem_id, ...]}
    """
    fmu = memory or FrameworkUpgradeMemory()
    seeded = 0
    skipped = 0
    seeded_ids: List[str] = []

    # 查询共享记忆中已有的升级记录，避免重复沉淀
    existing = {r.content.get("upgrade_id")
                for r in fmu.query_upgrades(keyword="upgrade")
                if r.content.get("type") == "upgrade"}

    for upgrade in _KNOWN_UPGRADES:
        upg_id = upgrade["upgrade_id"]
        if upg_id in existing:
            skipped += 1
            continue
        # 通过 record_upgrade 沉淀完整闭环（触发→评估→决策→落地）
        rec = fmu.record_upgrade(
            trigger=upgrade["trigger"],
            impact=upgrade["scope"],
            feasibility={"tech": "兼容", "migration": "低"},
            risk=upgrade["risk"],
            priority=upgrade["priority"],
            decision=upgrade["decision"],
            reason=upgrade["decision_reason"],
            tasks=upgrade["implemented"]["tasks"],
            pr_links=upgrade["implemented"]["pr_links"],
            version=upgrade["implemented"]["version"],
            owner="data_analyst",
            upg_id=upg_id,
        )
        seeded += 1
        seeded_ids.append(rec.mem_id)

        # 同时写入一条 task 记录（升级任务卡）
        fmu._add("task", {
            "type": "upgrade_task",
            "upgrade_id": upg_id,
            "tasks": upgrade["implemented"]["tasks"],
            "status": "done",
        }, owner="data_analyst")

        # 同时写入一条 skill 记录（升级经验沉淀）
        fmu._add("skill", {
            "type": "upgrade_lesson",
            "upgrade_id": upg_id,
            "lesson": "框架升级必须走完整闭环：触发→评估→人类拍板→落地留痕",
        }, owner="data_analyst")

    return {"seeded": seeded, "skipped": skipped, "records": seeded_ids}


# ============================================================
# 二、升级记录复盘审计（运营线·data_analyst）
# ============================================================

def audit_upgrade_records(memory: Optional[FrameworkUpgradeMemory] = None) -> Dict[str, Any]:
    """对共享记忆中的升级记录做复盘审计。

    审计维度：
      1. 闭环完整性：每条升级记录是否包含触发/评估/决策/落地四个环节
      2. 只增不改：升级记录是否可追溯（无删除/覆盖，旧记录保留）
      3. 版本清晰：每条记录是否含版本号，可定位到具体框架版本
      4. 状态一致性：记录 status 字段是否存在合法值（active/superseded）

    Returns:
        审计报告 dict。
    """
    fmu = memory or FrameworkUpgradeMemory()

    records = fmu.query_upgrades(keyword="upgrade")
    complete_upgrades = [r for r in records
                         if r.content.get("type") == "upgrade"]

    # 1. 闭环完整性：每个完整升级记录四环节齐全
    chain_complete = 0
    chain_incomplete: List[str] = []
    for rec in complete_upgrades:
        content = rec.content
        has_trigger = bool(content.get("trigger"))
        has_scope = bool(content.get("scope"))
        has_risk = bool(content.get("risk"))
        has_priority = bool(content.get("priority"))
        has_decision = bool(content.get("decision"))
        has_implemented = bool(content.get("implemented"))
        if (has_trigger and has_scope and has_risk and has_priority
                and has_decision and has_implemented):
            chain_complete += 1
        else:
            chain_incomplete.append(content.get("upgrade_id", rec.mem_id))

    # 2. 只增不改：检查共享记忆的不可变性
    all_records = fmu.get_all_records()
    total_records = len(all_records)
    active_records = sum(1 for r in all_records if r.status == "active")
    superseded_records = sum(1 for r in all_records if r.status == "superseded")
    # 检查是否有相同 mem_id 的旧版本保留（只增不改的标志）
    mem_ids = [r.mem_id for r in all_records]
    immutable_ok = len(set(mem_ids)) == len(mem_ids)  # 每个 mem_id 唯一

    # 3. 版本清晰：检查每条 upgrade 记录是否含版本号
    versioned = sum(1 for rec in complete_upgrades
                    if rec.content.get("implemented", {}).get("version"))
    version_missing: List[str] = [
        r.content.get("upgrade_id", r.mem_id)
        for r in complete_upgrades
        if not r.content.get("implemented", {}).get("version")
    ]

    # 4. 状态一致性：所有记录 status 必须为 active 或 superseded
    VALID_STATUSES = {"active", "superseded"}
    invalid_statuses = [r.mem_id for r in all_records
                        if r.status not in VALID_STATUSES]

    # 5. 记录完整性：包含 content/task/skill 三类
    kinds = {}
    for r in all_records:
        kinds[r.kind] = kinds.get(r.kind, 0) + 1

    # 汇总
    total_upgrades = len(complete_upgrades)
    chain_rate = (chain_complete / total_upgrades * 100) if total_upgrades else 0.0
    version_rate = (versioned / total_upgrades * 100) if total_upgrades else 0.0

    audit_result = {
        "summary": {
            "total_upgrades": total_upgrades,
            "chain_complete": chain_complete,
            "chain_incomplete": chain_incomplete,
            "chain_rate": round(chain_rate, 1),
            "versioned": versioned,
            "version_missing": version_missing,
            "version_rate": round(version_rate, 1),
        },
        "immutability": {
            "total_records": total_records,
            "active": active_records,
            "superseded": superseded_records,
            "immutable_ok": immutable_ok,
        },
        "status_consistency": {
            "valid": len(invalid_statuses) == 0,
            "invalid_records": invalid_statuses,
        },
        "kind_distribution": kinds,
        "verdict": (
            "通过" if (chain_complete == total_upgrades
                       and immutable_ok
                       and not invalid_statuses)
            else "存在审计问题，需人工复核"
        ),
    }
    return audit_result


# ============================================================
# 三、升级记录查询辅助（运营线·data_analyst）
# ============================================================

def list_upgrade_summaries(memory: Optional[FrameworkUpgradeMemory] = None) -> List[Dict[str, Any]]:
    """列出共享记忆中的所有升级记录摘要（供运营复盘使用）。"""
    fmu = memory or FrameworkUpgradeMemory()
    summaries = []
    for rec in fmu.query_upgrades(keyword="upgrade"):
        content = rec.content
        if content.get("type") != "upgrade":
            continue
        summaries.append({
            "upgrade_id": content.get("upgrade_id", "-"),
            "trigger": content.get("trigger", "-"),
            "priority": content.get("priority", "-"),
            "decision": content.get("decision", "-"),
            "version": content.get("implemented", {}).get("version", "-"),
            "status": rec.status,
            "mem_id": rec.mem_id,
        })
    return summaries


# ============================================================
# 四、主入口：运营线升级记录沉淀 + 复盘审计
# ============================================================

def run_data_ops_upgrade(memory: Optional[FrameworkUpgradeMemory] = None) -> Dict[str, Any]:
    """运营线主入口：先沉淀已知升级记录，再对全部记录做复盘审计。

    Returns:
        {"seeded": ..., "audit": ..., "summaries": [...]}
    """
    fmu = memory or FrameworkUpgradeMemory()
    seed_result = seed_known_upgrades(fmu)
    audit = audit_upgrade_records(fmu)
    summaries = list_upgrade_summaries(fmu)
    return {
        "seeded": seed_result,
        "audit": audit,
        "summaries": summaries,
    }


# ============================================================
# 五、演示 / 自测
# ============================================================

def demo():
    print("=" * 70)
    print("框架升级记录沉淀与复盘审计（wp_data_ops·data_analyst）")
    print("=" * 70)

    # 1. 沉淀已知升级记录
    print("\n[1] 升级记录沉淀（只增不改只追加）")
    result = run_data_ops_upgrade()
    seeded = result["seeded"]
    print(f"  沉淀: {seeded['seeded']} 条新增，{seeded['skipped']} 条跳过（已存在）")
    for mem_id in seeded["records"]:
        print(f"    - {mem_id}")

    # 2. 复盘审计
    print("\n[2] 升级记录复盘审计")
    audit = result["audit"]
    print(f"  升级总数: {audit['summary']['total_upgrades']}")
    print(f"  闭环完整率: {audit['summary']['chain_rate']}% "
          f"({audit['summary']['chain_complete']}/{audit['summary']['total_upgrades']})")
    print(f"  版本清晰率: {audit['summary']['version_rate']}% "
          f"({audit['summary']['versioned']}/{audit['summary']['total_upgrades']})")
    print(f"  不可变性: {'✅ 通过' if audit['immutability']['immutable_ok'] else '❌ 失败'}")
    print(f"  状态一致性: {'✅ 通过' if audit['status_consistency']['valid'] else '❌ 失败'}")
    print(f"  审计结论: {audit['verdict']}")

    # 3. 升级摘要
    print("\n[3] 升级记录摘要")
    for s in result["summaries"]:
        print(f"  {s['upgrade_id']} | {s['trigger'][:30]}... | "
              f"{s['priority']} | {s['decision']} | {s['version']} | {s['status']}")

    print("\n✅ 运营线升级记录沉淀与复盘审计完成")


if __name__ == "__main__":
    demo()
