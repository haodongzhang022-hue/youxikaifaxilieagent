"""
test_mb_funnel_demo.py - M-B 漏斗 Demo 桩测试 (Issue #135)

门禁 G2「单版体验门禁」Demo 桩回归方向：
  1. MB-01 funnel_demo：L0/L1 轻量版入口 + PlayState 状态流转（含非法流转护栏）
  2. MB-02 cloud_stub：假云/下载 Demo 桩（消费 CloudSession/DownloadStatus/Enhancement）
  3. 端到端漏斗五环节走通（L0 web / L1 cocos）+ 带宽调度 + 90% 预释放 + 本地接管

里程碑：M-B（L0/L1 + CG 锚点 + 跳云 Demo 桩）· WP-04 门禁 G2
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from server.core.funnel_demo import FunnelState
from server.core.cloud_stub import CloudStub, DEFAULT_DOWNLOAD_TOTAL
from server.core.bandwidth_scheduler import schedule_download_budget, PREF_DEFAULT
from server.proto.messages import (
    serialize, deserialize,
    PlayState, EnhancementRequest, EnhancementType,
    CloudSessionApply, CloudSessionPrewarm, CloudSessionHeartbeat, CloudSessionRelease,
    DownloadStatusReport, DownloadChunkComplete,
    PLAY_STATE_LOCAL_LITE, PLAY_STATE_CG_ANCHOR,
    PLAY_STATE_CLOUD_PLAY, PLAY_STATE_LOCAL_FULL,
)


class TestFunnelDemoStateMachine(unittest.TestCase):
    """MB-01 · L0/L1 漏斗引擎 PlayState 状态流转"""

    def test_enter_lite_sets_local_lite(self):
        f = FunnelState("P1", platform="web")
        f.enter_lite()
        self.assertEqual(f.state, PLAY_STATE_LOCAL_LITE)
        self.assertEqual(f.current(), "LOCAL_LITE")

    def test_request_enhance_transitions_to_cg(self):
        f = FunnelState("P1")
        f.enter_lite()
        req = f.request_enhance()
        self.assertIsInstance(req, EnhancementRequest)
        self.assertEqual(req.request_type, EnhancementType.CG_PLAY)
        self.assertEqual(f.state, PLAY_STATE_CG_ANCHOR)

    def test_cg_play_then_jump_cloud(self):
        f = FunnelState("P1", platform="web")
        f.enter_lite()
        f.request_enhance()
        self.assertEqual(f.play_cg(), "cg_anchor_playing")
        jump = f.jump_cloud()
        self.assertEqual(f.state, PLAY_STATE_CLOUD_PLAY)
        self.assertIsInstance(jump["apply"], CloudSessionApply)
        self.assertTrue(f.cloud.cloud_active)

    def test_illegal_transition_guard(self):
        """护栏：从 LOCAL_LITE 不能直达 LOCAL_FULL / CLOUD_PLAY"""
        f = FunnelState("P1")
        f.enter_lite()
        # 绕过 CG 直接想跳云应被拒（非法流转）
        f.state = PLAY_STATE_LOCAL_LITE
        f.cloud = CloudStub("P1")
        with self.assertRaises(RuntimeError):
            f.jump_cloud()
        self.assertEqual(f.state, PLAY_STATE_LOCAL_LITE)

    def test_full_funnel_local_takeover(self):
        f = FunnelState("P1001", platform="web")
        r = f.run_full_funnel(download_steps=5)
        self.assertEqual(r["final_state"], "LOCAL_FULL")
        self.assertEqual(r["takeover"]["download_pct"], 100.0)
        self.assertEqual(f.takeover_log, ["local_takeover_ok"])
        self.assertIn("L0/L1_轻量入口", r["funnel"])


class TestCloudStub(unittest.TestCase):
    """MB-02 · 假云/下载 Demo 桩"""

    def test_apply_activates_cloud(self):
        stub = CloudStub("P2")
        apply_msg = stub.apply(from_state=PLAY_STATE_LOCAL_LITE)
        self.assertTrue(stub.cloud_active)
        self.assertIsInstance(apply_msg, CloudSessionApply)
        # 云激活后带宽预算应受调度限速（下载非全速）
        self.assertLess(apply_msg.bandwidth_budget, 100)

    def test_prewarm_heartbeat_release_flow(self):
        stub = CloudStub("P2")
        pw = stub.prewarm()
        self.assertIsInstance(pw, CloudSessionPrewarm)
        ap = stub.apply()
        self.assertTrue(stub.cloud_active)
        hb = stub.heartbeat()
        self.assertIsInstance(hb, CloudSessionHeartbeat)
        rel = stub.release(target_state=PLAY_STATE_LOCAL_FULL)
        self.assertIsInstance(rel, CloudSessionRelease)
        self.assertFalse(stub.cloud_active)
        self.assertTrue(stub.released)

    def test_heartbeat_requires_active(self):
        stub = CloudStub("P2")
        with self.assertRaises(RuntimeError):
            stub.heartbeat()

    def test_download_step_respects_bandwidth_scheduler(self):
        stub = CloudStub("P2")
        stub.apply()
        r = stub.download_step(step_mb=30)
        report = r["report"]
        self.assertIsInstance(report, DownloadStatusReport)
        self.assertIsInstance(r["chunk"], DownloadChunkComplete)
        # 云激活时下载限速档位应 < 100
        self.assertLess(report.bandwidth_budget, 100)

    def test_download_complete_and_pre_release(self):
        stub = CloudStub("P2")
        stub.apply()
        # 一次下满 -> 达 100% -> 触发 90% 预释放
        r = stub.download_step(step_mb=DEFAULT_DOWNLOAD_TOTAL)
        self.assertTrue(stub.is_download_complete())
        self.assertEqual(r["pct"], 100.0)
        self.assertTrue(r["pre_release"])

    def test_serialized_report_roundtrip(self):
        stub = CloudStub("P2")
        stub.apply()
        blob = stub.serialized_report()
        restored = deserialize(blob, DownloadStatusReport)
        self.assertEqual(restored.download_id, stub.download_id)


class TestEndToEndFunnel(unittest.TestCase):
    """端到端漏斗五环节走通（L0 web / L1 cocos）+ 带宽调度一致"""

    def test_e2e_web_l0(self):
        f = FunnelState("L0PLAYER", platform="web")
        r = f.run_full_funnel(download_steps=5)
        self.assertEqual(r["platform"], "web")
        self.assertEqual(r["final_state"], "LOCAL_FULL")
        self.assertEqual(len(r["funnel"]), 5)
        self.assertTrue(r["takeover"]["pre_released"])

    def test_e2e_cocos_l1(self):
        f = FunnelState("L1PLAYER", platform="cocos")
        r = f.run_full_funnel(download_steps=4)
        self.assertEqual(r["platform"], "cocos")
        self.assertEqual(r["final_state"], "LOCAL_FULL")

    def test_bandwidth_no_double_loss(self):
        """云激活时下载被调度限速，保证云/下载不双输"""
        budget = schedule_download_budget(is_cloud_active=True,
                                          download_pct=50.0, user_pref=PREF_DEFAULT)
        self.assertGreater(budget["cloud_budget_ratio"], 0)
        self.assertLess(budget["download_budget_ratio"], 100)
        # 云关闭 -> 全速下载
        idle = schedule_download_budget(is_cloud_active=False, download_pct=50.0)
        self.assertEqual(idle["download_budget_ratio"], 100)


if __name__ == "__main__":
    unittest.main(verbosity=2)
