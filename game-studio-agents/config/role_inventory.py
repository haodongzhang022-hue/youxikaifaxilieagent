# ============================================================
# 角色-实现映射索引 CLI (Role Inventory)
# 版本: v1.0
# 说明: WP-01 落地产出——读取 config/role_inventory.yaml 映射索引，
#       提供 `--list`（列出全部角色及实现状态）与 `--gap`（差距索引）两个 CLI。
#
# 事实源口径（对齐架构师 [LOW] 风险规避）：
#   - ecosystem_roles.yaml 为生态角色事实源（21 个）
#   - roles.yaml 为研发岗位事实源（58 个）
#   - role_inventory.yaml 仅为映射索引，不重复定义角色行为
#
# 强制对照（对齐架构师 [LOW] 风险规避，防 WP-03 `_all_done` 空转）：
#   --gap 强制调用 ecosystem_role_registry.EcosystemRoleRegistry.summary() 与
#   ecosystem_handlers 的注册命名做逐项比对，确认：
#     1. role_inventory 中标注 implemented 的生态角色，在 registry.summary()
#        `dispatchable`（已注册可派发）清单中必须存在；
#     2. 生态 handler 注册命名（ecosystem_handlers.REGISTERED_HANDLERS）与
#        role_inventory 生态段 role_id 清单完全一致。
#   任一对不上即报 gap，防止 WP-03 依赖的 `_all_done` 因角色未落地而空转。
#
# 语言: Python 3 (可运行)
# ============================================================
from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from typing import Dict, List

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

_HERE = os.path.dirname(os.path.abspath(__file__))
INVENTORY_PATH = os.path.join(_HERE, "role_inventory.yaml")


# ============================================================
# 一、加载映射索引
# ============================================================

def load_inventory(path: str = INVENTORY_PATH) -> Dict:
    """加载 role_inventory.yaml 映射索引。

    返回 { "dev_roles": [...], "ecosystem_roles": [...] }，
    缺文件 / 解析失败时回退为空字典（便于 --list 在未落地时仍可展示声明）。
    """
    if yaml is None or not os.path.exists(path):
        return {"dev_roles": [], "ecosystem_roles": []}
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        inv = data.get("inventory", {}) or {}
        return {
            "dev_roles": inv.get("dev_roles", []) or [],
            "ecosystem_roles": inv.get("ecosystem_roles", []) or [],
        }
    except Exception as exc:  # noqa: BLE001
        print(f"[role_inventory] 加载失败({exc})，返回空索引")
        return {"dev_roles": [], "ecosystem_roles": []}


# ============================================================
# 二、强制对照：registry.summary() + ecosystem_handlers 注册命名
# ============================================================

def _registry_dispatchable() -> List[str]:
    """调用 ecosystem_role_registry.summary() 获取已注册可派发生态角色清单。

    此对照是强制项（架构师 [LOW] 风险规避）：生态角色必须在 registry 登记
    且可派发，否则 WP-03 的 `_all_done` 依赖的 eco_* 任务将空转。
    """
    try:
        from ecosystem_role_registry import EcosystemRoleRegistry
        reg = EcosystemRoleRegistry().load()
        reg.register()          # register 返回 List，注册表在 reg 自身上
        summary = reg.summary()
        return list(summary.get("dispatchable", []))
    except Exception as exc:  # noqa: BLE001
        print(f"[role_inventory] 强制跑 ecosystem_role_registry.summary() 失败: {exc}")
        return []


def _handlers_registered() -> List[str]:
    """获取 ecosystem_handlers 中已注册的生态 handler 命名（role_id 集合）。

    WP-02/02b 落地产出 ecosystem_handlers.REGISTERED_HANDLERS，是生态角色
    真实承接 handler 的事实清单，必须与 role_inventory 生态段对齐。
    """
    try:
        from ecosystem_handlers import REGISTERED_HANDLERS
        return list(REGISTERED_HANDLERS)
    except ImportError:
        # ecosystem_handlers 尚未落地（仅 WP-01 先行）时，回退为 registry 清单
        return []
    except Exception as exc:  # noqa: BLE001
        print(f"[role_inventory] 读取 ecosystem_handlers 失败: {exc}")
        return []


# ============================================================
# 三、CLI 实现
# ============================================================

def cmd_list(inv: Dict) -> int:
    """--list：列出全部角色及其实现状态。"""
    dev = inv["dev_roles"]
    eco = inv["ecosystem_roles"]
    print("=" * 74)
    print("角色-实现映射索引（role_inventory.yaml）")
    print(f"  研发岗位（roles.yaml 事实源）: {len(dev)} 个")
    print(f"  生态角色（ecosystem_roles.yaml 事实源）: {len(eco)} 个")
    print("=" * 74)

    print("\n【研发岗位】")
    for r in dev:
        print(f"  {r['role_id']:<24} [{r['status']:<14}] {r.get('name','')}")

    print("\n【生态角色】")
    for r in eco:
        print(f"  {r['role_id']:<24} [{r['status']:<14}] {r.get('name','')}")

    print("\n【状态统计】")
    dev_stat = Counter(r["status"] for r in dev)
    eco_stat = Counter(r["status"] for r in eco)
    print(f"  研发岗位: {dict(dev_stat)}")
    print(f"  生态角色: {dict(eco_stat)}")
    return 0


