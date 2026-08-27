# ============================================================
# 角色-实现映射索引 CLI (Role Inventory)
# 版本: v1.0
# 说明: 读取 config/role_inventory.yaml，提供角色-实现映射索引查询：
#   - --list:  列出全部角色及其实现状态
#   - --gap:   输出差距索引（declared_only / registered_only / implemented 统计）
#   - --check: 强制跑 ecosystem_role_registry.summary() 对照
#              验证 role_id 清单与生态角色注册命名是否一致（防 WP-03 空转）
#
# 事实源口径（对齐架构师 [LOW] 风险规避）:
#   - roles.yaml:              研发核心圈角色事实源
#   - ecosystem_roles.yaml:    生态角色事实源
#   - role_inventory.yaml:     映射索引（非事实源，仅汇总状态）
#   - ecosystem_role_registry.py: 生态角色注册的**实际运行态**事实
#
# 语言: Python 3 (可运行)
# ============================================================
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

_HERE = os.path.dirname(os.path.abspath(__file__))
_INVENTORY_PATH = os.path.join(_HERE, "role_inventory.yaml")
_ECOSYSTEM_REGISTRY = os.path.join(_HERE, "ecosystem_role_registry.py")


# ============================================================
# 一、加载与查询
# ============================================================

def load_inventory(path: Optional[str] = None) -> Dict[str, Any]:
    """加载 role_inventory.yaml。"""
    path = path or _INVENTORY_PATH
    if yaml is None or not os.path.exists(path):
        print(f"[role_inventory] 无法加载 {path}（yaml 缺失或文件不存在）")
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as exc:  # noqa: BLE001
        print(f"[role_inventory] 加载失败({exc})")
        return {}


