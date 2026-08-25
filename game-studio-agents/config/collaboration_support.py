# ============================================================
# 协作支持 Agent 行为逻辑
# 版本: v0.2
# 说明: 定义协作支持圈角色的行为逻辑，
#       让"生产跑得顺"：沟通传递、催进度、资产整理、调解、零工负载均衡。
# 语言: Python (面向架构与原型)
# ============================================================

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ============================================================
# 一、通用消息与状态
# ============================================================

@dataclass
class Message:
    """统一消息结构（复用 v0.1 的消息总线约定）"""
    id: str
    type: str          # TASK / REVIEW / REPORT / BUG / APPROVAL / NOTIFICATION ...
    from_role: str
    to_role: str
    content: Dict = field(default_factory=dict)
    timestamp: float = 0.0
    priority: str = "NORMAL"   # LOW / NORMAL / HIGH / URGENT


@dataclass
class TaskStatus:
    task_id: str
    owner: str
    ddl: float
    progress: float = 0.0      # 0~1
    status: str = "TODO"       # TODO / IN_PROGRESS / BLOCKED / DONE
    last_update: float = 0.0


# ============================================================
# 二、通讯官 (Communicator)
# ============================================================

class Communicator:
    """跨岗位沟通传递：路由 + 转译 + 上下文沉淀"""

    def __init__(self):
        self.routes: Dict[str, str] = {}      # 语义意图 -> 目标岗位
        self.context_log: List[str] = []       # 沟通/决策日志
        self.term_dict = {                     # 跨领域术语映射
            "策划->技术": {"爽感": "game feel / 手感指标", "卡点": "瓶颈/blocker"},
            "技术->策划": {"RPC": "远程调用", "GC": "内存回收"},
            "策划->美术": {"氛围": "lighting & mood", "写实": "realistic style"},
        }

    def route(self, msg: Message) -> Optional[str]:
        """决定消息该给谁"""
        intent = msg.content.get("intent", "")
        return self.routes.get(intent, msg.to_role)

    def translate(self, text: str, src_domain: str, dst_domain: str) -> str:
        """跨领域转译"""
        key = f"{src_domain}->{dst_domain}"
        mapping = self.term_dict.get(key, {})
        for term, gloss in mapping.items():
            text = text.replace(term, f"{term}({gloss})")
        return text

    def archive(self, decision: str, task_id: str):
        """沉淀关键决策上下文"""
        self.context_log.append(f"[{task_id}] {decision}")

    def handle(self, msg: Message) -> Message:
        target = self.route(msg)
        # 跨领域则转译
        if msg.content.get("cross_domain"):
            msg.content["body"] = self.translate(
                msg.content.get("body", ""),
                msg.content.get("src_domain", ""),
                msg.content.get("dst_domain", ""))
        msg.to_role = target
        self.archive(f"消息 {msg.id} 路由给 {target}", msg.content.get("task_id", "-"))
        return msg


# ============================================================
# 三、进度督导 (Progress Pusher)
# ============================================================

class ProgressPusher:
    """进度督导（v1.0 升级版）。

    从 v0.2 的独立演示升级为**程序规则化 + 声明化策略**的可生效 Agent：
      - 继承 BaseAgent，复用 TaskQueue/MessageBus；
      - 决策走 DecisionEngine 规则引擎（WATCH/PUSH/ESCALATE/WARN）；
      - 阈值/节奏/打扰成本抽到 progress_pusher_policy.yaml，可调不碰代码；
      - 详见 config/progress_pusher.py 与 docs/进度督导使用指南.md。

    此处保留薄封装，便于在「协作支持编排演示」中统一调用。
    """

    def __init__(self, lag_threshold: float = 2.0, block_timeout: float = 24.0):
        # 兼容 v0.2 的旧签名：把构造参数并入策略后，交给真正的 Agent
        from progress_pusher import ProgressPusherAgent, load_policy, DEFAULT_POLICY
        policy = load_policy()
        policy.setdefault("lag_threshold_days", lag_threshold)
        policy.setdefault("block_timeout_hours", block_timeout)
        self._agent = ProgressPusherAgent(policy=policy)
        self._agent.boot()   # 加载策略 + 注册规则，确保决策引擎就绪
        self.tasks = self._agent.queue.tasks
        self.lag_threshold = lag_threshold
        self.block_timeout = block_timeout

    def track(self, task: TaskStatus, now: float):
        # 复用 TaskQueue，把 v0.2 的 TaskStatus 转为 Task 结构
        from task_scheduler import Task
        self._agent.queue.add(Task(
            id=task.task_id, owner=task.owner, ddl=task.ddl,
            progress=task.progress, state=task.status,
            updated_at=task.last_update or now))

    def overdue_days(self, task: TaskStatus, now: float) -> float:
        return max(0.0, now - task.ddl)

    def decide_action(self, task: TaskStatus, now: float) -> str:
        """决定：正常 / 催办 / 升级（走规则引擎）"""
        t = self._agent.queue.tasks.get(task.task_id)
        if t is None:
            self.track(task, now)
            t = self._agent.queue.tasks[task.task_id]
        decision = self._agent.supervise(t, now=now)
        return decision["action"]

    def push_message(self, task: TaskStatus, now: float = 0.0) -> Message:
        return Message(
            id=f"push_{task.task_id}", type="NOTIFICATION",
            from_role="progress_pusher", to_role=task.owner,
            content={"action": "PUSH", "task_id": task.task_id,
                     "overdue_days": self.overdue_days(task, now)},
            priority="URGENT" if self.overdue_days(task, now) > self.lag_threshold else "HIGH")

    def escalate(self, task: TaskStatus) -> Message:
        return Message(
            id=f"esc_{task.task_id}", type="NOTIFICATION",
            from_role="progress_pusher", to_role="project_manager",
            content={"action": "ESCALATE", "task_id": task.task_id,
                     "blocker": task.status},
            priority="URGENT")


