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

如果环境变量不可用，模块还会尝试从 `git remote.origin.url` 探测。

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
```

## 所有角色如何引用

所有角色的 prompt（`.cnb/settings.yml`）和流水线 prompt（`.cnb.yml`）中，
都需要包含以下指令：

```
【仓库自适应识别】
在需要 @ 其他角色时，必须先运行 `python3 config/agent_identity.py`
（或引用 AgentIdentity 模块）从环境变量 CNB_REPO_SLUG 探测当前仓库，
然后用 `@<探测到的slug>(角色名)` 完整格式召唤。
禁止写死仓库路径，禁止用裸 @CodeBuddy。
```

## 跨仓库 vs 同仓库

| 场景 | 推荐做法 |
|------|---------|
| **同仓库** | 可直接 `@角色名`，但建议仍用完整格式 `@owner/repo(角色名)` 消除歧义 |
| **跨仓库** | **必须**用完整格式 `@owner/repo(角色名)` 带壳召唤，否则权限受限 |
| **未知仓库** | 优先用 AgentIdentity 模块探测；若探测失败，显式告警不静默使用裸格式 |

## 测试

```bash
python3 game-studio-agents/config/agent_identity.py   # 自测
bash game-studio-agents/tests/test_agent_identity.sh  # 测试信号灯
```
