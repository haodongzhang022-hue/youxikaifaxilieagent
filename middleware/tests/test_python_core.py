"""middleware Python 核心测试（pytest 兼容，也可直接运行）。"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bindings.python.cabi import (
    GameMiddleware, procgen_terrain, procgen_level, procgen_resources,
    procgen_props, procgen_narrative, roll_loot, calc_damage,
    fp_from_int, fp_from_float, fp_to_float, fp_mul, fp_div,
    fp_add, fp_sub, hash_json, STATE_PLAYING,
)

def test_fixed_point():
    assert fp_to_float(fp_mul(fp_from_int(3), fp_from_int(4))) == 12.0
    assert fp_to_float(fp_div(fp_from_int(3), fp_from_int(4))) == 0.75
    assert fp_add(fp_from_int(3), fp_from_int(4)) == fp_from_int(7)
    assert fp_sub(fp_from_int(10), fp_from_int(4)) == fp_from_int(6)
    # 浮点转换 round-trip
    assert fp_to_float(fp_from_float(2.5)) == 2.5

def test_terrain_determinism():
    h1 = hash_json(procgen_terrain("seed42", 8, 8, {"octaves": 3}))
    h2 = hash_json(procgen_terrain("seed42", 8, 8, {"octaves": 3}))
    assert h1 == h2
    h3 = hash_json(procgen_terrain("seed99", 8, 8, {"octaves": 3}))
    assert h1 != h3  # 不同 seed 不同

def test_all_generators_deterministic():
    gens = [procgen_terrain, procgen_level, procgen_resources, procgen_props, procgen_narrative]
    for g in gens:
        for seed in ("a", "b", "c"):
            args = (seed,) if g is not procgen_terrain else (seed, 8, 8, {})
            o1 = hash_json(g(*args))
            o2 = hash_json(g(*args))
            assert o1 == o2, f"{g.__name__} {seed}"

def test_loot_determinism():
    l1 = roll_loot(1, 42)
    l2 = roll_loot(1, 42)
    assert hash_json(l1) == hash_json(l2)
    assert l1["items"]  # 有掉落

def test_damage_fixedpoint():
    d = calc_damage({"base_power": 100}, {"atk": 100}, {"def": 50})
    assert d >= 1

def test_middleware_state_machine():
    mw = GameMiddleware()
    mw.set_state(STATE_PLAYING)
    assert mw.get_state() == STATE_PLAYING
    mw.update(0.1)

def test_terrain_shape():
    t = procgen_terrain("s", 4, 4, {})
    assert len(t["data"]) == 16  # 4x4
    assert t["width"] == 4 and t["height"] == 4

if __name__ == "__main__":
    import traceback
    fns = [v for k, v in list(globals().items()) if k.startswith("test_")]
    passed = 0
    for fn in fns:
        try:
            fn(); print(f"PASS {fn.__name__}"); passed += 1
        except Exception as e:
            print(f"FAIL {fn.__name__}: {e}"); traceback.print_exc()
    print(f"\n{passed}/{len(fns)} tests passed")
    sys.exit(0 if passed == len(fns) else 1)
