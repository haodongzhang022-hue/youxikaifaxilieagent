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
#include <vector>
#include <cstdio>
#include <cstdint>
#include <cstring>

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
    /// 统一 SHA-256：与 TS hashJson / Python hash_json 输出一致。
    std::string WorldHash(const std::string& seed) {
        std::string terrain = GenerateTerrain(seed, 8, 8);
        return Sha256Hex(terrain);
    }

    /// 切换到新世界种子（程序化生成）
    void SwitchWorld(const std::string& seed) {
        world_seed_ = seed;
    }

private:
    /// SHA-256 十六进制小写输出（与 TS/Python 统一）。
    static std::string Sha256Hex(const std::string& input) {
        // SHA-256 常量
        static const uint32_t K[64] = {
            0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
            0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
            0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
            0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
            0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
            0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
            0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
            0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
        };
        static const uint32_t H0[8] = {
            0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,
            0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19
        };

        // 预处理：填充
        size_t l = input.size();
        uint64_t bitLen = (uint64_t)l * 8;
        size_t newLen = ((l + 8) / 64 + 1) * 64;
        std::vector<uint8_t> msg(newLen, 0);
        memcpy(msg.data(), input.data(), l);
        msg[l] = 0x80;
        // 64-bit bit length (big endian)
        for (int i = 0; i < 8; i++) {
            msg[newLen - 1 - i] = (uint8_t)(bitLen >> (8 * i));
        }

        uint32_t h[8];
        memcpy(h, H0, sizeof(H0));

        // 处理每个 64 字节块
        for (size_t offset = 0; offset < newLen; offset += 64) {
            uint32_t w[64];
            for (int i = 0; i < 16; i++) {
                w[i] = ((uint32_t)msg[offset + i*4] << 24) |
                       ((uint32_t)msg[offset + i*4 + 1] << 16) |
                       ((uint32_t)msg[offset + i*4 + 2] << 8) |
                       ((uint32_t)msg[offset + i*4 + 3]);
            }
            for (int i = 16; i < 64; i++) {
                uint32_t s0 = __rotr32(w[i-15], 7) ^ __rotr32(w[i-15], 18) ^ (w[i-15] >> 3);
                uint32_t s1 = __rotr32(w[i-2], 17) ^ __rotr32(w[i-2], 19) ^ (w[i-2] >> 10);
                w[i] = w[i-16] + s0 + w[i-7] + s1;
            }

            uint32_t a = h[0], b = h[1], c = h[2], d = h[3];
            uint32_t e = h[4], f = h[5], g = h[6], hh = h[7];

            for (int i = 0; i < 64; i++) {
                uint32_t S1 = __rotr32(e, 6) ^ __rotr32(e, 11) ^ __rotr32(e, 25);
                uint32_t ch = (e & f) ^ (~e & g);
                uint32_t temp1 = hh + S1 + ch + K[i] + w[i];
                uint32_t S0 = __rotr32(a, 2) ^ __rotr32(a, 13) ^ __rotr32(a, 22);
                uint32_t maj = (a & b) ^ (a & c) ^ (b & c);
                uint32_t temp2 = S0 + maj;

                hh = g; g = f; f = e; e = d + temp1;
                d = c; c = b; b = a; a = temp1 + temp2;
            }

            h[0] += a; h[1] += b; h[2] += c; h[3] += d;
            h[4] += e; h[5] += f; h[6] += g; h[7] += hh;
        }

        // 输出十六进制小写
        char buf[65];
        static const char hexd[] = "0123456789abcdef";
        int pos = 0;
        for (int i = 0; i < 8; i++) {
            for (int j = 28; j >= 0; j -= 4) {
                buf[pos++] = hexd[(h[i] >> j) & 0xF];
            }
        }
        buf[64] = '\0';
        return std::string(buf);
    }

    static uint32_t __rotr32(uint32_t x, int n) {
        return (x >> n) | (x << (32 - n));
    }

    std::string world_seed_;
};

}  // namespace GameMiddleware

#endif /* UNREAL_ADAPTER_H */
