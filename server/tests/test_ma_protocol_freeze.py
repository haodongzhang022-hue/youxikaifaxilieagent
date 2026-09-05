"""
test_ma_protocol_freeze.py - M-A 协议冻结一致性测试 (Issue #135)

门禁 G1「协议一致门禁」回归：
  1. 4 组协议消息 dataclass 序列化/反序列化一致（to_dict -> from_dict）
  2. 字段兼容（必填字段缺失抛错 / 新增 optional 字段不破坏旧数据）
  3. PlayState 三态状态机流转合法性
  4. 带宽感知调度器 4 分支 + 边界情况

里程碑：M-A（协议冻结）· WP-02 §3.1 · WP-04 门禁 G1
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from server.proto.messages import (
    serialize, deserialize,
    PlayState, TimeoutPolicy, EnhancementType,
    SaveSyncPush, SaveSyncPull,
    CloudSessionApply, CloudSessionPrewarm, CloudSessionHeartbeat, CloudSessionRelease,
    DownloadStatusReport, DownloadChunkComplete,
    EnhancementRequest,
    PLAY_STATE_LOCAL_LITE, PLAY_STATE_CG_ANCHOR,
    PLAY_STATE_CLOUD_PLAY, PLAY_STATE_LOCAL_FULL,
)
from server.core.bandwidth_scheduler import (
    schedule_download_budget,
    PREF_DEFAULT, PREF_QUALITY, PREF_DOWNLOAD,
    PRE_RELEASE_THRESHOLD,
)


class TestProtocolSerialization(unittest.TestCase):
    """M-A 协议消息序列化一致性"""

    def test_savesync_push_roundtrip(self):
        msg = SaveSyncPush.create("P1", "chapter3_checkpoint", platform="cocos", data_version=2)
        restored = deserialize(serialize(msg), SaveSyncPush)
        self.assertEqual(restored.player_id, "P1")
        self.assertEqual(restored.progress_checkpoint, "chapter3_checkpoint")
        self.assertEqual(restored.platform, "cocos")
        self.assertEqual(restored.data_version, 2)

    def test_savesync_pull_roundtrip(self):
        msg = SaveSyncPull.create("P1", "chapter3_checkpoint", platform="ue")
        restored = deserialize(serialize(msg), SaveSyncPull)
        self.assertEqual(restored.progress_checkpoint, "chapter3_checkpoint")
        self.assertEqual(restored.platform, "ue")

    def test_cloud_session_family_roundtrip(self):
        apply = CloudSessionApply.create("P1", from_state=PLAY_STATE_LOCAL_LITE,
                                         bandwidth_budget=30)
        r = deserialize(serialize(apply), CloudSessionApply)
        self.assertEqual(r.from_state, PLAY_STATE_LOCAL_LITE)
        self.assertEqual(r.bandwidth_budget, 30)
        self.assertTrue(r.session_id)

        prewarm = CloudSessionPrewarm.create("P1", play_stage="cg_intro", expected_duration=15)
        r = deserialize(serialize(prewarm), CloudSessionPrewarm)
        self.assertEqual(r.play_stage, "cg_intro")
        self.assertEqual(r.expected_duration, 15)

        hb = CloudSessionHeartbeat.create("P1", session_id="s1", sequence=3)
        r = deserialize(serialize(hb), CloudSessionHeartbeat)
        self.assertEqual(r.session_id, "s1")
        self.assertEqual(r.sequence, 3)

        rel = CloudSessionRelease.create("P1", session_id="s1",
                                         timeout_policy=TimeoutPolicy.PRE_RELEASE,
                                         target_state=PLAY_STATE_LOCAL_FULL)
        r = deserialize(serialize(rel), CloudSessionRelease)
        self.assertEqual(r.timeout_policy, TimeoutPolicy.PRE_RELEASE)
        self.assertEqual(r.target_state, PLAY_STATE_LOCAL_FULL)

    def test_download_status_roundtrip(self):
        report = DownloadStatusReport.create("P1", bytes_done=800, bytes_total=1000,
                                             resume_point=80, bandwidth_budget=65)
        r = deserialize(serialize(report), DownloadStatusReport)
        self.assertEqual(r.bytes_done, 800)
        self.assertEqual(r.resume_point, 80)
        self.assertEqual(r.bandwidth_budget, 65)

        chunk = DownloadChunkComplete.create("P1", chunk_index=5, bytes_done=512,
                                             pre_release_signal=True)
        r = deserialize(serialize(chunk), DownloadChunkComplete)
        self.assertEqual(r.chunk_index, 5)
        self.assertTrue(r.pre_release_signal)

    def test_enhancement_roundtrip(self):
        req = EnhancementRequest.create("P1",
                                        from_state=PLAY_STATE_LOCAL_LITE,
                                        target_stage=PLAY_STATE_CLOUD_PLAY,
                                        request_type=EnhancementType.CLOUD_UPGRADE)
        r = deserialize(serialize(req), EnhancementRequest)
        self.assertEqual(r.from_state, PLAY_STATE_LOCAL_LITE)
        self.assertEqual(r.target_stage, PLAY_STATE_CLOUD_PLAY)
        self.assertEqual(r.request_type, EnhancementType.CLOUD_UPGRADE)


class TestFieldCompatibility(unittest.TestCase):
    """字段兼容门禁：新增 optional 字段不破坏旧数据"""

    def test_defaults_for_missing_optional_fields(self):
        """缺少新增字段时应回退默认值，不抛错（向后兼容）"""
        # 构造只含必填 player_id 的旧式 payload
        payload = '{"player_id": "P_OLD"}'
        restored = deserialize(payload, SaveSyncPush)
        self.assertEqual(restored.progress_checkpoint, "")
        self.assertEqual(restored.platform, "web")
        self.assertEqual(restored.data_version, 1)

    def test_missing_required_field_raises(self):
        """缺少必填字段 player_id 应抛 KeyError"""
        payload = '{"progress_checkpoint": "cp"}'
        with self.assertRaises(KeyError):
            deserialize(payload, SaveSyncPush)


class TestPlayStateMachine(unittest.TestCase):
    """PlayState 三态状态机流转合法性"""

    def test_valid_transitions(self):
        self.assertTrue(PlayState.can_transition(PLAY_STATE_LOCAL_LITE, PLAY_STATE_CG_ANCHOR))
        self.assertTrue(PlayState.can_transition(PLAY_STATE_CG_ANCHOR, PLAY_STATE_CLOUD_PLAY))
        self.assertTrue(PlayState.can_transition(PLAY_STATE_CG_ANCHOR, PLAY_STATE_LOCAL_FULL))
        self.assertTrue(PlayState.can_transition(PLAY_STATE_CLOUD_PLAY, PLAY_STATE_LOCAL_FULL))
        self.assertTrue(PlayState.can_transition(PLAY_STATE_CLOUD_PLAY, PLAY_STATE_LOCAL_LITE))  # 断网回退

    def test_invalid_transitions(self):
        # 不允许跳步/逆向
        self.assertFalse(PlayState.can_transition(PLAY_STATE_LOCAL_LITE, PLAY_STATE_CLOUD_PLAY))
        self.assertFalse(PlayState.can_transition(PLAY_STATE_LOCAL_FULL, PLAY_STATE_LOCAL_LITE))
        self.assertFalse(PlayState.can_transition(PLAY_STATE_LOCAL_FULL, PLAY_STATE_CG_ANCHOR))

    def test_full_path(self):
        """完整漏斗路径 LOCAL_LITE->CG->CLOUD->LOCAL_FULL 全部合法"""
        path = [PLAY_STATE_LOCAL_LITE, PLAY_STATE_CG_ANCHOR,
                PLAY_STATE_CLOUD_PLAY, PLAY_STATE_LOCAL_FULL]
        for src, dst in zip(path, path[1:]):
            self.assertTrue(PlayState.can_transition(src, dst),
                            f"expected {PlayState.to_str(src)}->{PlayState.to_str(dst)}")


class TestBandwidthScheduler(unittest.TestCase):
    """带宽感知调度器 4 分支 + 边界（WP-02 §3.1）"""

    def test_cloud_active_default_limits_60_70(self):
        """云激活 + 默认偏好 -> 60-70% 档位"""
        r = schedule_download_budget(True, 50.0, PREF_DEFAULT)
        self.assertGreaterEqual(r["download_budget_ratio"], 60)
        self.assertLessEqual(r["download_budget_ratio"], 70)

    def test_cloud_active_quality_limits_40_50(self):
        """云激活 + 画质优先 -> 40-50% 档位"""
        r = schedule_download_budget(True, 50.0, PREF_QUALITY)
        self.assertGreaterEqual(r["download_budget_ratio"], 40)
        self.assertLessEqual(r["download_budget_ratio"], 50)

    def test_cloud_active_download_ratio_80(self):
        """云激活 + 下载优先 -> 80% 档位"""
        r = schedule_download_budget(True, 50.0, PREF_DOWNLOAD)
        self.assertEqual(r["download_budget_ratio"], 80)

    def test_cloud_inactive_full_speed(self):
        """云关闭 -> 全速 100%"""
        r = schedule_download_budget(False, 50.0, PREF_DEFAULT)
        self.assertEqual(r["download_budget_ratio"], 100)

    def test_pre_release_signal_at_90(self):
        """下载达 90%+ 触发预释放信号"""
        r = schedule_download_budget(True, PRE_RELEASE_THRESHOLD, PREF_DEFAULT)
        self.assertTrue(r["pre_release_signal"])
        r = schedule_download_budget(False, 95.0, PREF_DOWNLOAD)
        self.assertTrue(r["pre_release_signal"])

    def test_no_pre_release_below_threshold(self):
        """下载未达 90% 不触发预释放"""
        r = schedule_download_budget(True, 89.0, PREF_DEFAULT)
        self.assertFalse(r["pre_release_signal"])

    def test_boundary_pct_clamped(self):
        """进度超界/负值被夹取到 0-100"""
        r = schedule_download_budget(False, 150.0, PREF_DOWNLOAD)
        self.assertEqual(r["download_budget_ratio"], 100)
        self.assertTrue(r["pre_release_signal"])  # 150 -> clamp 100 >= 90
        r = schedule_download_budget(False, -5.0, PREF_DEFAULT)
        self.assertEqual(r["download_budget_ratio"], 100)
        self.assertFalse(r["pre_release_signal"])

    def test_unknown_pref_falls_back_default(self):
        """未知偏好回退默认档位"""
        r = schedule_download_budget(True, 50.0, "bogus_pref")
        self.assertGreaterEqual(r["download_budget_ratio"], 60)
        self.assertLessEqual(r["download_budget_ratio"], 70)


if __name__ == "__main__":
    unittest.main()
