# MA-01~MA-04 · M-A 协议冻结实现说明（Issue #135）

> 里程碑：**M-A（协议冻结）** · MVP 首个实际开发里程碑
> 承接：程序线（engine_dev + server_dev + client_dev + cto 分工协作）
> 上游：WP-01/02/04 方案 ✅ 已合入 PR #136，无阻塞依赖

---

## 一、落地范围与文件映射

| 工作包 | 内容 | 落地文件 |
|--------|------|---------|
| MA-01 | 4 组协议 IDL 扩展（字段只增不改，版本 1.0→1.1） | `server/proto/protocol.proto` |
| MA-02 | 枚举 + 消息 dataclass 增量实现 | `server/proto/messages.py` |
| MA-03 | 带宽感知调度器（无状态纯算法） | `server/core/bandwidth_scheduler.py` |
| MA-04 | 协议一致性 + 状态机 + 带宽分支单测 | `server/tests/test_ma_protocol_freeze.py` |

## 二、协议冻结增量（protocol.proto v1.1）

遵循既有 v1.0 风格，新增字段**只增不改、用 optional 语义、版本号递增**，四端共用一份 IDL：

1. **存档同步 SaveSync**：`SaveSyncPush / SaveSyncPull / SaveSyncResponse`
   - 字段：progress_checkpoint / platform / data_version / session_token（切端续接）
2. **云会话 CloudSession**：`CloudSessionApply / Prewarm / Heartbeat / Release / CloudSessionState`
   - 字段：session_id / play_stage / timeout_policy / bandwidth_budget（CG 预热/心跳/释放）
   - 新增枚举 `TimeoutPolicy`（DEFAULT / PRE_RELEASE / USER_EXIT）
3. **下载状态 DownloadStatus**：`DownloadStatusReport / DownloadChunkComplete / DownloadStatusResponse`
   - 字段：download_id / chunk_index / bytes_done / resume_point / bandwidth_budget（边下边玩/断点续传）
4. **增强入口 EnhancementRequest**：`EnhancementRequest / EnhancementResponse`
   - 字段：from_state / target_stage / request_type（「增强画质」跳云）
   - 新增枚举 `EnhancementType`（CG_PLAY / CLOUD_UPGRADE）

新增 `PlayState` 枚举，对齐 WP-01 三态状态机：
`LOCAL_LITE(1) → CG_ANCHOR(2) → CLOUD_PLAY(3) → LOCAL_FULL(4)`（+UNKNOWN=0 占位）。

## 三、messages.py 增量实现

- 模块常量 + `PlayState / TimeoutPolicy / EnhancementType` 枚举类
  - `PlayState.TRANSITIONS` + `can_transition()` 固化合法状态流转
- 4 组协议消息 dataclass，均带 `to_dict / from_dict / create`，与既有 `GameRequest` 风格一致
- 序列化复用既有 `serialize / deserialize`（JSON 载体，语义对齐 proto）

## 四、带宽感知调度器（MA-03）

`server/core/bandwidth_scheduler.py`，**无状态纯函数** `schedule_download_budget()`：
- 输入 `is_cloud_active / download_pct / user_pref`，输出 `download_budget_ratio`
- 云激活默认 60-70%；画质优先 40-50%；下载优先 80%；云关闭全速 100%
- 下载 ≥90% 触发 `pre_release_signal`（对齐策划 R5 提前释放）

跨引擎各端复用同一算法实现（Web/Cocos TS、Unity C#、UE C++ 绑定同一 IDL 与调度逻辑）。

## 五、测试与门禁回归（MA-04）

`server/tests/test_ma_protocol_freeze.py` 共 **18 用例**，覆盖：
- 4 组协议 serialize↔deserialize roundtrip
- 字段兼容（缺可选字段回退默认；缺必填抛错）
- PlayState 状态机合法/非法流转 + 完整漏斗路径
- 带宽调度 4 分支 + 90% 预释放边界 + 进度夹取 + 未知偏好回退

运行方式：`PYTHONPATH=. python3 server/tests/test_ma_protocol_freeze.py -v`

**门禁回归**（WP-04 G1 协议一致门禁 + 既有测试全绿）：
- `test_ma_protocol_freeze.py`：18/18 ✅
- `test_server.py`：25/25 ✅
- `test_pitfalls_scan.py`：14/14 ✅

## 六、衔接下一里程碑

MA-01~04 完成后，供经理验收 → 解锁 **M-B**（L0/L1 + CG 锚点 + 跳云 Demo 桩）。
M-A 只锚协议/算法，真云渲染/无缝切换全量留 UE 阶段储备，符合「阶段不对就算错」铁律。

*产出：程序线 engine_dev(协议边界/版本) + server_dev(消息类/状态机) + client_dev(带宽算法) + cto(门禁回归/护栏) 协作产出。*
