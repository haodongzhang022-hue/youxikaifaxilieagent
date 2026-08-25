# ============================================================
# 市场预演与纳什均衡引擎
# 版本: v0.2
# 说明: 在"发布"前模拟整个市场生态，让各圈层角色互相博弈，
#       直到收敛到纳什均衡，输出发布建议与生态位诊断。
# 语言: Python (面向架构与原型，可逐步落地)
# ============================================================

from __future__ import annotations
import random
import itertools
from dataclasses import dataclass, field
from typing import Dict, List, Tuple


# ============================================================
# 一、基础数据结构
# ============================================================

@dataclass
class Strategy:
    """一个角色在模拟中的策略（可调参数组合）"""
    name: str
    params: Dict[str, float] = field(default_factory=dict)

    def clone(self, **overrides) -> "Strategy":
        new_params = dict(self.params)
        new_params.update(overrides)
        return Strategy(self.name, new_params)


@dataclass
class Outcome:
    """一次模拟运行的结果"""
    metrics: Dict[str, float] = field(default_factory=dict)
    role_payoffs: Dict[str, float] = field(default_factory=dict)


@dataclass
class Role:
    """一个生态角色（可被模拟的 Agent）"""
    role_id: str
    name: str
    circle: str
    payoff_fn: callable  # 输入(全局context, 自己的策略, 他人策略) -> 收益
    strategy_space: List[Strategy]  # 该角色可选的离散策略空间

    def payoff(self, context, all_strategies):
        mine = all_strategies[self.role_id]
        return self.payoff_fn(context, mine, all_strategies)


# ============================================================
# 二、市场模拟引擎（单次运行）
# ============================================================

class MarketSimulator:
    """
    单次市场模拟：给定所有角色的策略，计算一次市场结果。
    这里使用简化模型：以 DAU / 留存 / 付费 / 口碑 / ROI 为主，
    实际可接入更细的数值仿真。
    """

    def __init__(self, context: Dict, roles: List[Role]):
        self.context = context
        self.roles = {r.role_id: r for r in roles}

    def run(self, strategies: Dict[str, Strategy]) -> Outcome:
        c = self.context

        # ---- 研发产物品质（决定上限）----
        quality = c.get("base_quality", 60.0)
        # ---- 商业化结构：IAP(内购) 与 IAA(广告) 的取舍 ----
        iap = strategies["payer"].params.get("iap_depth", 0.5)
        iaa = strategies["advertiser"].params.get("ad_density", 0.2)
        # 广告密度过高会损伤玩家体验
        ad_experience_penalty = max(0.0, iaa - 0.4) * 1.5

        # ---- 玩家圈响应 ----
        mass = c.get("mass_player_base", 100000) * (quality / 60.0)
        # 上手门槛
        complexity = strategies["mass_player"].params.get("complexity", 0.3)
        acquisition_rate = 1.0 - min(1.0, complexity) * 0.6

        # 留存受"广告体验损伤"影响
        d1_retention = 0.4 * (1 - ad_experience_penalty)
        d30_retention = 0.12 * (1 - ad_experience_penalty) * (quality / 60.0)

        dau = mass * acquisition_rate * d1_retention * 0.5
        maus = dau * 15

        # ---- 付费与广告营收 ----
        ltv = c.get("arpu_base", 2.0) * iap * d30_retention * 30
        iap_revenue = maus * ltv
        ad_revenue = maus * (iaa * c.get("ecpm_base", 5.0) / 1000) * c.get("ad_impressions", 8)

        total_revenue = iap_revenue + ad_revenue

        # ---- 外部市场：渠道与竞品压力 ----
        channel_cut = c.get("channel_cut", 0.3)
        competition_pressure = c.get("competition_pressure", 0.5)
        reachable_revenue = total_revenue * (1 - channel_cut) * (1 - 0.5 * competition_pressure)

        # ---- 口碑 ----
        reputation = 5.0 - (iaa * 5) + (quality / 60.0) * 2 - ad_experience_penalty

        # ---- 汇总 ----
        metrics = {
            "dau": dau,
            "d30_retention": d30_retention,
            "iap_revenue": iap_revenue,
            "ad_revenue": ad_revenue,
            "total_revenue": reachable_revenue,
            "reputation": reputation,
            "roi": reachable_revenue / max(c.get("marketing_budget", 50000), 1),
        }
        return Outcome(metrics=metrics)


