# 程序线 · 承接报告（PR #137 下游解锁 · M-B MB-01/MB-02 · REVIEW_RESULT）

## 一、路由守卫确认

- 游戏向经理在 Issue #135 合并后派发评论 **@程序线** 承接 **MB-01 + MB-02**（M-B 里程碑代码落地）。
- `.routing_active.txt` = 「程序线 美术线」，本轮程序线 active（CNB_BUILD_STAGE_NAME=程序线执行(下游解锁)）。
- 本部门被点名承接 → 执行（策划/测试/PM/运营跳过，不凑热闹）。

## 二、承接工作包领取结果

| # | 工作包 | 主责角色 | 优先级 | 依赖 | 状态 |
|---|--------|----------|:------:|:----:|:----:|
| MB-01 | L0/L1 轻量版 Demo（Web/H5 入口 + PlayState 状态流转） | client_dev + cocos_dev | P0 | M-A ✅ | ✅ DONE |
| MB-02 | 「点增强跳云」Demo 桩（消费 CloudSession/DownloadStatus/Enhancement 协议做假跳云流转） | client_dev + server_dev | P0 | M-A ✅ + MB-01 | ✅ DONE |

## 三、组内分工表（协作工作台 @分工 · group_audit 留痕）

M-B 为**部门级**跨角色工作包，经协作工作台拆 **5 子任务**派发给部门内角色：

| 子任务 | 承接角色 | 产出 |
|--------|---------|------|
| MB-01 L0/L1 漏斗 Demo 引擎 `funnel_demo`（Web/H5 入口 + PlayState 状态流转） | client_dev | `server/core/funnel_demo.py` |
| MB-01 L1 Cocos 小程序入口消费校验 + 协议绑定对齐 | cocos_dev | funnel_demo 双端 platform 分支 + 复用校验 |
| MB-02 假云/下载 Demo 桩 `cloud_stub`（消费 CloudSession/DownloadStatus/Enhancement） | server_dev | `server/core/cloud_stub.py` |
| PlayState 状态机护栏 + funnel/cloud 集成边界审校 | engine_dev | 非法流转拦截 + 集成回归 |
| M-B 阶段护栏（真云渲染留 UE 储备）+ 门禁 G2 回归统筹 | cto | `mb_funnel_runner.py` + `test_mb_funnel_demo.py` + 全量回归 |

- 协作工作台留痕：origin=程序线部门统一头 → DELEGATE(SPLIT) → 5 子任务派发 client_dev/cocos_dev/server_dev/engine_dev/cto → 各方 ACCEPTED → 并行产出 → COMPLETE → DONE
- 留痕落盘：`…/issue135/mb_funnel_demo_group_audit.json`（11 事件）

## 四、跨部门协作记录（request_peer）

| 协作方向 | 部门 | 协作内容 | 状态 |
|---------|------|---------|:----:|
| 上游消费 | 程序线（内部） | M-A 协议冻结（CloudSession/DownloadStatus/Enhancement/PlayState）✅ 已消费 | ✅ |
| 并行协作 | 美术线 | **MB-03** CG 锚点占位素材（WP-03 标准）→ 供漏斗②③段 CG 遮罩呈现；引擎已透传 `cg_anchor_playing` 遮罩态等待素材注入 | 🔗 并行（程序不阻塞，CG 素材到后由表现层接入）|
| 上游输入 | 策划线 | WP-01 漏斗五环节 + 三态状态机（已消费为状态流转基准） | ✅ |

> MB-03 由美术线本轮同步承接（经理级联派发），程序线以 `cg_anchor_playing` 占位态预留接入点，**不越权直投美术线**；G2 门禁由经理在 MB-01/02/03 齐备后统一验收。

## 五、REVIEW_RESULT 上报

**结论：✅ 通过**

**产出物**（落地于 `server/` + `…/issue135/`，见本 PR）：
1. `server/core/funnel_demo.py`（MB-01）— L0/L1 轻量版漏斗引擎，PlayState 状态机 + 非法流转护栏
2. `server/core/cloud_stub.py`（MB-02）— 假云/下载 Demo 桩，消费云会话/下载/增强协议 + 带宽调度 + 90% 预释放
3. `server/core/mb_funnel_runner.py` — 端到端演示 runner（L0 web + L1 cocos）
4. `server/tests/test_mb_funnel_demo.py` — G2 方向单测 **14 用例**
5. `mb_funnel_demo_实现说明.md` + `mb_funnel_demo_group_audit.json`

**门禁回归**：
- `test_mb_funnel_demo.py` **14/14** · `test_ma_protocol_freeze.py` **18/18** · `test_server.py` **25/25** · `test_pitfalls_scan.py` **14/14**（全绿）
- 端到端 runner：L0 网页 + L1 Cocos 漏斗五环节走通至 LOCAL_FULL（本地接管）

**关键要点**：
1. M-B 消费 M-A 协议（不新造私有格式），funnel/cloud 均为跨 L0/L1 共享逻辑，表现层随引擎（阶段合规）
2. 漏斗五环节走通：L0/L1 轻量入口 → 增强画质→CG 锚点 → 假跳云(Apply) → 边下边玩下载 → 90% 预释放 → 本地接管
3. 带宽感知调度复用 M-A 算法，云激活限速防「双输」，90% 预释放控成本
4. 阶段护栏成立：MVP 只落假跳云 Demo 桩，真云渲染/无缝切换留 UE 阶段储备

**下游建议**：MB-01/02/03 齐备后由经理验收 G2 → 解锁 M-C（Unity App 内容落地）。

---
*全程机制驱动：路由守卫 → 领取 MB-01/MB-02 → CollaborationWorkbench @分工(5 角色) → request_peer 登记美术线 MB-03 协作 → 代码落地+门禁回归 → REVIEW_RESULT 上报。*
