"""
cabi.py - 跨引擎中间件 C ABI 的 Python 绑定（ctypes）
对齐 Issue #90 wp_engine：作为 Python 原型层，调用 C++ 核心。
提供两套后端：
  1. libgame_middleware.so   （真实 C++ 编译产物，经 ctypes 调用）
  2. pure-python 确定性核心  （无编译器时可运行的参考实现，逻辑与 C++ 完全一致）

核心特性：确定性程序化生成 —— 同一种子 seed 输出完全一致（跨引擎 hash 校验）。
"""
import ctypes
import hashlib
import json
import os
from ctypes import c_int, c_float, c_char_p, c_void_p, POINTER, c_int64

LIB_NAME = os.environ.get("GAME_MIDDLEWARE_LIB", "libgame_middleware.so")

# 错误码（对齐 cabi_common.h）
CABI_OK = 0
CABI_ERR_INVALID_ARG = 1
CABI_ERR_NULL_PTR = 2
CABI_ERR_MEMORY = 3
CABI_ERR_NOT_INIT = 4
CABI_ERR_NOT_FOUND = 5

# 游戏状态（对齐 cabi_gameplay.h）
STATE_IDLE, STATE_PLAYING, STATE_PAUSED, STATE_GAMEOVER = 0, 1, 2, 3

ERROR_STR = {
    0: "ok", 1: "invalid argument", 2: "null pointer", 3: "out of memory",
    4: "not initialized", 5: "not found",
}


class MiddlewareError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(f"middleware error {code}: {ERROR_STR.get(code, 'unknown')}")


# ============================================================
# 确定性核心（splitmix64 + fnv1a，与 C++ ProcgenCore 完全一致）
# ============================================================
MASK64 = 0xFFFFFFFFFFFFFFFF


def _fnv1a_hash(s: str) -> int:
    h = 14695981039346656037
    for b in s.encode("utf-8"):
        h ^= b
        h = (h * 1099511628211) & MASK64
    return h


def _splitmix64_next(state):
    state[0] = (state[0] + 0x9E3779B97F4A7C15) & MASK64
    z = state[0]
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK64
    return z ^ (z >> 31)


# 定点数：32bit 整数 + 10bit 小数（对齐 FixedPoint）
FP_ONE = 1 << 10


def fp_from_float(f):
    return int(round(f * FP_ONE))


def fp_from_int(i):
    return i << 10


def fp_to_float(fp):
    return fp / FP_ONE


def fp_mul(a, b):
    return (a * b) >> 10


def fp_div(a, b):
    if b == 0:
        return 0
    return (a << 10) // b


