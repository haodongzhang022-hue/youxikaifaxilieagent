# M-C Unity App 内容落地 — 设计说明

> Issue #135 · M-C 里程碑 · MC-01/02/03 · 程序线

## 一、工作包概述

M-C = **Unity App 内容落地**。在 M-B L0/L1 Demo 桩基础上，扩展 Unity(L2) 端接入，
打通「增强跳云 → 并行下载 → 本地完整版接管」漏斗链路。

三工作包合一实现：

| # | 工作包 | 产出模块 | 核心职责 |
|---|--------|---------|---------|
| MC-01 | Unity 增强入口跳云 | `UnityAppSession` | 消费 Enhancement/CloudSession 协议 → 点增强 → CG → 跳云 |
| MC-02 | Unity 下载并行 | `UnityParallelDownloader` | 消费 DownloadStatus → 分片并行/断点续传/边下边玩/带宽调度/90% 预释放 |
| MC-03 | Unity 完整地图+玩法 | `UnityAppContent` | middleware 确定性生成 terrain/level/resources/props/narrative，P/Invoke 对齐 UnityAdapter.cs |

## 二、代码文件清单

| 文件 | 职责 |
|------|------|
| `server/core/unity_app_demo.py` | MC-01/02/03 主实现（UnityAppSession + UnityParallelDownloader + UnityAppContent + UnityFunnelRunner） |
| `server/core/mc_unity_runner.py` | 端到端 runner（Unity App 完整漏斗演示） |
| `server/tests/test_mc_unity_app.py` | G3 方向单测（29 用例） |
| `middleware/adapters/unity/UnityAdapter.cs` | C# P/Invoke 扩展（新增 level/resources/props/narrative 声明） |

## 三、漏斗链路

```
Unity App 入口 (LOCAL_LITE)
  → 点「增强画质」EnhancementRequest → CG_ANCHOR
  → CG 播完 → 云会话 CloudSessionApply → CLOUD_PLAY
  → UnityParallelDownloader 分片并行下载（边下边玩）
  → 下载 90% → 预释放信号 → 云会话释放
  → 下载 100% → LOCAL_FULL（本地完整版接管）
  → UnityAppContent 完整地图确定性生成（terrain/level/resources/props/narrative）
```

全程 `PlayState.can_transition` 状态机护栏，非法流转直接拒绝。

## 四、关键技术设计

### 4.1 MC-01 UnityAppSession
- 消费 M-A `EnhancementRequest`（点击增强跳云）
- 消费 M-A `CloudSessionApply/Prewarm/Heartbeat/Release`
- 状态机：LOCAL_LITE → CG_ANCHOR → CLOUD_PLAY → LOCAL_FULL

### 4.2 MC-02 UnityParallelDownloader
- 100MB 总量 / 10MB 分片 → 10 个 chunks
- `parallel_step(n)` 模拟 n 路并行下载
- `resume_point()` 断点续传位点（未下载分片的起始字节）
- 复用 `bandwidth_scheduler.schedule_download_budget`（云激活限速 60-70%）
- 下载 ≥90% 自动触发预释放信号

### 4.3 MC-03 UnityAppContent
- 调用 middleware Python 绑定确定性生成五类内容
- `world_hash` 用 SHA-256 校验（同 seed 同 hash，跨引擎一致）
- `UnityAdapter.cs` 新增 P/Invoke 声明（level/resources/props/narrative）
- 与 Web/Cocos/UE 共享同一确定性核心（middleware C ABI）

## 五、门禁回归

| 套件 | 结果 |
|------|------|
| `test_mc_unity_app.py` | 29/29 ✅ |
| `test_mb_funnel_demo.py` | 19/19 ✅ |
| `test_ma_protocol_freeze.py` | 18/18 ✅ |
| `test_server.py` | 25/25 ✅ |
| `test_pitfalls_scan.py` | 14/14 ✅ |
| **合计** | **105/105** ✅ |

## 六、阶段护栏

- M-C 只做 Unity(L2) 增强跳云 + 并行下载 Demo
- 真云渲染/多版同发标 UE 阶段（M-D/M-E）储备，不越阶段硬做
- 代码消费 M-A 协议不另造私有格式，跨引擎复用
