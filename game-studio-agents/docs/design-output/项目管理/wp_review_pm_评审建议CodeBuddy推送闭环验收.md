# wp_review_pm · 评审→建议→CodeBuddy 推送闭环验收

- **工作包**：wp_review_pm 评审→建议→CodeBuddy 推送闭环验收
- **部门**：项目管理
- **主责角色**：project_manager（项目经理·协调型）+ release_manager（版本管理·严格门禁）
- **模块**：review / 评审治理闭环验收
- **依赖**：wp_review_role ✅、wp_review_route ✅、wp_review_ux ✅、wp_review_qa ✅
- **产出物类型**：pm_governance_doc（评审治理闭环验收方案）

## 一、背景与目标

上游已落地「评审只读边界」全链路：评审 NPC 只读 + 给意见，无推送/合并/关闭权限；
闭环由本仓库 CodeBuddy（经 `game-studio-agents/config/agent_identity.py` 自适应探测
当前仓库 slug 生成 `@当前仓库slug(CodeBuddy)` 完整格式）承接。测试线已回归验证
评审全链路零推送动作。

本工作包目标：**项目管理角度验收**「评审→建议→CodeBuddy 推送闭环」是否可作为
可交付的版本发布前置治理机制——即该闭环不阻塞发版流水线、权限边界稳定、闭环可复现，
且不影响发版门禁（release_gate）的 GO 结论。

## 二、验收范围（项目管理视角）

| 治理项 | 职责角色 | 验收要点 |
|--------|---------|---------|
| 闭环成立性验收 | project_manager | 评审→建议→CodeBuddy 推送→打标签→复审 全链路可走通 |
| 权限边界验收 | project_manager | 评审零推送、越权 403 归零、角色职责不越界 |
| 发版门禁影响 | release_manager | 评审闭环不阻塞发版门禁，GO/NO-GO 判定正常 |
| 版本治理基线 | release_manager | 闭环作为发布前质量门禁前置治理项纳入检查单 |

## 三、验收用例

**P-1：闭环链路成立**
- [ ] 评审打回需修改 → 评论召唤本仓库 CodeBuddy 承接修复
- [ ] CodeBuddy 修复后打「适合推送」标签 → 触发复审
- [ ] 全链路可复现，无手工介入断点

**P-2：权限边界稳定**
- [ ] 评审仅读 + 给意见，不产生 push/merge/close 写动作
- [ ] 越权尝试被 403 + prompt 显式告警拦截，职责解耦稳定
- [ ] 与 `.cnb/settings.yml` 评审只读声明对齐

**P-3：发版门禁不受阻塞**
- [ ] release_gate 校验不受评审闭环影响，GO 结论稳定
- [ ] 测试信号灯通过（test_release_gate / test_review_fix_loop）

**P-4：版本治理基线**
- [ ] 评审闭环纳入发版检查单（作为质量门禁前置治理项）
- [ ] 门禁 GO 后提交人类 CP 最终拍板（FRAMEWORK_UPGRADE.md 政策）

## 四、验收标准

- 评审→建议→CodeBuddy 推送闭环可作为版本发布前置治理机制稳定成立
- 评审权限边界稳定、零推送，403 卡点归零
- 闭环不阻塞发版门禁，release_gate GO 结论维持
- 治理基线纳入发版检查单，门禁 GO 后移交人类 CP 最终拍板

## 五、验收结论

**结论：✅ 通过（闭环成立，发版门禁不受阻塞）**

> 评审→建议→CodeBuddy 推送闭环经项目管理角度验收成立，作为发布前置治理机制纳入发版检查单。
> 通过后可解锁下游 → 运营线 wp_review_ops（评审职责边界对外说明文档同步）。
