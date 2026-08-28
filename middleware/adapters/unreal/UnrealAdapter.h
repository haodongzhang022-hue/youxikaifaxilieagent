/*
 * UnrealAdapter.h - Unreal (原生 C++) 引擎适配器
 * 对齐 Issue #90 wp_engine：UE 原生源码直接编译 C++ 核心，零桥接。
 *
 * 职责：
 *   1. UE5 高保真渲染接入 middleware C++ 核心（原生源码集成）
 *   2. 消费确定性程序化生成输出，做高质量场景表现
 *   3. 体现「选 C++ 的最大收益」：Unity→UE 迁移成本最低（C++ 核心直接编译入 UE）
 */
#ifndef UNREAL_ADAPTER_H
#define UNREAL_ADAPTER_H

#include <string>

// 引入 C ABI 核心（原生源码集成，直接调用）
#include "../../include/cabi_common.h"
#include "../../include/cabi_gameplay.h"
#include "../../include/cabi_procgen.h"

namespace GameMiddleware {

/**
 * Unreal 引擎适配器。
 * 护城河版本：UE5 负责最高质量渲染，逻辑/程序化生成复用 C++ 核心。
 * 零桥接 —— C++ 核心直接编译进 UE，性能最优、迁移成本最低。
 */
class UnrealAdapter {
public:
    explicit UnrealAdapter(const std::string& seed = "unreal_default")
        : world_seed_(seed) {}

    /// 初始化 UE + middleware 核心
    int Initialize() {
        int rc = cabi_init(nullptr);
        if (rc != CABI_OK) return rc;
        return cabi_gameplay_set_state(GAMEPLAY_STATE_PLAYING);
    }

    void Shutdown() {
        cabi_shutdown();
    }

    /// 从 middleware 生成确定性地形（UE 高质量渲染输入）
    std::string GenerateTerrain(const std::string& seed,
                                int width = 256, int height = 256) {
        char* out_json = nullptr;
        int rc = cabi_procgen_terrain(
            seed.c_str(), width, height, "{}", &out_json);
        if (rc != CABI_OK || out_json == nullptr) {
            return "{}";
        }
        std::string result(out_json);
        cabi_procgen_free_result(out_json);
        return result;
    }

    /// 跨引擎一致性 golden hash（与 Web/Cocos/Unity 比对）
    std::string WorldHash(const std::string& seed) {
        std::string terrain = GenerateTerrain(seed, 8, 8);
        // 一致性 hash：与 TS hashJson 对齐（简化实现，实际用统一 hash 器）
        unsigned h = 0;
        for (char c : terrain) {
            h = ((h << 5) - h) + static_cast<unsigned char>(c);
        }
        char buf[16];
        snprintf(buf, sizeof(buf), "%08X", h);
        return std::string(buf);
    }

    /// 切换到新世界种子（程序化生成）
    void SwitchWorld(const std::string& seed) {
        world_seed_ = seed;
    }

private:
    std::string world_seed_;
};

}  // namespace GameMiddleware

#endif /* UNREAL_ADAPTER_H */