# ============================================================
# 三、收益函数（各角色如何评价一次结果）
# ============================================================

def make_payoffs(context):
    """根据上下文构造各角色的收益函数"""

    def payer_payoff(ctx, mine, all_strats):
        out = ctx["last_outcome"]
        # 付费玩家既要"营收好"也看重"体验不崩"
        return out.metrics["iap_revenue"] - max(0, all_strats["advertiser"].params["ad_density"] - 0.4) * 100000

    def advertiser_payoff(ctx, mine, all_strats):
        out = ctx["last_outcome"]
        # 广告方只看广告营收
        return out.metrics["ad_revenue"]

    def mass_player_payoff(ctx, mine, all_strats):
        out = ctx["last_outcome"]
        # 泛玩家看重口碑与留存
        return out.metrics["reputation"] * out.metrics["dau"]

    def publisher_payoff(ctx, mine, all_strats):
        out = ctx["last_outcome"]
        return out.metrics["roi"]

    return {
        "mass_player": mass_player_payoff,
        "payer": payer_payoff,
        "advertiser": advertiser_payoff,
        "publisher": publisher_payoff,
    }


# ============================================================
# 四、纳什均衡求解
# ============================================================

class NashSolver:
    """
    通过"最优响应迭代"（Best Response Dynamics）寻找纳什均衡。
    每个角色在给定他人策略下，选择使自身收益最大的策略，迭代直至收敛。
    """

    def __init__(self, roles: List[Role], context: Dict, simulator: MarketSimulator):
        self.roles = roles
        self.context = context
        self.simulator = simulator
        self.context["last_outcome"] = Outcome()

    def best_response(self, role: Role, strategies: Dict[str, Strategy]) -> Strategy:
        """在他人策略固定时，为该角色选收益最大的策略"""
        best = None
        best_payoff = float("-inf")
        others = {k: v for k, v in strategies.items() if k != role.role_id}
        for candidate in role.strategy_space:
            trial = dict(others)
            trial[role.role_id] = candidate
            outcome = self.simulator.run(trial)
            self.context["last_outcome"] = outcome
            payoff = role.payoff(self.context, trial)
            if payoff > best_payoff:
                best_payoff = payoff
                best = candidate
        return best

    def solve(self, initial: Dict[str, Strategy],
              max_iter: int = 100, tol: float = 0.01) -> Tuple[Dict[str, Strategy], int]:
        """迭代到纳什均衡（最优响应动态）"""
        strategies = {k: v.clone() for k, v in initial.items()}
        self.context["last_outcome"] = self.simulator.run(strategies)
        for it in range(1, max_iter + 1):
            changed = False
            for role in self.roles:
                # 当前策略下该角色的收益
                prev_payoff = role.payoff(self.context, strategies)
                # 找出给定他人策略时的最优响应
                best = None
                best_payoff = prev_payoff
                for candidate in role.strategy_space:
                    trial = dict(strategies)
                    trial[role.role_id] = candidate
                    outcome = self.simulator.run(trial)
                    # 重要：每次候选评估都要同步最新的模拟结果到上下文，
                    # 否则角色的收益函数读到的是上一轮的过时数据，
                    # 会破坏纳什均衡求解的正确性。
                    self.context["last_outcome"] = outcome
                    trial_payoff = role.payoff_fn(self.context, candidate, trial)
                    if trial_payoff > best_payoff + tol:
                        best_payoff = trial_payoff
                        best = candidate
                if best is not None:
                    strategies[role.role_id] = best
                    changed = True
            # 重新跑一次并同步 last_outcome
            self.context["last_outcome"] = self.simulator.run(strategies)
            if not changed:
                # 无人能单方面改进 => 收敛到纳什均衡
                return strategies, it - 1
        return strategies, max_iter


# ============================================================
# 五、敏感性分析 & 帕累托改进
# ============================================================

def sensitivity_analysis(simulator, base_strategies, param_axis: str, values: List[float]):
    """改变某一参数，观察均衡与整体结果如何变化，找最稳的生态位"""
    results = []
    for v in values:
        modified = {k: s.clone() for k, s in base_strategies.items()}
        # 沿指定轴的第一个角色改该参数
        for role_id, strat in modified.items():
            strat.params[param_axis] = v
            break
        outcome = simulator.run(modified)
        results.append((v, outcome.metrics))
    return results


