# ============================================================
# 预设实例化器（PresetInstantiator）—— v0.8 核心交付
# 版本: v0.1
# 说明: 承接 Issue #19「预设实例化 → 真实项目团队组装与联动」。
#       把 role_presets.yaml（L1角色 / L2技术栈 / L3小组）与
#       project_type_presets.yaml（P1项目类型 / P2阶段 / P3团队规模）
#       中选中的预设，**实例化为 roles.yaml 的正式角色**
#       （status: agent_enabled），并组装成按六大部门分组、可直接被
#       GameProducerAgent / 部门 Agent 承接调度的项目团队。
#
# 与 v0.7（PR #17 多部门 Agent 端到端联动）的协同：
#   - 本实例化器复用 v0.7 的部门划分（策划线/程序线/美术线/测试线/
#     项目管理/运营线，内部键 design/program/art/qa/pm/ops 对齐
#     game_producer_agent.DEPARTMENTS）；
#   - 实例化产出的正式角色可直接被部门 Agent / 经理按工作包承接，
#     从而把「预设选型」与「多部门端到端联动」两条线打通成同一条流水线。
#
# 实例化规则（呼应 role_presets.yaml 的"轻量定义"约定）：
#   - 一个 preset 只需给差异化字段（personality/风格/技术栈/侧重）；
#   - 实例化 = 取 base_role 的完整定义（responsibilities/tasks/
#     state_machine/agent_logic），叠加 preset 的差异化字段，
#     role_id 追加后缀，status 置为 agent_enabled。
#
# 语言: Python 3 (可运行)
# ============================================================
from __future__ import annotations

import copy
import os
from typing import Any, Dict, List, Optional

# 尝试加载 PyYAML（缺失时给出明确提示）
try:
    import yaml as _yaml
except Exception:  # pragma: no cover
    _yaml = None

# 默认配置文件路径（相对本文件所在目录）
_HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROLES = os.path.join(_HERE, "roles.yaml")
DEFAULT_ROLE_PRESETS = os.path.join(_HERE, "role_presets.yaml")
DEFAULT_PROJECT_PRESETS = os.path.join(_HERE, "project_type_presets.yaml")

# 六大部门内部键 → 中文名（与 game_producer_agent.DEPARTMENTS 对齐）
DEPT_KEY_BY_NAME = {
    "策划线": "design", "程序线": "program", "美术线": "art",
    "测试线": "qa", "项目管理": "pm", "运营线": "ops",
}


