"""
cloud_stub.py - 假云/下载 Demo 桩（MB-02 · Issue #135 M-B 里程碑）

假跳云服务端 Demo 桩：消费 M-A 协议 CloudSession / DownloadStatus / Enhancement
三组消息，做「假云会话 + 下载进度 + 带宽调度 + 预释放接管」的**全假接口**流转，
打通漏斗五环节的「假跳云 → 下载状态 → 本地接管」三段，不接真实云渲染。

对齐 WP-02 §6 MVP Demo 桩技术骨架：
  L0/L1 轻量版 → 点「增强画质」→ CG(CG锚点/遮罩) → 假跳云(CloudSession Apply)
    → 「云高配」占位画面(边下边玩下载模拟) → 下载 90% 触发「即将切换本地」→ 本地接管

设计要点：
  - 无状态核心算法 + 内存态会话簿：核心纯函数可测，会话簿仅模拟 Demo 会话生命周期
  - 复用 bandwidth_scheduler 无状态带宽调度：云激活限速、90% 预释放
  - 全部消息走 M-A 协议 dataclass（to_dict/from_dict/serialize），跨引擎同一契约
"""

import uuid
from typing import Dict, Optional

from server.proto.messages import (
    serialize,
    PlayState,
    CloudSessionApply, CloudSessionPrewarm,
    CloudSessionHeartbeat, CloudSessionRelease,
    DownloadStatusReport, DownloadChunkComplete,
    PLAY_STATE_LOCAL_LITE, PLAY_STATE_CG_ANCHOR,
    PLAY_STATE_LOCAL_FULL,
)
from server.core.bandwidth_scheduler import (
    schedule_download_budget,
    PREF_DEFAULT,
)

# 下载总量（Demo 用，单位：虚拟 MB）
DEFAULT_DOWNLOAD_TOTAL = 100
# 边下边玩单步默认增量（虚拟 MB）
DEFAULT_STEP_MB = 10
# 云会话时长上限（对齐成本护栏 30-60min，Demo 用秒/心跳计数占位）
MAX_SESSION_STEPS = 12


# ============================================================
# 假云会话簿（内存态 · 单 Demo 会话）
# ============================================================
class CloudStub:
    """假云/下载 Demo 桩：管理一次『假跳云 + 边下边玩下载』Demo 会话"""

    def __init__(self, player_id: str, session_token: str = ""):
        self.player_id = player_id
        self.session_token = session_token or str(uuid.uuid4())
        self.session_id = str(uuid.uuid4())
        self.cloud_active = False
        self.download_id = str(uuid.uuid4())
        self.bytes_done = 0
        self.bytes_total = DEFAULT_DOWNLOAD_TOTAL
        self.heartbeats = 0
        self.prewarm_count = 0
        self.released = False
        self.prefer = PREF_DEFAULT
        self._chunk_seq = 0    # 独立分片序号，递增与 heartbeat 解耦

    # ---------- 带宽感知下载预算 ----------
    def _budget(self) -> Dict:
        pct = (self.bytes_done / self.bytes_total) * 100.0 if self.bytes_total else 100.0
        return schedule_download_budget(self.cloud_active, pct, self.prefer)

    # ---------- 云会话：预热 / 申请 / 心跳 / 释放 ----------
    def prewarm(self, expected_duration: int = 30) -> CloudSessionPrewarm:
        """CG 播放期后台静默预热（Prewarm）"""
        self.prewarm_count += 1
        return CloudSessionPrewarm.create(
            player_id=self.player_id, play_stage=PlayState.to_str(PLAY_STATE_CG_ANCHOR),
            expected_duration=expected_duration, session_token=self.session_token)

    def apply(self, from_state: int = PLAY_STATE_LOCAL_LITE) -> CloudSessionApply:
        """假跳云：申请云会话（CloudSession Apply），置云激活态"""
        # 【修复】先激活云再算带宽预算——避免 _budget() 在 cloud_active=False 时返回 0
        self.cloud_active = True
        self.released = False
        budget = self._budget()
        return CloudSessionApply.create(
            player_id=self.player_id, session_id=self.session_id,
            from_state=from_state,
            bandwidth_budget=budget["cloud_budget_ratio"],
            session_token=self.session_token)

    def heartbeat(self) -> CloudSessionHeartbeat:
        """云会话心跳（保活，防僵尸会话）"""
        if not self.cloud_active:
            raise RuntimeError("cloud session not active")
        self.heartbeats += 1
        return CloudSessionHeartbeat.create(
            player_id=self.player_id, session_id=self.session_id,
            sequence=self.heartbeats, session_token=self.session_token)

    def release(self, timeout_policy: int = None,
                target_state: int = PLAY_STATE_LOCAL_FULL) -> CloudSessionRelease:
        """释放云会话（超时/退出/下载 90%+ 预释放/本地接管）"""
        if not self.cloud_active:
            raise RuntimeError("cloud session not active")
        from server.proto.messages import TIMEOUT_DEFAULT, TIMEOUT_PRE_RELEASE
        policy = timeout_policy if timeout_policy is not None else TIMEOUT_DEFAULT
        self.cloud_active = False
        self.released = True
        return CloudSessionRelease.create(
            player_id=self.player_id, session_id=self.session_id,
            timeout_policy=policy, target_state=target_state,
            session_token=self.session_token)

    # ---------- 下载：状态上报 / 分片完成（边下边玩） ----------
    def download_step(self, step_mb: int = DEFAULT_STEP_MB,
                      chunk_index: Optional[int] = None) -> dict:
        """
        模拟边下边玩下载推进一步。

        :return: dict {
          "report": DownloadStatusReport, "chunk": DownloadChunkComplete,
          "budget": dict(带宽调度结果), "pct": float, "pre_release": bool
        }
        """
        budget = self._budget()
        self.bytes_done = min(self.bytes_total, self.bytes_done + step_mb)
        pct = (self.bytes_done / self.bytes_total) * 100.0
        pre_release = budget["pre_release_signal"] or pct >= 90.0

        report = DownloadStatusReport.create(
            player_id=self.player_id, download_id=self.download_id,
            bytes_done=self.bytes_done, bytes_total=self.bytes_total,
            resume_point=self.bytes_done,
            bandwidth_budget=budget["download_budget_ratio"],
            session_token=self.session_token)

        # 【修复】独立自增序号，不再依赖 heartbeat 计数（不调心跳时分片序号也应递增）
        self._chunk_seq += 1
        ci = chunk_index if chunk_index is not None else self._chunk_seq
        chunk = DownloadChunkComplete.create(
            player_id=self.player_id, download_id=self.download_id,
            chunk_index=ci, bytes_done=self.bytes_done,
            pre_release_signal=pre_release, session_token=self.session_token)
        return {
            "report": report, "chunk": chunk, "budget": budget,
            "pct": round(pct, 1), "pre_release": pre_release,
        }

    def is_download_complete(self) -> bool:
        return self.bytes_done >= self.bytes_total

    def serialized_report(self) -> str:
        """返回 DownloadStatusReport 的 JSON 载体（跨引擎契约对齐 serialize）。

        基于当前状态直接构造 report，无副作用（不调用 download_step()）。
        """
        # 基于当前状态计算带宽档位（不推进 bytes_done）
        budget = self._budget()
        report = DownloadStatusReport.create(
            player_id=self.player_id, download_id=self.download_id,
            bytes_done=self.bytes_done, bytes_total=self.bytes_total,
            resume_point=self.bytes_done,
            bandwidth_budget=budget["download_budget_ratio"],
            session_token=self.session_token)
        return serialize(report)
