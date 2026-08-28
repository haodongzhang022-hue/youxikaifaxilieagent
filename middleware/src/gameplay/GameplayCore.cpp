/*
 * GameplayCore.cpp - 玩法核心实现
 * 引擎无关状态机 + 30Hz 固定 Tick + 事件系统 + JSON 中立数据
 */
#include "cabi_gameplay.h"
#include <cstdlib>
#include <cstring>

#define TICK_INTERVAL (1.0f / 30.0f)

static int s_state = GAMEPLAY_STATE_IDLE;
static float s_accumulator = 0.0f;
static int s_tick_count = 0;
static cabi_event_callback s_event_cb = NULL;

/* 极简键值存储（单实例演示） */
#define DATA_CAPACITY 16
static struct { char key[32]; char value[256]; int len; } s_data[DATA_CAPACITY];
static int s_data_count = 0;

extern "C" int cabi_gameplay_init(void) {
    s_state = GAMEPLAY_STATE_IDLE;
    s_accumulator = 0.0f;
    s_tick_count = 0;
    s_event_cb = NULL;
    s_data_count = 0;
    return CABI_OK;
}

extern "C" int cabi_gameplay_shutdown(void) {
    s_event_cb = NULL;
    s_data_count = 0;
    return CABI_OK;
}

extern "C" int cabi_gameplay_update(float delta_seconds) {
    if (delta_seconds < 0.0f) return CABI_ERR_INVALID_ARG;
    s_accumulator += delta_seconds;
    while (s_accumulator >= TICK_INTERVAL) {
        s_tick_count++;
        s_accumulator -= TICK_INTERVAL;
        /* 推进状态机：PLAYING 状态推进 Tick */
        if (s_state == GAMEPLAY_STATE_PLAYING && s_event_cb) {
            s_event_cb(1001, &s_tick_count, sizeof(s_tick_count)); /* TICK 事件 */
        }
    }
    return CABI_OK;
}

extern "C" int cabi_gameplay_set_state(int state_id) {
    if (state_id < GAMEPLAY_STATE_IDLE || state_id > GAMEPLAY_STATE_GAMEOVER)
        return CABI_ERR_INVALID_ARG;
    int old = s_state;
    s_state = state_id;
    if (s_event_cb) s_event_cb(1000, &state_id, sizeof(state_id)); /* STATE 变更事件 */
    return old;
}

extern "C" int cabi_gameplay_get_state(int* out_state) {
    if (out_state == NULL) return CABI_ERR_NULL_PTR;
    *out_state = s_state;
    return CABI_OK;
}

extern "C" int cabi_gameplay_register_event_callback(cabi_event_callback cb) {
    s_event_cb = cb;
    return CABI_OK;
}

extern "C" int cabi_gameplay_emit_event(int event_type, const void* payload, int payload_size) {
    if (s_event_cb == NULL) return CABI_ERR_NOT_INIT;
    s_event_cb(event_type, payload, payload_size);
    return CABI_OK;
}

extern "C" int cabi_gameplay_set_data(const char* key, const char* json_data) {
    if (!key || !json_data) return CABI_ERR_NULL_PTR;
    /* 查找或插入 */
    for (int i = 0; i < s_data_count; i++) {
        if (strcmp(s_data[i].key, key) == 0) {
            strncpy(s_data[i].value, json_data, 255);
            s_data[i].value[255] = '\0';
            s_data[i].len = (int)strlen(json_data);
            return CABI_OK;
        }
    }
    if (s_data_count >= DATA_CAPACITY) return CABI_ERR_MEMORY;
    strncpy(s_data[s_data_count].key, key, 31);
    strncpy(s_data[s_data_count].value, json_data, 255);
    s_data[s_data_count].value[255] = '\0';
    s_data[s_data_count].len = (int)strlen(json_data);
    s_data_count++;
    return CABI_OK;
}

extern "C" int cabi_gameplay_get_data(const char* key, char** out_json, int* out_size) {
    if (!key || !out_json || !out_size) return CABI_ERR_NULL_PTR;
    for (int i = 0; i < s_data_count; i++) {
        if (strcmp(s_data[i].key, key) == 0) {
            char* copy = (char*)malloc(s_data[i].len + 1);
            if (!copy) return CABI_ERR_MEMORY;
            memcpy(copy, s_data[i].value, s_data[i].len + 1);
            *out_json = copy;
            *out_size = s_data[i].len;
            return CABI_OK;
        }
    }
    return CABI_ERR_NOT_FOUND;
}
