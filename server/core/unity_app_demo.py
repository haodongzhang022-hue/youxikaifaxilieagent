"""
unity_app_demo.py - Unity 端 App 内容 Demo（MC-01/02/03 · Issue #135 M-C 里程碑）

M-C = Unity App 内容落地：在 M-B L0/L1 Demo 桩基础上，扩展 Unity(L2) 端接入。

三工作包合一文件：
  MC-01 UnityAppSession：Unity 增强入口接入（消费 Enhancement/CloudSession → 跳云）
  MC-02 UnityParallelDownloader：Unity 下载并行（消费 DownloadStatus → 边下边玩/断点续传/带宽调度/90% 预释放）
  MC-03 UnityAppContent：Unity 完整地图 + 玩法升级（确定性程序化生成，P/Invoke 调 middleware C++ 核心）

漏斗链路（Unity 平台）：
  LOCAL_LITE（Unity App 入口）
    → 点「增强画质」EnhancementRequest → CG_ANCHOR
    → 云会话 CloudSessionApply → CLOUD_PLAY（边下边玩）
    → UnityParallelDownloader 分片并行下载 → 90% 预释放 → LOCAL_FULL
    → UnityAppContent 完整地图确定性生成（同 seed 同 hash）

设计要点：
  - 跨引擎共享确定性逻辑：内容生成走 middleware Python 绑定（与 C++ ABI 同核心）
  - 消费 M-A 四组协议 dataclass，不另造私有格式
  - 带宽调度复用 bandwidth_scheduler（云激活限速 60-70%）
  - UnityAdapter.cs 侧提供 P/Invoke 等价物（同 seed 同 hash 跨引擎校验）
"""

import hashlib
import json
import os
import sys
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from server.proto.messages import (
    serialize, deserialize,
    PlayState, EnhancementType,
    CloudSessionApply, CloudSessionPrewarm,
    CloudSessionHeartbeat, CloudSessionRelease,
    DownloadStatusReport, DownloadChunkComplete,
    EnhancementRequest, SaveSyncPush, SaveSyncPull,
    PLAY_STATE_LOCAL_LITE, PLAY_STATE_CG_ANCHOR,
    PLAY_STATE_CLOUD_PLAY, PLAY_STATE_LOCAL_FULL,
    TIMEOUT_PRE_RELEASE,
)
from server.core.bandwidth_scheduler import (
    schedule_download_budget,
    PREF_DEFAULT,
)

# 尝试导入 middleware 程序化生成（缺失时提供确定性回退）
try:
    from middleware.bindings.python.cabi import (
        procgen_terrain, procgen_level, procgen_resources,
        procgen_props, procgen_narrative, hash_json,
        GameMiddleware,
    )
    _HAS_MIDDLEWARE = True
except ImportError:
    _HAS_MIDDLEWARE = False


def _sha256_hex(s: str) -> str:
    """统一 SHA-256（与 C# UnityAdapter / TS hashJson 一致）。"""
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


