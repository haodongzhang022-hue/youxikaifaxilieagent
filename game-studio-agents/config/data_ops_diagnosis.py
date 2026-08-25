# ============================================================
# 市场预演生态位诊断与发布建议 (Data Ops Diagnosis)
# 版本: v1.0
# 说明: wp_data_ops（运营线·data_analyst）的落地产出。
#       对市场预演纳什均衡结果做**生态位诊断**与**发布建议**，
#       并输出**敏感性分析**结论——评估均衡结果对各关键参数的
#       稳健性，找出最稳的生态位与发布窗口。
#
# 输入：wp_numeric_model 产出的市场预演结果
#       （market_simulator 的纳什均衡 metrics / equilibrium / context）。
# 输出：生态位健康度诊断 + 敏感性分析结论 + 发布建议。
#
# 语言: Python 3 (可运行)
# 依赖: market_simulator.py / market_input_bridge.py（同目录）
# ============================================================
from __future__ import annotations

from typing import Any, Dict, List

from market_simulator import MarketSimulator


# ============================================================
# 一、生态位健康度诊断
# ============================================================

def diagnose_ecosystem(metrics: Dict[str, float]) -> Dict[str, Any]:
    """对纳什均衡结果做生态位健康度诊断。

    从市场规模(DAU)、留存、商业化结构(IAP/IAA)、口碑、ROI 等维度
    综合评估生态位是否健康、可持续，并给出生态位定位标签。
    """
    dau = metrics.get("dau", 0.0)
    d30 = metrics.get("d30_retention", 0.0)
    iap = metrics.get("iap_revenue", 0.0)
    ad = metrics.get("ad_revenue", 0.0)
    reputation = metrics.get("reputation", 0.0)
    roi = metrics.get("roi", 0.0)
    total_rev = iap + ad

    # 商业化结构健康度：IAP / IAA 是否失衡
    if total_rev > 0:
        iap_share = iap / total_rev
    else:
        iap_share = 0.5

    issues = []
    if dau < 5000:
        issues.append("市场规模过小(DAU<5000)")
    if d30 < 0.08:
        issues.append("长线留存偏低(30日<8%)")
    if reputation < 3.5:
        issues.append("口碑偏低(<3.5/10，可能因广告过密或品质不足)")
    if roi < 1.0:
        issues.append("ROI不足(<1，投放不经济)")
    if iap_share > 0.9:
        issues.append("商业化过度依赖内购(IAP占比>90%)，抗风险弱")
    if iap_share < 0.1:
        issues.append("商业化过度依赖广告(IAA占比>90%)，体验损伤风险")

    if not issues:
        position = "健康/蓝海"
        overall = 5
    elif len(issues) <= 2:
        position = "稳健/可优化"
        overall = 4
    elif len(issues) <= 4:
        position = "竞争/需调整"
        overall = 3
    else:
        position = "红海/风险"
        overall = 2

    return {
        "position": position,
        "health_score": overall,          # 5=健康 ... 1=危险
        "issues": issues,
        "commercial_mix": {
            "iap_share": round(iap_share, 3),
            "iaa_share": round(1 - iap_share, 3),
        },
        "diagnosis": {
            "dau": round(dau, 0),
            "d30_retention": round(d30, 4),
            "reputation": round(reputation, 2),
            "roi": round(roi, 2),
        },
    }


# ============================================================
# 二、敏感性分析
# ============================================================

