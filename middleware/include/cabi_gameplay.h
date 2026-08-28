/*
 * cabi_gameplay.h - 玩法核心 C ABI
 * 对齐 Issue #90 wp_engine：引擎无关玩法状态机 + 事件系统
 */
#ifndef CABI_GAMEPLAY_H
#define CABI_GAMEPLAY_H

#include "cabi_common.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ---- 状态定义 ---- */
#define GAMEPLAY_STATE_IDLE      0
#define GAMEPLAY_STATE_PLAYING   1
#define GAMEPLAY_STATE_PAUSED    2
#define GAMEPLAY_STATE_GAMEOVER  3

/* ---- 生命周期 ---- */
int cabi_gameplay_init(void);
int cabi_gameplay_shutdown(void);

/* ---- 更新循环（30Hz 固定 Tick 累加器） ---- */
int cabi_gameplay_update(float delta_seconds);

/* ---- 状态管理 ---- */
int cabi_gameplay_set_state(int state_id);
int cabi_gameplay_get_state(int* out_state);

/* ---- 事件系统 ---- */
int cabi_gameplay_register_event_callback(cabi_event_callback cb);
int cabi_gameplay_emit_event(int event_type, const void* payload, int payload_size);

/* ---- 数据模型（JSON 序列化，引擎无关中立数据） ---- */
int cabi_gameplay_set_data(const char* key, const char* json_data);
int cabi_gameplay_get_data(const char* key, char** out_json, int* out_size);

#ifdef __cplusplus
}
#endif

#endif /* CABI_GAMEPLAY_H */
