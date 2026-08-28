# ============================================================
# 游戏开发小组闭环引擎 (Game Dev Team Engine)
# 版本: v1.0
# 说明: 参考 dongjiagoushi 的 DevTeamEngine 与 Goose 开源项目的
#       "执行-验证-规划-监督" 四维闭环，为**游戏开发程序线**落地
#       "开发小组" 机制——多个角色循环的小组，一套循环 N 个开发，
#       而非单个开发自己循环。
#
# Goose 四维闭环映射（游戏开发程序线）:
#   - Planner/Leader   → 技术总监（cto，小组长）：定策略、拆任务、收尾整合
#   - Coder/Executor   → N 个开发角色（默认 2）：客户端/服务端/引擎/工具链等
#   - Reviewer/Critic  → 客观验证器（测试/lint/编译/资源校验）：只有"否决权"
#   - Orchestrator     → 本引擎 GameDevTeamEngine：确定性状态机（非 LLM 控制流转）
#
# 设计动机: 单 Agent 自己写码又自己判断"是否完成/是否继续"，极易自圆其说
#           陷入死循环。本引擎用确定性代码控制流程，把"执行"与"验证"分离，
#           超限熔断上报 Leader，进度北极星监督管得住循环。
#
# 语言: Python 3 (可运行，不依赖第三方库)
# ============================================================
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


# ============================================================
# 一、开发小组常量与状态
# ============================================================

# 默认每小组开发数（一套循环 N 个开发，默认 2）
DEFAULT_DEVS_PER_TEAM = 2

# 硬性熔断阈值
DEFAULT_MAX_ATTEMPTS = 3       # 单个开发同一子任务重做上限（超限上报 Leader 换方案）
DEFAULT_MAX_ITERATIONS = 20    # 整个小组总迭代上限（超限熔断）
DEFAULT_MAX_IDLE_SECONDS = 1800.0  # 空闲超时判定卡死（秒）

# 开发阶段验证状态
APPROVED = "APPROVED"
REJECTED = "REJECTED"


@dataclass
class DevTask:
    """一个开发子任务（小组内某开发的一次产出目标）"""
    dev_role: str                    # 承接开发角色（client_dev / server_dev / ...）
    module: str                      # 产出模块
    desc: str = ""
    goal_meter: float = 0.0          # 进度北极星：当前完成度（0~goal_total）
    goal_total: float = 1.0          # 目标完成度
    attempts: int = 0                # 重做次数（熔断判定）
    status: str = "PENDING"          # PENDING / IN_PROGRESS / APPROVED / REJECTED / FUSED
    artifact: Dict[str, Any] = field(default_factory=dict)
    verify_note: str = ""
    last_activity: float = field(default_factory=time.time)

    def is_done(self) -> bool:
        return self.status == "APPROVED" or self.status == "FUSED"


@dataclass
class DevRound:
    """一轮小组循环的记录（全组一次 execute→verify 的留痕）"""
    round_no: int
    tasks: List[str] = field(default_factory=list)   # 本轮涉及的 dev_role 清单
    verified: List[str] = field(default_factory=list)
    rejected: List[str] = field(default_factory=list)
    fused: List[str] = field(default_factory=list)
    ts: float = field(default_factory=time.time)


@dataclass
class GameDevTeam:
    """一个游戏开发小组（Leader + N 开发 的整体）"""
    team_id: str
    leader: str                        # 小组长（技术总监 cto）
    devs: List[str] = field(default_factory=list)   # N 个开发角色（默认 2）
    tasks: Dict[str, DevTask] = field(default_factory=dict)   # dev_role -> DevTask
    rounds: List[DevRound] = field(default_factory=list)      # 循环留痕
    created_at: float = field(default_factory=time.time)
    delivered: bool = False            # 是否已统一交付


# ============================================================
# 二、开发小组闭环引擎（确定性状态机 = Goose 的 Orchestrator）
# ============================================================