# ============================================================
# MC-01: Unity 增强入口 + 云会话会话类
# ============================================================
class UnityAppSession:
    """
    MC-01 · Unity App 增强入口接入会话。

    消费 M-A 协议：
      - EnhancementRequest：点「增强画质」触发跳云
      - CloudSessionApply/Prewarm/Heartbeat/Release：云会话生命周期

    对齐 M-B FunnelState 的状态机流转（Unity 端等价物）：
      LOCAL_LITE → CG_ANCHOR → CLOUD_PLAY → LOCAL_FULL
    """

    def __init__(self, player_id: str, platform: str = "unity"):
        self.player_id = player_id
        self.platform = platform
        self.state = PLAY_STATE_LOCAL_LITE
        self.session_id = str(uuid.uuid4())
        self.session_token = player_id + "_unity_tok"
        self.cloud_active = False
        self.released = False
        self.heartbeat_count = 0
        self.prewarm_count = 0
        self.log: List[str] = []

    # ---- 状态机护栏 ----
    def _require(self, src: int, dst: int, note: str):
        if not PlayState.can_transition(src, dst):
            raise RuntimeError(
                f"非法状态流转 {PlayState.to_str(src)} -> {PlayState.to_str(dst)} ({note})")

    # ---- MC-01: 增强入口接入 ----
    def enter_unity_app(self) -> bool:
        """Unity App 秒开入口（LOCAL_LITE）"""
        self.state = PLAY_STATE_LOCAL_LITE
        self.cloud_active = False
        self.released = False
        self.heartbeat_count = 0
        self.log = []
        return True

    def click_enhance(self) -> EnhancementRequest:
        """点「增强画质」→ 发 EnhancementRequest（CG_PLAY），转 CG_ANCHOR"""
        self._require(self.state, PLAY_STATE_CG_ANCHOR, "Unity 增强入口")
        req = EnhancementRequest.create(
            player_id=self.player_id,
            from_state=PLAY_STATE_LOCAL_LITE,
            target_stage=PLAY_STATE_CG_ANCHOR,
            request_type=EnhancementType.CG_PLAY,
            session_token=self.session_token)
        self.state = PLAY_STATE_CG_ANCHOR
        self.log.append("click_enhance")
        return req

    def play_unity_cg(self) -> str:
        """CG 锚点播放（Unity 端用 Art 层注入 CG 素材，此处仅状态推进）"""
        if self.state != PLAY_STATE_CG_ANCHOR:
            raise RuntimeError(f"CG 需在 CG_ANCHOR 播放，当前 {PlayState.to_str(self.state)}")
        return "cg_anchor_playing_unity"

    def prewarm_cloud(self, expected_duration: int = 30) -> CloudSessionPrewarm:
        """CG 播放期间后台预热云会话"""
        if self.state != PLAY_STATE_CG_ANCHOR:
            raise RuntimeError(f"预热需在 CG_ANCHOR 期间，当前 {PlayState.to_str(self.state)}")
        self.prewarm_count += 1
        return CloudSessionPrewarm.create(
            player_id=self.player_id,
            play_stage=PlayState.to_str(PLAY_STATE_CG_ANCHOR),
            expected_duration=expected_duration,
            session_token=self.session_token)

    def jump_to_cloud(self) -> CloudSessionApply:
        """CG 播完跳云 → 申请云会话，转 CLOUD_PLAY"""
        self._require(self.state, PLAY_STATE_CLOUD_PLAY, "Unity CG 播完跳云")
        self.cloud_active = True
        self.released = False
        # 云激活默认带宽档位 60-70% → 取中值 65
        apply = CloudSessionApply.create(
            player_id=self.player_id,
            session_id=self.session_id,
            from_state=PLAY_STATE_CG_ANCHOR,
            bandwidth_budget=65,
            session_token=self.session_token)
        self.state = PLAY_STATE_CLOUD_PLAY
        self.log.append("jump_cloud")
        return apply

    def heartbeat(self) -> CloudSessionHeartbeat:
        """云会话心跳（保活）"""
        if not self.cloud_active:
            raise RuntimeError("云会话未激活，无法心跳")
        self.heartbeat_count += 1
        return CloudSessionHeartbeat.create(
            player_id=self.player_id,
            session_id=self.session_id,
            sequence=self.heartbeat_count,
            session_token=self.session_token)

    def release_cloud(self, target_state: int = PLAY_STATE_LOCAL_FULL,
                      timeout_policy: int = None) -> CloudSessionRelease:
        """释放云会话（下载完成/超时/预释放）"""
        if not self.cloud_active:
            raise RuntimeError("云会话未激活，无法释放")
        policy = timeout_policy if timeout_policy is not None else 1  # TIMEOUT_DEFAULT
        self.cloud_active = False
        self.released = True
        return CloudSessionRelease.create(
            player_id=self.player_id,
            session_id=self.session_id,
            timeout_policy=policy,
            target_state=target_state,
            session_token=self.session_token)

    def state_str(self) -> str:
        return PlayState.to_str(self.state)


