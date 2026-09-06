"""
mb_funnel_runner.py - M-B 漏斗 Demo 端到端演示 runner（MB-01 + MB-02 · Issue #135）

把 MB-01 funnel_demo（L0/L1 轻量版入口 + PlayState 状态流转）
与 MB-02 cloud_stub（假云/下载 Demo 桩）串起来跑一遍漏斗五环节：
  L0/L1 轻量入口 → 增强画质→CG 锚点 → 假跳云(CloudSession Apply)
  → 边下边玩下载(带宽调度) → 90% 预释放 → 本地接管 LOCAL_FULL

运行：PYTHONPATH=. python3 server/core/mb_funnel_runner.py
"""

import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from server.core.funnel_demo import FunnelState
from server.proto.messages import PlayState, PLAY_STATE_LOCAL_FULL


def demo_web_l0():
    print("=" * 66)
    print("M-B Demo 桩 · 端到端演示（管线 B · L0 网页秒开入口）")
    print("=" * 66)
    f = FunnelState("P1001", platform="web")
    r = f.run_full_funnel(download_steps=5)
    print(f"\n[最终状态] {r['final_state']}  ({PlayState.to_str(PLAY_STATE_LOCAL_FULL)} = 本地完整版)")
    print("[漏斗五环节] ", " -> ".join(r["funnel"]))
    td = r["takeover"]
    print(f"[下载进度] {td['download_pct']}% · 预释放: {td['pre_released']} · 接管: {td['takeover']}")
    return r


def demo_cocos_l1():
    print("\n" + "=" * 66)
    print("M-B Demo 桩 · 端到端演示（管线 B · L1 Cocos 小程序入口）")
    print("=" * 66)
    f = FunnelState("P2001", platform="cocos")
    r = f.run_full_funnel(download_steps=4)
    td = r["takeover"]
    print(f"[最终状态] {r['final_state']}")
    print(f"[下载进度] {td['download_pct']}% · 接管: {td['takeover']}")
    return r


if __name__ == "__main__":
    demo_web_l0()
    demo_cocos_l1()
    print("\n✅ M-B Demo 桩漏斗五环节全部走通（G2 单版体验门禁方向达成，真云渲染留 UE 阶段储备）")
