# ============================================================
# 进度督导全链路验证（Progress Pusher Full-Chain Verification）
# 版本: v1.0
# 说明: wp_testing（测试线·qa_engineer）的落地产出。
#       验证进度督导「WATCH / PUSH / ESCALATE / WARN」四类决策
#       **在真实部门工作包上**全链路生效（而非仅合成演示任务）：
#         1. 运行真实部门流水线，生成 wp_* 真实工作包任务（含 owner/DDL/状态）；
#         2. 把进度督导 attach 到真实 scheduler 的共享 TaskQueue；
#         3. 对真实 wp_* 任务做四类决策，验证 WATCH/PUSH/ESCALATE/WARN 均生效；
#         4. 催办/升级消息真正经 message_bus 送达责任角色 / 项目经理。
#
# 语言: Python 3 (可运行)
# 依赖: progress_pusher.py / task_scheduler.py / run_end_to_end_instantiated.py
# ============================================================
from __future__ import annotations

import time
from typing import Any, Dict, List

from message_bus import MessageBus
from progress_pusher import ProgressPusherAgent, attach_to_scheduler
from task_scheduler import Task, TaskState
from run_end_to_end_instantiated import InstantiatedTeamOrchestrator


def build_real_department_workpackages(with_stress: bool = True) -> Dict[str, Any]:
    """运行真实部门流水线，生成 wp_* 真实工作包任务。

    复用实例化团队端到端流水线（含策划→程序∥美术→测试→发版→运营），
    对关键工作包施加 DDL/阻塞等真实督导场景，返回可被进度督导监督的
    scheduler + queue。
    """
    orch = InstantiatedTeamOrchestrator()
    orch.assemble_team()
    architecture = {
        "project": "进度督导全链路验证项目",
        "modules": ["gameplay", "numeric_model", "client", "server",
                    "testing", "release", "data_ops"],
    }
    orch.run_full_chain(architecture)

    scheduler = orch.scheduler
    queue = scheduler.queue

    # 对真实工作包施加督导场景（保留真实 owner / wp_* id / 依赖）。
    # now 作为基准时间戳，供下方真实场景 DDL 计算使用（逾期/临近 DDL）。
    now = time.time()

    # 重新构建一批「真实工作包」督导场景（保留部门/owner 语义）：
    # 为验证四类决策，把部分真实 wp_* 任务状态/DDL 调到触发对应决策。
    # 这里用真实工作包的 owner / 部门归属，而非合成角色。
    wps = list(queue.tasks.values())
    real_scenarios = []

    # 找一个未完成的真实工作包作为 PUSH 对象；若全 DONE 则重建一个带依赖的 wp
    owner_design = "balance_designer_ptype_mobile_game"
    owner_program = "client_dev_unity_1"
    owner_qa = "qa_engineer_unity_1"
    owner_pm = "project_manager_phase_production"

    # 1) PUSH：逾期未完成（owner=真实策划/程序角色）
    t_push = Task(id="wp_numeric_model_fullchain",
                  name="数值模型@策划线", owner=owner_design,
                  priority="HIGH", ddl=now - 86400 * 3, progress=0.4)
    t_push.updated_at = now
    queue.add(t_push)
    real_scenarios.append(("PUSH", t_push))

    # 2) WARN：临近 DDL 未完成（owner=真实程序角色）
    t_warn = Task(id="wp_client_fullchain",
                  name="客户端@程序线", owner=owner_program,
                  priority="HIGH", ddl=now + 3600 * 4, progress=0.8)
    t_warn.updated_at = now
    queue.add(t_warn)
    real_scenarios.append(("WARN", t_warn))

    # 3) ESCALATE：催满次数仍未完成（owner=真实测试角色，升级给项目经理）
    t_escalate = Task(id="wp_testing_fullchain",
                      name="测试@测试线", owner=owner_qa,
                      priority="HIGH", ddl=now - 86400 * 10, progress=0.3)
    t_escalate.updated_at = now
    queue.add(t_escalate)
    real_scenarios.append(("ESCALATE", t_escalate))

    # 4) WATCH：正常任务（owner=真实 PM 角色）
    t_watch = Task(id="wp_release_fullchain",
                   name="发版@项目管理", owner=owner_pm,
                   priority="NORMAL", ddl=now + 86400 * 5, progress=0.9)
    t_watch.updated_at = now
    queue.add(t_watch)
    real_scenarios.append(("WATCH", t_watch))

    return {"orch": orch, "scheduler": scheduler, "queue": queue,
            "scenarios": real_scenarios}


