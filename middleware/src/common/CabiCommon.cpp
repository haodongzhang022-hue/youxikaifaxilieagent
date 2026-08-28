/*
 * CabiCommon.cpp - 通用 C ABI 实现
 * 生命周期管理 + 极简 JSON 读取（无第三方依赖）
 */
#include "cabi_common.h"
#include <cstdlib>
#include <cstring>

static int s_initialized = 0;
static cabi_log_callback s_log_cb = NULL;

static void log_msg(const char* msg, int level) {
    if (s_log_cb != NULL) s_log_cb(msg, level);
}

extern "C" int cabi_init(cabi_log_callback log_cb) {
    if (s_initialized) return CABI_ERR_ALREADY_INIT;
    s_initialized = 1;
    s_log_cb = log_cb;
    log_msg("cabi middleware initialized", CABI_LOG_INFO);
    return CABI_OK;
}

extern "C" int cabi_shutdown(void) {
    if (!s_initialized) return CABI_OK;
    s_initialized = 0;
    s_log_cb = NULL;
    return CABI_OK;
}

extern "C" int cabi_version(void) {
    return 1;
}

extern "C" const char* cabi_error_string(int code) {
    switch (code) {
        case CABI_OK:              return "ok";
        case CABI_ERR_INVALID_ARG: return "invalid argument";
        case CABI_ERR_NULL_PTR:    return "null pointer";
        case CABI_ERR_MEMORY:      return "out of memory";
        case CABI_ERR_NOT_INIT:    return "not initialized";
        case CABI_ERR_NOT_FOUND:   return "not found";
        case CABI_ERR_VERSION:     return "version mismatch";
        case CABI_ERR_JSON_PARSE:  return "json parse error";
        default:                   return "unknown error";
    }
}

extern "C" void cabi_free(void* ptr) {
    free(ptr);
}

/* ---- 极简 JSON 字段读取（支持 "key": value 形式） ---- */
static const char* find_key(const char* json, const char* key) {
    if (!json || !key) return NULL;
    const char* p = json;
    size_t klen = strlen(key);
    while ((p = strstr(p, key)) != NULL) {
        /* 检查 key 后是否为 JSON 分隔符 ":" */
        const char* colon = p + klen;
        while (*colon == ' ') colon++;
        if (*colon == ':') return colon + 1;
        p++;
    }
    return NULL;
}

extern "C" int cabi_json_get_int(const char* json, const char* key, int* out) {
    if (!out) return 0;
    const char* v = find_key(json, key);
    if (!v) return 0;
    while (*v == ' ' || *v == '"') v++;
    *out = (int)strtol(v, NULL, 10);
    return 1;
}

extern "C" int cabi_json_get_float(const char* json, const char* key, float* out) {
    if (!out) return 0;
    const char* v = find_key(json, key);
    if (!v) return 0;
    while (*v == ' ' || *v == '"') v++;
    *out = (float)strtod(v, NULL);
    return 1;
}

extern "C" int cabi_json_get_string(const char* json, const char* key, char* out, int out_size) {
    if (!out || out_size <= 0) return 0;
    const char* v = find_key(json, key);
    if (!v) return 0;
    while (*v == ' ' || *v == '"') v++;
    int i = 0;
    while (*v && *v != '"' && i < out_size - 1) { out[i++] = *v++; }
    out[i] = '\0';
    return 1;
}
