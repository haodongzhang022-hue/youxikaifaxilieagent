# ============================================================
# 可调配小组池 (SquadPool)
# 版本: v1.0
# 说明: 小组**不隶属于任何部门**，作为独立资源池存在。
#       - 任何部门（策划线/程序线/美术线/测试线/项目管理/运营线）
#         都可以按需「调配」小组执行任务；
#       - 小组完成任务后**释放回池**，可被**重复调用**；
#       - **多个小组**并存，分别做不一样的事（按领域/技能标签寻址）。
#
# 与部门内小组的区别:
#   - 部门内小组（game_dev_team）: 固定在部门内部，随部门生命周期存在；
#   - 可调配小组（squad_pool）: 独立于部门，全局共享，按需调配、用完归还。
#
# 与 Goose 四维闭环的关系:
#   - 每个可调配小组内部仍走「执行-验证-规划-监督」闭环；
#   - 但小组本身是**可调配资源**，而非固定部门编制。
#
# 语言: Python 3 (可运行，不依赖第三方库)
# ============================================================
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ============================================================
# 一、小组状态常量
# ============================================================

# 小组状态
SQUAD_IDLE = "IDLE"        # 空闲待命，可被调配
SQUAD_BUSY = "BUSY"        # 正在执行任务（被某部门调配中）
SQUAD_READY = "READY"      # 任务完成，待释放
SQUAD_BLOCKED = "BLOCKED"  # 阻塞/异常，不可调配

# 调配结果
ACQUIRE_OK = "ACQUIRED"
ACQUIRE_NO_SQUAD = "NO_SQUAD"
ACQUIRE_BUSY = "ALL_BUSY"
ACQUIRE_UNREG = "UNREGISTERED"


# ============================================================
# 二、可调配小组 (Squad)
# ============================================================

@dataclass
class Squad:
    """一个可调配小组（独立于部门，全局共享资源）。

    每个小组:
      - 有唯一 squad_id；
      - 有领域/技能标签（skills），用于按需寻址（"做不一样的事"）；
      - 有小组长（leader）和成员（members）；
      - 有独立状态（IDLE/BUSY/READY/BLOCKED）；
      - 可被任何部门调配（acquire），完成后释放回池（release）重复使用。
    """
    squad_id: str                       # 唯一标识
    name: str                           # 小组名称（如 "客户端开发A组"）
    domain: str                         # 领域（如 "client_dev" / "ai_dev" / "ui_dev"）
    skills: List[str] = field(default_factory=list)   # 技能标签（"做不一样的事"的寻址依据）
    leader: str = ""                    # 小组长 role_id
    members: List[str] = field(default_factory=list)  # 小组成员 role_id 列表
    status: str = SQUAD_IDLE            # 当前状态
    owner_department: str = ""          # 当前调配方（哪个部门正在使用）
    task_id: str = ""                   # 当前执行的任务 id
    acquired_at: float = 0.0            # 被调配时间戳
    released_at: float = 0.0            # 释放回池时间戳
    assign_count: int = 0               # 累计被调配次数（"重复调用"留痕）
    created_at: float = field(default_factory=time.time)
    extra: Dict[str, Any] = field(default_factory=dict)   # 扩展信息

    def __post_init__(self):
        if not self.squad_id:
            self.squad_id = f"squad_{uuid.uuid4().hex[:8]}"
        if not self.leader:
            self.leader = f"{self.domain}_lead"
        if not self.members:
            self.members = [f"{self.domain}_member_{i}" for i in range(1, 4)]

    # ---------- 状态查询 ----------
    @property
    def is_available(self) -> bool:
        """是否可被调配（空闲待命）"""
        return self.status == SQUAD_IDLE

    @property
    def is_busy(self) -> bool:
        return self.status == SQUAD_BUSY

    def has_skill(self, skill: str) -> bool:
        """判断小组是否具备某技能/领域（大小写不敏感）"""
        skill_l = skill.lower()
        if skill_l in self.domain.lower():
            return True
        return any(s.lower() in skill_l or skill_l in s.lower()
                   for s in self.skills)

    # ---------- 状态流转 ----------
    def acquire(self, department: str, task_id: str = "") -> None:
        """被调配：进入 BUSY 状态"""
        self.status = SQUAD_BUSY
        self.owner_department = department
        self.task_id = task_id
        self.acquired_at = time.time()
        self.assign_count += 1

    def release(self) -> None:
        """释放回池：任务完成后归还，可被重复调用"""
        self.status = SQUAD_IDLE
        self.owner_department = ""
        self.task_id = ""
        self.released_at = time.time()

    def block(self, reason: str = "") -> None:
        """阻塞小组（异常/待修复）"""
        self.status = SQUAD_BLOCKED
        self.extra["block_reason"] = reason

    def ready(self) -> None:
        """解除阻塞，回到空闲"""
        self.status = SQUAD_IDLE

    # ---------- 序列化 ----------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "squad_id": self.squad_id,
            "name": self.name,
            "domain": self.domain,
            "skills": list(self.skills),
            "leader": self.leader,
            "members": list(self.members),
            "status": self.status,
            "owner_department": self.owner_department,
            "task_id": self.task_id,
            "assign_count": self.assign_count,
            "created_at": self.created_at,
            "extra": self.extra,
        }

    def __str__(self):
        return (f"Squad({self.squad_id}, name={self.name}, "
                f"domain={self.domain}, status={self.status})")


