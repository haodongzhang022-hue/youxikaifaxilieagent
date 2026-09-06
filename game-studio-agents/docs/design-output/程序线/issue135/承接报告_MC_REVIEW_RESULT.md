# 承接报告 · 程序线 · Issue #135 M-C MC-01/02/03

## 一、路由守卫确认

- 工作包：**MC-01/02/03**（Unity App 内容落地）
- 里程碑：**M-C**（MVP 第3个里程碑 · WP-04 G3 单版完整门禁）
- 路由：G2 单版体验门禁 GO → M-C 解锁 → 项目管理派发 MC-01~04
- 部门：程序线（`engine_dev` + `client_dev` + `server_dev` + `cto`）

## 二、承接工作包

| # | 工作包 | 主责角色 | 优先级 | 状态 |
|---|--------|---------|:------:|:----:|
| MC-01 | Unity 增强入口接入（消费 Enhancement/CloudSession → 跳云） | engine_dev + server_dev | P0 | ✅ DONE |
| MC-02 | Unity 下载并行（消费 DownloadStatus → 边下边玩/断点续传/90% 预释放） | client_dev | P0 | ✅ DONE |
| MC-03 | Unity 完整地图 + 玩法升级（确定性程序化生成 P/Invoke 核心） | engine_dev | P1 | ✅ DONE |

## 三、组内分工表

| 子任务 | 承接角色 | 产出 |
|--------|---------|------|
| MC-01 增强跳云 + MC-03 完整地图确定性核心 | engine_dev | `UnityAppSession` + `UnityAppContent` |
| MC-02 并行下载 UnityParallelDownloader | client_dev | `UnityParallelDownloader`（分片/断点续传/边下边玩） |
| MC-01 云会话生命周期协议消费 | server_dev | CloudSessionApply/Prewarm/Heartbeat/Release 对齐 M-A |
| M-C 阶段护栏 + 门禁 G3 回归统筹 | cto | `mc_unity_runner.py` + `test_mc_unity_app.py` + UnityAdapter.cs P/Invoke |

## 四、REVIEW_RESULT

**结论：✅ 通过**

### 产出物

| 文件 | 内容 |
|------|------|
| `server/core/unity_app_demo.py` | MC-01 UnityAppSession + MC-02 UnityParallelDownloader + MC-03 UnityAppContent + UnityFunnelRunner |
| `server/core/mc_unity_runner.py` | Unity App 端到端演示 runner |
| `server/tests/test_mc_unity_app.py` | G3 方向单测 **29 用例** |
| `middleware/adapters/unity/UnityAdapter.cs` | C# P/Invoke 扩展（level/resources/props/narrative + GenerateFullWorld） |
| `设计说明` | M-C 实现架构与关键设计 |

### 门禁回归（105/105 全绿）

- `test_mc_unity_app` **29/29** ✅
- `test_mb_funnel_demo` **19/19** ✅
- `test_ma_protocol_freeze` **18/18** ✅
- `test_server` **25/25** ✅
- `test_pitfalls_scan` **14/14** ✅

### 端到端 runner 实测

```
Unity App 入口 → 增强画质 → CG → 跳云(CLOUD_PLAY)
  → 并行下载（100MB/10分片）→ 90% 预释放 → LOCAL_FULL
  → 完整地图确定性生成（terrain/level/resources/props/narrative）
  → world_hash 确定性校验 ✅
```

## 五、关键要点

1. **Unity App 端完整漏斗走通**：增强跳云 + 并行下载 + 本地完整版接管，全程状态机护栏
2. **跨引擎共享确定性核心**：内容生成走 middleware Python 绑定（与 C++ ABI 同核心），同 seed 同 hash
3. **消费 M-A 协议不另造私有格式**：Enhancement/CloudSession/DownloadStatus 全部用 M-A dataclass
4. **带宽调度复用**：云激活限速 60-70%，画质/下载优先可切换，90% 预释放信号
5. **阶段合规**：M-C 只做 Unity 增强跳云 + 并行下载 Demo；真云渲染/多版同发标 UE 阶段（M-D/M-E）储备

## 六、下游

- MC-01~03 完成 → 测试线 **MC-04**（Unity 端 G3 单版完整门禁回归）可介入
- G3 GO → 解锁 **M-D**（UE 阶段储备）
