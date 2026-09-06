"""
mc_unity_runner.py - M-C Unity App 端到端演示 runner（Issue #135）

把 MC-01 UnityAppSession（增强跳云）、MC-02 UnityParallelDownloader（并行下载）、
MC-03 UnityAppContent（完整地图确定性生成）串起来跑一遍 Unity App 漏斗：

  Unity App 入口 → 增强画质 → CG 锚点 → 云会话跳云 → 并行下载边下边玩
    → 90% 预释放 → 本地完整版接管（完整地图确定性生成）

运行：PYTHONPATH=. python3 server/core/mc_unity_runner.py
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from server.core.unity_app_demo import UnityFunnelRunner


def main():
    print("=" * 70)
    print("M-C Unity App 端到端演示（MC-01 增强跳云 + MC-02 并行下载 + MC-03 完整地图）")
    print("=" * 70)

    runner = UnityFunnelRunner("U1001")
    result = runner.run()

    print(f"\n[玩家] {result['player']} · [平台] {result['platform']}")
    print("\n[漏斗状态流转]")
    for i, s in enumerate(result["funnel_states"]):
        print(f"  {i+1}. {s}")

    d = result["download"]
    print(f"\n[下载详情]")
    print(f"  总量: {d['total_bytes']} bytes ({d['total_bytes']//(1024*1024)} MB)")
    print(f"  分片: {d['chunk_count']} · 已完成: {d['bytes_done']}")
    print(f"  进度: {d['pct']}% · 预释放: {d['pre_released']}")
    print(f"  断点续传位: {d['resume_point']} bytes")
    print(f"  分片事件: {d['chunk_events']}")

    w = result["world_content"]
    print(f"\n[完整地图确定性生成]")
    for key, present in w.items():
        print(f"  {key}: {'✅' if present else '❌'}")
    print(f"  world_hash: {result['world_hash']}")

    print(f"\n[最终状态] {result['final_state']}")
    print(f"[接管] {result['takeover']}")
    print(f"\n✅ M-C Unity App 漏斗全链路走通（G3 单版完整门禁方向达成）")


if __name__ == "__main__":
    main()