def sensitivity_conclusions(simulator: MarketSimulator,
                            base_strategies: Dict[str, Any],
                            axis: str = "iap_depth",
                            values: List[float] = (0.3, 0.5, 0.7, 0.9),
                            axis_role: str = "payer") -> Dict[str, Any]:
    """对某一参数做敏感性分析，评估均衡结果稳健性。

    沿指定参数轴改变取值，观察整体营收 / ROI 如何变化，判断：
      - 是否敏感（波动大）→ 发布策略需谨慎，避免参数波动击穿盈亏线；
      - 是否存在更优生态位（某参数下 ROI/留存最优）。

    与 market_simulator.sensitivity_analysis 的区别：后者把参数写在第一个
    角色的策略上（可能并非真正消费该参数的角色），导致营收不随参数变化。
    这里把参数作用在**实际消费该参数的角色**（axis_role，默认付费玩家 payer
    消费 iap_depth），从而得到有意义的敏感性结论。
    """
    rows = []
    revs = []
    rois = []
    for v in list(values):
        # 克隆均衡策略，并只把 axis 参数写到消费该参数的角色策略上
        trial = {rid: s.clone() for rid, s in base_strategies.items()}
        if axis_role in trial:
            trial[axis_role].params[axis] = v
        m = simulator.run(trial).metrics
        rows.append({"param_value": v,
                     "total_revenue": round(m.get("total_revenue", 0), 0),
                     "roi": round(m.get("roi", 0), 3),
                     "dau": round(m.get("dau", 0), 0)})
        revs.append(m.get("total_revenue", 0))
        rois.append(m.get("roi", 0))

    # 敏感性度量：营收 / ROI 的变异系数（波动大→敏感）
    def _cv(nums):
        if not nums:
            return 0.0
        mean = sum(nums) / len(nums)
        if mean == 0:
            return 0.0
        var = sum((x - mean) ** 2 for x in nums) / len(nums)
        return (var ** 0.5) / mean

    rev_cv = _cv(revs)
    roi_cv = _cv(rois)
    sensitivity_level = "低(稳健)" if (rev_cv < 0.2 and roi_cv < 0.2) else \
                        ("中(需关注)" if (rev_cv < 0.5 and roi_cv < 0.5) else "高(脆弱)")
    best_roi = max(rois) if rois else 0
    best_value = values[rois.index(best_roi)] if rois else None

    return {
        "axis": axis,
        "sensitivity_level": sensitivity_level,
        "revenue_cv": round(rev_cv, 3),
        "roi_cv": round(roi_cv, 3),
        "best_roi": round(best_roi, 3),
        "best_param_value": best_value,
        "rows": rows,
    }


# ============================================================
# 三、发布建议
# ============================================================

def release_recommendation(ecosystem_diag: Dict[str, Any],
                           sens: Dict[str, Any],
                           metrics: Dict[str, float]) -> Dict[str, Any]:
    """综合生态位诊断 + 敏感性分析，给出发布建议。"""
    position = ecosystem_diag["position"]
    health = ecosystem_diag["health_score"]
    issues = ecosystem_diag["issues"]
    sens_level = sens.get("sensitivity_level", "中(需关注)")

    decisions = []
    if health >= 4:
        decisions.append("可正常发布：生态位健康，具备发布条件")
    elif health == 3:
        decisions.append("建议优化后发布：存在可控问题，先修复关键项再上")
    else:
        decisions.append("暂缓发布：生态位风险高，需重大调整")

    if sens_level == "高(脆弱)":
        decisions.append("参数敏感度高：发布前需锁定关键参数，避免投放/商业化波动击穿盈亏线")
    elif sens_level == "中(需关注)":
        decisions.append("参数敏感性中等：发布时设置参数下限护栏，动态监控")

    if "商业化过度依赖内购" in issues:
        decisions.append("建议引入广告变现补充，降低单一商业化依赖")
    if "商业化过度依赖广告" in issues:
        decisions.append("建议控制广告密度，保护留存与口碑")

    # 发布时机与优先级
    roi = metrics.get("roi", 0)
    if roi >= 2.0:
        timing = "优先发布（高ROI，抢占生态位）"
    elif roi >= 1.0:
        timing = "正常节奏发布（ROI达标）"
    else:
        timing = "谨慎发布（ROI不足，先优化商业化）"

    return {
        "verdict": decisions[0] if decisions else "评估中",
        "release_timing": timing,
        "precautions": decisions[1:],
        "go_no_go": "GO" if (health >= 3 and sens_level != "高(脆弱)") else "NO-GO",
    }


