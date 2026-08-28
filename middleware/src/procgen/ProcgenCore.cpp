/*
 * ProcgenCore.cpp - 程序化生成核心实现
 * 确定性：同一种子（seed）→ 完全一致的输出（跨引擎 hash 校验）
 * 生成：地形 heightmap / 关卡 / 资源分布 / 装饰物 / 叙事
 */
#include "cabi_procgen.h"
#include "cabi_common.h"
#include <cstdlib>
#include <cstring>
#include <cstdio>
#include <stdint.h>

/* ---- splitmix64 确定性 PRNG ---- */
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

extern "C" int cabi_procgen_rand_u32(const char* seed, uint32_t* out_value) {
    if (!seed || !out_value) return CABI_ERR_NULL_PTR;
    splitmix64_state st = fnv1a_hash(seed);
    *out_value = (uint32_t)(splitmix64_next(&st) & 0xFFFFFFFFULL);
    return CABI_OK;
}

extern "C" int cabi_procgen_rand_float(const char* seed, float* out_value) {
    if (!seed || !out_value) return CABI_ERR_NULL_PTR;
    splitmix64_state st = fnv1a_hash(seed);
    uint64_t r = splitmix64_next(&st);
    *out_value = (float)((r >> 11) * (1.0 / 9007199254740992.0)); /* [0,1) */
    return CABI_OK;
}

/* ---- 地形生成：value-noise 高度图（确定性） ---- */
extern "C" int cabi_procgen_terrain(const char* seed, int width, int height,
                                    const char* params_json, char** out_heightmap_json) {
    if (!seed || !out_heightmap_json || width <= 0 || height <= 0)
        return CABI_ERR_NULL_PTR;

    /* 解析参数：octaves（分形噪声层级，默认 4） */
    int octaves = 4;
    if (params_json) cabi_json_get_int(params_json, "octaves", &octaves);
    if (octaves < 1) octaves = 1;
    if (octaves > 8) octaves = 8;

    splitmix64_state st = fnv1a_hash(seed);

    /* 生成 heightmap */
    int n = width * height;
    int* heights = (int*)malloc(sizeof(int) * n);
    if (!heights) return CABI_ERR_MEMORY;

    for (int y = 0; y < height; y++) {
        for (int x = 0; x < width; x++) {
            uint64_t r = splitmix64_next(&st);
            int h = (int)(r % 100); /* 0-99 高度 */
            heights[y * width + x] = h;
        }
    }

    /* 简单平滑（一次均值滤波，确定性） */
    int* smoothed = (int*)malloc(sizeof(int) * n);
    if (!smoothed) { free(heights); return CABI_ERR_MEMORY; }
    for (int y = 0; y < height; y++) {
        for (int x = 0; x < width; x++) {
            long sum = 0; int cnt = 0;
            for (int dy = -1; dy <= 1; dy++) {
                for (int dx = -1; dx <= 1; dx++) {
                    int nx = x + dx, ny = y + dy;
                    if (nx >= 0 && nx < width && ny >= 0 && ny < height) {
                        sum += heights[ny * width + nx]; cnt++;
                    }
                }
            }
            smoothed[y * width + x] = (int)(sum / cnt);
        }
    }
    free(heights);

    /* 序列化为 JSON */
    size_t cap = (size_t)n * 6 + 64;
    char* buf = (char*)malloc(cap);
    if (!buf) { free(smoothed); return CABI_ERR_MEMORY; }
    int off = snprintf(buf, cap, "{\"width\":%d,\"height\":%d,\"seed\":\"%s\",\"data\":[",
                       width, height, seed);
    for (int i = 0; i < n; i++) {
        off += snprintf(buf + off, cap - off, "%d%s", smoothed[i], i < n - 1 ? "," : "");
    }
    snprintf(buf + off, cap - off, "]}");
    free(smoothed);

    *out_heightmap_json = buf;
    return CABI_OK;
}