def all_roles(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """返回全部角色（roles_inventory + ecosystem_roles_inventory）。"""
    return list(data.get("roles_inventory", [])) + list(data.get("ecosystem_roles_inventory", []))


def by_status(data: Dict[str, Any], status: str) -> List[Dict[str, Any]]:
    """按实现状态筛选角色。"""
    return [r for r in all_roles(data) if r.get("impl_status") == status]


def status_summary(data: Dict[str, Any]) -> Dict[str, Any]:
    """实现状态汇总。"""
    roles = all_roles(data)
    counter = Counter(r.get("impl_status", "unknown") for r in roles)
    return {
        "total": len(roles),
        "by_status": dict(counter),
    }


def eco_registry_check(data: Dict[str, Any]) -> Dict[str, Any]:
    """强制跑 ecosystem_role_registry.summary() 对照。

    验证：
      1. role_inventory.yaml 中的生态角色 role_id 清单
         与 ecosystem_role_registry 实际注册的角色清单是否一致；
      2. 报告 mismatch（差异）供 WP-03 _all_done 修复参考。
    """
    # 从 role_inventory.yaml 取生态角色清单
    inv_eco_roles = {
        r["role_id"] for r in data.get("ecosystem_roles_inventory", [])
    }

    # 动态 import ecosystem_role_registry 并跑 summary()
    try:
        sys.path.insert(0, _HERE)
        from ecosystem_role_registry import EcosystemRoleRegistry
        registry = EcosystemRoleRegistry().load()
        registry.register()  # 注册到 message_bus，使 summary() 的 registered_to_bus 真实有效
        registry_summary = registry.summary()
        registered = set(registry_summary.get("dispatchable", []))
        registered_to_bus = set(registry_summary.get("registered_to_bus", []))
        eco_total = registry_summary.get("total", 0)
    except Exception as exc:  # noqa: BLE001
        return {
            "check_passed": False,
            "error": f"无法运行 ecosystem_role_registry.summary(): {exc}",
            "inventory_eco_count": len(inv_eco_roles),
            "registry_eco_count": 0,
        }

    # 对照
    in_inv_not_reg = sorted(inv_eco_roles - registered)
    in_reg_not_inv = sorted(registered - inv_eco_roles)
    in_inv_not_bus = sorted(inv_eco_roles - registered_to_bus)
    match = not in_inv_not_reg and not in_reg_not_inv

    return {
        "check_passed": match,
        "inventory_eco_count": len(inv_eco_roles),
        "registry_eco_count": eco_total,
        "registry_dispatchable": len(registered),
        "registry_bus_registered": len(registered_to_bus),
        "in_inventory_not_registered": in_inv_not_reg,
        "in_registry_not_inventory": in_reg_not_inv,
        "in_inventory_not_bus": in_inv_not_bus,
        "note": "role_inventory.yaml 生态角色清单 vs ecosystem_role_registry.summary()",
    }


# ============================================================
# 二、CLI 输出
# ============================================================

def cmd_list(data: Dict[str, Any], args: argparse.Namespace) -> int:
    """--list: 列出全部角色及其实现状态。"""
    roles = all_roles(data)
    if not roles:
        print("[role_inventory] 空索引")
        return 1

    # 按 source 分组展示
    for section_name, section_roles in [
        ("roles.yaml", data.get("roles_inventory", [])),
        ("ecosystem_roles.yaml", data.get("ecosystem_roles_inventory", [])),
    ]:
        print(f"\n=== {section_name}（{len(section_roles)} 个）===")
        for r in section_roles:
            rid = r["role_id"]
            status = r.get("impl_status", "?")
            ref = r.get("impl_ref", "") or "-"
            print(f"  {rid:<28} {status:<18} {ref}")

    # 汇总
    summary = status_summary(data)
    print(f"\n总计: {summary['total']} 个角色")
    for s, c in summary["by_status"].items():
        print(f"  {s}: {c}")

    return 0


def cmd_gap(data: Dict[str, Any], args: argparse.Namespace) -> int:
    """--gap: 输出差距索引（重点 gap 角色与建议）。"""
    roles = all_roles(data)
    if not roles:
        print("[role_inventory] 空索引")
        return 1

    gap_roles = [r for r in roles if r.get("impl_status") in ("declared_only",)]
    reg_roles = [r for r in roles if r.get("impl_status") == "registered_only"]
    impl_roles = [r for r in roles if r.get("impl_status") == "implemented"]

    print("=" * 70)
    print("角色-实现差距索引 (Role Gap Index)")
    print("=" * 70)

    # 状态汇总
    summary = status_summary(data)
    print(f"\n[实现状态汇总] total={summary['total']}")
    for s, c in summary["by_status"].items():
        pct = c * 100.0 / max(1, summary["total"])
        print(f"  {s:<18} {c:>4} ({pct:.0f}%)")

    # GAP 1: declared_only（声明但未注册/未实现）
    print(f"\n[GAP-1] declared_only（{len(gap_roles)} 个，声明但无实现）")
    if gap_roles:
        for r in gap_roles:
            src = r.get("source", "?")
            variant = r.get("variant", "?")
            dept = r.get("department", r.get("circle", "?"))
            note = r.get("note", "")
            print(f"  {r['role_id']:<28} dept={dept:<12} variant={variant:<5} src={src}  {note}")
    else:
        print("  ✅ 无 declared_only 角色")

    # GAP 2: registered_only（已注册但无独立 handler）
    print(f"\n[GAP-2] registered_only（{len(reg_roles)} 个，已注册但依赖部门聚合承接）")
    for r in reg_roles:
        src = r.get("source", "?")
        ref = r.get("impl_ref", "")
        print(f"  {r['role_id']:<28} src={src:<20} → {ref}")

    # GAP 3: implemented 覆盖率
    print(f"\n[GAP-3] implemented（{len(impl_roles)} 个，真实可执行）")
    for r in impl_roles:
        ref = r.get("impl_ref", "")
        print(f"  {r['role_id']:<28} → {ref}")

    # 强制跑 ecosystem_role_registry.summary() 对照
    print("\n[生态角色对照] ecosystem_role_registry.summary()")
    check = eco_registry_check(data)
    if check.get("error"):
        print(f"  ⚠️  {check['error']}")
    else:
        print(f"  inventory 生态角色: {check['inventory_eco_count']} 个")
        print(f"  registry 生态角色: {check['registry_eco_count']} 个")
        print(f"  registry dispatchable: {check['registry_dispatchable']} 个")
        print(f"  registry bus_registered: {check['registry_bus_registered']} 个")
        if check["check_passed"]:
            print("  ✅ 对照通过：role_inventory 生态角色清单与 registry 一致")
        else:
            if check["in_inventory_not_registered"]:
                print(f"  ⚠️  inventory 有但 registry 无: {check['in_inventory_not_registered']}")
            if check["in_registry_not_inventory"]:
                print(f"  ⚠️  registry 有但 inventory 无: {check['in_registry_not_inventory']}")
            if check["in_inventory_not_bus"]:
                print(f"  ⚠️  inventory 有但未注册到 bus: {check['in_inventory_not_bus']}")
            return 1

    return 0


def cmd_check(data: Dict[str, Any], args: argparse.Namespace) -> int:
    """--check: 强制跑 ecosystem_role_registry.summary() 对照。"""
    check = eco_registry_check(data)
    if check.get("error"):
        print(f"[role_inventory] {check['error']}")
        return 1

    print("生态角色注册对照检查:")
    for k, v in check.items():
        if k != "note":
            print(f"  {k}: {v}")
    print(f"  note: {check['note']}")

    return 0 if check["check_passed"] else 1


def cmd_summary(data: Dict[str, Any], args: argparse.Namespace) -> int:
    """--summary: JSON 摘要输出（供外部消费）。"""
    summary = status_summary(data)
    check = eco_registry_check(data)
    output = {
        "inventory": summary,
        "eco_registry_check": check,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


# ============================================================
# 三、入口
# ============================================================

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="role_inventory",
        description="角色-实现映射索引 CLI（WP-01 产出）",
    )
    parser.add_argument("--list", action="store_true", help="列出全部角色及其实现状态")
    parser.add_argument("--gap", action="store_true", help="输出差距索引（declared_only / registered_only / implemented）")
    parser.add_argument("--check", action="store_true", help="强制跑 ecosystem_role_registry.summary() 对照")
    parser.add_argument("--summary", action="store_true", help="输出 JSON 摘要")
    parser.add_argument("--path", help="自定义 role_inventory.yaml 路径")

    args = parser.parse_args(argv)

    data = load_inventory(args.path)
    if not data:
        print("[role_inventory] 索引加载失败")
        return 1

    if args.list:
        return cmd_list(data, args)
    if args.gap:
        return cmd_gap(data, args)
    if args.check:
        return cmd_check(data, args)
    if args.summary:
        return cmd_summary(data, args)

    # 无参数时默认输出 gap
    return cmd_gap(data, args)


if __name__ == "__main__":
    raise SystemExit(main())
