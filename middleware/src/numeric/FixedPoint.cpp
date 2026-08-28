/*
 * FixedPoint.cpp - 定点数实现（32bit 整数 + 10bit 小数，1/1024 精度）
 * 目的：跨引擎数值 bit 级一致，避免浮点精度差异
 */
#include "cabi_numeric.h"
#include <cmath>

#define FP_FRACTION_BITS 10
#define FP_ONE (1 << FP_FRACTION_BITS)      /* 1.0 的定点表示 */

/* ---- 基础转换 ---- */
extern "C" FixedPoint fp_from_float(float f) {
    return (FixedPoint)llroundf(f * FP_ONE);
}

extern "C" FixedPoint fp_from_int(int i) {
    return ((FixedPoint)i) << FP_FRACTION_BITS;
}

extern "C" float fp_to_float(FixedPoint fp) {
    return (float)fp / (float)FP_ONE;
}

extern "C" FixedPoint fp_add(FixedPoint a, FixedPoint b) {
    return a + b;
}

extern "C" FixedPoint fp_sub(FixedPoint a, FixedPoint b) {
    return a - b;
}

extern "C" FixedPoint fp_mul(FixedPoint a, FixedPoint b) {
    /* 定点乘法：结果右移小数位，避免溢出用 __int128 */
    return (FixedPoint)(((__int128)a * b) >> FP_FRACTION_BITS);
}

extern "C" FixedPoint fp_div(FixedPoint a, FixedPoint b) {
    if (b == 0) return 0;
    return (FixedPoint)(((__int128)a << FP_FRACTION_BITS) / b);
}

extern "C" int fp_compare(FixedPoint a, FixedPoint b) {
    if (a < b) return -1;
    if (a > b) return 1;
    return 0;
}

/* ---- 等级成长曲线 ---- */
extern "C" int cabi_numeric_get_level_exp(int level, int* out_exp) {
    if (out_exp == NULL) return CABI_ERR_NULL_PTR;
    if (level < 1) level = 1;
    /* 指数曲线：exp = 100 * level^2（跨端一致的纯函数） */
    *out_exp = 100 * level * level;
    return CABI_OK;
}

extern "C" int cabi_numeric_get_level_stats(int level, const char* stat_name, FixedPoint* out_value) {
    if (out_value == NULL || stat_name == NULL) return CABI_ERR_NULL_PTR;
    if (level < 1) level = 1;
    FixedPoint base = fp_from_int(level * 10);
    if (stat_name[0] == 'h') base = fp_mul(base, fp_from_int(12)); /* hp */
    else if (stat_name[0] == 'a') base = fp_mul(base, fp_from_int(3));  /* atk */
    else if (stat_name[0] == 'd') base = fp_mul(base, fp_from_int(2));  /* def */
    *out_value = base;
    return CABI_OK;
}

/* ---- 战斗公式 ---- */
extern "C" FixedPoint cabi_numeric_calc_atk(FixedPoint base_atk, FixedPoint atk_pct) {
    /* final_atk = base_atk * (1 + atk_pct) */
    FixedPoint one = fp_from_int(1);
    return fp_mul(base_atk, fp_add(one, atk_pct));
}

extern "C" FixedPoint cabi_numeric_calc_def(FixedPoint base_def, FixedPoint def_pct) {
    FixedPoint one = fp_from_int(1);
    return fp_mul(base_def, fp_add(one, def_pct));
}

extern "C" FixedPoint cabi_numeric_calc_crit(FixedPoint base_crit, FixedPoint crit_rate) {
    /* crit = base_crit * (1 + crit_rate) */
    FixedPoint one = fp_from_int(1);
    return fp_mul(base_crit, fp_add(one, crit_rate));
}
