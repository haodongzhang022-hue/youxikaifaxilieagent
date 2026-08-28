# wp_module_acceptance · 功能模块验收测试体系

- **工作包**：wp_module_acceptance 功能模块验收测试体系
- **部门**：测试线
- **主责角色**：qa_engineer + auto_qa
- **模块**：testing / 功能模块验收
- **产出物类型**：test_module_acceptance（按功能模块验收测试体系）

## 一、验收原则

本工作包确立了**以功能模块为单位**的验收测试体系：

1. **模块粒度**：以每个功能模块为测试单元，不以小功能点为准；
2. **实际支撑**：每个模块的验收确认均以**实际运行测试脚本的断言通过**为唯一依据；
3. **可证明**：测试脚本可运行、可复现、结果可查看；
4. **可反驳**：若断言不通过，则对应模块验收不通过，可回溯定位。

## 二、功能模块测试脚本清单

所有脚本位于 `game-studio-agents/tests/modules/` 目录：

| # | 功能模块 | 测试脚本 | 断言数 | 状态 |
|---|---------|---------|-------|------|
| 1 | 消息总线 | test_mod_message_bus.sh | 9 | ✅ |
| 2 | 任务调度 | test_mod_task_scheduler.sh | 9 | ✅ |
| 3 | Agent 内核 | test_mod_agent_core.sh | 7 | ✅ |
| 4 | Agent 身份自适应 | test_mod_agent_identity.sh | 6 | ✅ |
| 5 | 角色协作层 | test_mod_collaboration.sh | 8 | ✅ |
| 6 | 统一派发能力 | test_mod_dispatch.sh | 8 | ✅ |
| 7 | 游戏向经理 | test_mod_game_producer.sh | 9 | ✅ |
| 8 | 部门 Agent | test_mod_department_agents.sh | 11 | ✅ |
| 9 | 进度督导 | test_mod_progress_pusher.sh | 9 | ✅ |
| 10 | 发版质量门禁 | test_mod_release_gate.sh | 7 | ✅ |
| 11 | 生态角色 | test_mod_ecosystem_roles.sh | 6 | ✅ |
| 12 | 预设实例化 | test_mod_instantiator.sh | 6 | ✅ |
| 13 | 合并确认 | test_mod_merged_confirm.sh | 7 | ✅ |
| 14 | 借鉴学习 | test_mod_reference_learner.sh | 4 | ✅ |
| 15 | 端到端联动 | test_mod_end_to_end.sh | 6 | ✅ |

**合计：15 个功能模块，112 项断言，全部通过。**

## 三、验收结论

✅ **15/15 个功能模块全部验收通过**，每个模块的确认均以实际测试结果为支撑，
具备可运行、可复现、可证明、可反驳的验收特征。

## 四、与 CI 集成

`test_all_modules.sh` 已接入 `.cnb.yml` 的 `pull_request` 测试信号灯阶段，
PR 提交时自动运行全部 15 个模块测试，任一模块失败即阻塞合并。

## 五、运行方法

```bash
# 一键运行全部
bash game-studio-agents/tests/modules/test_all_modules.sh

# 单独运行某模块
bash game-studio-agents/tests/modules/test_mod_message_bus.sh
```