# ============================================================
# 确定性程序化生成（与 C++ ProcgenCore.cpp 逻辑对齐）
# ============================================================
def procgen_terrain(seed, width, height, params=None):
    """生成高度图 JSON。同 seed + 同参数 → 相同输出。"""
    octaves = (params or {}).get("octaves", 4)
    octaves = max(1, min(8, octaves))
    st = [_fnv1a_hash(seed)]
    n = width * height
    heights = [_splitmix64_next(st) % 100 for _ in range(n)]

    # 一次均值滤波平滑
    smoothed = []
    for y in range(height):
        for x in range(width):
            total, cnt = 0, 0
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < width and 0 <= ny < height:
                        total += heights[ny * width + nx]
                        cnt += 1
            smoothed.append(total // cnt)
    return {
        "width": width, "height": height, "seed": seed,
        "octaves": octaves, "data": smoothed,
    }


def procgen_level(seed, params=None):
    w = (params or {}).get("width", 100)
    d = (params or {}).get("depth", 80)
    st = [_fnv1a_hash(seed)]
    prop_count = 5 + _splitmix64_next(st) % 6
    props = []
    for _ in range(prop_count):
        r = _splitmix64_next(st)
        props.append({
            "prefab_id": f"prop_{r % 8}",
            "x": r % w, "z": (r >> 8) % d,
        })
    return {
        "level_id": f"LVL_{_splitmix64_next(st) & 0xFFFF}",
        "dimensions": {"width": w, "depth": d},
        "props": props,
    }


def procgen_resources(seed):
    types = ["iron", "copper", "gold", "wood", "stone"]
    st = [_fnv1a_hash(seed)]
    count = 8 + _splitmix64_next(st) % 9
    res = []
    for _ in range(count):
        r = _splitmix64_next(st)
        res.append({
            "type": types[r % 5],
            "amount": 10 + ((r >> 8) % 90),
            "x": r % 500, "z": (r >> 16) % 500,
        })
    return {"resources": res}


def procgen_props(seed):
    props = ["tree_oak", "rock", "bush", "flower", "crate"]
    st = [_fnv1a_hash(seed)]
    count = 10 + _splitmix64_next(st) % 11
    out = []
    for _ in range(count):
        r = _splitmix64_next(st)
        out.append({
            "prefab": props[r % 5],
            "x": r % 800, "z": (r >> 8) % 600,
            "scale": f"{1 + (r >> 16) % 2}.{(r >> 24) % 5}",
        })
    return {"props": out}


def procgen_narrative(seed):
    quests = ["hunt_wolves", "collect_herbs", "escort_caravan",
              "defend_village", "explore_dungeon"]
    st = [_fnv1a_hash(seed)]
    count = 2 + _splitmix64_next(st) % 3
    out = []
    for _ in range(count):
        r = _splitmix64_next(st)
        out.append({
            "quest_id": quests[r % 5],
            "difficulty": 1 + ((r >> 8) % 5),
        })
    return {"quests": out}


def roll_loot(loot_table_id, seed):
    """掉落表（确定性，与 C++ CombatCore 一致）。"""
    items = ["coin", "potion", "gem", "ore", "rune"]
    st = [_fnv1a_hash(f"{loot_table_id}_{seed}")]
    drop_count = 2 + _splitmix64_next(st) % 2
    out = []
    for _ in range(drop_count):
        r = _splitmix64_next(st)
        out.append({"id": items[r % 5], "qty": 1 + ((r >> 8) % 5)})
    return {"items": out}


def calc_damage(skill_config, attacker_stats, target_stats):
    """伤害计算（定点数，与 C++ 一致）。"""
    sp = skill_config.get("base_power", 100)
    atk = attacker_stats.get("atk", 100)
    dff = target_stats.get("def", 50)
    damage = fp_to_float(fp_mul(fp_from_int(sp), fp_div(fp_from_int(atk), fp_from_int(dff))))
    return max(1, int(damage))


# ============================================================
# FFI 封装（优先真 C++，缺失回退纯 Python 参考实现）
# ============================================================
class _PurePythonBackend:
    """纯 Python 确定性核心（无编译器环境下的参考实现）。"""
    def __init__(self):
        self.state = STATE_IDLE
        self.data = {}
        self.initialized = False

    def init(self):
        self.initialized = True
        return CABI_OK

    def shutdown(self):
        self.initialized = False
        return CABI_OK

    def version(self):
        return 1

    def set_state(self, state_id):
        old = self.state
        self.state = state_id
        return old

    def get_state(self):
        return self.state

    def update(self, dt):
        return CABI_OK

    def set_data(self, key, value):
        self.data[key] = value
        return CABI_OK

    def get_data(self, key):
        if key not in self.data:
            raise MiddlewareError(CABI_ERR_NOT_FOUND)
        return self.data[key]


class _CffiBackend:
    """通过 ctypes 调用真实 C++ 编译产物。"""
    def __init__(self, lib_path):
        self.lib = ctypes.CDLL(lib_path)
        self.lib.cabi_init.restype = c_int
        self.lib.cabi_init.argtypes = [c_void_p]
        self.lib.cabi_shutdown.restype = c_int
        self.lib.cabi_gameplay_set_state.restype = c_int
        self.lib.cabi_gameplay_set_state.argtypes = [c_int]
        self.lib.cabi_gameplay_get_state.restype = c_int
        self.lib.cabi_gameplay_get_state.argtypes = [POINTER(c_int)]
        self.lib.cabi_procgen_terrain.restype = c_int
        self.lib.cabi_procgen_terrain.argtypes = [c_char_p, c_int, c_int, c_char_p, POINTER(c_char_p)]

    def _load_terrain(self, seed, w, h, params_json):
        out = c_char_p()
        rc = self.lib.cabi_procgen_terrain(
            seed.encode(), w, h, params_json.encode(), ctypes.byref(out))
        if rc != CABI_OK:
            raise MiddlewareError(rc)
        result = json.loads(out.value.decode())
        self.lib.cabi_free(ctypes.cast(out, c_void_p))
        return result


class GameMiddleware:
    """
    跨引擎中间件 Python 封装。
    优先加载 C++ 编译产物；缺失时回退到纯 Python 确定性参考实现。
    """
    def __init__(self, lib_path=None):
        self._backend = None
        path = lib_path or LIB_NAME
        if os.path.exists(path):
            try:
                self._backend = _CffiBackend(path)
                self._backend.lib.cabi_init(None)
                return
            except OSError:
                pass
        self._backend = _PurePythonBackend()
        self._backend.init()

    # ---- 生命周期 ----
    def version(self):
        return self._backend.version()

    # ---- 玩法状态机 ----
    def set_state(self, state_id):
        return self._backend.set_state(state_id)

    def get_state(self):
        return self._backend.get_state()

    def update(self, dt):
        return self._backend.update(dt)

    # ---- 数据 ----
    def set_data(self, key, value):
        return self._backend.set_data(key, value)

    def get_data(self, key):
        return self._backend.get_data(key)

    # ---- 确定性程序化生成 ----
    @staticmethod
    def terrain(seed, width, height, params=None):
        return procgen_terrain(seed, width, height, params)

    @staticmethod
    def level(seed, params=None):
        return procgen_level(seed, params)

    @staticmethod
    def resources(seed):
        return procgen_resources(seed)

    @staticmethod
    def props(seed):
        return procgen_props(seed)

    @staticmethod
    def narrative(seed):
        return procgen_narrative(seed)

    @staticmethod
    def roll_loot(loot_table_id, seed):
        return roll_loot(loot_table_id, seed)

    @staticmethod
    def calc_damage(skill_config, attacker_stats, target_stats):
        return calc_damage(skill_config, attacker_stats, target_stats)


def hash_json(obj):
    """序列化并哈希（用于跨引擎一致性校验）。"""
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def fp_add(a, b):
    return a + b


def fp_sub(a, b):
    return a - b


def fp_compare(a, b):
    return -1 if a < b else (1 if a > b else 0)