# ============================================================
# 四、资产管理/清道夫 (Asset Manager / Cleaner)
# ============================================================

@dataclass
class Asset:
    asset_id: str
    name: str
    type: str          # texture / model / config / doc / code / audio ...
    ref_count: int = 0
    used: bool = True
    size_kb: float = 0.0


class AssetManager:
    """整理、去重、清理垃圾资产，维护引用关系"""

    def __init__(self):
        self.assets: Dict[str, Asset] = {}

    def add(self, asset: Asset):
        self.assets[asset.asset_id] = asset

    def find_duplicates(self, name_key: str) -> List[Asset]:
        """按名称特征找出疑似重复资产"""
        return [a for a in self.assets.values() if name_key in a.name]

    def cleanup(self) -> List[str]:
        """清理无引用且未被使用的垃圾资产，返回清理清单"""
        removed = []
        for aid, asset in list(self.assets.items()):
            if asset.ref_count == 0 and not asset.used:
                removed.append(aid)
                del self.assets[aid]
        return removed

    def archive(self, aid: str) -> bool:
        """归档被引用的历史资产"""
        asset = self.assets.get(aid)
        if asset and asset.ref_count == 0:
            asset.used = False   # 移出活跃区
            return True
        return False


# ============================================================
# 五、调解员 (Mediator)
# ============================================================

class Mediator:
    """处理岗位间冲突：调查根因 → 提出折中 → 必要时升级仲裁"""

    def __init__(self, escalate_after_rounds: int = 2):
        self.escalate_after_rounds = escalate_after_rounds
        self.conflict_rounds: Dict[str, int] = {}

    def investigate(self, conflict_id: str, demands: Dict[str, str]) -> Dict:
        """收集多方诉求，找根因"""
        # 简化：根因 = 各方诉求里冲突的点
        keys = set()
        for d in demands.values():
            keys |= set(d.keys())
        root_causes = [k for k in keys if len({d.get(k) for d in demands.values()}) > 1]
        return {"conflict_id": conflict_id, "root_causes": root_causes,
                "demands": demands}

    def propose_compromise(self, analysis: Dict) -> Optional[Dict]:
        """提出折中方案"""
        rc = analysis["root_causes"]
        if not rc:
            return None
        # 简化：对每个冲突根因，给出一个"各让一步"的默认折中
        return {k: "compromise_value" for k in rc}

    def decide(self, conflict_id: str, demands: Dict[str, str]) -> str:
        """决定：折中 or 升级仲裁"""
        self.conflict_rounds[conflict_id] = self.conflict_rounds.get(conflict_id, 0) + 1
        if self.conflict_rounds[conflict_id] > self.escalate_after_rounds:
            return "ARBITRATE"
        return "COMPROMISE"


# ============================================================
# 六、零工/外包池 (Gig Worker Pool)
# ============================================================

