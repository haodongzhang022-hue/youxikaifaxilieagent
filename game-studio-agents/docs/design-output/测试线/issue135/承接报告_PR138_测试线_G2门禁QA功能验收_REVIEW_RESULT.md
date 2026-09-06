# 🧪 测试线 · PR #138 下游解锁承接结果（G2 门禁 QA 功能验收 · Issue #135）

## 一、路由守卫确认

- 事件：PR #138（M-B MB-01/02 漏斗 Demo 桩）已合并 → post-merge 下游解锁（G2 门禁 + M-C）。
- `.routing_active.txt` = `程序线 测试线 项目管理` → 测试线 **active**（CNB_BUILD_STAGE_NAME=测试线执行(下游解锁)）。
- 合并 commit 路由标记显式声明：**测试线触发**（解锁 G2 单版体验门禁 + M-C）。
- 路由守卫通过：本部门被点名承接本轮测试线工作包 → 执行。

## 二、本轮工作包领取结果

| # | 工作包 | 模块 | 主责角色 | 优先级 | 状态 |
|---|--------|------|----------|:------:|:----:|
| G2-门禁 | M-B 交付物独立功能验收（G2 单版体验门禁**测试侧 GO 依据**） | testing | qa_engineer + auto_qa | HIGH | ✅ DONE |

> **判定**：M-B 三件套（程序 MB-01/02 + 美术 MB-03）合入后，G2 单版体验门禁验收需**独立 QA 功能验收**（区别于程序侧自测），
> 测试线独立验证漏斗五环节可用、协议契约合规、CG manifest 兼容、状态机护栏有效，为 G2 门禁提供测试侧 GO 依据。

## 三、组内分工表（协作工作台 @分工 · group_audit 留痕）

G2 门禁 QA 功能验收为**部门级跨角色验收包**，经协作工作台拆 2 子任务派发（留痕 `g2_gate_qa_group_audit.json`，8 事件）：

| 子任务 | 承接角色 | 产出 |
|--------|---------|------|
| MB-01 funnel_demo / MB-02 cloud_stub **独立功能验收**（37 断言场景：L0/L1 全流程、整除边界、序列化无副作用、非法流转护栏、CG 契约） | qa_engineer | 37/37 QA 功能验收断言全绿 |
| **全量回归统筹** + CG manifest 契约校验 + PlayState 状态机护栏边界 + 框架级回归确认 | auto_qa | 76 服务端回归 + routing 16/16 · stage 20/20 · adapters 25/25 · producer 24/24 全绿 |

- 协作工作台留痕：origin=测试线部门统一头 → DELEGATE(SPLIT) → 2 子任务派发 `qa_engineer` / `auto_qa` → 双方 ACCEPTED → COMPLETE → DONE
- 留痕落盘：`…/issue135/g2_gate_qa_group_audit.json`

## 四、验收结果（独立 QA 视角实测）

### ① 场景 1：L0 网页漏斗五环节全流程 — 16/16 通过 ✅
- 环节① LOCAL_LITE → ② CG_ANCHOR → ③ play_cg → ④ CLOUD_PLAY → ⑤ LOCAL_FULL 全流程走通
- EnhancementRequest 协议字段（player_id / session_token）正确
- 云会话激活 + 带宽预算 > 0（非恒 0）
- 下载 100% 达满 + 90% 预释放触发 + 本地接管成功
- 非法流转护栏：CG_ANCHOR 直接 download 被拒 / LOCAL_FULL 重复增强被拒

### ② 场景 2：L1 Cocos + 下载整除偏差 — 3/3 通过 ✅
- steps=3（整除偏差场景）下载仍达 100% + LOCAL_FULL
- steps=0 拒绝下载即接管（抛 ValueError）

### ③ 场景 3：cloud_stub 序列化无副作用 — 5/5 通过 ✅
- `serialized_report()` 不推进 `bytes_done`（无状态变更副作用）
- chunk_index 独立自增序号
- 90%+ 触发预释放信号

