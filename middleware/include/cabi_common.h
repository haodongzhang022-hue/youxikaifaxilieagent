/*
 * cabi_common.h - 跨引擎中间件通用 C ABI 规范
 * 对齐 Issue #90「跨平台架构增强」wp_engine C++中间件/ABI标准化
 * 原则：纯 C 头文件（无 C++ 特性），保证跨语言 FFI 兼容
 */
#ifndef CABI_COMMON_H
#define CABI_COMMON_H

#ifdef __cplusplus
extern "C" {
#endif

/* ---- 错误码 ---- */
#define CABI_OK                 0   // 成功
#define CABI_ERR_INVALID_ARG    1   // 参数错误
#define CABI_ERR_NULL_PTR       2   // 空指针
#define CABI_ERR_MEMORY         3   // 内存不足
#define CABI_ERR_NOT_INIT       4   // 未初始化
#define CABI_ERR_NOT_FOUND      5   // 资源不存在
#define CABI_ERR_VERSION        6   // 版本不匹配
#define CABI_ERR_JSON_PARSE     7   // JSON 解析失败
#define CABI_ERR_ALREADY_INIT   8   // 重复初始化

/* ---- 日志级别 ---- */
#define CABI_LOG_DEBUG  0
#define CABI_LOG_INFO   1
#define CABI_LOG_WARN   2
#define CABI_LOG_ERROR  3

/* ---- 回调类型 ---- */
typedef void (*cabi_log_callback)(const char* message, int level);
typedef void (*cabi_event_callback)(int event_type, const void* payload, int payload_size);

/* ---- 通用生命周期 ---- */
int cabi_init(cabi_log_callback log_cb);
int cabi_shutdown(void);
int cabi_version(void);
const char* cabi_error_string(int code);

/* ---- 内存管理 ---- */
void cabi_free(void* ptr);

/* ---- JSON 帮助（内置极简 JSON，避免第三方依赖） ---- */
/* 从 JSON 对象中读取字段；找不到返回 0，找到返回 1 */
int cabi_json_get_int(const char* json, const char* key, int* out);
int cabi_json_get_float(const char* json, const char* key, float* out);
int cabi_json_get_string(const char* json, const char* key, char* out, int out_size);

#ifdef __cplusplus
}
#endif

#endif /* CABI_COMMON_H */
