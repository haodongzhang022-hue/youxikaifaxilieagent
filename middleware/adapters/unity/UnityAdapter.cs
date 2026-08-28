// UnityAdapter.cs - Unity (P/Invoke / Native Plugin) 引擎适配器
// 对齐 Issue #90 wp_engine：Unity 团结引擎经 P/Invoke + Native Plugin 调用 C++ 核心。
//
// 职责：
//   1. 将 Unity 渲染/物理接入 middleware C ABI
//   2. C# 侧经 P/Invoke 调用 C++（libgame_middleware_abi），与 Web/Cocos/UE 同核心
//   3. 保证 Unity 完整地图版本与其他端输出一致（同 seed 同 hash）
using System;
using System.Runtime.InteropServices;

namespace GameMiddleware.Unity
{
    /// <summary>
    /// Unity 引擎适配器。
    /// 完整地图 App 客户端：Unity 负责渲染，middleware C++ 核心负责逻辑/程序化生成。
    /// 经 P/Invoke 调用 Native Plugin，保证跨引擎确定性。
    /// </summary>
    public class UnityAdapter
    {
        public const string EngineName = "unity-pinvoke";

        // ---- Native Plugin (P/Invoke) 声明，对应 C ABI ----
        [DllImport("game_middleware_abi")]
        private static extern int cabi_init(IntPtr log_cb);
        [DllImport("game_middleware_abi")]
        private static extern int cabi_shutdown();
        [DllImport("game_middleware_abi")]
        private static extern int cabi_gameplay_set_state(int state_id);
        [DllImport("game_middleware_abi")]
        private static extern int cabi_gameplay_get_state(out int state);
        [DllImport("game_middleware_abi")]
        private static extern int cabi_procgen_terrain(
            [MarshalAs(UnmanagedType.LPStr)] string seed,
            int width, int height,
            [MarshalAs(UnmanagedType.LPStr)] string paramsJson,
            out IntPtr outJson);

        // 状态常量（对齐 cabi_gameplay.h）
        private const int STATE_PLAYING = 1;

        private string _worldSeed;

        public UnityAdapter(string seed = "unity_default")
        {
            _worldSeed = seed;
        }

        public void Initialize()
        {
            int rc = cabi_init(IntPtr.Zero);
            if (rc != 0)
                throw new Exception($"UnityAdapter: cabi_init failed rc={rc}");
            cabi_gameplay_set_state(STATE_PLAYING);
        }

        public void Shutdown()
        {
            cabi_shutdown();
        }

        /// <summary>
        /// 从 middleware 生成确定性地形（完整地图版本）。
        /// 与 Web/Cocos/UE 同一 C++ 核心 → 同 seed 输出 hash 一致。
        /// </summary>
        public string GenerateTerrain(string seed, int width = 64, int height = 64)
        {
            IntPtr outPtr;
            int rc = cabi_procgen_terrain(seed, width, height, "{}", out outPtr);
            if (rc != 0)
                throw new Exception($"UnityAdapter: terrain generation failed rc={rc}");
            string json = Marshal.PtrToStringAnsi(outPtr);
            return json;
        }

        /// <summary>跨引擎一致性校验（golden hash）。</summary>
        public string WorldHash(string seed)
        {
            string terrainJson = GenerateTerrain(seed, 8, 8);
            // 简化一致性：实际应由统一 hash 器（与服务端 wp_server 一致）
            return terrainJson.GetHashCode().ToString("X");
        }
    }
}
