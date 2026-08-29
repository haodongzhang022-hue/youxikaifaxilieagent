# ============================================================
# 可调配小组自动化调度模块 (SquadAutoScheduler)
# 版本: v1.0
# 说明: 解决「可调配小组池（SquadPool）」的**自动化对接**问题：
#       - **自动触发**：部门 Agent 收到工作包时，若工作包声明需要可调配小组
#         （work_package['squad_domain']），自动从小组池调配对应领域小组执行，
#         无需手动调用 dispatch_to_squad_by_domain()；
#       - **自动释放**：工作包执行完成（上报 REVIEW_RESULT）后，自动把调配的
#         小组释放回池，供其他部门/工作包重复调用。
#
# 与既有显式调用的区别：
#   - 既有 `dispatch_to_squad()` / `dispatch_to_squad_by_domain()` 需要**手动**触发
#     和**手动**释放；
#   - 本模块把这些动作**自动化**，接入部门 Agent 执行流程（_on_task_assign），
#     实现「收到工作包 → 自动调配小组 → 执行 → 自动释放」全链路闭环。
#
# 语言: Python 3 (可运行，不依赖第三方库)
# ============================================================
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from squad_pool import (SquadPool, Squad, create_default_squad_pool,
                       SQUAD_IDLE, SQUAD_BUSY, SQUAD_READY, SQUAD_BLOCKED)


# ============================================================
# 自动化调度器
# ============================================================

