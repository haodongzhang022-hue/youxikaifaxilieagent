/*
 * cabi_procgen.h - 程序化生成 C ABI
 * 对齐 Issue #90 wp_engine：地形/关卡/资源分布/装饰物/叙事生成
 * 核心：同一种子（seed）→ 确定性输出（跨引擎一致）
 */
#ifndef CABI_PROCGEN_H
#define CABI_PROCGEN_H

#include "cabi_common.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ---- 确定性伪随机（splitmix64，引擎无关） ---- */
int cabi_procgen_rand_u32(const char* seed, uint32_t* out_value);
int cabi_procgen_rand_float(const char* seed, float* out_value);

/* ---- 生成地形（heightmap JSON） ---- */
int cabi_procgen_terrain(const char* seed, int width, int height,
                         const char* params_json, char** out_heightmap_json);

/* ---- 生成关卡 ---- */
int cabi_procgen_level(const char* seed, const char* level_params,
                       char** out_level_json);

/* ---- 生成资源分布 ---- */
int cabi_procgen_resources(const char* seed, const char* terrain_data,
                           const char* rules_json, char** out_resources_json);

/* ---- 生成建筑/装饰物 ---- */
int cabi_procgen_props(const char* seed, const char* params_json,
                       char** out_props_json);

/* ---- 生成叙事（任务 + 对话 JSON Schema） ----
 * 输出结构: {"quests":[{"quest_id","difficulty",
 *   "dialogues":[{"speaker","text","choice"}]}]}
 * speaker: npc_elder/npc_guard/npc_merchant/npc_blacksmith/npc_mage
 * choice: 0=普通对话, 1=含分支选项
 * 确定性：同 seed 跨引擎（C++/Python/TS/C#）输出 hash 一致
 */
int cabi_procgen_narrative(const char* seed, const char* narrative_schema,
                           char** out_narrative_json);

/* ---- 释放结果内存 ---- */
int cabi_procgen_free_result(char* result);

#ifdef __cplusplus
}
#endif

#endif /* CABI_PROCGEN_H */
