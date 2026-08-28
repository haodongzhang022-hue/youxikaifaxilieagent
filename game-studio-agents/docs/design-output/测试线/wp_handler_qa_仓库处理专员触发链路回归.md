# wp_handler_qa · 仓库处理专员触发链路回归验证

- **工作包**：wp_handler_qa 回归验证仓库处理专员触发链路正确性
- **部门**：测试线（部门整体派发）
- **触发源**：PR #52 合并 + 程序线 wp_handler_program 验收通过 → 级联解锁
- **主责角色**：qa_engineer + auto_qa（组内 @分工）
- **依赖**：wp_handler_program ✅（PR #52 合并落地）、wp_review_qa ✅（PR #75 已合并）
- **产出物类型**：test_regression_doc（回归验证报告）

## 一、验证结论总览

| 验证项 | 结论 | 依据 |
|---|---|---|
| 1. 仓库处理专员在评审-修复闭环触发链路正确 | ✅ | test_review_fix_loop.sh 8/8、test_dept_npc_pipeline.sh 16/16 |
| 2. 标签驱动流程（修复→打标签→触发新一轮评审）正确 | ✅ | .cnb.yml 闭环打标签驱动（适合推送/合并/关闭），无 push 依赖 |
| 3. 召唤优先级链（仓库处理专员→CodeBuddy 兜底）生效 | ✅ | test_agent_identity.sh 18/18、agent_identity.py 自测通过 |
| 4. PR #75（wp_review_qa）验收通过后级联到 PM | ✅ | PR #75 已合并（wp_review_qa 落地），下游可解锁项目管理 |

**综合结论：✅ 通过（wp_handler_qa 验收通过，可解锁下游项目管理 wp_handler_pm）**

## 二、逐项验证明细

### 1. 仓库处理专员在评审-修复闭环触发链路正确性（qa_engineer）

**回归验证**：
- `test_review_fix_loop.sh` **8/8 通过**：评审-修复闭环上下文路由正确、闭环健康判别正确（修复打标签后正常待评审，不误报中断）；
- `test_dept_npc_pipeline.sh` **16/16 通过**：六大部门（含测试线）在 issue.open + pull_request.merged 两事件链路中均正确接通，部门执行阶段含组内协作 + 跨部门协作指令；
- `.cnb/settings.yml` 第 139 行正确注册 **仓库处理专员** 角色，明确「本仓库唯一执行者」身份，与 CodeBuddy 并存互补（本仓库修复优先仓库处理专员，CodeBuddy 通用兜底）；
- `.cnb.yml` 评审-修复闭环中仓库处理专员为**主修复角色**，评审给意见后由仓库处理专员就地修复并**打标签**标记状态（适合推送/适合合并/适合关闭）。

**结论**：触发链路从「评审给意见」→「仓库处理专员就地修复」→「打标签」→「触发下一轮评审」全链路正确接通，无 push 依赖、无身份错位。

### 2. 标签驱动流程验证（auto_qa）

**回归验证**：
- `.cnb.yml` 评审-修复闭环明确**本系统故意设计不允许 push**，闭环通过**打标签**驱动；
- 打标签流程闭环：修复完成 → 打「适合推送」标签 → 触发新一轮评审；评审通过 → 打「适合合并」标签 → 进入合并门禁；无法解决 → 打「适合关闭」标签 → 标记关闭；
- `test_review_fix_loop.sh` 8/8 验证闭环健康判别：修复已打标签、新评审尚在下一轮 → 正常待评审，不误报中断；真正中断须有硬性信号（打标签失败/评审超时）；
- 仓库处理专员为本仓库**唯一**打标签执行者（`.cnb/settings.yml` 第 144 行），其他角色发现需打标签时必须召唤仓库处理专员。

**结论**：标签驱动流程「修复 → 打适合推送标签 → 触发新一轮评审」完整正确，无需 push 事件，闭环机制在测试中可复现。

### 3. 召唤优先级链验证（auto_qa）

**回归验证**：
- `test_agent_identity.sh` **18/18 通过**，其中关键断言：
  - **[14/18]** 召唤优先级链正确：**仓库处理专员 → CodeBuddy（逐个降级）**；
  - **[13/18]** 仓库处理专员角色已注册；**[7/18]** 默认优先召唤仓库处理专员；
  - **[15/18]** 可显式指定 role=CodeBuddy 兜底召唤；
  - **[10/18][11/18]** 召唤行独立裸@行、可被平台解析；
  - **[16/18]** 仅输出唯一召唤行，无多重触发；