# ============================================================
# 四、主入口：对市场预演结果做完整诊断
# ============================================================

def run_data_ops(market_input, market_result: Dict[str, Any],
                 axis: str = "iap_depth") -> Dict[str, Any]:
    """对 wp_numeric_model 产出的市场预演结果做完整运营诊断。

    Args:
        market_input: market_input_bridge.build_market_input 产物。
        market_result: market_input.solve() 的返回（含 equilibrium/metrics）。
        axis: 敏感性分析所沿参数轴（默认 IAP 深度）。

    Returns:
        生态位诊断 + 敏感性结论 + 发布建议 的聚合报告。
    """
    metrics = market_result["metrics"]
    eco_diag = diagnose_ecosystem(metrics)

    # 敏感性分析：基于均衡策略，沿参数轴扰动观察稳健性
    simulator = market_input.to_simulator()
    eq_strategies = {}
    from market_simulator import Strategy
    for rid, info in market_result["equilibrium"].items():
        eq_strategies[rid] = Strategy(info["strategy"], dict(info["params"]))
    # 参数轴 → 消费该参数的角色映射（敏感性才有意义）
    axis_role = {
        "iap_depth": "payer", "ad_density": "advertiser",
        "complexity": "mass_player", "budget": "publisher",
    }.get(axis, "payer")
    sens = sensitivity_conclusions(simulator, eq_strategies, axis=axis,
                                   axis_role=axis_role)
    reco = release_recommendation(eco_diag, sens, metrics)

    return {
        "project": market_result.get("project"),
        "ecosystem_diagnosis": eco_diag,
        "sensitivity": sens,
        "release_recommendation": reco,
    }


# ============================================================
# 五、演示
# ============================================================

def demo():
    print("=" * 70)
    print("市场预演生态位诊断与发布建议（wp_data_ops·data_analyst）")
    print("  对纳什均衡结果做生态位诊断 + 敏感性分析 + 发布建议")
    print("=" * 70)

    from market_input_bridge import build_market_input

    # 复用 wp_numeric_model 的市场预演输入
    numeric_model = {
        "economy": "经济产出/消耗模型", "growth_curve": "成长曲线",
        "balance": "平衡性数值",
        "base_quality": 65.0, "arpu": 2.5, "ecpm": 6.0,
        "ad_impressions": 8, "channel_cut": 0.3, "competition": 0.4,
        "marketing_budget": 80000, "mass_player_base": 200000,
        "complexity": 0.35,
        "monetization": {"iap_depth": 0.5, "iaa_density": 0.25},
    }
    market_input = build_market_input(numeric_model, project="移动端手游 demo")
    market_result = market_input.solve()
    report = run_data_ops(market_input, market_result)

    print("\n[1] 生态位健康度诊断")
    eco = report["ecosystem_diagnosis"]
    print(f"    生态位: {eco['position']}  健康分: {eco['health_score']}/5")
    for issue in eco["issues"]:
        print(f"      - 问题: {issue}")
    if not eco["issues"]:
        print("      - 无显著问题")

    print("\n[2] 敏感性分析结论（沿 iap_depth 轴）")
    sens = report["sensitivity"]
    print(f"    敏感度: {sens['sensitivity_level']}  (营收CV={sens['revenue_cv']}, ROI CV={sens['roi_cv']})")
    for r in sens["rows"]:
        print(f"      iap={r['param_value']}  营收={r['total_revenue']:.0f}  ROI={r['roi']}")

    print("\n[3] 发布建议")
    reco = report["release_recommendation"]
    print(f"    结论: {reco['verdict']}")
    print(f"    时机: {reco['release_timing']}")
    print(f"    放行: {reco['go_no_go']}")
    for p in reco["precautions"]:
        print(f"      - {p}")

    return report


if __name__ == "__main__":
    demo()
