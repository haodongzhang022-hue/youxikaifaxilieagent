# ============================================================
# 角色-实现映射索引 CLI (Role Inventory)
# 版本: v1.0
# 说明: 读取 config/role_inventory.yaml（单一事实来源），输出：
#   - --list : 列出所有角色及其状态/实现类
#   - --gap  : 输出"声明≠存在"的差距表（registered_only / declared_only）
#       供架构师一眼看出哪些角色真存在、哪些停在声明层。
# 语言: Python 3 (可运行)
# ============================================================
from __future__ import annotations

import argparse
import os
import sys

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

DEFAULT_INVENTORY = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "role_inventory.yaml")

# 状态中文描述
STATUS_LABEL = {
    "implemented":     "✅ 已实体化",
    "registered_only": "⚠️ 仅注册可派发（无承接handler）",
    "declared_only":   "❌ 仅声明（无实现）",
    "preset_standby":  "🔁 预设备用",
}

# 非"已实体化"即为差距
GAP_STATUSES = {"registered_only", "declared_only", "preset_standby"}


def load_inventory(path: str = DEFAULT_INVENTORY) -> dict:
    """加载 role_inventory.yaml，返回角色列表。"""
    if yaml is None:
        sys.exit("缺少 PyYAML，请先 `pip install pyyaml`。")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    roles = data.get("roles", [])
    if not isinstance(roles, list):
        sys.exit("role_inventory.yaml 格式错误：roles 应为列表。")
    return data


def list_roles(path: str = DEFAULT_INVENTORY) -> None:
    """--list：列出全部角色。"""
    data = load_inventory(path)
    roles = data["roles"]
    print(f"角色-实现映射索引（共 {len(roles)} 个角色）\n"
          f"{'='*88}")
    print(f"{'role_id':<24} {'状态':<28} {'实现类'}")
    print("-" * 88)
    for r in roles:
        status = STATUS_LABEL.get(r["status"], r["status"])
        print(f"{r['role_id']:<24} {status:<28} {r['implementation']}")


def list_gap(path: str = DEFAULT_INVENTORY) -> int:
    """--gap：输出声明≠实现的差距表。"""
    data = load_inventory(path)
    roles = data["roles"]
    gaps = [r for r in roles if r["status"] in GAP_STATUSES]

    print(f"角色-实现差距表（声明≠存在，共 {len(gaps)} 个）\n"
          f"{'='*88}")
    if not gaps:
        print("✅ 无差距：所有角色均已实体化。")
        return 0

    print(f"{'role_id':<24} {'状态':<28} {'来源':<18} {'实现类'}")
    print("-" * 88)
    for r in gaps:
        status = STATUS_LABEL.get(r["status"], r["status"])
        print(f"{r['role_id']:<24} {status:<28} {r['source']:<18} {r['implementation']}")

    # 分圈汇总
    by_status: dict = {}
    for r in gaps:
        by_status.setdefault(r["status"], 0)
        by_status[r["status"]] += 1
    print("-" * 88)
    for st, cnt in by_status.items():
        print(f"  {STATUS_LABEL.get(st, st)}: {cnt} 个")
    return len(gaps)


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(prog="role_inventory",
                                     description="角色-实现映射索引差距工具")
    parser.add_argument("--list", action="store_true",
                        help="列出所有角色及其实现状态")
    parser.add_argument("--gap", action="store_true",
                        help="输出声明≠实现的差距表")
    parser.add_argument("--file", default=DEFAULT_INVENTORY,
                        help="指定 role_inventory.yaml 路径（默认自动探测）")
    args = parser.parse_args(argv)

    if args.list:
        list_roles(args.file)
        return 0
    if args.gap:
        return 0 if list_gap(args.file) == 0 else 1

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
