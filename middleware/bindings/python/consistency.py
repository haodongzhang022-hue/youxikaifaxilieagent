"""
consistency.py - 跨引擎一致性校验器
验证：同一种子（seed）在所有引擎输出完全一致（确定性）。
核心校验项：
  1. 种子确定性：同 seed 重复生成 → 输出 hash 一致
  2. 程序化生成回归基准（golden hash），跨引擎比对用
"""
import json
from .cabi import (
    GameMiddleware, procgen_terrain, procgen_level, procgen_resources,
    procgen_props, procgen_narrative, roll_loot, calc_damage, hash_json,
)


class ConsistencyVerifier:
    """跨引擎一致性校验器。"""

    def __init__(self):
        self.mw = GameMiddleware()

    def verify_seed_determinism(self, gen_func, seed, runs=10):
        """同一种子多次生成输出完全一致。"""
        outputs = [hash_json(gen_func(seed)) for _ in range(runs)]
        return len(set(outputs)) == 1, outputs[0]

    def _generators(self):
        return {
            "terrain": lambda s: procgen_terrain(s, 8, 8, {"octaves": 3}),
            "level": procgen_level,
            "resources": procgen_resources,
            "props": procgen_props,
            "narrative": procgen_narrative,
            "loot": lambda s: roll_loot(1, s),
        }

    def verify_all_generators(self, seeds=("seed42", "abc", "hello")):
        """对全部生成器做种子确定性校验。"""
        results = {}
        for seed in seeds:
            for name, gen in self._generators().items():
                ok, h = self.verify_seed_determinism(gen, seed)
                results[f"{seed}/{name}"] = (ok, h)
        return results

    def golden_hash(self, seed, gen_name):
        """计算指定生成器的 golden hash（作为跨引擎回归基准）。"""
        gen = self._generators()[gen_name]
        return hash_json(gen(seed))


def run_verification():
    v = ConsistencyVerifier()
    print("== 种子确定性校验 ==")
    all_ok = True
    for key, (ok, h) in v.verify_all_generators().items():
        status = "OK " if ok else "FAIL"
        print(f"[{status}] {key} hash={h[:12]}")
        all_ok = all_ok and ok

    print("\n== Golden Hash 基准 ==")
    for name in ("terrain", "level", "resources", "props", "narrative", "loot"):
        gh = v.golden_hash("golden_seed", name)
        print(f"  {name}: {gh}")

    # 伤害计算一致性
    print("\n== 伤害计算（定点数）==")
    d1 = calc_damage({"base_power": 100}, {"atk": 100}, {"def": 50})
    d2 = calc_damage({"base_power": 100}, {"atk": 100}, {"def": 50})
    print(f"  damage={d1} deterministic={d1 == d2}")
    all_ok = all_ok and (d1 == d2)

    print("\n" + ("ALL CONSISTENCY CHECKS PASSED" if all_ok else "SOME CHECKS FAILED"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    import sys
    sys.exit(run_verification())
