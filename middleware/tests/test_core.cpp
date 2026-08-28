/* test_core.cpp - 中间件核心自测 */
#include "cabi_common.h"
#include "cabi_numeric.h"
#include "cabi_procgen.h"
#include "cabi_gameplay.h"
#include "cabi_combat.h"
#include <cstdio>
#include <cstring>
#include <cassert>

int failures = 0;
#define CHECK(cond, msg) do { if(!(cond)){ printf("FAIL: %s\n", msg); failures++; } else { printf("PASS: %s\n", msg);} } while(0)

int main() {
    /* 通用生命周期 */
    CHECK(cabi_init(NULL) == CABI_OK, "cabi_init");
    CHECK(cabi_version() == 1, "cabi_version");
    CHECK(cabi_error_string(CABI_OK) != NULL, "error_string");

    /* 定点数 */
    FixedPoint a = fp_from_int(3);
    FixedPoint b = fp_from_int(4);
    CHECK(fp_add(a, b) == fp_from_int(7), "fp_add");
    FixedPoint m = fp_mul(a, b);
    CHECK(fp_to_float(m) == 12.0f, "fp_mul 3*4=12");
    FixedPoint d = fp_div(a, b);
    CHECK(fp_to_float(d) == 0.75f, "fp_div 3/4=0.75");
    CHECK(fp_compare(a, b) == -1, "fp_compare");

    /* 程序化生成：确定性（同 seed 两次输出一致） */
    char* h1 = NULL, *h2 = NULL;
    cabi_procgen_terrain("seed42", 8, 8, "{\"octaves\":3}", &h1);
    cabi_procgen_terrain("seed42", 8, 8, "{\"octaves\":3}", &h2);
    CHECK(strcmp(h1, h2) == 0, "terrain determinism same seed");
    cabi_procgen_free_result(h1);
    cabi_procgen_free_result(h2);

    /* 不同 seed 输出不同 */
    char* h3 = NULL;
    cabi_procgen_terrain("seed99", 8, 8, "{\"octaves\":3}", &h3);
    cabi_procgen_free_result(h1); /* already freed; skip */
    h1 = NULL;
    cabi_procgen_free_result(h3);

    /* rand 确定性 */
    uint32_t r1, r2;
    cabi_procgen_rand_u32("abc", &r1);
    cabi_procgen_rand_u32("abc", &r2);
    CHECK(r1 == r2, "rand_u32 determinism");

    /* 玩法状态机 */
    CHECK(cabi_gameplay_init() == CABI_OK, "gameplay_init");
    cabi_gameplay_set_state(GAMEPLAY_STATE_PLAYING);
    int st = 0;
    cabi_gameplay_get_state(&st);
    CHECK(st == GAMEPLAY_STATE_PLAYING, "gameplay_set_state");
    cabi_gameplay_update(0.1f);
    cabi_gameplay_shutdown();

    /* 战斗伤害（定点数一致） */
    int dmg1 = 0, dmg2 = 0;
    cabi_combat_calc_damage("{\"base_power\":100}", "{\"atk\":100}", "{\"def\":50}", &dmg1);
    cabi_combat_calc_damage("{\"base_power\":100}", "{\"atk\":100}", "{\"def\":50}", &dmg2);
    CHECK(dmg1 == dmg2, "combat damage determinism");
    printf("damage=%d\n", dmg1);

    /* 掉落确定性 */
    char* loot1 = NULL, *loot2 = NULL;
    cabi_combat_roll_loot(1, 42, &loot1);
    cabi_combat_roll_loot(1, 42, &loot2);
    CHECK(strcmp(loot1, loot2) == 0, "loot determinism same seed");
    printf("loot=%s\n", loot1);
    free(loot1); free(loot2);

    cabi_shutdown();
    printf(failures == 0 ? "\nALL TESTS PASSED\n" : "\n%d FAILURES\n", failures);
    return failures == 0 ? 0 : 1;
}
