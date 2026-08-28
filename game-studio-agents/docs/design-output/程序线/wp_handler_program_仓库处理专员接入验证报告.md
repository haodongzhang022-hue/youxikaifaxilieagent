# 程序线 · wp_handler_program 验证报告

> 工作包：`wp_handler_program` — 验证仓库处理专员在流水线中的正确接入与召唤链路
> 责任部门：程序线（部门整体派发）· 触发源：PR #52 合并后下游解锁
> 主责角色：cto / engine_dev / tools_dev / server_dev（组内 @分工）
> 状态：✅ 验证通过

## 一、验证结论总览

| 验证项 | 结论 | 依据 |
|---|---|---|
| 1. 仓库处理专员角色注册正确 | ✅ | `.cnb/settings.yml` 已注册「仓库处理专员」角色，与 CodeBuddy 并存互补 |
| 2. 评审-修复闭环标签驱动链路正确 | ✅ | `.cnb.yml` 闭环打标签驱动（适合推送/合并），无 push 依赖 |
| 3. agent_identity.py 自适应召唤格式正确引用 | ✅ | 全角色 prompt 引用，18/18 测试通过 |
| 4. PR#59/#64 与 PR#52 冲突可解决 | ✅ | 冲突文件与 PR#52 改动重叠，rebasing 后可解决 |

**综合结论：✅ 通过（wp_handler_program 验收通过，可解锁下游测试线 wp_handler_qa）**

## 二、逐项验证明细

### 1. 仓库处理专员角色注册正确（cto）
- `.cnb/settings.yml` 第 139 行定义 `仓库处理专员` 角色，为本仓库**唯一执行者**；
- 与 CodeBuddy **并存互补**：本仓库修复优先仓库处理专员，CodeBuddy 通用兜底；
- 召唤优先级链固化：**仓库处理专员 → CodeBuddy（逐个降级，一次只召唤一个）**；
- 修复闭环统一由仓库处理专员就地修复并**打标签**标记状态（适合推送/适合合并/适合关闭）。

### 2. 评审-修复闭环标签驱动触发链路正确（engine_dev）
- `.cnb.yml` 评审-修复闭环**改为打标签驱动**：评审给意见 → 仓库处理专员修代码 → **打标签**触发下一轮 pull_request 评审，不依赖 push 事件；
- 系统**故意设计不允许 push**：任何 NPC 不得尝试 push（会 403），闭环通过标签驱动；
- `test_review_fix_loop.sh` **8/8 通过**：上下文路由、闭环健康判别（正常待评审 vs 真正中断）均正确；
- `test_dept_npc_pipeline.sh` **16/16 通过**：6 部门下游解锁执行阶段（含程序线）链路全部接通。

### 3. agent_identity.py 自适应召唤格式正确引用（tools_dev）
- `.cnb/settings.yml` 与 `.cnb.yml` 各角色 prompt 均引用 `agent_identity.py`（AgentIdentity）自适应识别仓库上下文，**禁止写死路径**；
- `python3 game-studio-agents/config/agent_identity.py` 自测通过：仓库探测、召唤格式、跨仓策略、操作建议全部正确；
- `test_agent_identity.sh` **18/18 通过**：含召唤格式带壳、跨仓识别、唯一召唤行、防多重触发、无裸召唤等全部通过。

### 4. PR#59/#64 与 PR#52 冲突可解决（server_dev）
- PR #52（已合并）改动 `.cnb/settings.yml` / `.cnb.yml` 成为当前基线；
- PR #59（禁止评审角色输出权限推送内容）与 PR #64（修正召唤格式指引）均 open，`mergeable_state = conflict`；
- 冲突文件与 PR #52 改动重叠（`.cnb.yml` / `settings.yml`），属**机械性冲突**：两个 PR 均简化评审 prompt / 召唤格式指引，与 PR #52 的标签驱动、仓库处理专员方向一致，**rebasing 到 main 后即可解决**；
- 冲突实际解决由**仓库处理专员**（打标签唯一执行者）承接，程序线已核验其可解决性。

## 三、组内分工表（经协作工作台 · group_audit）

| 子任务 | 承接角色 | 内容 | 状态 |
|---|---|---|---|
| wp_handler_program__sub1 | cto | 验证角色注册与召唤优先级链 | ✅ DONE |
| wp_handler_program__sub2 | engine_dev | 验证闭环标签驱动链路 | ✅ DONE |
| wp_handler_program__sub3 | tools_dev | 验证 agent_identity 引用 + 回归测试 | ✅ DONE |
| wp_handler_program__sub4 | server_dev | 核验 PR#59/#64 冲突可解决性 | ✅ DONE |

> 工作包跨 4 个程序角色，经 `role_collaboration.CollaborationWorkbench.delegate` 组内 @分工拆派，全程留痕可审计（DELEGATE SPLIT + 各角色 SUB_ACCEPT/SUB_COMPLETE 共 9 条事件）。

## 四、跨部门协作记录（request_peer）
- 本工作包为机制验证，无跨部门执行依赖；
- 关联跨部门点：验证通过后解锁**下游测试线 wp_handler_qa**（依赖 wp_handler_program ✅）；
- 冲突解决由**仓库处理专员**（仓库处理岗，非六大执行部门）承接，程序线已核验。

## 五、REVIEW_RESULT 上报

**结论：✅ 通过**

**产出物说明（wp_handler_program）**：
- 本验证报告（`wp_handler_program_仓库处理专员接入验证报告.md`）；
- 4 项验证全部通过：角色注册、标签驱动闭环、agent_identity 自适应引用、冲突可解决；
- 回归测试全绿：`test_agent_identity.sh` 18/18、`test_dept_npc_pipeline.sh` 16/16、`test_review_fix_loop.sh` 8/8、YAML 校验通过；
- 验收通过后**解锁下游** → 测试线 `wp_handler_qa`（回归验证仓库处理专员触发链路）。

> 全程机制驱动（task_scheduler + message_bus）。程序线 wp_handler_program 验收通过，级联解锁测试线。
