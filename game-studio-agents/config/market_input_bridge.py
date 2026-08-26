# ============================================================
# 数值模型 → 市场预演标准化输入桥梁 (NumericModel → MarketSimulator)
# 版本: v1.0
# 说明: wp_numeric_model（策划线·balance_designer）的落地产出。
#       把策划的数值模型 / 商业化设计（economy / growth_curve / balance /
#       monetization）转译为 `market_simulator.MarketSimulator` 能直接消费的
#       标准化输入（context + roles），跑通「研发产物 → 市场预演沙盒」。
#
# 解耦原则：
#   - 数值模型（研发侧，balance_designer 产出）与 市场模拟（发布侧，
#     MarketSimulator）通过本桥梁解耦；策划改数值只动数值模型，不碰模拟器。
#   - 标准化输入契约 = market_simulator 的 context 字段 + roles 策略空间，
#     由本模块负责转换，保证二者数据类型 / 单位 / 字段名一致。
#
# 语言: Python 3 (可运行)
# 依赖: market_simulator.py（同目录）
# ============================================================
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from market_simulator import MarketSimulator, Role, Strategy, NashSolver, Outcome


# ============================================================
# 一、数值模型 → 市场 context 的映射
# ============================================================

# 数值模型字段 → 市场模拟 context 字段
# 数值模型（研发侧）字段名与市场模拟（发布侧）字段名的规范化映射表。
# 新增数值字段时在此登记映射，保证 bridge 可扩展且字段名一致。
FIELD_MAP = {
    # 数值模型字段        市场模拟 context 字段
    "base_quality":       "base_quality",           # 研发产物品质（决定上限）
    "arpu":               "arpu_base",              # 人均付费基准(ARPU)
    "ecpm":               "ecpm_base",              # 广告千次曝光收益
    "ad_impressions":     "ad_impressions",         # 日均广告曝光次数
    "channel_cut":        "channel_cut",            # 渠道分账比例
    "competition":        "competition_pressure",   # 竞品压力
    "marketing_budget":   "marketing_budget",       # 宣发预算
    "mass_player_base":   "mass_player_base",       # 潜在泛玩家大盘
}


def numeric_model_to_context(numeric_model: Dict[str, Any]) -> Dict[str, Any]:
    """把数值模型 / 商业化设计转译为市场模拟的标准化 context。

    只映射双方都认识的字段（FIELD_MAP），未映射的数值字段不强行塞入，
    避免把研发侧临时字段污染成模拟器的 context 而引入歧义。
    缺省字段用市场模拟器默认基线兜底（MarketSimulator.run 有内置默认值）。
    """
    context: Dict[str, Any] = {}
    for src_key, dst_key in FIELD_MAP.items():
        if src_key in numeric_model:
            context[dst_key] = numeric_model[src_key]
    # 供模拟过程使用的 last_outcome 占位（与 market_simulator 约定一致）
    context.setdefault("last_outcome", Outcome())
    return context


# ============================================================
# 二、数值模型 → 玩家/市场角色策略空间
# ============================================================

def build_roles(numeric_model: Dict[str, Any]) -> List[Role]:
    """根据数值模型 / 商业化设计构建参与博弈的生态角色与策略空间。

    用数值模型里的商业化结构（IAP vs IAA 取舍 / 上手门槛 / 宣发预算）
    作为各角色可选策略的基准，供 NashSolver 在纳什均衡博弈中使用。

    默认给出与 market_simulator.demo 对齐的四角色博弈结构：
      - 泛玩家(mass_player)：上手门槛复杂度
      - 付费玩家(payer)：内购深度(IAP)
      - 广告方(advertiser)：广告密度(IAA)
      - 宣发平台(publisher)：宣发预算
    """
    monetization = numeric_model.get("monetization", {}) or {}
    iap_depth = float(monetization.get("iap_depth", 0.5))
    iaa_density = float(monetization.get("iaa_density", 0.2))
    complexity = float(numeric_model.get("complexity", 0.3))
    budget = float(numeric_model.get("marketing_budget", 80000))

    # IAP/IAA 的权衡：围绕数值模型给的值展开策略区间，让模拟器能"博弈"
    iap_lo = max(0.1, iap_depth - 0.2)
    iap_hi = min(1.0, iap_depth + 0.3)
    iaa_lo = max(0.05, iaa_density - 0.15)
    iaa_hi = min(0.8, iaa_density + 0.3)
    complexity_lo = max(0.1, complexity - 0.15)
    complexity_hi = min(0.9, complexity + 0.3)
    budget_lo = budget * 0.5
    budget_hi = budget * 1.5

    roles = [
        Role("mass_player", "泛玩家", "players",
             payoff_fn=lambda ctx, mine, others: (
                 ctx["last_outcome"].metrics["reputation"]
                 * ctx["last_outcome"].metrics["dau"]),
             strategy_space=[
                 Strategy("低门槛", {"complexity": round(complexity_lo, 2)}),
                 Strategy("基准门槛", {"complexity": round(complexity, 2)}),
                 Strategy("中门槛", {"complexity": round(complexity_hi, 2)}),
             ]),
        Role("payer", "付费玩家", "players",
             payoff_fn=lambda ctx, mine, others: (
                 ctx["last_outcome"].metrics["iap_revenue"]
                 - max(0, others["advertiser"].params["ad_density"] - 0.4) * 100000),
             strategy_space=[
                 Strategy("温和内购", {"iap_depth": round(iap_lo, 2)}),
                 Strategy("基准内购", {"iap_depth": round(iap_depth, 2)}),
                 Strategy("深度内购", {"iap_depth": round(iap_hi, 2)}),
             ]),
        Role("advertiser", "广告方", "market",
             payoff_fn=lambda ctx, mine, others: ctx["last_outcome"].metrics["ad_revenue"],
             strategy_space=[
                 Strategy("低密度广告", {"ad_density": round(iaa_lo, 2)}),
                 Strategy("基准密度", {"ad_density": round(iaa_density, 2)}),
                 Strategy("高密度广告", {"ad_density": round(iaa_hi, 2)}),
             ]),
        Role("publisher", "宣发平台", "market",
             payoff_fn=lambda ctx, mine, others: ctx["last_outcome"].metrics["roi"],
             strategy_space=[
                 Strategy("保守预算", {"budget": round(budget_lo, 0)}),
                 Strategy("基准预算", {"budget": round(budget, 0)}),
                 Strategy("激进预算", {"budget": round(budget_hi, 0)}),
             ]),
    ]
    return roles


