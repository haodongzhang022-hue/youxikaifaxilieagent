/*
 * cabi_numeric.h - 定点数/数值计算 C ABI
 * 对齐 Issue #90 wp_engine：跨平台数值精度一致（定点数）
 */
#ifndef CABI_NUMERIC_H
#define CABI_NUMERIC_H

#include "cabi_common.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ---- 定点数类型：32bit 整数部分 + 10bit 小数（1/1024 精度） ---- */
typedef int64_t FixedPoint;

/* ---- 定点数操作 ---- */
FixedPoint fp_from_float(float f);
FixedPoint fp_from_int(int i);
float fp_to_float(FixedPoint fp);
FixedPoint fp_add(FixedPoint a, FixedPoint b);
FixedPoint fp_sub(FixedPoint a, FixedPoint b);
FixedPoint fp_mul(FixedPoint a, FixedPoint b);
FixedPoint fp_div(FixedPoint a, FixedPoint b);
int fp_compare(FixedPoint a, FixedPoint b);   /* -1/0/1 */

/* ---- 等级成长曲线 ---- */
int cabi_numeric_get_level_exp(int level, int* out_exp);
int cabi_numeric_get_level_stats(int level, const char* stat_name, FixedPoint* out_value);

/* ---- 战斗公式 ---- */
FixedPoint cabi_numeric_calc_atk(FixedPoint base_atk, FixedPoint atk_pct);
FixedPoint cabi_numeric_calc_def(FixedPoint base_def, FixedPoint def_pct);
FixedPoint cabi_numeric_calc_crit(FixedPoint base_crit, FixedPoint crit_rate);

#ifdef __cplusplus
}
#endif

#endif /* CABI_NUMERIC_H */