class GameDevTeamEngine:
    """
    游戏开发小组闭环引擎（确定性状态机）。

    用确定性代码控制"一套循环 N 个开发"的流程，不让 LLM 决定下一步/是否结束：
      execute → verify → (REJECTED → rework) / (APPROVED → fuse) → integrate → deliver

    核心原则:
      1. 执行-验证分离：dev 只负责做，合格与否由客观验证器裁定，绝不自行裁定"完成"
      2. 确定性状态机：decide() 用代码决定流转，不让 LLM 自决
      3. 硬性熔断：单 dev 重做超 max_attempts 上报 Leader 换方案；
                   总迭代超 max_iterations 熔断；空闲超时判卡死
      4. 进度北极星监督：写 goal_meter，停滞/横跳/重复错误可被拦截
      5. 记录优先于对话：过程只写进度留痕，干完统一交付给经理
    """

    def __init__(self,
                 devs_per_team: int = DEFAULT_DEVS_PER_TEAM,
                 max_attempts: int = DEFAULT_MAX_ATTEMPTS,
                 max_iterations: int = DEFAULT_MAX_ITERATIONS,
                 max_idle_seconds: float = DEFAULT_MAX_IDLE_SECONDS,
                 verifier: Optional[Callable[[DevTask], tuple]] = None,
                 sentinel: Optional[Callable[[DevTask], bool]] = None):
        """
        verifier: Callable(task)->(ok, note)，客观验证器（测试/lint/编译）。None 用内置默认。
        sentinel: Callable(task)->bool，进度北极星哨兵，返回 True 表示停滞/横跳需拦截。
        """
        self.devs_per_team = max(1, int(devs_per_team))
        self.max_attempts = max_attempts
        self.max_iterations = max_iterations
        self.max_idle_seconds = max_idle_seconds
        self.verifier = verifier or self._default_verifier
        self.sentinel = sentinel
        self.team: Optional[GameDevTeam] = None
        self.fused_artifact: Dict[str, Any] = {}
        self.metrics: Dict[str, Any] = field(default_factory=dict) if False else {}
        self.logs: List[str] = []

    # ---------- 日志 ----------
    def _log(self, msg: str):
        self.logs.append(f"[{time.strftime('%H:%M:%S')}] {msg}")

    # ---------- 小组构建 ----------
    def create_team(self, team_id: str, leader: str, dev_roles: List[str],
                    module: str, desc: str = "", goal_total: float = 1.0) -> GameDevTeam:
        """创建开发小组：Leader + N 开发，每个开发一个 DevTask。"""
        if len(dev_roles) < 1:
            raise ValueError("开发小组至少需要 1 个开发角色")
        if len(dev_roles) > self.devs_per_team:
            # 若传入开发数超过 devs_per_team，截断（一套循环 N 个开发）
            dev_roles = dev_roles[:self.devs_per_team]
        team = GameDevTeam(team_id=team_id, leader=leader, devs=list(dev_roles))
        for role in dev_roles:
            team.tasks[role] = DevTask(
                dev_role=role, module=module, desc=desc,
                goal_total=goal_total,
            )
        self.team = team
        self._log(f"创建开发小组 {team_id}: Leader={leader} 开发={dev_roles}（一套循环 {len(dev_roles)} 个开发）")
        return team

    # ---------- 开发执行 ----------
    def execute_dev(self, dev_role: str,
                    produce: Optional[Callable[[DevTask], Dict[str, Any]]] = None) -> DevTask:
        """让一个开发执行其子任务（Coder 只负责"做"）。"""
        task = self.team.tasks.get(dev_role)
        if task is None:
            raise KeyError(f"开发角色 {dev_role} 不在当前小组内")
        if task.is_done():
            return task
        task.status = "IN_PROGRESS"
        task.attempts += 1
        task.last_activity = time.time()
        if produce:
            artifact = produce(task)
        else:
            artifact = self._default_produce(task)
        task.artifact = artifact
        # 进度北极星：记录完成度推进（执行推进当前节点）
        task.goal_meter = min(task.goal_total, task.goal_meter + 0.5)
        self._log(f"开发 {dev_role} 执行产出 {task.module}（第{task.attempts}次）")
        return task

    # ---------- 客观验证 ----------
    def verify_dev(self, dev_role: str) -> str:
        """客观验证器裁定某开发产出：返回 APPROVED / REJECTED。"""
        task = self.team.tasks.get(dev_role)
        if task is None or task.status != "IN_PROGRESS":
            return REJECTED
        # 进度北极星哨兵：停滞/横跳/重复错误 → 拦截
        if self.sentinel and self.sentinel(task):
            task.status = REJECTED
            task.verify_note = "哨兵拦截：进度停滞/横跳"
            self._log(f"开发 {dev_role} 被哨兵拦截：{task.verify_note}")
            return REJECTED
        ok, note = self.verifier(task)
        task.verify_note = note
        if ok:
            task.status = APPROVED
            task.goal_meter = task.goal_total  # 验证通过 = 完成度打满
            self._log(f"开发 {dev_role} 验证通过 APPROVED")
            return APPROVED
        task.status = REJECTED
        self._log(f"开发 {dev_role} 验证驳回 REJECTED：{note}")
        return REJECTED

    # ---------- 确定性状态机（Orchestrator 核心） ----------
    def run_round(self,
                  produce: Optional[Callable[[DevTask], Dict[str, Any]]] = None) -> DevRound:
        """
        跑一轮小组循环：全部未完成开发 execute → 全部 verify。
        返回本轮记录。
        """
        if self.team is None:
            raise RuntimeError("尚未创建开发小组，请先 create_team")
        round_no = len(self.team.rounds) + 1
        if round_no > self.max_iterations:
            self._log("熔断：总迭代次数超 max_iterations")
            raise RuntimeError(f"开发小组熔断：迭代超过 {self.max_iterations} 次")
        r = DevRound(round_no=round_no)
        pending = [t.dev_role for t in self.team.tasks.values() if not t.is_done()]
        for role in pending:
            task = self.team.tasks[role]
            # 硬性熔断：单个开发重做超上限 → 上报 Leader 换方案
            if task.attempts >= self.max_attempts and task.status == REJECTED:
                task.status = REJECTED
                task.verify_note = f"熔断：单开发重做超 {self.max_attempts} 次，上报 Leader 换方案"
                r.rejected.append(role)
                self._log(f"开发 {role} 熔断上报 Leader：{task.verify_note}")
                continue
            # 空闲超时判定卡死
            if time.time() - task.last_activity > self.max_idle_seconds:
                r.rejected.append(role)
                self._log(f"开发 {role} 空闲超时，判定卡死")
                continue
            # 执行-验证分离
            self.execute_dev(role, produce)
            r.tasks.append(role)
            result = self.verify_dev(role)
            if result == APPROVED:
                r.verified.append(role)
            else:
                r.rejected.append(role)
        # 全组 APPROVED → 小组长整合（fuse）
        all_done = all(t.is_done() for t in self.team.tasks.values())
        if all_done:
            fused = self._fuse()
            r.fused = list(fused.get("integrated", {}).keys())
        self.team.rounds.append(r)
        return r

    def _fuse(self) -> Dict[str, Any]:
        """小组长整合全组开发产出为统一交付物（Leader 收尾整合）。"""
        modules = {}
        for role, task in self.team.tasks.items():
            if task.artifact is not None:
                modules[role] = task.artifact
                task.status = "FUSED"
        self.fused_artifact = {
            "team_id": self.team.team_id,
            "leader": self.team.leader,
            "devs": list(self.team.devs),
            "module": next(iter(self.team.tasks.values())).module,
            "integrated": modules,
            "dev_count": len(self.team.devs),
            "fused_at": time.time(),
        }
        self._log(f"小组长整合全组 {len(modules)} 份开发产出，形成统一交付物")
        return self.fused_artifact

    # ---------- 统一交付 ----------
    def deliver_to_manager(self, manager_role: str = "producer",
                           notify: Optional[Callable[[str, Dict[str, Any]], None]] = None) -> Dict[str, Any]:
        """
        干完统一交付给经理（一次性通知 + 完整进度回放）。
        notify: 回调（manager_role, payload）；None 时仅记录。
        返回交付物。
        """
        if not self.fused_artifact:
            raise RuntimeError("尚未整合产出，不能交付")
        payload = {
            "event": "dev_team_deliver",
            "team_id": self.team.team_id,
            "leader": self.team.leader,
            "artifact": self.fused_artifact,
            "progress": self.progress_history(),
        }
        if notify:
            notify(manager_role, payload)
        self.team.delivered = True
        self._log(f"统一交付给经理 {manager_role}（含完整进度回放）")
        return payload

    # ---------- 二级信息 ----------
    def progress_history(self) -> Dict[str, Any]:
        """进度回放：每轮每个开发的状态与完成度。"""
        history = []
        for r in self.team.rounds:
            history.append({
                "round": r.round_no,
                "executed": r.tasks,
                "verified": r.verified,
                "rejected": r.rejected,
                "fused": r.fused,
            })
        return {
            "team_id": self.team.team_id,
            "leader": self.team.leader,
            "devs": list(self.team.devs),
            "rounds": history,
            "dev_ratio": self.dev_ratio(),
        }

    def team_overview(self) -> Dict[str, Any]:
        """小组俯瞰：每个开发当前状态 + 完成度。"""
        return {
            "team_id": self.team.team_id,
            "leader": self.team.leader,
            "devs": [
                {
                    "role": t.dev_role,
                    "status": t.status,
                    "goal_meter": t.goal_meter,
                    "goal_total": t.goal_total,
                    "attempts": t.attempts,
                    "verify_note": t.verify_note,
                }
                for t in self.team.tasks.values()
            ],
            "delivered": self.team.delivered,
        }

    # ---------- 开发密度量化 ----------
    def dev_ratio(self) -> float:
        """
        开发密度量化：开发实干角色占比。
        辅助质量闸门（评审/测试）在小组外，不挤占开发名额。
        """
        if self.team is None:
            return 0.0
        dev_count = len(self.team.devs)
        # 实干角色 = 开发 + 小组长（整合），辅助（评审/测试/经理）不算
        working = dev_count + 1  # +1 小组长
        return round(dev_count / working, 2) if working else 0.0

    # ---------- 内置默认实现 ----------
    def _default_produce(self, task: DevTask) -> Dict[str, Any]:
        """默认产出：按模块生成一个可验证的制品（供无注入时自测）。"""
        return {
            "module": task.module,
            "dev_role": task.dev_role,
            "artifact_type": "code",
            "content": f"{task.module} 实现产物（{task.dev_role}）",
        }

    def _default_verifier(self, task: DevTask) -> tuple:
        """默认客观验证器：产出非空即通过（供无注入时自测）。"""
        if not task.artifact or not task.artifact.get("content"):
            return False, "开发产出为空"
        return True, "客观验证通过（产出非空）"