### ④ 场景 4：MB-03 CG manifest 契约兼容 — 7/7 通过 ✅
- `manifest_version` / `milestone` / `total_duration_s` 字段齐全
- 三镜头（A苍穹中枢/B星核晶体/C虚空侵蚀）齐备
- L0/L1 双引擎分支（`web_l0` / `cocos_l1`）可寻址
- transition 遮罩契约（portal）存在
- CG 总时长 5+4+5=14s 正确

### ⑤ 场景 5：PlayState 状态机护栏边界 — 6/6 通过 ✅
- 合法流转：LOCAL_LITE→CG_ANCHOR ✅ / CG_ANCHOR→CLOUD_PLAY ✅ / CLOUD_PLAY→LOCAL_FULL ✅
- 非法拦截：LOCAL_LITE→LOCAL_FULL ❌拦 / CG_ANCHOR→LOCAL_LITE ❌拦 / LOCAL_LITE→CLOUD_PLAY ❌拦

### ⑥ 全量回归
- test_mb_funnel_demo **19/19** · test_ma_protocol_freeze **18/18** · test_server **25/25** · test_pitfalls_scan **14/14** = **76/76 全绿**
- 框架级：test_routing **16/16** · test_stage_aware_engine **20/20** · test_engine_adapters **25/25** · test_producer_agent **24/24**
- e2e runner：L0 web + L1 Cocos 漏斗五环节走通至 **LOCAL_FULL**

## 五、跨部门协作记录（request_peer）

| 协作方向 | 部门 | 内容 | 状态 |
|---------|------|------|:----:|
| 被测对象 | 程序线 MB-01/02 | funnel_demo + cloud_stub 独立功能验收 | ✅ 37/37 |
| 被测契约 | 美术线 MB-03 | `cg_asset_manifest` 注入契约兼容性校验 | ✅ 7/7 |
| 下游验收 | 项目管理 WP-04 | G2 门禁测试侧 GO 依据，供 release_manager 组织验收 | 🔗 供 G2 |
| 上游消费 | 程序线内部 | M-A 协议消息 dataclass 契约核验 | ✅ |

## 六、REVIEW_RESULT 上报

**结论：✅ 通过（G2 门禁测试侧 GO）**

**产出物说明**：
1. **37 项独立 QA 功能验收断言全绿** — L0/L1 漏斗全流程、整除偏差、序列化无副作用、CG 契约、状态机护栏
2. **76 服务端回归全绿** + 框架级 4 套回归（routing 16/16 / stage 20/20 / adapters 25/25 / producer 24/24）
3. **e2e runner** 独立复跑：L0 web + L1 Cocos 均走通至 LOCAL_FULL
4. **留痕**：`…/issue135/g2_gate_qa_group_audit.json`（8 事件）

**关键要点**：
1. 测试线独立验证（非程序侧自测）M-B 交付物满足 WP-04 G2 单版体验门禁功能要求
2. 漏斗五环节 L0/L1 → CG 锚点 → 假跳云 → 下载 100% → 本地接管全流程可走通
3. CG manifest 契约与 funnel_demo `cg_anchor_playing` 遮罩态接入点兼容
4. PlayState 状态机护栏有效，非法流转全部被拒

**交付建议**：
- G2 门禁测试侧 GO 依据已齐备，供项目管理 release_manager 组织 G2 门禁正式验收
- 正式 G2 验收通过后 → 解锁 M-C（Unity App 内容落地）
- 测试线 M-D/M-E 阶段多版并存回归测试基线待 G4 门禁解锁后承接

---
*机制驱动：post-merge 路由激活（测试线 active）→ 领取 G2 QA 验收 → CollaborationWorkbench 组内 @分工(2 角色) → request_peer 跨部门登记 → REVIEW_RESULT 上报。*