class SquadAutoScheduler:
    """
    可调配小组自动化调度器。

    统一封装「自动触发调配 + 自动释放」逻辑，接入部门 Agent 执行流程：
      - 部门 Agent 收到工作包 → 调用 `auto_acquire_and_dispatch()`：
          若工作包声明 `squad_domain`，自动从池调配小组并派发；
      - 部门 Agent 执行完成 → 调用 `auto_release_for_wp()`：
          自动把本次调配的小组释放回池。

    关键设计：
      1. **自动触发**：工作包携带 `squad_domain` 字段即视为"需要可调配小组"，
         自动按领域匹配并调配空闲小组；
      2. **自动释放**：工作包 id → 已调配小组 id 的映射留痕，完成后自动归还；
      3. **重复调用**：小组释放后回到 IDLE，可被后续工作包再次调配；
      4. **容错**：调配失败不阻塞部门执行（部门走自身内部实现兜底）；
         释放失败不阻塞验收（记录告警）。
    """

    def __init__(self, squad_pool: Optional[SquadPool] = None,
                 max_track: int = 1000):
        """初始化自动化调度器。

        Args:
            squad_pool: 可调配小组池（缺省时创建默认小组池）
            max_track: 工作包→小组映射留痕上限（有界，防止无限增长）
        """
        self.squad_pool = squad_pool or create_default_squad_pool()
        # 工作包 id → 已调配的小组 id（用于任务完成后自动释放）
        self._wp_squad_map: Dict[str, str] = {}
        # 领域 → 本调度器最后调配给某工作包的小组（供同一部门复用）
        self._last_acquired: Dict[str, str] = {}
        # 自动化调度留痕（有界）
        self._auto_log: List[Dict[str, Any]] = []
        self._max_track = max_track
        self.auto_trigger_enabled = True   # 自动触发开关
        self.auto_release_enabled = True   # 自动释放开关

    # ============================================================
    # 自动触发调配
    # ============================================================

    def auto_acquire_and_dispatch(self, work_package: Dict[str, Any],
                                  dispatch_cap,
                                  department: str = "") -> Dict[str, Any]:
        """自动触发调配：工作包声明需要小组时自动从池调配并派发。

        触发规则：
          - work_package['squad_domain'] 存在 → 需要可调配小组；
          - 自动按领域调配空闲小组（优先复用已被本部门占用的同领域小组）；
          - 若小组已调配给本部门且正在执行该工作包，则直接复用不重复调配。

        Args:
            work_package: 标准工作包（须含 id / label）
            dispatch_cap: DispatchCapability 实例（用于派发）
            department: 调配方部门名

        Returns:
            {"auto_dispatched": bool, "squad_id": str|None, "reason": str}
        """
        if not self.auto_trigger_enabled:
            return {"auto_dispatched": False, "squad_id": None,
                    "reason": "自动触发已关闭"}

        squad_domain = work_package.get("squad_domain")
        if not squad_domain:
            return {"auto_dispatched": False, "squad_id": None,
                    "reason": "工作包未声明 squad_domain，不需要小组"}

        wp_id = work_package.get("id", "")
        caller = department or "unknown"

        # 1) 复用：本部门已调配的同领域小组（正在执行该工作包）
        if wp_id in self._wp_squad_map:
            squad_id = self._wp_squad_map[wp_id]
            squad = self.squad_pool.get(squad_id)
            if squad and squad.status == SQUAD_BUSY:
                self._log("auto_reuse", f"复用小组 {squad.name} 执行 {wp_id}")
                return {"auto_dispatched": True, "squad_id": squad_id,
                        "reason": f"复用已调配小组 {squad.name}"}

        # 2) 查已注册的匹配小组（优先找空闲的）
        candidates = self.squad_pool.find(domain=squad_domain)
        idle_candidates = [s for s in candidates if s.status == SQUAD_IDLE]
        busy_same_dept = [s for s in candidates
                          if s.status == SQUAD_BUSY
                          and s.owner_department == caller]

        target = None
        # 优先复用本部门已占用的同领域小组（多任务共用一个小队）
        if busy_same_dept:
            target = busy_same_dept[0]
        elif idle_candidates:
            # 自动从池中调配：选 assign_count 最少（负载均衡）
            target = min(idle_candidates, key=lambda s: s.assign_count)

        if target is None:
            self._log("auto_no_squad", f"领域[{squad_domain}]无可调配小组"
                      f"（空闲 {len(idle_candidates)} 个，忙碌 {len(candidates)-len(idle_candidates)} 个）")
            return {"auto_dispatched": False, "squad_id": None,
                    "reason": f"领域[{squad_domain}]无可调配小组"}

        # 3) 调用 dispatch_to_squad 派发（会处理 acquire / release / 状态流转）
        result = dispatch_cap.dispatch_to_squad(
            target.squad_id, work_package, caller)

        if result.dispatched:
            # 记录映射，供任务完成后自动释放
            self._wp_squad_map[wp_id] = target.squad_id
            self._last_acquired[squad_domain] = target.squad_id
            self._log("auto_trigger", f"自动调配小组 {target.name} 执行 {wp_id} → {result.owner}")
            return {"auto_dispatched": True, "squad_id": target.squad_id,
                    "reason": f"自动调配 {target.name} 执行 {wp_id}"}
        else:
            self._log("auto_trigger_fail",
                      f"自动调配小组 {target.name} 派发失败: {result.reason}")
            return {"auto_dispatched": False, "squad_id": None,
                    "reason": f"自动调配派发失败: {result.reason}"}

    # ============================================================
    # 自动释放
    # ============================================================

    def auto_release_for_wp(self, work_package_id: str) -> Dict[str, Any]:
        """自动释放：工作包完成后归还调配的小组到池。

        仅在 auto_release_enabled 开启时生效。
        幂等：同一工作包重复调用不会重复释放。

        Args:
            work_package_id: 已完成的工作包 id

        Returns:
            {"released": bool, "squad_id": str|None, "reason": str}
        """
        if not self.auto_release_enabled:
            return {"released": False, "squad_id": None, "reason": "自动释放已关闭"}

        squad_id = self._wp_squad_map.pop(work_package_id, None)
        if squad_id is None:
            return {"released": False, "squad_id": None,
                    "reason": f"工作包 {work_package_id} 未调配小组，无需释放"}

        squad = self.squad_pool.get(squad_id)
        if squad is None:
            return {"released": False, "squad_id": squad_id,
                    "reason": f"小组 {squad_id} 不存在"}

        # 仅当小组仍被占用（BUSY/READY）时释放
        if squad.status in (SQUAD_BUSY, SQUAD_READY):
            rel = self.squad_pool.release(squad_id)
            self._log("auto_release", f"自动释放小组 {squad.name}（{work_package_id} 完成）")
            return {"released": rel["ok"], "squad_id": squad_id,
                    "reason": f"小组 {squad.name} 已释放回池"}
        elif squad.status == SQUAD_BLOCKED:
            self._log("auto_release_blocked", f"小组 {squad.name} 处于 BLOCKED，跳过释放")
            return {"released": False, "squad_id": squad_id,
                    "reason": f"小组 {squad.name} 处于 BLOCKED"}
        else:  # IDLE
            # 已空闲，无需释放（幂等）
            self._log("auto_release_idle", f"小组 {squad.name} 已空闲，跳过释放")
            return {"released": True, "squad_id": squad_id,
                    "reason": f"小组 {squad.name} 已空闲"}

    def auto_release_by_department(self, department: str) -> List[str]:
        """自动释放某部门占用的全部可调配小组（用于部门整体收尾）。

        Returns:
            已释放的小组 id 列表
        """
        released = self.squad_pool.release_by_department(department)
        # 清理映射中的已释放条目
        stale = [wp for wp, sid in self._wp_squad_map.items()
                 if sid in released]
        for wp in stale:
            del self._wp_squad_map[wp]
        self._log("auto_release_dept", f"自动释放部门[{department}]全部小组: {len(released)} 个")
        return released

    # ============================================================
    # 查询 / 状态
    # ============================================================

    def get_squad_for_wp(self, work_package_id: str) -> Optional[str]:
        """查询某工作包当前调配的小组 id。"""
        return self._wp_squad_map.get(work_package_id)

    def get_wp_for_squad(self, squad_id: str) -> Optional[str]:
        """查询某小组当前关联的工作包 id。"""
        for wp, sid in self._wp_squad_map.items():
            if sid == squad_id:
                return wp
        return None

    def active_squads(self) -> List[str]:
        """当前正被自动调度的小组 id 列表。"""
        return list(set(self._wp_squad_map.values()))

    def summary(self) -> Dict[str, Any]:
        """自动化调度状态总览。"""
        return {
            "auto_trigger_enabled": self.auto_trigger_enabled,
            "auto_release_enabled": self.auto_release_enabled,
            "tracked_work_packages": len(self._wp_squad_map),
            "active_squads": self.active_squads(),
            "total_log": len(self._auto_log),
            "squad_pool": self.squad_pool.summary(),
        }

    def enable_auto_trigger(self, enabled: bool = True):
        """开启/关闭自动触发调配。"""
        self.auto_trigger_enabled = enabled

    def enable_auto_release(self, enabled: bool = True):
        """开启/关闭自动释放。"""
        self.auto_release_enabled = enabled

    # ============================================================
    # 内部方法
    # ============================================================

    def _log(self, event: str, note: str):
        """记录自动化调度留痕（有界）。"""
        self._auto_log.append({
            "event": event, "note": note, "at": time.time(),
        })
        if len(self._auto_log) > self._max_track:
            self._auto_log = self._auto_log[-self._max_track:]


