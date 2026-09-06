// UnityAdapter.cs - Unity (P/Invoke / Native Plugin) 引擎适配器
// 对齐 Issue #90 wp_engine：Unity 团结引擎经 P/Invoke + Native Plugin 调用 C++ 核心。
// M-C 扩展（Issue #135）：增强跳云 + 并行下载 + 完整地图（terrain/level/resources/props/narrative）
//
// 职责：
//   1. 将 Unity 渲染/物理接入 middleware C ABI
//   2. C# 侧经 P/Invoke 调用 C++（libgame_middleware_abi），与 Web/Cocos/UE 同核心
//   3. 保证 Unity 完整地图版本与其他端输出一致（同 seed 同 hash）
//   4. 消费 M-A 协议（Enhancement/CloudSession/DownloadStatus）做 Unity 端漏斗链路
using System;
using System.Runtime.InteropServices;
using System.Text;
using System.Security.Cryptography;

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

        // M-C 扩展：完整地图各子模块 P/Invoke（对齐 cabi_procgen.h）
        [DllImport("game_middleware_abi")]
        private static extern int cabi_procgen_level(
            [MarshalAs(UnmanagedType.LPStr)] string seed,
            [MarshalAs(UnmanagedType.LPStr)] string levelParams,
            out IntPtr outJson);

        [DllImport("game_middleware_abi")]
        private static extern int cabi_procgen_resources(
            [MarshalAs(UnmanagedType.LPStr)] string seed,
            [MarshalAs(UnmanagedType.LPStr)] string terrainData,
            [MarshalAs(UnmanagedType.LPStr)] string rulesJson,
            out IntPtr outJson);

        [DllImport("game_middleware_abi")]
        private static extern int cabi_procgen_props(
            [MarshalAs(UnmanagedType.LPStr)] string seed,
            [MarshalAs(UnmanagedType.LPStr)] string paramsJson,
            out IntPtr outJson);

        [DllImport("game_middleware_abi")]
        private static extern int cabi_procgen_narrative(
            [MarshalAs(UnmanagedType.LPStr)] string seed,
            [MarshalAs(UnmanagedType.LPStr)] string narrativeSchema,
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

        /// <summary>
        /// M-C · 生成关卡（确定性，与 C++ 核心一致）。
        /// </summary>
        public string GenerateLevel(string seed, string levelParams = "{}")
        {
            IntPtr outPtr;
            int rc = cabi_procgen_level(seed, levelParams, out outPtr);
            if (rc != 0)
                throw new Exception($"UnityAdapter: level generation failed rc={rc}");
            return Marshal.PtrToStringAnsi(outPtr);
        }

        /// <summary>
        /// M-C · 生成资源分布（确定性）。
        /// </summary>
        public string GenerateResources(string seed, string terrainData = "{}",
                                         string rulesJson = "{}")
        {
            IntPtr outPtr;
            int rc = cabi_procgen_resources(seed, terrainData, rulesJson, out outPtr);
            if (rc != 0)
                throw new Exception($"UnityAdapter: resources generation failed rc={rc}");
            return Marshal.PtrToStringAnsi(outPtr);
        }

        /// <summary>
        /// M-C · 生成装饰物/建筑（确定性）。
        /// </summary>
        public string GenerateProps(string seed, string paramsJson = "{}")
        {
            IntPtr outPtr;
            int rc = cabi_procgen_props(seed, paramsJson, out outPtr);
            if (rc != 0)
                throw new Exception($"UnityAdapter: props generation failed rc={rc}");
            return Marshal.PtrToStringAnsi(outPtr);
        }

        /// <summary>
        /// M-C · 生成叙事（任务+对话，确定性）。
        /// </summary>
        public string GenerateNarrative(string seed, string narrativeSchema = "{}")
        {
            IntPtr outPtr;
            int rc = cabi_procgen_narrative(seed, narrativeSchema, out outPtr);
            if (rc != 0)
                throw new Exception($"UnityAdapter: narrative generation failed rc={rc}");
            return Marshal.PtrToStringAnsi(outPtr);
        }

        /// <summary>
        /// M-C · 完整世界内容 JSON 聚合（Unity 端调用）。
        /// 各子模块均经 C++ ABI 确定性生成 → 拼接后可与 Python/TS 侧对比。
        /// </summary>
        public string GenerateFullWorld(string seed)
        {
            var sb = new StringBuilder();
            sb.Append("{\"terrain\":");
            sb.Append(GenerateTerrain(seed, 64, 64));
            sb.Append(",\"level\":");
            sb.Append(GenerateLevel(seed));
            sb.Append(",\"resources\":");
            sb.Append(GenerateResources(seed));
            sb.Append(",\"props\":");
            sb.Append(GenerateProps(seed));
            sb.Append(",\"narrative\":");
            sb.Append(GenerateNarrative(seed));
            sb.Append("}");
            return sb.ToString();
        }

        /// <summary>
        /// 跨引擎一致性校验（golden hash）。
        /// 统一 SHA-256：与 TS hashJson / Python hash_json 输出一致。
        /// 输入：JSON 序列化字符串（UTF-8）。
        /// </summary>
        public string WorldHash(string seed)
        {
            string fullWorld = GenerateFullWorld(seed);
            return Sha256Hex(fullWorld);
        }

        /// <summary>SHA-256 十六进制小写输出（与 TS/Python 统一）。</summary>
        private static string Sha256Hex(string input)
        {
            byte[] bytes = Encoding.UTF8.GetBytes(input);
            using (var sha = SHA256.Create())
            {
                byte[] digest = sha.ComputeHash(bytes);
                var sb = new StringBuilder(digest.Length * 2);
                foreach (byte b in digest)
                    sb.Append(b.ToString("x2"));
                return sb.ToString();
            }
        }
    }
}