def initial_strategies(roles: List[Role]) -> Dict[str, Strategy]:
    """为每个角色取策略空间第一个作为初始策略（供 NashSolver 起步）。"""
    return {r.role_id: r.strategy_space[0] for r in roles}


# ============================================================
# 三、数值模型 → 市场预演标准化输入（主入口）
# ============================================================

@dataclass
class MarketInput:
    """数值模型转译后的市场预演标准化输入（供 MarketSimulator 消费）。"""
    project: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    roles: List[Role] = field(default_factory=list)
    initial: Dict[str, Strategy] = field(default_factory=dict)
    numeric_model: Dict[str, Any] = field(default_factory=dict)

    def to_simulator(self) -> MarketSimulator:
        """构造 MarketSimulator 实例（标准沙盒入口）。"""
        return MarketSimulator(self.context, self.roles)

    def solve(self, max_iter: int = 100, tol: float = 0.01) -> Dict[str, Any]:
        """跑一次纳什均衡求解，返回「均衡策略 + 均衡结果指标」。

        这是 wp_numeric_model 的最终产物：把策划的数值模型输出为可执行的
        市场预演沙盒，并收敛到纳什均衡。
        """
        simulator = self.to_simulator()
        solver = NashSolver(self.roles, self.context, simulator)
        eq, iters = solver.solve(self.initial, max_iter=max_iter, tol=tol)
        final_outcome = simulator.run(eq)
        self.context["last_outcome"] = final_outcome
        return {
            "project": self.project,
            "equilibrium": {rid: {"strategy": s.name, "params": dict(s.params)}
                            for rid, s in eq.items()},
            "iterations": iters,
            "metrics": dict(final_outcome.metrics),
            "context": dict(self.context),
        }


def build_market_input(numeric_model: Dict[str, Any],
                       project: str = "未命名") -> MarketInput:
    """把数值模型 / 商业化设计转译为市场预演标准化输入（主入口）。

    Args:
        numeric_model: 策划侧数值模型产出，字段含 economy / growth_curve /
                       balance / monetization / base_quality / arpu 等。
        project: 项目名（用于结果归属标识）。

    Returns:
        MarketInput：可直接 to_simulator() / solve() 的标准输入。
    """
    context = numeric_model_to_context(numeric_model)
    roles = build_roles(numeric_model)
    return MarketInput(
        project=project,
        context=context,
        roles=roles,
        initial=initial_strategies(roles),
        numeric_model=numeric_model,
    )


# ============================================================
# 四、演示
# ============================================================

def demo():
    print("=" * 70)
    print("数值模型 → 市场预演标准化输入桥梁（wp_numeric_model）")
    print("  跑通「研发产物 → 市场预演沙盒」")
    print("=" * 70)

    # 一份 balance_designer 产出的数值模型 / 商业化设计
    numeric_model = {
        "economy": "经济产出/消耗模型",
        "growth_curve": "成长曲线",
        "balance": "平衡性数值",
        "base_quality": 65.0,
        "arpu": 2.5,
        "ecpm": 6.0,
        "ad_impressions": 8,
        "channel_cut": 0.3,
        "competition": 0.4,
        "marketing_budget": 80000,
        "mass_player_base": 200000,
        "complexity": 0.35,
        "monetization": {"iap_depth": 0.5, "iaa_density": 0.25},
    }
    market_input = build_market_input(numeric_model, project="移动端手游 demo")
    result = market_input.solve()

    print("\n[1] 标准化输入 context（映射到市场模拟）")
    for k, v in market_input.context.items():
        if k != "last_outcome":
            print(f"    {k:<20}: {v}")

    print("\n[2] 参与博弈的生态角色与策略空间")
    for r in market_input.roles:
        names = ", ".join(s.name for s in r.strategy_space)
        print(f"    {r.role_id:<12}({r.circle}) 策略: {names}")

    print("\n[3] 纳什均衡收敛")
    print(f"    收敛于第 {result['iterations']} 轮")
    print("    [均衡策略]")
    for rid, info in result["equilibrium"].items():
        print(f"      {rid:<12} -> {info['strategy']} {info['params']}")

    print("\n[4] 均衡结果指标（研发产物 → 市场预演输出）")
    for k, v in result["metrics"].items():
        print(f"      {k:<16}: {v:.2f}")

    print("\n[5] 生态位诊断")
    m = result["metrics"]
    print(f"      口碑: {m['reputation']:.2f}/10")
    print(f"      30日留存: {m['d30_retention']*100:.1f}%")
    print(f"      ROI: {m['roi']:.2f}")
    return result


if __name__ == "__main__":
    demo()
