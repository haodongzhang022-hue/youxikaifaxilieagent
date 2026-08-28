/*
 * CombatCore.cpp - 战斗核心实现
 * 伤害计算（定点数）+ 技能结算 + 掉落表（种子可复现）
 */
#include "cabi_combat.h"
#include "cabi_numeric.h"
#include "cabi_common.h"
#include <cstdlib>
#include <cstring>
#include <cstdio>

#define COMBAT_TICK (1.0f / 30.0f)

/* splitmix64 确定性 PRNG（引擎无关，同 seed 同输出） */
typedef uint64_t splitmix64_state;
static uint64_t splitmix64_next(splitmix64_state* s) {
    uint64_t z = (*s += 0x9E3779B97F4A7C15ULL);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
    return z ^ (z >> 31);
}

static uint64_t fnv1a_hash(const char* str) {
    uint64_t h = 14695981039346656037ULL;
    for (const unsigned char* p = (const unsigned char*)str; *p; p++) {
        h ^= *p;
        h *= 1099511628211ULL;
    }
    return h;
}

extern "C" int cabi_combat_init(void) { return CABI_OK; }
extern "C" int cabi_combat_shutdown(void) { return CABI_OK; }

extern "C" int cabi_combat_tick(float accumulated_dt) {
    if (accumulated_dt < 0) return CABI_ERR_INVALID_ARG;
    return CABI_OK;
}

extern "C" int cabi_combat_cast_skill(int skill_id, int attacker_id, int target_id) {
    if (skill_id <= 0) return CABI_ERR_INVALID_ARG;
    return CABI_OK; /* 简化：技能施放成功 */
}

extern "C" int cabi_combat_calc_damage(const char* skill_config, const char* attacker_stats,
                                       const char* target_stats, int* out_damage) {
    if (!skill_config || !attacker_stats || !target_stats || !out_damage)
        return CABI_ERR_NULL_PTR;

    /* 解析：skill 系数 base_power；攻击方 atk；防守方 def */
    int base_power = 100, atk = 100, def = 50;
    cabi_json_get_int(skill_config, "base_power", &base_power);
    cabi_json_get_int(attacker_stats, "atk", &atk);
    cabi_json_get_int(target_stats, "def", &def);

    /* 定点数计算，保证跨引擎 bit 级一致 */
    FixedPoint fp_power = fp_from_int(base_power);
    FixedPoint fp_atk   = fp_from_int(atk);
    FixedPoint fp_def   = fp_from_int(def);

    /* damage = base_power * atk / def （定点除法保证一致） */
    FixedPoint ratio = fp_div(fp_atk, fp_def);
    FixedPoint damage = fp_mul(fp_power, ratio);
    *out_damage = (int)fp_to_float(damage);
    if (*out_damage < 1) *out_damage = 1;
    return CABI_OK;
}

extern "C" int cabi_combat_apply_status(int status_id, int target_id, int duration_ms) {
    if (status_id <= 0) return CABI_ERR_INVALID_ARG;
    return CABI_OK;
}

extern "C" int cabi_combat_remove_status(int status_id, int target_id) {
    if (status_id <= 0) return CABI_ERR_INVALID_ARG;
    return CABI_OK;
}

extern "C" int cabi_combat_roll_loot(int loot_table_id, int seed, char** out_loot_json) {
    if (!out_loot_json) return CABI_ERR_NULL_PTR;

    char seed_str[32];
    snprintf(seed_str, sizeof(seed_str), "%d_%d", loot_table_id, seed);
    splitmix64_state st = fnv1a_hash(seed_str);

    /* 确定性掉落：3 个物品槽，品质由种子决定 */
    const char* items[5] = {"coin", "potion", "gem", "ore", "rune"};
    int drop_count = 2 + (int)(splitmix64_next(&st) % 2); /* 2-3 个 */

    char buf[512];
    int off = snprintf(buf, sizeof(buf), "{\"items\":[");
    for (int i = 0; i < drop_count; i++) {
        uint64_t r = splitmix64_next(&st);
        int idx = (int)(r % 5);
        int qty = 1 + (int)((r >> 8) % 5);
        off += snprintf(buf + off, sizeof(buf) - off, "{\"id\":\"%s\",\"qty\":%d}%s",
                        items[idx], qty, i < drop_count - 1 ? "," : "");
    }
    snprintf(buf + off, sizeof(buf) - off, "]}");

    char* copy = (char*)malloc(strlen(buf) + 1);
    if (!copy) return CABI_ERR_MEMORY;
    strcpy(copy, buf);
    *out_loot_json = copy;
    return CABI_OK;
}