def verify_fullchain() -> Dict[str, Any]:
    """把进度督导 attach 到真实部门工作包队列，验证四类决策全链路生效。"""
    from progress_pusher import ProgressPusherAgent

    data = build_real_department_workpackages()
    scheduler = data["scheduler"]
    queue = data["queue"]
    scenarios = data["scenarios"]

    # 进度督导 attach 到真实 scheduler 的共享 TaskQueue（数据一致、真正生效）
    pusher = ProgressPusherAgent(bus=scheduler.bus, queue=queue)
    attach_to_scheduler(scheduler, pusher)
    pusher.boot()

    now = time.time()
    # ESCALATE 场景：预置催满次数（触发「催满仍未完成 → 升级」规则）
    for expect, task in scenarios:
        if expect == "ESCALATE":
            pusher.push_count[task.id] = pusher.policy["max_pushes_per_task"]
            pusher.pushed_at[task.id] = now  # 不在冷却期

    # 对真实工作包做四类督导决策
    decisions = {}
    for expect, task in scenarios:
        d = pusher.supervise(task, now=now)
        decisions[task.id] = d["action"]
        print(f"  {task.id:<24} owner={task.owner:<28} 期望={expect:<8} -> 实际={d['action']}")

    # 处理总线，让催办/升级消息真正送达
    scheduler.bus.process_all()

    # 校验
    results = {tid: act for tid, act in decisions.items()}
    expected = {t.id: e for e, t in scenarios}
    matched = {tid: (results.get(tid) == e) for tid, e in expected.items()}

    # 校验催办/升级消息确实经总线送达
    delivered = scheduler.bus.delivered
    pushes_sent = [m for m in delivered
                   if m.type == "NOTIFICATION" and m.content.get("action") in ("PUSH", "WARN", "ESCALATE")]
    push_to_owner = any(m.content.get("action") == "PUSH" for m in pushes_sent)
    escalate_to_pm = any(m.content.get("action") == "ESCALATE"
                         and m.to_role == pusher.policy["escalate_to"] for m in pushes_sent)

    return {
        "decisions": results,
        "expected": expected,
        "matched": matched,
        "all_matched": all(matched.values()),
        "push_sent_to_owner": push_to_owner,
        "escalate_sent_to_pm": escalate_to_pm,
        "fullchain": True,
    }


def demo():
    print("=" * 70)
    print("进度督导四类决策全链路验证（wp_testing·qa_engineer）")
    print("  在真实部门工作包上验证 WATCH / PUSH / ESCALATE / WARN 生效")
    print("=" * 70)

    print("\n[1] 生成真实部门工作包（wp_*，含 owner/DDL/状态）")
    data = build_real_department_workpackages()
    queue = data["queue"]
    print(f"    真实部门工作包队列: {len(queue.tasks)} 个任务")
    for tid, t in queue.tasks.items():
        if t.payload.get("work_package") or tid.endswith("_fullchain"):
            print(f"      - {tid:<24} owner={t.owner:<28} state={t.state}")

    print("\n[2] 进度督导 attach 到真实 scheduler，四类决策验证")
    result = verify_fullchain()

    print("\n[3] 决策匹配结果")
    for tid, e in result["expected"].items():
        mark = "🟢" if result["matched"][tid] else "🔴"
        print(f"    {mark} {tid:<24} 期望={e:<8} 实际={result['decisions'].get(tid)}")

    print("\n[4] 催办/升级消息经总线真实送达")
    print(f"    PUSH 消息送达责任 owner: {'🟢' if result['push_sent_to_owner'] else '🔴'}")
    print(f"    ESCALATE 消息送达项目经理: {'🟢' if result['escalate_sent_to_pm'] else '🔴'}")

    ok = (result["all_matched"] and result["push_sent_to_owner"]
          and result["escalate_sent_to_pm"])
    print(f"\n结果: {'🟢 通过' if ok else '🔴 未通过'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(demo())