# ============================================================
# 演示 / 自测
# ============================================================

def demo():
    print("=" * 70)
    print("可调配小组自动化调度 (SquadAutoScheduler) 演示")
    print("  自动触发调配 · 自动释放 · 重复调用 · 容错")
    print("=" * 70)

    from message_bus import MessageBus
    from dispatch_capability import DispatchCapability
    from squad_pool import create_default_squad_pool

    bus = MessageBus()
    pool = create_default_squad_pool()
    cap = DispatchCapability("producer", bus=bus, squad_pool=pool)
    auto = SquadAutoScheduler(squad_pool=pool)

    # 注册小组长到总线（供派发）
    for s in pool.list_squads():
        leader = s["leader"]
        if leader not in bus.roles:
            bus.register(leader)
            bus.on(leader, lambda m: None)

    print("\n[1] 自动触发：工作包声明 squad_domain → 自动调配小组")
    wp1 = {"id": "wp_client_auto_001", "label": "客户端 UI 自动化",
           "module": "client", "squad_domain": "client_dev"}
    r1 = auto.auto_acquire_and_dispatch(wp1, cap, department="程序线")
    print(f"    auto_dispatched={r1['auto_dispatched']} squad_id={r1['squad_id']}")
    if r1["auto_dispatched"]:
        s1 = pool.get(r1["squad_id"])
        print(f"    小组状态: {s1.status} | owner={s1.owner_department} | assign_count={s1.assign_count}")

    print("\n[2] 工作包完成后自动释放")
    r2 = auto.auto_release_for_wp(wp1["id"])
    print(f"    released={r2['released']} reason={r2['reason']}")
    if r1["auto_dispatched"]:
        s1 = pool.get(r1["squad_id"])
        print(f"    释放后小组状态: {s1.status}（应为 IDLE）")

    print("\n[3] 同一小组可被重复调用（另一部门再次调配）")
    wp2 = {"id": "wp_client_auto_002", "label": "客户端 UI v2",
           "module": "client", "squad_domain": "client_dev"}
    r3 = auto.auto_acquire_and_dispatch(wp2, cap, department="美术线")
    if r3["auto_dispatched"]:
        s2 = pool.get(r3["squad_id"])
        print(f"    自动调配成功: {s2.name} assign_count={s2.assign_count}")

    print("\n[4] 无 squad_domain 的工作包不触发小组")
    wp3 = {"id": "wp_no_squad", "label": "普通任务", "module": "gameplay"}
    r4 = auto.auto_acquire_and_dispatch(wp3, cap, department="策划线")
    print(f"    auto_dispatched={r4['auto_dispatched']} reason={r4['reason']}")

    print("\n[5] 按领域自动释放（部门收尾）")
    auto.auto_release_by_department("美术线")
    released_squads = [s for s in pool.list_squads() if s["status"] == SQUAD_IDLE]
    print(f"    空闲小组数: {len(released_squads)}")

    print("\n[6] 多个不同领域小组并行自动化")
    wp_a = {"id": "wp_ai_auto", "label": "AI 行为树", "module": "ai_logic",
            "squad_domain": "ai_dev"}
    wp_e = {"id": "wp_engine_auto", "label": "引擎适配", "module": "engine",
            "squad_domain": "engine_dev"}
    ra = auto.auto_acquire_and_dispatch(wp_a, cap, department="程序线")
    re = auto.auto_acquire_and_dispatch(wp_e, cap, department="程序线")
    print(f"    AI 小组: {ra['auto_dispatched']} | 引擎小组: {re['auto_dispatched']}")
    print(f"    当前活跃小组: {len(auto.active_squads())} 个")

    # 清理
    auto.auto_release_for_wp(wp_a["id"])
    auto.auto_release_for_wp(wp_e["id"])
    auto.auto_release_for_wp(wp2["id"])

    # 断言核心能力
    ok = (r1["auto_dispatched"] and r2["released"]
          and r3["auto_dispatched"] and not r4["auto_dispatched"]
          and ra["auto_dispatched"] and re["auto_dispatched"])
    print(f"\n结果: {'🟢 通过' if ok else '🔴 未通过'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(demo())