class GigWorkerPool:
    """按负载把闲余能力分配给吃紧岗位，做负载均衡提速"""

    def __init__(self):
        self.loads: Dict[str, float] = {}       # 岗位 -> 负载(0~1)
        self.gig_capacity: Dict[str, int] = {}  # 零工 -> 可承接能力
        self.task_pool: List[Dict] = []         # 可外包任务

    def update_load(self, role_id: str, load: float):
        self.loads[role_id] = load

    def most_busy(self, threshold: float = 0.8) -> Optional[str]:
        """找出最吃紧的岗位"""
        busy = [r for r, l in self.loads.items() if l >= threshold]
        if not busy:
            return None
        return max(busy, key=lambda r: self.loads[r])

    def can_outsource(self, task: Dict) -> bool:
        """判断任务能否外包：标准化 + 非核心质量关键"""
        return task.get("standardized", False) and not task.get("core_quality", False)

    def dispatch(self, task: Dict) -> Optional[str]:
        """把可外包任务分派给空闲零工"""
        if not self.can_outsource(task):
            return None
        for gig, cap in self.gig_capacity.items():
            if cap > 0:
                self.gig_capacity[gig] -= 1
                self.task_pool.append({**task, "gig": gig})
                return gig
        return None

    def rebalance_suggestion(self, threshold: float = 0.8) -> List[str]:
        """给出负载均衡建议（谁吃紧、可把哪些活外包）"""
        suggestions = []
        busy = self.most_busy(threshold)
        if busy:
            suggestions.append(f"岗位 {busy} 负载过高，建议将可外包标准化任务交给零工池")
        for task in self.task_pool:
            if not task.get("dispatched"):
                gig = self.dispatch(task)
                if gig:
                    suggestions.append(f"任务 {task['name']} 已外包给 {gig}")
        return suggestions


# ============================================================
# 七、门卫/守门人 (Gatekeeper)
# ============================================================

class Gatekeeper:
    """守发版/入库/合规闸口"""

    def __init__(self):
        self.criteria: Dict[str, List[str]] = {}  # 闸口类型 -> 放行标准项

    def set_criteria(self, gate_type: str, items: List[str]):
        self.criteria[gate_type] = items

    def check(self, gate_type: str, evidence: Dict[str, bool]) -> tuple:
        """逐项核验，返回 (是否放行, 未达标项列表)"""
        required = self.criteria.get(gate_type, [])
        failed = [item for item in required if not evidence.get(item, False)]
        return (len(failed) == 0), failed


# ============================================================
# 八、协作支持编排示例
# ============================================================

def demo():
    print("=" * 60)
    print("协作支持 Agent 行为演示")
    print("=" * 60)

    # 通讯官
    com = Communicator()
    com.routes = {"design_review": "lead_designer", "bug_report": "qa_engineer"}
    msg = Message("m1", "TASK", "system_designer", "unknown",
                  {"intent": "design_review", "body": "提交背包系统设计，卡点在性能", "task_id": "t1"})
    routed = com.handle(msg)
    print(f"\n[通讯官] 消息 {routed.id} 已路由到 {routed.to_role}")

    # 进度督导
    pusher = ProgressPusher(lag_threshold=2.0)
    t = TaskStatus("t1", "client_dev", ddl=10.0, progress=0.5, last_update=5.0)
    pusher.track(t, now=13.0)
    action = pusher.decide_action(t, now=13.0)
    print(f"[进度督导] 任务 t1 决策: {action}")
    if action == "PUSH":
        print(f"  -> 发送催促: {pusher.push_message(t, now=13.0).content['action']}")

    # 资产管理
    am = AssetManager()
    am.add(Asset("a1", "old_tex_001", "texture", ref_count=0, used=False))
    am.add(Asset("a2", "char_hero", "model", ref_count=3, used=True))
    removed = am.cleanup()
    print(f"[资产管理] 清理垃圾资产: {removed}")

    # 调解员
    med = Mediator(escalate_after_rounds=1)
    analysis = med.investigate("c1", {"策划": {"手感": "A"}, "程序": {"手感": "B"}})
    action2 = med.decide("c1", {"策划": {}, "程序": {}})
    print(f"[调解员] 冲突 c1 根因: {analysis['root_causes']}, 决策: {action2}")

    # 零工池
    pool = GigWorkerPool()
    pool.update_load("server_dev", 0.9)
    pool.gig_capacity = {"gig_1": 2}
    suggestions = pool.rebalance_suggestion(threshold=0.8)
    print(f"[零工池] 负载均衡建议: {suggestions}")

    # 门卫
    gk = Gatekeeper()
    gk.set_criteria("release", ["no_critical_bug", "tests_passed"])
    passed, failed = gk.check("release", {"no_critical_bug": True, "tests_passed": False})
    print(f"[门卫] 发版门禁: 放行={passed}, 未达标={failed}")


if __name__ == "__main__":
    demo()
