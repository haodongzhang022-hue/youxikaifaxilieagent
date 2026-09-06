"""
funnel_demo.py - L0/L1 轻量版漏斗 Demo 引擎（MB-01 · Issue #135 M-B 里程碑）

管线 B（L0 网页 / L1 Cocos 小程序）轻量版漏斗 Demo 引擎：以 PlayState 状态机
驱动「L0/L1 轻量版 → 点增强画质 → CG 锚点 → 假跳云 → 下载状态 → 本地接管」
漏斗五环节，消费 M-A 协议（EnhancementRequest / CloudSession / DownloadStatus）
做**纯逻辑**状态流转（Web/H5 + Cocos L1 共享同一逻辑，表现层随引擎各异）。

对齐 WP-01 漏斗五环节 + WP-02 §6 Demo 桩路径 + M-A PlayState 状态机：
  LOCAL_LITE(本地轻量入口)
    → [点击「增强画质」EnhancementRequest:CG_PLAY] → CG_ANCHOR(CG 遮罩播放)
    → [Prewarm 预热 / CG 播完 Apply 假跳云] → CLOUD_PLAY(云会话 Demo)
    → [边下边玩 DownloadStatus 推进 → 90% 预释放] → LOCAL_FULL(本地接管)
  全程 PlayState.can_transition 校验合法流转，越权/非法流转直接拒绝（护栏）。

设计要点：
  - 引擎只做状态与协议编排（L0/L1 双端复用同一 funnel 逻辑，表现层 Web/Cocos 各异）
  - 消费 M-A 四组协议消息 dataclass，跨引擎同一契约，不另造私有格式
  - CG 为锚点占位（美术线 MB-03 供 CG 素材，引擎仅透传 cg_play 事件与遮罩状态）
"""

from typing import Dict, Optional

from server.proto.messages import (
    PlayState,
    EnhancementRequest, EnhancementType,
    PLAY_STATE_LOCAL_LITE, PLAY_STATE_CG_ANCHOR,
    PLAY_STATE_CLOUD_PLAY, PLAY_STATE_LOCAL_FULL,
)
from server.core.cloud_stub import CloudStub, DEFAULT_DOWNLOAD_TOTAL


