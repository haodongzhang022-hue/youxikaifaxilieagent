# wp_handler_ops · 对外文档同步角色变更

- **工作包**：wp_handler_ops 对外文档同步角色变更（仓库处理专员角色对外说明）
- **部门**：运营线
- **触发源**：项目管理 wp_handler_pm 验收通过 → 解锁下游运营线
- **主责角色**：data_analyst + game_operator（组内 @分工）
- **依赖**：wp_handler_pm ✅（项目管理评审-修复闭环验收通过）、wp_handler_qa ✅（测试线回归验证通过）
- **产出物类型**：ops_doc_sync（运营文档同步报告）

## 一、变更要点梳理

### 1. 新增角色：仓库处理专员

PR #52 合并引入 **仓库处理专员**（Repository Handler）角色，与 CodeBuddy **并存互补**：

| 能力项 | 说明 |
|--------|------|
| 角色定位 | 本仓库**唯一执行者**，集成打标签 / 修复 / 仓库操作能力 |
| 与 CodeBuddy 关系 | 本仓库修复优先仓库处理专员，CodeBuddy 通用兜底 |
| 打标签唯一性 | 只有仓库处理专员可以执行打标签操作（适合推送/合并/关闭） |
| 召唤格式 | `@<当前仓库slug>(仓库处理专员)`，禁止裸 @ |
| 实现 | `.cnb/settings.yml` npc.roles + `agent_identity.py` KNOWN_ROLES |

### 2. 召唤优先级链

```
仓库处理专员 → CodeBuddy → (兜底停止)
```

- 同一时刻**只召唤一个角色**，防止多重 NPC 同时触发；
- 仓库处理专员不可用 / 权限不足时降级到 CodeBuddy（仅建议、不执行打标签）。

### 3. 对外文档需同步位置

| 文档 | 需同步内容 |
|------|-----------|
| README.md（仓库根） | ① 核心编排角色表补充「仓库处理专员」；② Agent 清单补充该角色 |
| README.md「跨仓库 NPC 召唤指南」 | 召唤格式示例补充仓库处理专员 |
| 运营线 README | 承接工作包记录补充本轮两个新工作包 |

## 二、同步执行结果

- **README.md**：核心编排角色表新增「仓库处理专员」行，标注用途为「本仓库修复/打标签唯一执行者」；
- **README.md**：跨仓库 NPC 召唤指南同步新增仓库处理专员召唤说明；
- **运营线 README**：承接工作包表新增 wp_handler_ops / wp_review_ops 记录。

## 三、组内分工表（经协作工作台 @分工 · group_audit）

| 子任务 | 承接角色 | 内容 | 状态 |
|--------|---------|------|------|
| wp_handler_ops__sub1 | data_analyst | 梳理仓库处理专员角色变更要点，产出对外说明文档 | ✅ DONE |
| wp_handler_ops__sub2 | game_operator | 将角色变更同步到对外运营文档，检查并更新 README 角色清单 | ✅ DONE |

> 分工经 `role_collaboration.CollaborationWorkbench.delegate` 拆派，全程留痕可审计。

## 四、跨部门协作记录（request_peer）

| 方向 | 部门 | 协作内容 | 状态 |
|------|------|---------|------|
| 上游消费 | 项目管理 | 消费 wp_handler_pm 验收报告（评审-修复闭环验收） | ✅ 已消费 |
| 上游消费 | 测试线 | 消费 wp_handler_qa 回归验证报告（触发链路正确性） | ✅ 已消费 |
| 上游消费 | 程序线 | 消费 wp_handler_program 接入验证报告 | ✅ 已消费 |

## 五、REVIEW_RESULT 上报

**结论：✅ 通过**

**产出物说明（wp_handler_ops）**：
- 本对外文档角色变更同步报告（`wp_handler_ops_对外文档角色变更.md`）；
- 已梳理仓库处理专员角色变更要点（角色定位、召唤优先级链、打标签唯一性）；
- 已同步更新外部文档（README.md 角色表 + 召唤指南 + 运营线 README）。

> 全程机制驱动。运营线 wp_handler_ops 验收通过，外部文档已同步角色变更。
