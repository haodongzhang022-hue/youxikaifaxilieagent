"""
test_mc_unity_app.py - M-C Unity App 测试 (Issue #135)

门禁 G3「单版完整门禁」回归：
  MC-01 UnityAppSession：增强入口跳云（Enhancement/CloudSession 协议消费）
  MC-02 UnityParallelDownloader：分片并行下载/断点续传/带宽调度/90% 预释放
  MC-03 UnityAppContent：完整地图确定性生成（terrain/level/resources/props/narrative）
  端到端：Unity App 完整漏斗走通至 LOCAL_FULL

里程碑：M-C（Unity App 内容落地）· WP-04 门禁 G3
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from server.core.unity_app_demo import (
    UnityAppSession, UnityParallelDownloader, UnityAppContent, UnityFunnelRunner,
)
from server.proto.messages import (
    serialize, deserialize,
    PlayState,
    CloudSessionApply, CloudSessionPrewarm, CloudSessionHeartbeat, CloudSessionRelease,
    DownloadStatusReport, DownloadChunkComplete,
    EnhancementRequest, EnhancementType,
    PLAY_STATE_LOCAL_LITE, PLAY_STATE_CG_ANCHOR,
    PLAY_STATE_CLOUD_PLAY, PLAY_STATE_LOCAL_FULL,
)


# ============================================================
# MC-01: Unity 增强入口会话
# ============================================================
class TestUnityAppSession(unittest.TestCase):
    """MC-01 · Unity App 增强入口跳云"""

    def test_enter_sets_local_lite(self):
        s = UnityAppSession("U1", platform="unity")
        s.enter_unity_app()
        self.assertEqual(s.state, PLAY_STATE_LOCAL_LITE)
        self.assertEqual(s.state_str(), "LOCAL_LITE")

    def test_click_enhance_transitions_to_cg(self):
        s = UnityAppSession("U1")
        s.enter_unity_app()
        req = s.click_enhance()
        self.assertIsInstance(req, EnhancementRequest)
        self.assertEqual(req.request_type, EnhancementType.CG_PLAY)
        self.assertEqual(s.state, PLAY_STATE_CG_ANCHOR)
        self.assertEqual(s.log, ["click_enhance"])

    def test_cg_play_and_prewarm(self):
        s = UnityAppSession("U1")
        s.enter_unity_app()
        s.click_enhance()
        self.assertEqual(s.play_unity_cg(), "cg_anchor_playing_unity")
        prewarm = s.prewarm_cloud(expected_duration=30)
        self.assertIsInstance(prewarm, CloudSessionPrewarm)
        self.assertEqual(prewarm.expected_duration, 30)
        self.assertEqual(s.prewarm_count, 1)

    def test_jump_cloud_transitions_to_cloud_play(self):
        s = UnityAppSession("U1")
        s.enter_unity_app()
        s.click_enhance()
        s.play_unity_cg()
        apply = s.jump_to_cloud()
        self.assertIsInstance(apply, CloudSessionApply)
        self.assertTrue(s.cloud_active)
        self.assertEqual(s.state, PLAY_STATE_CLOUD_PLAY)
        self.assertEqual(apply.bandwidth_budget, 65)  # 云激活默认档

    def test_heartbeat_requires_active_cloud(self):
        s = UnityAppSession("U1")
        s.enter_unity_app()
        with self.assertRaises(RuntimeError):
            s.heartbeat()

    def test_heartbeat_after_jump(self):
        s = UnityAppSession("U1")
        s.enter_unity_app()
        s.click_enhance()
        s.play_unity_cg()
        s.jump_to_cloud()
        hb = s.heartbeat()
        self.assertIsInstance(hb, CloudSessionHeartbeat)
        self.assertEqual(hb.sequence, 1)
        self.assertEqual(s.heartbeat_count, 1)

    def test_release_cloud_requires_active(self):
        s = UnityAppSession("U1")
        s.enter_unity_app()
        with self.assertRaises(RuntimeError):
            s.release_cloud()

    def test_release_after_jump(self):
        s = UnityAppSession("U1")
        s.enter_unity_app()
        s.click_enhance()
        s.play_unity_cg()
        s.jump_to_cloud()
        rel = s.release_cloud(target_state=PLAY_STATE_LOCAL_FULL)
        self.assertIsInstance(rel, CloudSessionRelease)
        self.assertFalse(s.cloud_active)
        self.assertTrue(s.released)

    def test_illegal_transition_guard(self):
        """护栏：LOCAL_LITE 不能直达 CLOUD_PLAY（必须先 CG）"""
        s = UnityAppSession("U1")
        s.enter_unity_app()
        # 尝试直接跳云应被拒
        with self.assertRaises(RuntimeError):
            s.jump_to_cloud()
        self.assertEqual(s.state, PLAY_STATE_LOCAL_LITE)

    def test_illegal_cg_play_guard(self):
        """护栏：CG 需在 CG_ANCHOR 态播放"""
        s = UnityAppSession("U1")
        s.enter_unity_app()
        with self.assertRaises(RuntimeError):
            s.play_unity_cg()


# ============================================================
# MC-02: Unity 并行下载管理器
# ============================================================
class TestUnityParallelDownloader(unittest.TestCase):
    """MC-02 · Unity 并行下载"""

    def setUp(self):
        # 100MB 总量, 10MB 分片 → 10 chunks
        self.dl = UnityParallelDownloader("U1", total_bytes=100 * 1024 * 1024,
                                          chunk_size=10 * 1024 * 1024)
        self.assertEqual(self.dl.num_chunks, 10)

    def test_initial_state(self):
        self.assertEqual(self.dl.bytes_done, 0)
        self.assertEqual(self.dl.pct, 0.0)
        self.assertFalse(self.dl.is_complete())
        self.assertEqual(self.dl.resume_point(), 0)

    def test_parallel_step_downloads_two_chunks(self):
        events = self.dl.parallel_step(parallel_count=2)
        self.assertEqual(len(events), 2)
        self.assertEqual(self.dl.bytes_done, 20 * 1024 * 1024)
        self.assertEqual(self.dl.pct, 20.0)

    def test_parallel_step_respects_limit(self):
        events = self.dl.parallel_step(parallel_count=3)
        self.assertEqual(len(events), 3)
        self.assertEqual(self.dl.bytes_done, 30 * 1024 * 1024)

    def test_complete_all_downloads(self):
        events = self.dl.complete_all()
        self.assertTrue(self.dl.is_complete())
        self.assertEqual(self.dl.pct, 100.0)
        self.assertEqual(self.dl.bytes_done, self.dl.total_bytes)
        self.assertGreaterEqual(len(events), self.dl.num_chunks)

    def test_download_report_serialization(self):
        events = self.dl.parallel_step(parallel_count=1)
        self.assertEqual(len(events), 1)
        report = events[0]["report"]
        self.assertIsInstance(report, DownloadStatusReport)
        restored = deserialize(serialize(report), DownloadStatusReport)
        self.assertEqual(restored.player_id, "U1")
        self.assertEqual(restored.bytes_done, 10 * 1024 * 1024)
        self.assertEqual(restored.bytes_total, 100 * 1024 * 1024)

    def test_chunk_complete_serialization(self):
        events = self.dl.parallel_step(parallel_count=1)
        chunk = events[0]["chunk"]
        self.assertIsInstance(chunk, DownloadChunkComplete)
        restored = deserialize(serialize(chunk), DownloadChunkComplete)
        self.assertEqual(restored.player_id, "U1")
        self.assertEqual(restored.bytes_done, 10 * 1024 * 1024)

    def test_bandwidth_budget_cloud_active(self):
        """云激活时下载档位应受限"""
        self.dl.set_cloud_active(True)
        events = self.dl.parallel_step(parallel_count=1)
        budget = events[0]["budget"]
        self.assertLess(budget["download_budget_ratio"], 100)
        self.assertGreater(budget["cloud_budget_ratio"], 0)

    def test_bandwidth_budget_cloud_inactive(self):
        """云未激活时下载全速"""
        events = self.dl.parallel_step(parallel_count=1)
        budget = events[0]["budget"]
        self.assertEqual(budget["download_budget_ratio"], 100)

    def test_pre_release_at_90_percent(self):
        """90% 时触发预释放信号"""
        events = []
        guard = 0
        while not self.dl.is_complete() and guard < 20:
            batch = self.dl.parallel_step(parallel_count=2)
            events.extend(batch)
            guard += 1
        # 找到含预释放信号的事件（90% 及以上触发）
        pre_release_events = [e for e in events if e["pre_release"]]
        self.assertTrue(any(e["pre_release"] for e in events),
                        "下载达 90%+ 应触发预释放信号")

    def test_resume_point_after_partial_download(self):
        self.dl.parallel_step(parallel_count=2)
        rp = self.dl.resume_point()
        self.assertEqual(rp, 2 * self.dl.chunk_size)

    def test_bandwidth_preferences(self):
        """不同用户偏好下带宽调度档位不同"""
        from server.core.bandwidth_scheduler import PREF_QUALITY, PREF_DOWNLOAD

        # 画质优先: 云激活时下载限速更低
        dl_quality = UnityParallelDownloader(
            "U_Q", total_bytes=100 * 1024 * 1024, chunk_size=10 * 1024 * 1024,
            prefer=PREF_QUALITY)
        dl_quality.set_cloud_active(True)
        events = dl_quality.parallel_step(parallel_count=1)
        budget_q = events[0]["budget"]
        self.assertLessEqual(budget_q["download_budget_ratio"], 50)

        # 下载优先: 云激活时下载档位更高
        dl_dl = UnityParallelDownloader(
            "U_D", total_bytes=100 * 1024 * 1024, chunk_size=10 * 1024 * 1024,
            prefer=PREF_DOWNLOAD)
        dl_dl.set_cloud_active(True)
        events = dl_dl.parallel_step(parallel_count=1)
        budget_d = events[0]["budget"]
        self.assertGreaterEqual(budget_d["download_budget_ratio"], 80)




# ============================================================
# MC-03: Unity 完整地图确定性生成
# ============================================================
class TestUnityAppContent(unittest.TestCase):
    """MC-03 · Unity 完整地图 + 玩法"""

    def test_generate_full_world(self):
        content_gen = UnityAppContent("unity_seed_test")
        world = content_gen.generate_full_world()
        self.assertIn("terrain", world)
        self.assertIn("level", world)
        self.assertIn("resources", world)
        self.assertIn("props", world)
        self.assertIn("narrative", world)

    def test_terrain_deterministic(self):
        """同 seed → 同 hash"""
        c1 = UnityAppContent("seed_abc")
        c1.generate_full_world()
        c2 = UnityAppContent("seed_abc")
        c2.generate_full_world()
        self.assertEqual(c1.get_hash(), c2.get_hash())

    def test_different_seed_different_hash(self):
        c1 = UnityAppContent("seed_one")
        c1.generate_full_world()
        c2 = UnityAppContent("seed_two")
        c2.generate_full_world()
        self.assertNotEqual(c1.get_hash(), c2.get_hash())

    def test_content_has_narrative(self):
        content_gen = UnityAppContent("unity_seed_narr")
        world = content_gen.generate_full_world()
        narr = world["narrative"]
        self.assertIn("quests", narr)
        self.assertGreaterEqual(len(narr["quests"]), 1)

    def test_verify_consistency(self):
        """跨引擎一致性校验"""
        ok = UnityAppContent.verify_consistency("test_consistency_seed")
        self.assertTrue(ok)

    def test_content_hash_has_expected_format(self):
        content_gen = UnityAppContent("format_seed")
        content_gen.generate_full_world()
        h = content_gen.get_hash()
        # SHA-256 长度 64
        self.assertEqual(len(h), 64)
        # 十六进制
        int(h, 16)


# ============================================================
# 端到端: Unity App 完整漏斗
# ============================================================
class TestUnityFunnelRunner(unittest.TestCase):
    """Unity App 端到端完整漏斗"""

    def test_full_funnel(self):
        runner = UnityFunnelRunner("U_END_TO_END")
        result = runner.run()
        self.assertEqual(result["final_state"], "LOCAL_FULL")
        self.assertEqual(result["platform"], "unity")
        self.assertEqual(result["download"]["pct"], 100.0)
        self.assertTrue(result["download"]["pre_released"])
        self.assertGreater(result["download"]["chunk_events"], 0)
        # 世界内容全部生成
        for key, present in result["world_content"].items():
            self.assertTrue(present, f"{key} 应被生成")
        self.assertTrue(result["world_hash"])

    def test_runner_reuse(self):
        """多次运行不互相干扰"""
        r1 = UnityFunnelRunner("U_REUSE")
        r2 = UnityFunnelRunner("U_REUSE_2")
        res1 = r1.run()
        res2 = r2.run()
        self.assertEqual(res1["final_state"], "LOCAL_FULL")
        self.assertEqual(res2["final_state"], "LOCAL_FULL")


if __name__ == "__main__":
    unittest.main()