def pareto_frontier(simulator, roles, strategies_candidates: List[Dict[str, Strategy]]):
    """
    帕累托前沿：从候选策略集中，找出"至少一方更好、无人更差"的方案集合，
    用于标注纳什均衡附近的帕累托改进空间。
    """
    evaluated = []
    for strategies in strategies_candidates:
        outcome = simulator.run(strategies)
        evaluated.append((strategies, outcome))
    # 简化：比较各候选的整体收益向量是否被支配
    frontier = []
    for i, (si, oi) in enumerate(evaluated):
        dominated = False
        for j, (sj, oj) in enumerate(evaluated):
            if i == j:
                continue
            # 若 j 在每一维都不差且至少一维更好 => i 被支配
            if all(oj.metrics[k] >= oi.metrics[k] for k in oi.metrics) and \
               any(oj.metrics[k] > oi.metrics[k] for k in oi.metrics):
                dominated = True
                break
        if not dominated:
            frontier.append((si, oi))
    return frontier


# ============================================================
# 六、示例：一次完整的生态预演
# ============================================================

def demo():
    context = {
        "base_quality": 65.0,
        "mass_player_base": 200000,
        "arpu_base": 2.5,
        "ecpm_base": 6.0,
        "ad_impressions": 8,
        "channel_cut": 0.3,
        "competition_pressure": 0.4,
        "marketing_budget": 80000,
        "last_outcome": Outcome(),
    }

    # 定义参与博弈的角色与策略空间
    roles = [
        Role("mass_player", "泛玩家", "players",
             payoff_fn=lambda ctx, mine, others: ctx["last_outcome"].metrics["reputation"] * ctx["last_outcome"].metrics["dau"],
             strategy_space=[
                 Strategy("低门槛", {"complexity": 0.2}),
                 Strategy("中门槛", {"complexity": 0.5}),
             ]),
        Role("payer", "付费玩家", "players",
             payoff_fn=lambda ctx, mine, others: ctx["last_outcome"].metrics["iap_revenue"] - max(0, others["advertiser"].params["ad_density"] - 0.4) * 100000,
             strategy_space=[
                 Strategy("温和内购", {"iap_depth": 0.5}),
                 Strategy("深度内购", {"iap_depth": 0.9}),
             ]),
        Role("advertiser", "广告方", "market",
             payoff_fn=lambda ctx, mine, others: ctx["last_outcome"].metrics["ad_revenue"],
             strategy_space=[
                 Strategy("低密度广告", {"ad_density": 0.2}),
                 Strategy("高密度广告", {"ad_density": 0.6}),
             ]),
        Role("publisher", "宣发平台", "market",
             payoff_fn=lambda ctx, mine, others: ctx["last_outcome"].metrics["roi"],
             strategy_space=[
                 Strategy("小预算", {"budget": 40000}),
                 Strategy("大预算", {"budget": 120000}),
             ]),
    ]

    simulator = MarketSimulator(context, roles)
    solver = NashSolver(roles, context, simulator)

    # 初始策略
    initial = {
        "mass_player": roles[0].strategy_space[0],
        "payer": roles[1].strategy_space[0],
        "advertiser": roles[2].strategy_space[0],
        "publisher": roles[3].strategy_space[0],
    }

    print("=" * 60)
    print("市场生态预演：纳什均衡求解")
    print("=" * 60)

    equilibrium, iters = solver.solve(initial)
    final_outcome = simulator.run(equilibrium)
    context["last_outcome"] = final_outcome

    print(f"\n收敛于第 {iters} 轮（0 表示首轮即稳定）")
    print("\n[均衡策略]")
    for rid, strat in equilibrium.items():
        print(f"  {rid:<12} -> {strat.name} {strat.params}")

    print("\n[均衡结果指标]")
    for k, v in final_outcome.metrics.items():
        print(f"  {k:<16}: {v:.2f}")

    print("\n[生态位诊断]")
    print(f"  口碑: {final_outcome.metrics['reputation']:.2f}/10")
    print(f"  30日留存: {final_outcome.metrics['d30_retention']*100:.1f}%")
    print(f"  IAP营收: {final_outcome.metrics['iap_revenue']:.0f}  广告营收: {final_outcome.metrics['ad_revenue']:.0f}")
    print('  提示: 纳什均衡下的组合是“各角色不再单方面改动”的稳定态。')
    print("        若希望某方更好，需看帕累托改进空间与敏感性分析。")


if __name__ == "__main__":
    demo()
