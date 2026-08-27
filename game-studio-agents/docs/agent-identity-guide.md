# Agent 仓库自适应识别与 @ 召唤指南

## 背景

CNB 平台的 NPC 角色可以在**任意仓库**被跨仓库召唤。例如，其他仓库的评审 NPC
在评审到需要修复时，需要召唤 `dongdongxiaozu/youxikaifaxilieagent(CodeBuddy)`
来执行修复——但这个格式**不能写死**，因为：

1. 触发仓库可能不是 `youxikaifaxilieagent`，而是其他仓库；
2. 组织也可能不是 `dongdongxiaozu`；
3. 每次触发的仓库上下文不同，需要**自适应识别**。

## 模块位置

`config/agent_identity.py` —— 通用 Agent 身份自适应模块

## 如何自适应识别当前仓库

CNB 平台流水线运行时会注入以下环境变量，模块从中自动读取：

| 环境变量 | 说明 | 示例 |
|---------|------|------|
| `CNB_REPO_SLUG` | 完整仓库路径 `owner/repo` | `dongdongxiaozu/youxikaifaxilieagent` |
| `CNB_GROUP_SLUG` | 组织名 | `dongdongxiaozu` |
| `CNB_REPO_NAME` | 仓库名 | `youxikaifaxilieagent` |
| `CNB_BUILD_WEB_URL` | 构建 Web URL（可解析仓库） | `https://cnb.cool/...` |

如果环境变量不可用，模块还会尝试从 `git remote.origin.url` 探测，
且会**从当前目录向上查找 `.git`** 定位仓库根再读取 remote，保证评审在
任意子目录执行时也能探测到「当前被评审的仓库」。

## 核心 API

```python
from agent_identity import get_identity

identity = get_identity()

# 1. 探测仓库上下文
ctx = identity.detect_repo_context()
print(ctx.full_slug)          # "dongdongxiaozu/youxikaifaxilieagent"
print(ctx.owner)              # "dongdongxiaozu"
print(ctx.repo_name)          # "youxikaifaxilieagent"

# 2. 生成召唤格式
mention = identity.get_codebuddy_mention()
# "@dongdongxiaozu/youxikaifaxilieagent(CodeBuddy)"

fixer = identity.get_fixer_mention()
# "@dongdongxiaozu/youxikaifaxilieagent(仓库修复专员)"

# 3. 判断策略
strategy = identity.decide_mention_strategy("otherorg/otherrepo")
# strategy['strategy'] == 'cross_repo'
# strategy['mention'] == '@otherorg/otherrepo(CodeBuddy)'
# strategy['recommendation'] == '跨仓库必须使用完整格式...'

# 4. 【评审 NPC 专用】按「当前触发评审的仓库」自适应生成召唤 CodeBuddy 操作建议
advice = identity.get_review_operational_advice()
# 输出可直接粘贴进 PR 评论的操作建议：
#   「召唤本仓库 CodeBuddy · 仓库自适应识别」
#   当前触发评审的仓库为 `dongdongxiaozu/youxikaifaxilieagent`...
#   请召唤本仓库 CodeBuddy，评论正文用裸 `@CodeBuddy` 触发召唤（平台认裸 @）
#   带壳格式 `@dongdongxiaozu/youxikaifaxilieagent(CodeBuddy)` 仅作身份/权限标识
#   组织名 / 仓库名均自适应探测，禁止写死

# 也支持按目标仓库（跨仓）生成：
advice_cross = identity.get_review_operational_advice("otherorg/otherrepo")
# '@otherorg/otherrepo(CodeBuddy)'
```

> **评审场景硬性要求**：评审 NPC（代码审查员）在生成「召唤本仓库 CodeBuddy」的
> 操作建议时，**必须程序化调用 `get_review_operational_advice()`**（便捷函数
> `review_operational_advice()`），让它根据**当前触发评审的仓库**自动探测
> 组织名 + 仓库名（都不写死）。
>
> **⚠️ 触发召唤格式（v1.2 修正，对齐平台实际解析规则）**：
> - 平台 NPC 召唤解析器**只把裸 `@CodeBuddy` 解析成召唤事件**（触发 `comment@npc`）。
> - 带壳完整格式 `@组织/仓库(CodeBuddy)` **不被平台解析为召唤事件**，仅作身份/权限标识，
>   写在描述里即可。
> - 所以**真正要触发召唤，评论正文必须用裸 `@CodeBuddy`**（本仓库评论里即命中本仓库
>   CodeBuddy，具备推送/合并权限）。

## 所有角色如何引用

所有角色的 prompt（`.cnb/settings.yml`）和流水线 prompt（`.cnb.yml`）中，
都需要包含以下指令：

```
【仓库自适应识别】
在需要 @ 其他角色时，必须先运行 `python3 config/agent_identity.py`
（或引用 AgentIdentity 模块）从环境变量 CNB_REPO_SLUG / git remote 探测
当前仓库（组织名 + 仓库名不写死）。
**触发召唤用裸 `@CodeBuddy`**（平台解析器只认裸 @ 角色名）；带壳格式
`@<slug>(角色名)` 仅作身份/权限标识，不触发召唤。

【评审 NPC 召唤 CodeBuddy】
生成召唤本仓库 CodeBuddy 的操作建议时，必须调用
`get_review_operational_advice()`，按「当前触发评审的仓库」自适应探测，
并在建议中引导用裸 `@CodeBuddy` 触发召唤。
```

## 跨仓库 vs 同仓库

| 场景 | 触发召唤（平台认裸 @） | 身份/权限标识（带壳格式） |
|------|----------------------|---------------------------|
| **同仓库** | 评论正文用裸 `@CodeBuddy`，平台识别触发 | `@owner/repo(CodeBuddy)` 仅作身份标识 |
| **跨仓库** | 在**当前评论所在仓库**用裸 `@角色名`，命中该仓库对应角色 | `@目标仓库/角色名` 标识目标角色身份 |
| **未知仓库** | 优先用 AgentIdentity 探测；未探测到则显式告警 | 带壳格式仅在探测成功后作为身份标识 |

## 测试

```bash
python3 game-studio-agents/config/agent_identity.py   # 自测
bash game-studio-agents/tests/test_agent_identity.sh  # 测试信号灯
```