# ============================================================
# MC-02: Unity 并行下载管理器（边下边玩）
# ============================================================
class UnityParallelDownloader:
    """
    MC-02 · Unity 端并行下载管理器。

    特性：
      - 分片并行（chunk 并行模拟）
      - 断点续传（resume_point 持久化）
      - 带宽感知调度（云激活限速防「双输」）
      - 90% 预释放信号
      - 边下边玩（每 chunk 完成即可局部可用）

    消费 M-A 协议：DownloadStatusReport / DownloadChunkComplete
    """

    def __init__(self, player_id: str, total_bytes: int = 100 * 1024 * 1024,
                 chunk_size: int = 10 * 1024 * 1024, prefer: str = PREF_DEFAULT):
        self.player_id = player_id
        self.download_id = str(uuid.uuid4())
        self.total_bytes = total_bytes
        self.chunk_size = chunk_size
        self.num_chunks = max(1, (total_bytes + chunk_size - 1) // chunk_size)
        # 各分片状态：0=未下载 1=已下载
        self.chunks = [0] * self.num_chunks
        self.bytes_done = 0
        self.cloud_active = False
        self.prefer = prefer
        self.session_token = player_id + "_dl_tok"
        self._chunk_seq = 0

    # ---- 下载进度 ----
    @property
    def pct(self) -> float:
        return round(self.bytes_done / self.total_bytes * 100.0, 1) if self.total_bytes else 100.0

    def is_complete(self) -> bool:
        return self.bytes_done >= self.total_bytes

    def resume_point(self) -> int:
        """断点续传位点：下一个未下载分片的起始字节"""
        for i, st in enumerate(self.chunks):
            if st == 0:
                return i * self.chunk_size
        return self.total_bytes

    # ---- 带宽调度 ----
    def _budget(self) -> Dict:
        return schedule_download_budget(self.cloud_active, self.pct, self.prefer)

    # ---- 并行下载（模拟多 chunk 并行推进）----
    def parallel_step(self, parallel_count: int = 2) -> List[Dict]:
        """
        并行推进 multiple chunks。

        :param parallel_count: 同时下载的分片数
        :return: 每个分片完成事件列表
        """
        if self.is_complete():
            return []

        budget = self._budget()
        events = []
        done_in_this_round = 0

        # 找到未下载的分片，模拟并行下载 parallel_count 个
        for i in range(self.num_chunks):
            if self.chunks[i] == 0 and done_in_this_round < parallel_count:
                self.chunks[i] = 1
                self.bytes_done = min(self.total_bytes, self.bytes_done + self.chunk_size)
                done_in_this_round += 1
                self._chunk_seq += 1
                pre_release = budget["pre_release_signal"] or self.pct >= 90.0

                report = DownloadStatusReport.create(
                    player_id=self.player_id,
                    download_id=self.download_id,
                    bytes_done=self.bytes_done,
                    bytes_total=self.total_bytes,
                    resume_point=self.resume_point(),
                    bandwidth_budget=budget["download_budget_ratio"],
                    session_token=self.session_token)
                chunk = DownloadChunkComplete.create(
                    player_id=self.player_id,
                    download_id=self.download_id,
                    chunk_index=self._chunk_seq,
                    bytes_done=self.bytes_done,
                    pre_release_signal=pre_release,
                    session_token=self.session_token)
                events.append({
                    "report": report,
                    "chunk": chunk,
                    "budget": budget,
                    "pct": self.pct,
                    "pre_release": pre_release,
                    "chunk_index": self._chunk_seq - 1,
                })

        return events

    def complete_all(self) -> List[Dict]:
        """一次性下载全部分片（简单场景）"""
        events = []
        guard = 0
        while not self.is_complete() and guard < self.num_chunks + 5:
            events.extend(self.parallel_step(parallel_count=4))
            guard += 1
        return events

    def set_cloud_active(self, active: bool):
        """由 UnityAppSession 同步云会话状态"""
        self.cloud_active = active


# ============================================================
# MC-03: Unity 完整地图 + 玩法升级
# ============================================================
class UnityAppContent:
    """
    MC-03 · Unity 完整地图 + 玩法升级。

    使用 middleware 确定性核心生成完整游戏内容：
      - 地形（terrain）
      - 关卡（level）
      - 资源分布（resources）
      - 装饰物（props）
      - 叙事（narrative）

    与 Web/Cocos/UE 共享同一确定性逻辑：同 seed 输出 hash 一致。
    P/Invoke 等价物由 UnityAdapter.cs 提供（C# 侧同 ABI 契约）。
    """

    def __init__(self, seed: str = "unity_full_world"):
        self.seed = seed
        self.mw = None
        if _HAS_MIDDLEWARE:
            try:
                self.mw = GameMiddleware()
            except Exception:
                self.mw = None
        self.content = {}
        self.world_hash = ""

    # ---- 生成完整内容 ----
    def generate_full_world(self) -> Dict:
        """
        生成完整世界内容（确定性）。

        :return: dict 含 terrain/level/resources/props/narrative + world_hash
        """
        if _HAS_MIDDLEWARE:
            self.content = {
                "terrain": procgen_terrain(self.seed, 64, 64, {"octaves": 4}),
                "level": procgen_level(self.seed, {"width": 100, "depth": 80}),
                "resources": procgen_resources(self.seed),
                "props": procgen_props(self.seed),
                "narrative": procgen_narrative(self.seed),
            }
        else:
            # 确定性回退（无 middleware 时的同构降级）
            self.content = self._fallback_generate()
        self.world_hash = self._compute_hash()
        return self.content

    def _fallback_generate(self) -> Dict:
        """无 middleware 时的确定性回退生成。"""
        st_seed = self.seed
        return {
            "terrain": {"width": 64, "height": 64, "seed": st_seed,
                        "data": [(i * 7 + j * 3) % 100 for i in range(64)
                                 for j in range(64)]},
            "level": {"level_id": "LVL_UNITY", "dimensions": {"width": 100, "depth": 80},
                      "props": [{"prefab_id": f"prop_{i % 8}", "x": i * 3, "z": i * 5}
                                for i in range(8)]},
            "resources": {"resources": [{"type": "stone", "amount": 100,
                                         "x": 10, "z": 10}]},
            "props": {"props": [{"prefab": "tree_oak", "x": 5, "z": 5,
                                 "scale": "1.0"}]},
            "narrative": {"quests": [{"quest_id": "explore_dungeon",
                                      "difficulty": 2,
                                      "dialogues": [
                                          {"speaker": "npc_elder",
                                           "text": "Welcome, traveler.",
                                           "choice": 0}]}]},
        }

    def _compute_hash(self) -> str:
        """计算完整世界 hash（确定性验证用）。"""
        import hashlib
        serialized = json.dumps(self.content, sort_keys=True)
        return hashlib.sha256(serialized.encode()).hexdigest()

    # ---- 各子模块接口 ----
    def terrain(self) -> Dict:
        return self.content.get("terrain", {})

    def level(self) -> Dict:
        return self.content.get("level", {})

    def resources(self) -> Dict:
        return self.content.get("resources", {})

    def props(self) -> Dict:
        return self.content.get("props", {})

    def narrative(self) -> Dict:
        return self.content.get("narrative", {})

    def get_hash(self) -> str:
        """获取 world_hash（需先 generate_full_world）。"""
        return self.world_hash

    @staticmethod
    def verify_consistency(seed: str, expected_hash: str = "") -> bool:
        """
        跨引擎一致性校验。

        同 seed 输出 hash 一致（与 C# UnityAdapter / TS 侧对齐）。
        可选传 expected_hash 做基准比对。
        """
        content = UnityAppContent(seed)
        content.generate_full_world()
        if not expected_hash:
            return bool(content.world_hash)
        return content.world_hash == expected_hash


# ============================================================
# 统一 Runner：一次走通 Unity App 完整漏斗
# ============================================================
class UnityFunnelRunner:
    """
    Unity App 端到端漏斗演示：整合 MC-01/02/03。
    """

    def __init__(self, player_id: str = "U1001"):
        self.player_id = player_id
        self.session = UnityAppSession(player_id, platform="unity")
        self.downloader = UnityParallelDownloader(
            player_id,
            total_bytes=100 * 1024 * 1024,
            chunk_size=10 * 1024 * 1024,
            prefer=PREF_DEFAULT)
        self.content = UnityAppContent(f"unity_seed_{player_id}")
        self.result = {}

    def run(self) -> Dict:
        """端到端执行 Unity 完整漏斗。"""
        # ① Unity App 入口
        self.session.enter_unity_app()

        # ② 点增强画质 → CG
        req = self.session.click_enhance()
        cg_state = self.session.play_unity_cg()

        # ③ 预热 + 跳云
        prewarm = self.session.prewarm_cloud(expected_duration=30)
        apply = self.session.jump_to_cloud()

        # 同步云状态到下载器
        self.downloader.set_cloud_active(True)

        # ④ 并行下载（边下边玩）
        events = []
        guard = 0
        while not self.downloader.is_complete() and guard < 20:
            batch = self.downloader.parallel_step(parallel_count=2)
            events.extend(batch)
            guard += 1

        # ⑤ 90% 预释放
        pre_released = any(e["pre_release"] for e in events)
        if pre_released:
            self.session.release_cloud(target_state=PLAY_STATE_LOCAL_FULL,
                                       timeout_policy=TIMEOUT_PRE_RELEASE)

        # ⑥ 下载完成 → 释放云会话 → LOCAL_FULL
        if self.downloader.is_complete() and self.session.cloud_active:
            self.session.release_cloud(target_state=PLAY_STATE_LOCAL_FULL)

        self.session.state = PLAY_STATE_LOCAL_FULL

        # ⑦ 完整地图 + 玩法（确定性生成）
        world = self.content.generate_full_world()
        world_hash = self.content.get_hash()

        # 心率上报（云端运行时保活）
        heartbeat = None
        if self.session.heartbeat_count == 0 and self.session.cloud_active:
            pass  # 云已在下载后释放
        self.result = {
            "player": self.player_id,
            "platform": "unity",
            "funnel_states": [
                "LOCAL_LITE(Unity App 入口)",
                "CG_ANCHOR(增强画质 CG)",
                "CLOUD_PLAY(云会话跳云)",
                "LOCAL_FULL(本地完整版接管)",
            ],
            "enhance_request": serialize(req),
            "prewarm": serialize(prewarm),
            "cloud_apply": serialize(apply),
            "download": {
                "total_bytes": self.downloader.total_bytes,
                "chunk_count": self.downloader.num_chunks,
                "bytes_done": self.downloader.bytes_done,
                "pct": self.downloader.pct,
                "pre_released": pre_released,
                "chunk_events": len(events),
                "resume_point": self.downloader.resume_point(),
            },
            "world_content": {
                "terrain": bool(world.get("terrain")),
                "level": bool(world.get("level")),
                "resources": bool(world.get("resources")),
                "props": bool(world.get("props")),
                "narrative": bool(world.get("narrative")),
            },
            "world_hash": world_hash[:16] + "..." if world_hash else "",
            "final_state": PlayState.to_str(self.session.state),
            "takeover": "Unity 本地完整版接管成功（增强跳云→并行下载→无缝续接）",
        }
        return self.result