- `agent_identity.py` 自测通过：仓库探测（env_cnb_repo_slug）、同仓库/跨仓库策略、召唤格式生成全部正确；
- 跨仓库召唤：`@otherorg/otherrepo(仓库处理专员)` 自适应格式正确，禁止写死路径。

**结论**：召唤优先级链「仓库处理专员 → CodeBuddy 兜底」在 agent_identity.py 中固化，实际运行中优先召唤仓库处理专员，其不可用/权限不足时降级到 CodeBuddy（仅建议、不执行打标签），**同一时刻只召唤一个角色**，符合触发安全控制。

### 4. PR #75（wp_review_qa）验收后级联到 PM（qa_engineer）

**回归验证**：
- **PR #75 已合并**（`mergeable_state: merged`，标题「docs: 测试线承接wp_review_qa验收评审无推送权限边界回归」），产出 `wp_review_qa_验收评审无推送权限边界回归.md` 已落地到 `game-studio-agents/docs/design-output/测试线/`；
- wp_review_qa 5 组回归用例（R-1~R-5）已覆盖：评审 prompt 无推送诱导、运行不触发推送、发现问题交 CodeBuddy 闭环、越权操作被拦截、标签驱动闭环成立；
- wp_review_qa 结论为「✅ 待实测落地（配置已就绪，运行回归后终验）」——配合本轮 wp_handler_qa 实际回归，评审无推送边界从配置声明到运行行为已对齐；
- 按游戏向经理编排，wp_review_qa 验收通过后 → 解锁下游**项目管理 wp_review_pm**（评审→建议→CodeBuddy 推送闭环验收）。

**结论**：PR #75 已合并，wp_review_qa 产出落地，测试线评审治理回归已闭环；下游可解锁项目管理 wp_review_pm + 本轮 wp_handler_qa 级联的 wp_handler_pm。

## 三、组内分工表（经协作工作台 @分工 · group_audit）

| 子任务 | 承接角色 | 内容 | 状态 |
|---|---|---|---|
| wp_handler_qa__sub1 | qa_engineer | 回归验证仓库处理专员在评审-修复闭环触发链路正确性 + 标签驱动流程 + PR#75 级联 PM | ✅ DONE |
| wp_handler_qa__sub2 | auto_qa | 验证召唤优先级链（仓库处理专员→CodeBuddy 兜底）在实际运行中生效 + 回归测试执行 | ✅ DONE |

> 分工经 `role_collaboration.CollaborationWorkbench.delegate` 拆派，全程留痕可审计（DELEGATE SPLIT + 各角色 SUB_ACCEPT/SUB_COMPLETE）。

## 四、跨部门协作记录（request_peer）

| 方向 | 部门 | 协作内容 | 状态 |
|---|---|---|---|
| 上游消费 | 程序线 | 消费 wp_handler_program 验证报告做回归依据 | ✅ 已消费 |
| 上游消费 | 程序线 | 消费 wp_review_role/route（评审只读边界）做权限回归依据 | ✅ 已消费 |
| 下游解锁 | 项目管理 | wp_handler_pm + wp_review_pm：评审→建议→CodeBuddy 推送闭环验收 | ⏳ 待解锁 |
| 下游解锁 | 运营线 | wp_handler_ops：对外文档同步角色变更 | ⏳ 待 PM 通过 |

## 五、REVIEW_RESULT 上报

**结论：✅ 通过**

**产出物说明（wp_handler_qa）**：
- 本回归验证报告（`wp_handler_qa_仓库处理专员触发链路回归.md`）；
- 4 项验证全部通过：仓库处理专员触发链路、标签驱动流程、召唤优先级链、PR#75 级联；
- 回归测试全绿：`test_review_fix_loop.sh` 8/8、`test_agent_identity.sh` 18/18、`test_dept_npc_pipeline.sh` 16/16、`test_dispatch_capability.sh` 16/16、`test_role_collaboration.sh` 33/33；
- PR #75（wp_review_qa）已合并，评审无推送边界回归闭环成立；
- 验收通过后**解锁下游** → 项目管理 `wp_handler_pm`（评审-修复闭环验收）。

> 全程机制驱动（task_scheduler + message_bus）。测试线 wp_handler_qa 验收通过，级联解锁项目管理。