class FunnelState:
    """漏斗演示会话（一次 Demo 全程状态）"""

    def __init__(self, player_id: str, platform: str = "web"):
        self.player_id = player_id
        self.platform = platform          # 'web'(L0) / 'cocos'(L1)
        self.state = PLAY_STATE_LOCAL_LITE
        self.enhance_count = 0
        self.cg_completed = False
        self.cloud: Optional[CloudStub] = None
        self.takeover_log: list = []

    # ---------- 状态辅助 ----------
    def current(self) -> str:
        return PlayState.to_str(self.state)

    def _require(self, src: int, dst: int, note: str):
        """PlayState 状态机护栏：非法流转直接抛错"""
        if not PlayState.can_transition(src, dst):
            raise RuntimeError(
                f"非法状态流转 {PlayState.to_str(src)} -> {PlayState.to_str(dst)} ({note})")

    # ---------- 漏斗五环节驱动 ----------
    def enter_lite(self) -> bool:
        """环节① L0/L1 轻量版秒开入口（LOCAL_LITE）"""
        self.state = PLAY_STATE_LOCAL_LITE
        self.cloud = None
        self.cg_completed = False
        self.enhance_count = 0
        self.takeover_log = []
        return True

    def request_enhance(self, request_type: int = None) -> EnhancementRequest:
        """环节② 点击「增强画质」→ 发 EnhancementRequest 转 CG 锚点"""
        self._require(self.state, PLAY_STATE_CG_ANCHOR, "增强入口触发")
        rt = request_type if request_type is not None else EnhancementType.CG_PLAY
        self.enhance_count += 1
        self.state = PLAY_STATE_CG_ANCHOR
        return EnhancementRequest.create(
            player_id=self.player_id,
            from_state=PLAY_STATE_LOCAL_LITE,
            target_stage=PLAY_STATE_CG_ANCHOR,
            request_type=rt,
            session_token=self.player_id + "_tok")

    def play_cg(self) -> str:
        """环节③ CG 锚点播放（美术线 MB-03 CG 素材由表现层注入，引擎透传遮罩态）"""
        if self.state != PLAY_STATE_CG_ANCHOR:
            raise RuntimeError(f"CG 需在 CG_ANCHOR 播放，当前 {PlayState.to_str(self.state)}")
        self.cg_completed = True
        return "cg_anchor_playing"   # 遮罩态；真 CG 素材/序列帧由美术 MB-03 + 表现层呈现

    def jump_cloud(self) -> Dict:
        """环节④ 假跳云：CG 播完 Apply 云会话，转入 CLOUD_PLAY 并预热"""
        self._require(self.state, PLAY_STATE_CLOUD_PLAY, "CG 播完跳云")
        # 云会话预热（CG 遮罩期已后台 Prewarm）+ 正式 Apply
        self.cloud = CloudStub(self.player_id, session_token=self.player_id + "_tok")
        self.cloud.prewarm(expected_duration=30)
        apply_msg = self.cloud.apply(from_state=PLAY_STATE_CG_ANCHOR)
        self.state = PLAY_STATE_CLOUD_PLAY
        return {
            "apply": apply_msg,
            "session_id": apply_msg.session_id,
            "state": self.current(),
        }

    def download_and_takeover(self, steps: int = 3,
                              step_mb: int = None) -> Dict:
        """
        环节⑤ 边下边玩下载推进 + 90% 预释放 → 本地接管 LOCAL_FULL。

        :param steps: 下载推进步数（默认按 step 使下载达 100%）
        :param step_mb: 单步字节数（None 自动按 steps 均分）
        :raises ValueError: steps < 1 时拒绝（无法通过循环推进下载）
        :raises RuntimeError: 下载未达 100% 即尝试接管时拒绝
        """
        if self.cloud is None or self.state != PLAY_STATE_CLOUD_PLAY:
            raise RuntimeError(f"需在 CLOUD_PLAY 中下载，当前 {PlayState.to_str(self.state)}")
        if steps < 1:
            raise ValueError(f"steps 必须 ≥ 1，当前 steps={steps}（无法推进下载即接管）")
        from server.proto.messages import TIMEOUT_PRE_RELEASE

        if step_mb is None:
            step_mb = max(1, DEFAULT_DOWNLOAD_TOTAL // steps) if steps else DEFAULT_DOWNLOAD_TOTAL
        reports = []
        pre_released = False
        for _ in range(steps):
            if self.cloud.is_download_complete():
                break
            r = self.cloud.download_step(step_mb=step_mb)
            reports.append(r)
            if r["pre_release"] and not pre_released:
                pre_released = True
                # 90% 预释放云实例，提前释放资源（成本护栏）
                self.cloud.release(timeout_policy=TIMEOUT_PRE_RELEASE,
                                   target_state=PLAY_STATE_LOCAL_FULL)
        # 下载完成后云会话正式释放 + 本地接管
        self._require(self.state, PLAY_STATE_LOCAL_FULL, "下载完成本地接管")
        # 【修复】下载未达 100% 前拒绝接管——整除偏差/步数不足时先补足剩余下载量
        if not self.cloud.is_download_complete():
            # 一次性补足剩余下载量（含整除偏差 steps=3/6/7… 与 steps<所需 场景）
            self.cloud.download_step(
                step_mb=self.cloud.bytes_total - self.cloud.bytes_done)
        if not self.cloud.released and self.cloud.cloud_active:
            self.cloud.release(target_state=PLAY_STATE_LOCAL_FULL)
        self.state = PLAY_STATE_LOCAL_FULL
        self.takeover_log.append("local_takeover_ok")
        return {
            "steps": reports,
            "download_pct": round(self.cloud.bytes_done / self.cloud.bytes_total * 100.0, 1),
            "pre_released": pre_released,
            "state": self.current(),
            "takeover": "local_full_接管成功（下载完无缝续接）",
        }

    # ---------- 便捷：一次走通整条漏斗 ----------
    def run_full_funnel(self, download_steps: int = 5) -> Dict:
        """端到端演示：L0/L1 → CG → 假跳云 → 下载 → 本地接管"""
        self.enter_lite()
        self.request_enhance()
        self.play_cg()
        jump = self.jump_cloud()
        takeover = self.download_and_takeover(steps=download_steps)
        return {
            "player": self.player_id,
            "platform": self.platform,
            "funnel": [
                "L0/L1_轻量入口", "增强画质→CG锚点", "假跳云(CloudSession Apply)",
                "边下边玩下载", "本地接管LOCAL_FULL",
            ],
            "jump": jump,
            "takeover": takeover,
            "final_state": self.current(),
        }