# ============================================================
# 三、可调配小组池 (SquadPool)
# ============================================================

class SquadPool:
    """
    可调配小组池管理器。

    全局共享的小组资源池，任何部门/角色都可以：
      - register_squad(): 注册新小组（多种小组分别做不一样的事）
      - acquire(): 按领域/技能调配一个空闲小组
      - release(): 用完归还小组（重复调用）
      - find(): 按领域/技能查可用小组
      - list_squads(): 查看全部小组

    设计原则:
      1. 小组独立于部门——不绑定任何部门编制；
      2. 用完归还——acquire → 执行 → release，归还后可再次被调配；
      3. 领域寻址——按 skills/domain 匹配，"多个小组分别做不一样的事"。
    """

    def __init__(self, max_log_size: int = 1000):
        self._squads: Dict[str, Squad] = {}   # squad_id -> Squad
        self._assign_log: List[Dict[str, Any]] = []  # 调配留痕（有界，最多保留 max_log_size 条）
        self._max_log_size = max_log_size

    # ---------- 注册 / 注销 ----------
    def register_squad(self, squad: Squad) -> Squad:
        """注册一个可调配小组。"""
        if squad.squad_id in self._squads:
            raise ValueError(f"小组 {squad.squad_id} 已注册")
        self._squads[squad.squad_id] = squad
        return squad

    def create_squad(self, name: str, domain: str,
                     skills: Optional[List[str]] = None,
                     leader: str = "",
                     members: Optional[List[str]] = None,
                     squad_id: str = "") -> Squad:
        """创建并注册一个新小组。

        Args:
            name: 小组名称（如 "客户端开发A组"）
            domain: 领域（如 "client_dev" / "ai_dev" / "ui_dev"）
            skills: 技能标签（如 ["cocos", "unity"]）
            leader: 小组长 role_id
            members: 小组成员 role_id 列表
            squad_id: 自定义小组 id（缺省自动生成）
        """
        squad = Squad(
            squad_id=squad_id,
            name=name,
            domain=domain,
            skills=skills or [],
            leader=leader,
            members=members or [],
        )
        return self.register_squad(squad)

    def unregister_squad(self, squad_id: str) -> bool:
        """注销一个小组。"""
        if squad_id in self._squads:
            del self._squads[squad_id]
            return True
        return False

    # ---------- 调配 / 释放 ----------
    def acquire(self, domain: Optional[str] = None,
                skill: Optional[str] = None,
                department: str = "",
                task_id: str = "",
                prefer_idle: bool = True) -> Dict[str, Any]:
        """调配一个小组执行任务。

        寻址规则:
          1. 指定 skill 时：优先匹配具备该技能的小组；
          2. 指定 domain 时：匹配 domain 或 skill 包含该领域的小组；
          3. 都不指定：返回任意一个空闲小组。

        Args:
            domain: 目标领域（如 "client_dev"）
            skill: 目标技能（如 "cocos"）
            department: 调配方（部门名 / 角色名）
            task_id: 要执行的任务 id
            prefer_idle: 仅从空闲小组中调配（True 默认）；False 时若全忙则
                         优先选 assign_count 最少的小组（负载均衡）

        Returns:
            {"ok": bool, "squad": Squad|None, "reason": str}
        """
        candidates = self._find_candidates(domain=domain, skill=skill)

        if not candidates:
            return {
                "ok": False,
                "squad": None,
                "reason": f"没有领域[{domain}]/技能[{skill}]匹配的小组",
                "code": ACQUIRE_NO_SQUAD,
            }

        # 优先选空闲小组
        idle = [s for s in candidates if s.status == SQUAD_IDLE]
        if idle:
            # 多个候选时，优先选 assign_count 最少（负载均衡）
            squad = min(idle, key=lambda s: s.assign_count)
            squad.acquire(department, task_id)
            self._log_assign(squad, department, task_id, ACQUIRE_OK)
            return {"ok": True, "squad": squad, "reason": f"调配 {squad.name}", "code": ACQUIRE_OK}

        # 全部忙碌
        if not prefer_idle and candidates:
            # 允许"抢占式"调配：选 assign_count 最少的小组
            squad = min(candidates, key=lambda s: s.assign_count)
            squad.acquire(department, task_id)
            self._log_assign(squad, department, task_id, ACQUIRE_OK)
            return {"ok": True, "squad": squad, "reason": f"抢占式调配 {squad.name}", "code": ACQUIRE_OK}

        return {
            "ok": False,
            "squad": None,
            "reason": "匹配的小组全部忙碌，请稍后再试",
            "code": ACQUIRE_BUSY,
        }

    def release(self, squad_id: str) -> Dict[str, Any]:
        """释放小组回池（任务完成后归还，可被重复调用）。

        Returns:
            {"ok": bool, "squad": Squad|None, "reason": str}
        """
        squad = self._squads.get(squad_id)
        if squad is None:
            return {"ok": False, "squad": None,
                    "reason": f"小组 {squad_id} 不存在",
                    "code": ACQUIRE_UNREG}
        dept = squad.owner_department
        squad.release()
        self._log_release(squad, department=dept)
        return {"ok": True, "squad": squad,
                "reason": f"{squad.name} 已释放回池，可再次调配",
                "code": "RELEASED"}

    def release_by_department(self, department: str) -> List[str]:
        """释放某部门占用的全部小组（归还回池）。返回释放的小组 id 列表。"""
        released = []
        for sid, s in self._squads.items():
            if s.owner_department == department and s.status == SQUAD_BUSY:
                dept = s.owner_department
                s.release()
                self._log_release(s, department=dept)
                released.append(sid)
        return released

    # ---------- 查询 ----------
    def get(self, squad_id: str) -> Optional[Squad]:
        """按 squad_id 查小组。"""
        return self._squads.get(squad_id)

    def find(self, domain: Optional[str] = None,
             skill: Optional[str] = None,
             status: Optional[str] = None) -> List[Squad]:
        """按条件查小组。"""
        squads = self._find_candidates(domain=domain, skill=skill)
        if status is not None:
            squads = [s for s in squads if s.status == status]
        return squads

    def list_squads(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出全部小组（可选按状态过滤）。"""
        items = []
        for s in self._squads.values():
            if status is None or s.status == status:
                items.append(s.to_dict())
        return items

    def count(self, status: Optional[str] = None) -> int:
        """小组数量（可选按状态过滤）。"""
        if status is None:
            return len(self._squads)
        return sum(1 for s in self._squads.values() if s.status == status)

    def summary(self) -> Dict[str, Any]:
        """小组池总览。"""
        return {
            "total": len(self._squads),
            "idle": self.count(SQUAD_IDLE),
            "busy": self.count(SQUAD_BUSY),
            "ready": self.count(SQUAD_READY),
            "blocked": self.count(SQUAD_BLOCKED),
            "total_assignments": sum(s.assign_count for s in self._squads.values()),
            "squads": self.list_squads(),
        }

    # ---------- 内部方法 ----------
    def _find_candidates(self, domain: Optional[str] = None,
                         skill: Optional[str] = None) -> List[Squad]:
        """按领域/技能筛选候选小组。"""
        squads = list(self._squads.values())
        if domain:
            squads = [s for s in squads if domain.lower() in s.domain.lower()]
        if skill:
            squads = [s for s in squads if s.has_skill(skill)]
        return squads

    def _log_assign(self, squad: Squad, department: str,
                    task_id: str, code: str) -> None:
        self._assign_log.append({
            "event": "assign",
            "squad_id": squad.squad_id,
            "department": department,
            "task_id": task_id,
            "code": code,
            "at": time.time(),
        })
        self._trim_log()

    def _trim_log(self) -> None:
        """裁剪调配留痕，保持有界增长（保留最新 max_log_size 条）。"""
        if len(self._assign_log) > self._max_log_size:
            self._assign_log = self._assign_log[-self._max_log_size:]

    def _append_log(self, entry: Dict[str, Any]) -> None:
        """追加一条留痕记录并裁剪（供内部统一使用）。"""
        self._assign_log.append(entry)
        self._trim_log()

    def _log_release(self, squad: Squad, department: str = "") -> None:
        self._assign_log.append({
            "event": "release",
            "squad_id": squad.squad_id,
            "department": department,
            "at": time.time(),
        })
        self._trim_log()


# ============================================================
# 四、预置小组工厂（快速创建常见小组）
# ============================================================

def create_default_squad_pool() -> SquadPool:
    """创建一组预置可调配小组（多个小组分别做不一样的事）。

    覆盖游戏开发常见领域，每个小组独立、可灵活调配、可重复调用。
    """
    pool = SquadPool()
    pool.create_squad(
        name="客户端开发A组",
        domain="client_dev",
        skills=["client", "ui", "cocos", "unity"],
        leader="client_lead",
        members=["client_dev_1", "client_dev_2"],
    )
    pool.create_squad(
        name="服务端开发B组",
        domain="server_dev",
        skills=["server", "backend", "api", "database"],
        leader="server_lead",
        members=["server_dev_1", "server_dev_2"],
    )
    pool.create_squad(
        name="AI 逻辑C组",
        domain="ai_dev",
        skills=["ai", "behavior_tree", "npc", "adaptive"],
        leader="ai_lead",
        members=["ai_programmer_1", "ai_programmer_2"],
    )
    pool.create_squad(
        name="引擎适配D组",
        domain="engine_dev",
        skills=["engine", "cocos", "unreal", "render"],
        leader="engine_lead",
        members=["engine_dev_1", "engine_dev_2"],
    )
    pool.create_squad(
        name="工具链E组",
        domain="tools_dev",
        skills=["tools", "pipeline", "build", "scaffold"],
        leader="tools_lead",
        members=["tools_dev_1", "tools_dev_2"],
    )
    return pool


# ============================================================
# 五、演示
# ============================================================

def demo():
    print("=" * 70)
    print("可调配小组池 (SquadPool) 演示")
    print("  小组独立于部门 · 可灵活调配 · 可重复调用 · 多组各司其职")
    print("=" * 70)

    pool = create_default_squad_pool()

    print("\n[1] 注册预置小组（5 个小组，分别做不一样的事）")
    print(f"    小组池共 {pool.count()} 个小组")
    for s in pool.list_squads():
        print(f"    {s['squad_id']} | {s['name']} | domain={s['domain']} "
              f"| skills={s['skills']} | status={s['status']}")

    print("\n[2] 程序线调配「客户端开发A组」")
    r1 = pool.acquire(domain="client_dev", department="程序线", task_id="wp_client_01")
    if r1["ok"]:
        squad = r1["squad"]
        print(f"    ✅ 调配成功: {squad.name} → 程序线")
        print(f"    状态: {squad.status} | owner={squad.owner_department} "
              f"| assign_count={squad.assign_count}")

    print("\n[3] 同一小组被再次调用（重复调用）")
    # 先释放
    pool.release(r1["squad"].squad_id)
    print(f"    释放后: {r1['squad'].name} 状态={r1['squad'].status}")
    # 再次调配
    r2 = pool.acquire(domain="client_dev", department="美术线", task_id="wp_ui_02")
    if r2["ok"]:
        print(f"    ✅ 再次调配成功: {r2['squad'].name} → 美术线 "
              f"(assign_count={r2['squad'].assign_count})")

    print("\n[4] 按技能寻址（多个小组分别做不一样的事）")
    ai_squad = pool.acquire(skill="behavior_tree", department="程序线", task_id="wp_ai_01")
    if ai_squad["ok"]:
        print(f"    ✅ 按技能 [behavior_tree] 调配: {ai_squad['squad'].name}")

    print("\n[5] 不同领域小组互不影响")
    engine_squad = pool.acquire(domain="engine_dev", department="程序线", task_id="wp_engine_01")
    if engine_squad["ok"]:
        print(f"    ✅ 调配引擎组: {engine_squad['squad'].name}")
    tools_squad = pool.acquire(domain="tools_dev", department="测试线", task_id="wp_tools_01")
    if tools_squad["ok"]:
        print(f"    ✅ 调配工具链组: {tools_squad['squad'].name}")

    print("\n[6] 全部归还后小组池状态")
    pool.release_by_department("程序线")
    pool.release_by_department("美术线")
    pool.release_by_department("测试线")
    summary = pool.summary()
    print(f"    总小组={summary['total']} | 空闲={summary['idle']} "
          f"| 忙碌={summary['busy']} | 累计调配={summary['total_assignments']}")

    print("\n[7] 未注册领域查询")
    r = pool.acquire(domain="narrative_design", department="策划线")
    print(f"    调配 narrative_design: ok={r['ok']} reason={r['reason']}")

    # 断言核心能力
    ok = (pool.count() == 5
          and r1["ok"] and r2["ok"] and ai_squad["ok"]
          and engine_squad["ok"] and tools_squad["ok"]
          and not r["ok"]
          and summary["total"] == 5 and summary["idle"] == 5)
    print(f"\n结果: {'🟢 通过' if ok else '🔴 未通过'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(demo())