class PresetInstantiator:
    """预设实例化器：把分层预设实例化为正式角色并组装成项目团队。

    使用方式（链式）：
        inst = PresetInstantiator().load()
        inst.select_team("team_unity") \
            .select_stack("stack_unity_ecosystem") \
            .apply_project_type("ptype_mobile_game") \
            .apply_phase("phase_production") \
            .apply_team_scale("scale_medium")
        report = inst.instantiate()
    """

    def __init__(self, roles_path: str = DEFAULT_ROLES,
                 role_presets_path: str = DEFAULT_ROLE_PRESETS,
                 project_presets_path: str = DEFAULT_PROJECT_PRESETS):
        self.roles_path = roles_path
        self.role_presets_path = role_presets_path
        self.project_presets_path = project_presets_path

        # 已加载的原始数据
        self.roles: List[Dict[str, Any]] = []                 # roles.yaml 正式角色
        self.role_presets: List[Dict[str, Any]] = []          # L1 角色级预设
        self.stack_presets: List[Dict[str, Any]] = []         # L2 技术栈级预设
        self.team_presets: List[Dict[str, Any]] = []          # L3 小组级预设
        self.project_types: List[Dict[str, Any]] = []         # P1 项目类型
        self.phases: List[Dict[str, Any]] = []                # P2 产品阶段
        self.team_scales: List[Dict[str, Any]] = []           # P3 团队规模

        # 选中项（实例化输入）
        self._selected_team: Optional[Dict[str, Any]] = None
        self._selected_stack: Optional[Dict[str, Any]] = None
        self._selected_project_type: Optional[Dict[str, Any]] = None
        self._selected_phase: Optional[Dict[str, Any]] = None
        self._selected_scale: Optional[Dict[str, Any]] = None

        # 实例化输出
        self.instantiated_roles: List[Dict[str, Any]] = []
        self.assembled_team: Dict[str, List[Dict[str, Any]]] = {}  # {部门键: [角色]}

    # ============================================================
    # 加载
    # ============================================================
    def load(self) -> "PresetInstantiator":
        """加载全部配置文件。"""
        if _yaml is None:
            raise RuntimeError("缺少 PyYAML 依赖，请先 `pip install pyyaml`")
        self.roles = self._load_yaml(self.roles_path).get("roles", [])
        rp = self._load_yaml(self.role_presets_path)
        # role_presets/stack_presets/team_presets 为该文件顶层键
        self.role_presets = rp.get("role_presets", [])
        self.stack_presets = rp.get("stack_presets", [])
        self.team_presets = rp.get("team_presets", [])
        pp = self._load_yaml(self.project_presets_path)
        # project_types/phases/team_scales 为该文件顶层键（非 preset_system 下）
        self.project_types = pp.get("project_types", [])
        self.phases = pp.get("phases", [])
        self.team_scales = pp.get("team_scales", [])
        return self

    def _load_yaml(self, path: str) -> Dict[str, Any]:
        with open(path, "r", encoding="utf-8") as f:
            return _yaml.safe_load(f) or {}

    # ============================================================
    # 选择入口（可链式调用）
    # ============================================================
    def select_team(self, team_id: str) -> "PresetInstantiator":
        self._selected_team = self._find(self.team_presets, "preset_id", team_id, "L3 小组")
        return self

    def select_stack(self, stack_id: str) -> "PresetInstantiator":
        self._selected_stack = self._find(self.stack_presets, "preset_id", stack_id, "L2 技术栈")
        return self

    def apply_project_type(self, ptype_id: str) -> "PresetInstantiator":
        self._selected_project_type = self._find(self.project_types, "preset_id", ptype_id, "P1 项目类型")
        return self

    def apply_phase(self, phase_id: str) -> "PresetInstantiator":
        self._selected_phase = self._find(self.phases, "preset_id", phase_id, "P2 产品阶段")
        return self

    def apply_team_scale(self, scale_id: str) -> "PresetInstantiator":
        self._selected_scale = self._find(self.team_scales, "preset_id", scale_id, "P3 团队规模")
        return self

    def _find(self, items: List[Dict[str, Any]], key: str, value: str, what: str) -> Dict[str, Any]:
        for it in items:
            if it.get(key) == value:
                return it
        raise ValueError(f"未找到{what}预设: {value}")

    # ============================================================
    # 实例化核心
    # ============================================================
    def instantiate(self) -> Dict[str, Any]:
        """执行实例化：把选中的预设实例化为正式角色并组装团队。

        返回结构化报告（预设实例化清单 + 各部门装配 + 角色列表）。
        """
        if not (self._selected_team or self._selected_stack):
            raise ValueError("请先选择 L3 小组（select_team）或 L2 技术栈（select_stack）")

        role_by_id = {r["role_id"]: r for r in self.roles}
        instantiated: List[Dict[str, Any]] = []
        # 记录来源，便于追溯
        sources: List[Dict[str, Any]] = []

        # ---- 1. 由 L3 小组 composition 实例化 ----
        if self._selected_team:
            for item in self._selected_team.get("composition", []):
                base_role_id = item.get("role")
                preset_ref = item.get("preset")
                count = int(item.get("count", 1) or 1)
                note = item.get("note", "")
                for i in range(count):
                    inst = self._instantiate_one(
                        role_by_id, base_role_id, preset_ref,
                        suffix=f"{self._suffix(self._selected_team['preset_id'])}_{i + 1}",
                        extra_note=note,
                        source=f"team:{self._selected_team['preset_id']}")
                    if inst:
                        instantiated.append(inst)
                        sources.append({"source": f"team:{self._selected_team['preset_id']}",
                                        "role_id": inst["role_id"], "base_role": base_role_id,
                                        "preset": preset_ref, "count_idx": i + 1, "note": note})

        # ---- 2. 由 L2 技术栈 scope_roles 实例化（小组未覆盖时补齐） ----
        if self._selected_stack:
            # 按 base_role 去重：L3 小组已覆盖的 base_role，L2 不再重复实例化
            covered_base = {r.get("_base_role") for r in instantiated}
            for scope_role in self._selected_stack.get("scope_roles", []):
                if scope_role in covered_base:
                    continue  # 已被 L3 小组覆盖，避免重复
                inst = self._instantiate_one(
                    role_by_id, scope_role, None,
                    suffix=self._suffix(self._selected_stack["preset_id"]),
                    source=f"stack:{self._selected_stack['preset_id']}")
                if inst:
                    instantiated.append(inst)
                    sources.append({"source": f"stack:{self._selected_stack['preset_id']}",
                                    "role_id": inst["role_id"], "base_role": scope_role,
                                    "preset": None, "count_idx": 1, "note": "技术栈覆盖"})

        # ---- 2.5 补充 P2 阶段关键角色（策划/管理/运营），确保六部门齐全 ----
        if self._selected_phase:
            covered_base = {r.get("_base_role") for r in instantiated}
            phase_key_roles = self._selected_phase.get("key_roles", [])
            for krole in phase_key_roles:
                if krole == "全岗位":
                    continue
                # 跳过已覆盖的 base_role，也跳过预设锚点之外的抽象名
                if krole in covered_base or krole not in role_by_id:
                    continue
                inst = self._instantiate_one(
                    role_by_id, krole, None,
                    suffix=self._suffix(self._selected_phase["preset_id"]),
                    source=f"phase:{self._selected_phase['preset_id']}")
                if inst:
                    instantiated.append(inst)
                    covered_base.add(krole)
                    sources.append({"source": f"phase:{self._selected_phase['preset_id']}",
                                    "role_id": inst["role_id"], "base_role": krole,
                                    "preset": None, "count_idx": 1, "note": "阶段关键角色"})

        # ---- 2.6 补充 P1 项目类型关键角色（策划/运营等），确保六部门齐全 ----
        if self._selected_project_type:
            covered_base = {r.get("_base_role") for r in instantiated}
            ptype_key_roles = self._selected_project_type.get("key_roles", [])
            for krole in ptype_key_roles:
                if krole in covered_base or krole not in role_by_id:
                    continue
                inst = self._instantiate_one(
                    role_by_id, krole, None,
                    suffix=self._suffix(self._selected_project_type["preset_id"]),
                    source=f"ptype:{self._selected_project_type['preset_id']}")
                if inst:
                    instantiated.append(inst)
                    covered_base.add(krole)
                    sources.append({"source": f"ptype:{self._selected_project_type['preset_id']}",
                                    "role_id": inst["role_id"], "base_role": krole,
                                    "preset": None, "count_idx": 1, "note": "项目类型关键角色"})

        self.instantiated_roles = instantiated

        # ---- 3. 组装团队：按六大部门分组 ----
        self.assembled_team = self._assemble_team(instantiated)

        # ---- 4. 汇总报告 ----
        return {
            "project_type": self._selected_project_type and {
                "preset_id": self._selected_project_type["preset_id"],
                "name": self._selected_project_type.get("name"),
            },
            "phase": self._selected_phase and {
                "preset_id": self._selected_phase["preset_id"],
                "name": self._selected_phase.get("name"),
            },
            "team_scale": self._selected_scale and {
                "preset_id": self._selected_scale["preset_id"],
                "name": self._selected_scale.get("name"),
            },
            "team": self._selected_team and {
                "preset_id": self._selected_team["preset_id"],
                "name": self._selected_team.get("name"),
            },
            "stack": self._selected_stack and {
                "preset_id": self._selected_stack["preset_id"],
                "name": self._selected_stack.get("name"),
            },
            "instantiated_roles": [self._role_summary(r) for r in instantiated],
            "sources": sources,
            "assembled_team": {
                dept: [self._role_summary(r) for r in roles]
                for dept, roles in self.assembled_team.items()
            },
            "total_roles": len(instantiated),
            "department_count": {k: len(v) for k, v in self.assembled_team.items()},
        }

    def _instantiate_one(self, role_by_id: Dict[str, Dict[str, Any]],
                         base_role_id: str, preset_ref: Optional[str],
                         suffix: str, source: str,
                         extra_note: str = "") -> Optional[Dict[str, Any]]:
        """实例化单个角色：取 base_role 完整定义，叠加 preset 差异化字段。"""
        base = role_by_id.get(base_role_id)
        if not base:
            return None  # base_role 不存在则跳过（保持健壮）

        inst = copy.deepcopy(base)
        inst["role_id"] = f"{base_role_id}_{suffix}"
        inst["status"] = "agent_enabled"        # 实例化为正式角色，参与调度
        inst["_instantiated_from"] = source      # 来源追溯
        inst["_base_role"] = base_role_id

        # 叠 L1 角色级预设的差异化字段（personality / preset_fields）
        if preset_ref:
            preset = self._find(self.role_presets, "preset_id", preset_ref, f"L1 角色预设 {preset_ref}")
            inst["personality"] = preset.get("personality", inst.get("personality", ""))
            inst["preset_ref"] = preset_ref
            inst["preset_category"] = preset.get("category", "")
            # 差异化字段并入 preset_fields（供行为层读取）
            preset_fields = preset.get("preset_fields", {})
            inst.setdefault("preset_fields", {})
            inst["preset_fields"].update(preset_fields)
            # 名称追加风格标注
            if preset.get("name"):
                inst["name"] = f"{base.get('name', base_role_id)} · {preset['name']}"

        # 叠 L2 技术栈差异化字段（tech_stack / scope 备注）
        if self._selected_stack:
            inst.setdefault("preset_fields", {})
            inst["preset_fields"]["tech_stack"] = self._selected_stack.get("tech_stack", {})
            inst["preset_fields"]["stack_ref"] = self._selected_stack["preset_id"]

        if extra_note:
            inst["preset_fields"].setdefault("composition_note", extra_note)

        return inst

    def _assemble_team(self, roles: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """按六大部门（对齐 DEPARTMENTS）组装团队。"""
        team: Dict[str, List[Dict[str, Any]]] = {
            "design": [], "program": [], "art": [], "qa": [], "pm": [], "ops": [],
        }
        for r in roles:
            dept_name = r.get("department", "")
            key = DEPT_KEY_BY_NAME.get(dept_name)
            if key is None:
                # 未知部门归入 pm 兜底并告警
                key = "pm"
            team[key].append(r)
        # 各部门内按 agent_priority 排序（低优先先执行）
        for key in team:
            team[key].sort(key=lambda r: r.get("agent_priority", 999))
        return team

    def _suffix(self, preset_id: str) -> str:
        """由 preset_id 生成实例化后缀（去掉 team_/stack_ 前缀，保持可读）。"""
        return preset_id.replace("team_", "").replace("stack_", "").replace("-", "_")

    def _role_summary(self, r: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "role_id": r.get("role_id"),
            "name": r.get("name"),
            "department": r.get("department"),
            "status": r.get("status"),
            "base_role": r.get("_base_role"),
            "source": r.get("_instantiated_from"),
            "preset_ref": r.get("preset_ref"),
            "priority": r.get("agent_priority"),
        }

    # ============================================================
    # 导出为 roles.yaml 追加块 / 校验
    # ============================================================
    def to_roles_yaml(self) -> str:
        """把实例化后的正式角色序列化为可追加进 roles.yaml 的 YAML 文本。"""
        # 去掉内部追溯字段（保留给角色定义之外），仅输出正式角色字段
        export = []
        for r in self.instantiated_roles:
            role = {k: v for k, v in r.items() if not k.startswith("_")}
            export.append(role)
        return _yaml.safe_dump({"roles": export}, allow_unicode=True, sort_keys=False)

    def validate(self) -> List[str]:
        """校验：role_id 唯一性、base_role 引用有效、department 可识别。"""
        issues: List[str] = []
        seen: Dict[str, int] = {}
        for r in self.instantiated_roles:
            rid = r.get("role_id")
            seen[rid] = seen.get(rid, 0) + 1
            if r.get("status") != "agent_enabled":
                issues.append(f"{rid}: status 应为 agent_enabled")
            if r.get("department") not in DEPT_KEY_BY_NAME:
                issues.append(f"{rid}: 无法识别的部门 {r.get('department')}")
        for rid, cnt in seen.items():
            if cnt > 1:
                issues.append(f"{rid}: role_id 重复 {cnt} 次")
        if not self.instantiated_roles:
            issues.append("未实例化任何角色，请检查选择项")
        return issues


# ============================================================
# 演示 / 自测
# ============================================================
def demo() -> Dict[str, Any]:
    print("=" * 70)
    print("预设实例化器（v0.8）—— 预设选型 → 实例化 → 项目团队组装")
    print("=" * 70)

    inst = PresetInstantiator().load()
    # 场景示例：移动端手游 + 正式开发 + 中型团队 → Unity小组 + Unity技术栈
    inst.apply_project_type("ptype_mobile_game") \
        .apply_phase("phase_production") \
        .apply_team_scale("scale_medium") \
        .select_team("team_unity") \
        .select_stack("stack_unity_ecosystem")
    report = inst.instantiate()

    print(f"\n== 选型组合 ==")
    print(f"  项目类型: {report['project_type']['name']}")
    print(f"  产品阶段: {report['phase']['name']}")
    print(f"  团队规模: {report['team_scale']['name']}")
    print(f"  L3 小组:  {report['team']['name']}")
    print(f"  L2 技术栈: {report['stack']['name']}")

    print(f"\n== 实例化清单（共 {report['total_roles']} 个正式角色）==")
    print(f"{'role_id':<34}{'部门':<6}{'来源':<20}预设")
    for s in report["instantiated_roles"]:
        print(f"{s['role_id']:<34}{s['department']:<6}{s['source']:<20}{s['preset_ref'] or ''}")

    print("\n== 项目团队组装（按六大部门）==")
    for dept, roles in report["assembled_team"].items():
        ids = ", ".join(r["role_id"] for r in roles) or "(空)"
        print(f"  - {dept}: {ids}")

    print("\n== 校验 ==")
    issues = inst.validate()
    if issues:
        for it in issues:
            print(f"  ❌ {it}")
    else:
        print("  ✅ 通过：role_id 唯一、status 均 agent_enabled、部门可识别")

    return report


if __name__ == "__main__":
    demo()
