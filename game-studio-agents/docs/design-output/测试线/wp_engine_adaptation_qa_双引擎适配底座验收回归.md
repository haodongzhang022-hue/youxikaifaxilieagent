# wp_engine_adaptation_qa · 双引擎适配底座验收回归（测试线）

> 承接 PR #82（wp_engine_adaptation）合并后下游解锁的测试线工作包 `wp_engine_adaptation_qa`。
> 测试线部门统一头经协作工作台（CollaborationWorkbench）@分工 给 qa_engineer / auto_qa，全程留痕（group_audit）。

## 一、承接工作包领取结果

从 PR #82 合并后解锁的下游工作包中，**测试线负责 `wp_engine_adaptation_qa`**（双引擎适配底座验收测试），已领取：

| 工作包 | 模块 | 主责角色 | 产出物 | 状态 |
|--------|------|----------|--------|:----:|
| wp_engine_adaptation_qa | engine_adapters / engine_sync / deepseek_harness 接入验收 | qa_engineer + auto_qa | 双引擎适配底座验收回归 | ⛔ 阻塞（前置未满足） |

> 上游依赖：程序线 `wp_engine_adaptation_integration`（PR #87）— 当前 **conflict 未合并**。

## 二、组内分工表（经协作工作台 @分工 · group_audit）

| 子任务 | 承接角色 | 内容 | 状态 |
|--------|---------|------|:----:|
| wp_engine_adaptation_qa__sub1 | **qa_engineer** | 功能验收：engine_sync 同源校验闭环 + deepseek_harness 本地→回传 + engine_adapters 双栈契约 | ⛔ 阻塞 |
| wp_engine_adaptation_qa__sub2 | **auto_qa** | 自动化验收：test_engine_adaptation.sh 信号灯 + test_all_modules 全量回归 | ⛔ 阻塞 |

> 分工经协作工作台 delegate 记录，跨角色子任务全程留痕可审计（group_audit）。

## 三、跨部门协作记录（request_peer）

| 协作方向 | 部门 | 协作内容 | 状态 |
|---------|------|---------|:----:|
| 前置依赖 | **程序线** | wp_engine_adaptation_integration（PR #87）处于 **conflict 未合并**，main 上 test_engine_adaptation.sh 信号灯 RED，需程序线先解决冲突并合入集成 | ⛔ 待程序线处理 |
| 下游解锁 | 项目管理 | wp_engine_adaptation_qa 验收通过后方可解锁 wp_engine_adaptation_pm | ⏳ 待本包验收 |

## 四、REVIEW_RESULT 上报（向游戏向经理）

**结论：⛔ 打回（上游集成未合并，验收前置条件不满足）**

**产出物说明 / 阻塞原因（wp_engine_adaptation_qa）**：

1. **`test_engine_adaptation.sh` 信号灯 RED（退出码 1）**，实测运行：
   - 第 1 节「双引擎技术栈契约」**5 项断言失败**：测试断言旧版 API 输出（`typescript`/`blueprint` 小写、`scene -> .scene`/`map: .umap`、`引擎: cocos/unreal`、`resolve_engine('虚幻') = unreal`、`build_artifact_manifest`），但 main 上 `engine_adapters.py` 为 **PR #82 合并保留的新版 `EngineAdapter` 类架构**，缺少兼容层输出，断言不匹配；
   - 第 5 节「部门 Agent 引擎感知」**执行崩溃**：`ImportError: cannot import name '_engine_resource_hint' from 'department_agents'`——该函数在 main 上不存在；
2. **根因**：程序线 `wp_engine_adaptation_integration`（PR #87）负责补齐上述兼容层 + `_engine_resource_hint`，但该 PR 当前 **mergeable_state = conflict**，未合并到 main；main 与 test 文件处于新旧 API 不兼容状态。
3. **第 2/3/4 节通过**：engine_sync 同源校验（MATCH/MISSING/MISMATCH）、deepseek_harness 本地运行时、roles.yaml cocos_dev/ue_dev 岗位断言均 ✅。

**验收结论**：`wp_engine_adaptation_qa` 前置依赖（程序线 PR #87 合入）未满足，测试信号灯 RED，**本轮打回**。

**交付建议**：请程序线先解决 PR #87 的代码冲突并合入 `wp_engine_adaptation_integration`，使 `test_engine_adaptation.sh` 恢复全绿；合入后测试线重新领取 `wp_engine_adaptation_qa` 完成验收，通过后级联解锁项目管理 `wp_engine_adaptation_pm`。

> 全程机制驱动（task_scheduler + message_bus + role_collaboration）。