def cmd_gap(inv: Dict) -> int:
    """--gap：差距索引——找出「已声明但无实现/未注册」的角色，并做强制对照。

    检测三类 gap：
      G1 已声明但未注册到 message_bus 的生态角色（registry 无）——会被派发拒绝；
      G2 role_inventory 生态段与 ecosystem_handlers 注册命名不一致——handler 缺失；
      G3 研发岗位中标注 declared_only 的（仅声明、无独立实现）——列出供追踪。
    """
    eco = inv["ecosystem_roles"]
    dev = inv["dev_roles"]

    # ---- 强制对照 1：registry.summary() 可派发生态角色 ----
    dispatchable = set(_registry_dispatchable())
    # ---- 强制对照 2：ecosystem_handlers 注册命名 ----
    handlers = set(_handlers_registered())

    eco_ids = {r["role_id"] for r in eco}
    print("=" * 74)
    print("差距索引（--gap）")
    print("=" * 74)

    gaps: List[str] = []

    # G1：生态角色已声明但未注册到 message_bus
    g1 = sorted(eco_ids - dispatchable)
    print(f"\n[G1] 生态角色已声明但未注册到 message_bus（registry.summary() dispatchable）")
    if g1:
        print(f"  ❌ 缺口 {len(g1)} 个: {', '.join(g1)}")
        gaps.extend(g1)
    else:
        print(f"  ✅ 无缺口：全部 {len(eco_ids)} 个生态角色均已注册可派发")

    # G2：role_inventory 生态段 ∪ WP-02b `_alt` 样板 ↔ ecosystem_handlers 注册命名
    # 说明：ecosystem_handlers 负责承接两类 handler —— 生态角色（ecosystem_roles.yaml
    #       事实源）与 WP-02b `_alt` 样板（producer_alt/cto_alt/server_dev_alt）。
    #       强制对齐，防止 WP-03 `_all_done` 依赖的角色未落地而空转。
    #       注：department_agents 实现的部门主角色（lead_designer/cto/...）不在
    #       ecosystem_handlers 职责内，不参与本项对照。
    print(f"\n[G2] role_inventory 生态段∪_alt样板 ↔ ecosystem_handlers 注册命名 对齐")
    ALT_TEMPLATES = {"producer_alt", "cto_alt", "server_dev_alt"}
    expected_handlers = eco_ids | ALT_TEMPLATES
    if not handlers:
        print(f"  ⚠️  ecosystem_handlers 未落地（WP-02/02b 未执行），跳过 G2 强对照")
        print(f"     （本项在 WP-02 落地后强制：handler 命名须与映射表逐项对齐）")
    else:
        missing_in_handlers = sorted(expected_handlers - handlers)
        extra_in_handlers = sorted(handlers - expected_handlers)
        if not missing_in_handlers and not extra_in_handlers:
            print(f"  ✅ 完全一致：{len(handlers)} 个 handler 命名与映射表（生态段+_alt样板）对齐")
        else:
            if missing_in_handlers:
                print(f"  ❌ 映射表有、handler 缺 {len(missing_in_handlers)} 个: {', '.join(missing_in_handlers)}")
                gaps.extend(missing_in_handlers)
            if extra_in_handlers:
                print(f"  ⚠️  handler 有、映射表缺 {len(extra_in_handlers)} 个: {', '.join(extra_in_handlers)}")

    # G3：研发岗位 declared_only（仅声明、无独立实现，由部门聚合兜底）
    declared = [r["role_id"] for r in dev if r["status"] == "declared_only"]
    print(f"\n[G3] 研发岗位 declared_only（仅声明，由部门 Agent 聚合承接兜底）")
    if declared:
        print(f"  ⚠️  {len(declared)} 个: {', '.join(declared)}")
    else:
        print(f"  ✅ 无 declared_only 研发岗位")

    # G4：role_inventory 生态段缺失的 ecosystem_roles.yaml 事实源角色（同步防护）
    print(f"\n[G4] 映射索引生态段 ↔ ecosystem_roles.yaml 事实源 完整性")
    try:
        from ecosystem_role_registry import load_ecosystem_roles
        fact_eco = {r["role_id"] for r in load_ecosystem_roles()}
        missing_in_inv = sorted(fact_eco - eco_ids)
        if missing_in_inv:
            print(f"  ❌ 事实源有、映射索引缺 {len(missing_in_inv)} 个: {', '.join(missing_in_inv)}")
            gaps.extend(missing_in_inv)
        else:
            print(f"  ✅ 映射索引覆盖全部 {len(fact_eco)} 个生态角色事实源")
    except Exception as exc:  # noqa: BLE001
        print(f"  ⚠️  无法加载 ecosystem_roles.yaml 对照: {exc}")

    print("\n" + "=" * 74)
    if gaps:
        print(f"差距结论: 🔴 存在缺口 {len(gaps)} 个 -> {', '.join(sorted(set(gaps)))}")
        return 1
    print("差距结论: 🟢 无强制缺口，角色-实现映射对齐")
    return 0


# ============================================================
# 四、入口
# ============================================================

def main(argv: List[str] = None) -> int:
    parser = argparse.ArgumentParser(
        description="角色-实现映射索引 CLI（WP-01）")
    parser.add_argument("--list", action="store_true",
                        help="列出全部角色及实现状态")
    parser.add_argument("--gap", action="store_true",
                        help="差距索引：已声明但无实现/未注册的角色 + 强制 registry 对照")
    parser.add_argument("--path", default=INVENTORY_PATH,
                        help="role_inventory.yaml 路径（默认同目录）")
    args = parser.parse_args(argv)

    inv = load_inventory(args.path)
    if args.gap:
        return cmd_gap(inv)
    return cmd_list(inv)


if __name__ == "__main__":
    sys.exit(main())
