# 🧪 测试线 · PR #139 下游解锁承接结果（MC-04 · Unity 端 G3 单版完整门禁 QA 验收 · Issue #135）

## 一、路由守卫确认

- 事件：PR #139（`feat: M-C Unity App完整内容落地`）已合并 → post-merge 下游解锁（G3 门禁回归）。
- `.routing_active.txt` = `测试线` → 测试线 **active**（CNB_BUILD_STAGE_NAME=测试线执行(下游解锁)）。
- 游戏向经理在 Issue 评论中显式声明：**测试线命中**，承接 **MC-04**（Unity 端 G3 单版完整门禁回归）。
- 路由守卫通过：本部门被点名承接本轮测试线工作包 → 执行。

## 二、本轮工作包领取结果

| # | 工作包 | 模块 | 主责角色 | 优先级 | 状态 |
|---|--------|------|----------|:------:|:----:|
| MC-04 | Unity 端 G3 单版完整门禁独立 QA 验收 | `wp_testing/mc04` | qa_engineer + auto_qa | P1 | ✅ DONE |

> **判定**：MC-01/02/03 三件套（`UnityAppSession`/`UnityParallelDownloader`/`UnityAppContent` + `mc_unity_runner.py` + `UnityAdapter.cs`）合入后，G3 单版完整门禁验收需 **独立 QA 功能验收**（区别于程序侧自测），
> 测试线独立验证增强跳云链路/并行下载 90% 预释放/确定性地图 world_hash/状态机护栏，为 G3 门禁提供**测试侧 GO 依据**。

## 三、组内分工表（协作工作台 @分工 · group_audit 留痕）

MC-04 为**部门级跨角色验收包**，经协作工作台拆 2 子任务派发（留痕 `g3_gate_qa_group_audit.json`，8 事件）：

| 子任务 | 承接角色 | 产出 |
|--------|---------|------|
| Unity App **增强跳云链路/并行下载/确定性地图/状态机护栏** 独立功能验收（73 断言场景） | qa_engineer | 73/73 QA 独立功能验收断言全绿 |
| **G3 全量回归统筹** + 端到端 runner 验证 + UnityAdapter P/Invoke 契约校验 + 框架级回归确认 | auto_qa | 105 服务端回归 + middleware/adapters + routing 16/16 · stage 20/20 · engine_adapters 25/25 · producer 24/24 全绿 |

- 协作工作台留痕：origin=测试线部门统一头 → DELEGATE(SPLIT) → 2 子任务派发 `qa_engineer` / `auto_qa` → 双方 ACCEPTED → COMPLETE → DONE
- 留痕落盘：`…/issue135/g3_gate_qa/g3_gate_qa_group_audit.json`

## 四、验收结果（独立 QA 视角实测）

### ① 场景 1：MC-01 UnityAppSession 增强跳云链路 — 22/22 通过 ✅
- Unity App 入口秒开 LOCAL_LITE + platform=unity 正确
- EnhancementRequest 协议字段完整（request_type / from_state / target_stage）
- CG 锚点播放 + 云会话预热（duration=30s）
- 跳云 CLOUD_PLAY + 带宽预算 65%（云激活默认档）
- 云会话心跳 seq/计数正常
- **预释放**云会话（TIMEOUT_PRE_RELEASE）成功
- **非法流转护栏**：LOCAL_LITE 直接跳云被拒 / LOCAL_LITE 直接播 CG 被拒 / 未激活心跳被拒 / 未激活释放被拒

### ② 场景 2：MC-02 UnityParallelDownloader — 18/18 通过 ✅
- 分片切分 10 chunks / 100MB 总量正确
- 并行下载推进（parallel_step）bytes/pct 累计正确
- 报告与分片协议序列化回环（DownloadStatusReport / DownloadChunkComplete）
- 断点续传位点 resume_point 正确
- **云激活带宽受限**（download<100% + cloud>0）
- **画质优先**下载≤50% / **下载优先**下载≥80% 带宽档位区分正确
- **90% 预释放信号**触发
- complete_all 全量下载 100%