# ============================================================
# 三、便捷 API（供部门 Agent / 测试直接使用）
# ============================================================

def run_dev_team(work_package: Dict[str, Any],
                 dev_roles: Optional[List[str]] = None,
                 leader: str = "cto",
                 devs_per_team: int = DEFAULT_DEVS_PER_TEAM,
                 verifier: Optional[Callable[[DevTask], tuple]] = None,
                 produce: Optional[Callable[[DevTask], Dict[str, Any]]] = None,
                 max_iterations: int = DEFAULT_MAX_ITERATIONS) -> Dict[str, Any]:
    """
    一站式运行一个游戏开发小组闭环，返回完整结果。

    work_package: {module, label, project, ...}
    dev_roles: 小组内开发角色清单（默认程序线客户端+服务端，一套循环 2 个开发）
    """
    module = work_package.get("module", "program")
    wp_id = work_package.get("id") or work_package.get("label") or module
    if dev_roles is None:
        # 默认程序线开发小组：客户端 + 服务端（一套循环 2 个开发）
        dev_roles = ["client_dev", "server_dev"]

    engine = GameDevTeamEngine(devs_per_team=devs_per_team,
                               verifier=verifier, max_iterations=max_iterations)
    team = engine.create_team(
        team_id=f"{wp_id}__team",
        leader=leader,
        dev_roles=dev_roles,
        module=module,
        desc=work_package.get("label", module),
    )
    try:
        while not all(t.is_done() for t in team.tasks.values()):
            engine.run_round(produce=produce)
    except RuntimeError as e:
        return {
            "ok": False,
            "team_id": team.team_id,
            "reason": str(e),
            "overview": engine.team_overview(),
        }
    deliver = engine.deliver_to_manager(manager_role="producer")
    return {
        "ok": True,
        "team_id": team.team_id,
        "leader": team.leader,
        "devs": list(team.devs),
        "dev_count": len(team.devs),
        "dev_ratio": engine.dev_ratio(),
        "artifact": engine.fused_artifact,
        "deliver": deliver,
        "overview": engine.team_overview(),
        "progress": engine.progress_history(),
    }


# ============================================================
# 四、主程序（自测冒烟）
# ============================================================
if __name__ == "__main__":
    wp = {"id": "wp_demo", "module": "client", "label": "demo 玩法实现", "project": "Demo"}
    r = run_dev_team(wp, dev_roles=["client_dev", "server_dev"])
    print("== 游戏开发小组闭环自测 ==")
    print("ok:", r["ok"])
    print("dev_count:", r.get("dev_count"))
    print("dev_ratio:", r.get("dev_ratio"))
    print("overview:", r.get("overview"))
    print("progress_rounds:", r.get("progress", {}).get("rounds"))