/* ---- 关卡生成 ---- */
extern "C" int cabi_procgen_level(const char* seed, const char* level_params,
                                  char** out_level_json) {
    if (!seed || !out_level_json) return CABI_ERR_NULL_PTR;
    splitmix64_state st = fnv1a_hash(seed);

    int w = 100, d = 80;
    if (level_params) {
        cabi_json_get_int(level_params, "width", &w);
        cabi_json_get_int(level_params, "depth", &d);
    }

    /* 生成少量生成点 + 装饰物 */
    int prop_count = 5 + (int)(splitmix64_next(&st) % 6);
    char buf[1024];
    int off = snprintf(buf, sizeof(buf),
        "{\"level_id\":\"LVL_%u\",\"dimensions\":{\"width\":%d,\"depth\":%d},\"props\":[",
        (unsigned)(splitmix64_next(&st) & 0xFFFF), w, d);
    for (int i = 0; i < prop_count; i++) {
        uint64_t r = splitmix64_next(&st);
        int px = (int)(r % (uint64_t)w);
        int pz = (int)((r >> 8) % (uint64_t)d);
        off += snprintf(buf + off, sizeof(buf) - off,
            "{\"prefab_id\":\"prop_%d\",\"x\":%d,\"z\":%d}%s",
            (int)(r % 8), px, pz, i < prop_count - 1 ? "," : "");
    }
    snprintf(buf + off, sizeof(buf) - off, "]}");
    *out_level_json = strdup(buf);
    return CABI_OK;
}

/* ---- 资源分布生成 ---- */
extern "C" int cabi_procgen_resources(const char* seed, const char* terrain_data,
                                      const char* rules_json, char** out_resources_json) {
    if (!seed || !out_resources_json) return CABI_ERR_NULL_PTR;
    splitmix64_state st = fnv1a_hash(seed);
    const char* types[] = {"iron", "copper", "gold", "wood", "stone"};
    int count = 8 + (int)(splitmix64_next(&st) % 9);
    char buf[1024];
    int off = snprintf(buf, sizeof(buf), "{\"resources\":[");
    for (int i = 0; i < count; i++) {
        uint64_t r = splitmix64_next(&st);
        const char* t = types[r % 5];
        int amt = 10 + (int)((r >> 8) % 90);
        off += snprintf(buf + off, sizeof(buf) - off,
            "{\"type\":\"%s\",\"amount\":%d,\"x\":%d,\"z\":%d}%s",
            t, amt, (int)(r % 500), (int)((r >> 16) % 500), i < count - 1 ? "," : "");
    }
    snprintf(buf + off, sizeof(buf) - off, "]}");
    *out_resources_json = strdup(buf);
    return CABI_OK;
}

/* ---- 装饰物生成 ---- */
extern "C" int cabi_procgen_props(const char* seed, const char* params_json,
                                  char** out_props_json) {
    if (!seed || !out_props_json) return CABI_ERR_NULL_PTR;
    splitmix64_state st = fnv1a_hash(seed);
    const char* props[] = {"tree_oak", "rock", "bush", "flower", "crate"};
    int count = 10 + (int)(splitmix64_next(&st) % 11);
    char buf[1024];
    int off = snprintf(buf, sizeof(buf), "{\"props\":[");
    for (int i = 0; i < count; i++) {
        uint64_t r = splitmix64_next(&st);
        off += snprintf(buf + off, sizeof(buf) - off,
            "{\"prefab\":\"%s\",\"x\":%d,\"z\":%d,\"scale\":%d.%d}%s",
            props[r % 5], (int)(r % 800), (int)((r >> 8) % 600),
            (int)(1 + (r >> 16) % 2), (int)((r >> 24) % 5), i < count - 1 ? "," : "");
    }
    snprintf(buf + off, sizeof(buf) - off, "]}");
    *out_props_json = strdup(buf);
    return CABI_OK;
}

/* ---- 叙事生成 ---- */
extern "C" int cabi_procgen_narrative(const char* seed, const char* narrative_schema,
                                      char** out_narrative_json) {
    if (!seed || !out_narrative_json) return CABI_ERR_NULL_PTR;
    splitmix64_state st = fnv1a_hash(seed);
    const char* quests[] = {"hunt_wolves", "collect_herbs", "escort_caravan",
                            "defend_village", "explore_dungeon"};
    int count = 2 + (int)(splitmix64_next(&st) % 3);
    char buf[1024];
    int off = snprintf(buf, sizeof(buf), "{\"quests\":[");
    for (int i = 0; i < count; i++) {
        uint64_t r = splitmix64_next(&st);
        off += snprintf(buf + off, sizeof(buf) - off,
            "{\"quest_id\":\"%s\",\"difficulty\":%d}%s",
            quests[r % 5], (int)(1 + (r >> 8) % 5), i < count - 1 ? "," : "");
    }
    snprintf(buf + off, sizeof(buf) - off, "]}");
    *out_narrative_json = strdup(buf);
    return CABI_OK;
}

/* ---- 释放结果内存 ---- */
extern "C" int cabi_procgen_free_result(char* result) {
    if (result) free(result);
    return CABI_OK;
}