### ③ 场景 3：MC-03 UnityAppContent 确定性地图 — 19/19 通过 ✅
- 完整世界生成含 terrain / level / resources / props / narrative 五模块
- **同 seed → 同 world_hash**（确定性校验）
- **不同 seed → 不同 world_hash**（区分度校验）
- world_hash 为 SHA-256（64 hex 字符）
- **跨引擎一致性**校验通过（`UnityAppContent.verify_consistency`）
- middleware Python 绑定同 seed 同 hash（独立于 App 层验证）
- **UnityAdapter.cs P/Invoke 9 个 ABI 函数声明齐全**（terrain/level/resources/props/narrative + init/shutdown/gameplay_state）

### ④ 场景 4：端到端 Unity 完整漏斗 — 14/14 通过 ✅
- UnityFunnelRunner 全链路走通：LOCAL_LITE → CG_ANCHOR → CLOUD_PLAY → LOCAL_FULL
- 下载达 100% + 预释放触发 + 分片事件>0
- 世界内容五模块全部生成 + world_hash 存在
- 多次运行互不干扰（玩家/状态隔离）

### ⑤ auto_qa 全量回归确认
- **105/105 服务端回归全绿**：test_mc **29** + test_mb **19** + test_ma **18** + test_server **25** + test_pitfalls **14**
- middleware Python core **7/7** · 四引擎适配器 golden hash **9/9**
- 框架级：routing **16/16** · stage_aware_engine **20/20** · engine_adapters **25/25** · producer_agent **24/24**
- change-aware full suite **154** 全部通过

## 五、跨部门协作记录（request_peer）

| 协作方向 | 部门 | 内容 | 状态 |
|---------|------|------|:----:|
| 被测对象 | 程序线 MC-01/02/03 | `unity_app_demo.py` 三模块独立功能验收 | ✅ 73/73 |
| 被测对象 | 程序线 runner | `mc_unity_runner.py` 端到端漏斗独立复跑 | ✅ LOCAL_FULL |
| 被测契约 | 程序线 UnityAdapter.cs | P/Invoke 扩展 9 个 ABI 函数声明契约校验 | ✅ |
| 被测基础 | middleware | C++/Python 确定性核心 + 四引擎一致性 | ✅ |
| 下游验收 | 项目管理 WP-04 | **G3 门禁测试侧 GO 依据**，供 release_manager 组织验收 | 🔗 供 G3 |

## 六、REVIEW_RESULT 上报

**结论：✅ 通过（G3 单版完整门禁测试侧 GO）**

**产出物说明**：
1. **73 项独立 QA 功能验收断言全绿** — 增强跳云/并行下载/确定性地图/状态机护栏/协议契约/UnityAdapter P/Invoke
2. **105 服务端回归全绿**（含 test_mc_unity_app 29 用例）+ middleware 7/7 + adapters golden 9/9
3. **框架级回归全绿**：routing 16/16 / stage 20/20 / engine_adapters 25/25 / producer 24/24 + full-suite 154
4. **端到端 runner 独立复跑**：Unity App 漏斗走通至 LOCAL_FULL，world_hash 确定性校验通过
5. **留痕**：`…/issue135/g3_gate_qa/g3_gate_qa_group_audit.json`（8 事件）

**关键要点**：
1. 测试线独立验证（非程序侧自测）MC-01/02/03 Unity App 三件套满足 G3 单版完整门禁功能要求
2. 增强跳云链路完整（LOCAL_LITE → CG_ANCHOR → CLOUD_PLAY），云会话生命周期（prewarm/apply/heartbeat/release）全通
3. 并行下载含带宽调度（画质/下载偏好）与 90% 预释放信号
4. 确定性地图 world_hash 同 seed 同 hash，跨引擎一致性保持
5. UnityAdapter.cs P/Invoke 契约与 middleware Python 绑定对齐
6. PlayState 状态机护栏有效，非法流转全部被拒

**交付建议**：
- **G3 门禁测试侧 GO 依据已齐备**，供项目管理 release_manager 组织 G3 门禁正式签核
- 正式 G3 GO 后 → 解锁 M-D（UE 阶段储备：真云渲染/多版同发），进入 UE 引擎阶段编排
- 测试线在 M-D/E 阶段多版并存回归/一致性测试基线待 G4 门禁解锁后承接

---
*全程机制驱动：post-merge 路由激活（测试线 active）→ 领取 MC-04 → CollaborationWorkbench 组内 @分工(2 角色) → request_peer 跨部门登记 → REVIEW_RESULT 上报（通过 GO）。*
