# MB-01~MB-02 · M-B L0/L1漏斗Demo桩实现说明（Issue #135）

> 里程碑：**M-B（L0/L1 轻量版 + CG 锚点 + 「点增强跳云」Demo 桩）** · MVP
> 承接：程序线（client_dev + cocos_dev + server_dev + engine_dev + cto 分工协作）
> 上游：M-A 协议冻结 ✅（PR #137 合入）+ WP-01 漏斗 + WP-03 CG 标准 全部就绪，无阻塞
> 触发源：PR #137（M-A 协议冻结）合并 → 经理验收 G1 通过 → 解锁 M-B → 程序线 MB-01+MB-02 派发

---

## 一、落地范围与文件映射

| 工作包 | 内容 | 落地文件 |
|--------|------|---------|
| MB-01 | L0/L1 轻量版漏斗 Demo 引擎（Web/H5 + Cocos 共享逻辑 + PlayState 状态流转） | `server/core/funnel_demo.py` |
| MB-02 | 假云/下载 Demo 桩（消费 CloudSession/DownloadStatus/Enhancement 协议做假跳云流转） | `server/core/cloud_stub.py` |
| MB-01+02 | 端到端演示 runner（L0 web + L1 cocos 双入口） | `server/core/mb_funnel_runner.py` |
| MB-01+02 | 门禁 G2 方向单测（19 用例） | `server/tests/test_mb_funnel_demo.py` |
| — | 设计说明 + 分工审计留痕 | `…/issue135/mb_funnel_demo_实现说明.md` + `mb_funnel_demo_group_audit.json` |

---

## 二、MB-01 · funnel_demo（L0/L1 漏斗 Demo 引擎）

以 `PlayState` 状态机驱动漏斗五环节，消费 M-A 协议做**纯逻辑**状态流转，
Web(H5/L0) 与 Cocos(L1) 共享同一引擎逻辑，表现层随引擎各异（阶段合规铁律）：

```
LOCAL_LITE(轻量秒开入口)
  → [request_enhance: EnhancementRequest/CG_PLAY] → CG_ANCHOR(CG 遮罩播放)
  → [play_cg 完成] → [jump_cloud: Prewarm 预热 + CloudSession Apply] → CLOUD_PLAY(假云)
  → [download_and_takeover: DownloadStatus 边下边玩推进 → 90% 预释放] → LOCAL_FULL(本地接管)
```

- 全程用 `PlayState.can_transition` 校验合法流转，**非法流转（绕过 CG 直达云/本地）直接抛错**护栏
- `EnhancementRequest` 触发跳云入口，CG 为锚点占位（美术 MB-03 供素材，引擎只透传遮罩态）

## 三、MB-02 · cloud_stub（假云/下载 Demo 桩）

假跳云服务端 Demo 桩，消费 M-A 云会话/下载三组协议做**全假接口**流转：

- **云会话**：`Prewarm`(CG 遮罩期后台预热) → `Apply`(假跳云激活) → `Heartbeat`(保活防僵尸) → `Release`(超时/退出/90% 预释放/本地接管)
- **下载**：`DownloadStatusReport` + `DownloadChunkComplete`（边下边玩模拟，断点续传语义字段）
- **带宽调度**：复用 `bandwidth_scheduler` 无状态算法，云激活限速（默认 60-70%）、下载 90% 触发 `pre_release_signal`
- 消息全部走 M-A dataclass 的 `to_dict/from_dict/serialize`，跨引擎同一 JSON 契约

## 四、门禁与回归（WP-04 G2 方向）

- `test_mb_funnel_demo.py`：**19/19 ✅**（状态机流转 + 非法流转护栏 + 假云生命周期 + 带宽调度 + 端到端 L0/L1）
- 端到端 runner：`PYTHONPATH=. python3 server/core/mb_funnel_runner.py` → L0 web + L1 cocos 漏斗五环节全部走通至 LOCAL_FULL
- **全量门禁回归**：`test_ma_protocol_freeze` 18/18 · `test_server` 25/25 · `test_pitfalls_scan` 14/14 · `test_mb_funnel_demo` 19/19 全绿

## 五、衔接下一里程碑

MB-01/02（程序）与 MB-03（美术 CG 占位素材）完成后 → 经理验收 **G2 单版体验门禁** → 解锁 **M-C**（Unity App 内容落地）。
真云渲染/无缝切换全量留 UE 阶段储备，本 MVP 只落假跳云 Demo 桩，符合「阶段不对就算错」铁律。

*产出：程序线 client_dev(funnel_demo) + cocos_dev(L1 入口校验) + server_dev(cloud_stub) + engine_dev(状态机护栏) + cto(门禁/护栏统筹) 协作产出。*
