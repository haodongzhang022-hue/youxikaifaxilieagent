/*
 * cabi_combat.h - 战斗核心 C ABI
 * 对齐 Issue #90 wp_engine：战斗判定/伤害计算/状态效果/掉落（引擎无关）
 */
#ifndef CABI_COMBAT_H
#define CABI_COMBAT_H

#include "cabi_common.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ---- 战斗初始化 ---- */
int cabi_combat_init(void);
int cabi_combat_shutdown(void);

/* ---- 战斗 Tick（30Hz 固定步长） ---- */
int cabi_combat_tick(float accumulated_dt);

/* ---- 技能结算 ---- */
int cabi_combat_cast_skill(int skill_id, int attacker_id, int target_id);

/* ---- 伤害计算（定点数） ---- */
int cabi_combat_calc_damage(const char* skill_config, const char* attacker_stats,
                            const char* target_stats, int* out_damage);

/* ---- 状态效果（Buff/Debuff） ---- */
int cabi_combat_apply_status(int status_id, int target_id, int duration_ms);
int cabi_combat_remove_status(int status_id, int target_id);

/* ---- 掉落表（种子可复现） ---- */
int cabi_combat_roll_loot(int loot_table_id, int seed, char** out_loot_json);

#ifdef __cplusplus
}
#endif

#endif /* CABI_COMBAT_H */
