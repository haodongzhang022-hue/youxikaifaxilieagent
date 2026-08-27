# 合并确认机制（Merged Confirm Mechanism）

> 针对已打上「已合并」标签但仍处于 open 状态的 Issue，由**合并确认员**（独立于
> CodeBuddy 的另一个 NPC 角色）做工作内容确认：判断当前对话是否还有内容需要推进，
> 还是已适合关闭 / 需要新建 Issue 承接后续任务。

---

## 一、为什么需要这个机制

在事件驱动流水线中，很多 Issue 的代码改动已通过 PR 合并到 `main`，但 Issue 本身
仍处于 open 状态（因为流水线只负责合并代码，未主动清理已完成的 Issue）。长期积累
会导致：

- open Issue 列表混乱，难以区分「还在推进」与「已完成」；
- 已合并的 Issue 后续若有下一阶段任务，没有自动派发机制承接；
- 需要人工逐个查看评论历史判断是否可关闭，效率低。

**核心目标**：类似现有审查机制（评审→修复→重推闭环），通过定时探查带「已合并」
标签的 Issue 数量，数量 > 0 即触发**合并确认员**逐个确认，自动决定关闭 / 新建 / 保留。

---

## 二、触发链（事件驱动，无需人工）

```
crontab（每日 06:00 Asia/Shanghai）
   └─ 合并标签探查（config/merged_confirm_agent.py 自测）
        └─ 合并确认员 NPC 逐个确认（npc:go）
             ├─ N == 0 → 无需确认，结束
             └─ N > 0 → 逐个确认：
                  ├─ 已合并且无后续 → 关闭 Issue
                  ├─ 已合并有后续（未派发）→ 新建 Issue 承接 + 关闭原 Issue
                  └─ 有阻塞/待复核/依赖未收尾 → 保留 Issue
```

## 三、合并确认员职责

| 决策 | 触发条件 | 动作 |
|------|---------|------|
| **close** | 已合并且无后续任务（下游已由新 Issue 承接） | 关闭原 Issue |
| **new_issue** | 已合并但有明确后续任务（未派发） | 新建 Issue 承接并分配任务，关闭原 Issue |
| **keep** | 已合并但仍有阻塞/待复核/依赖未收尾 | 保留 Issue，待收尾 |

## 四、核心实现

| 文件 | 作用 |
|------|------|
| `config/merged_confirm_agent.py` | 合并确认 Agent 核心逻辑：探查（probe）/ 确认（confirm）/ 决策（decide） |
| `tests/test_merged_confirm_agent.sh` | 测试信号灯（7 项断言） |
| `.cnb.yml`（`main:` 下 crontab） | 每日定时触发确认流程 |
| `.cnb/settings.yml` | 注册「合并确认员」角色 |

## 五、运行方式

```bash
# 合并确认 Agent 自测
python3 game-studio-agents/config/merged_confirm_agent.py

# 测试信号灯
bash game-studio-agents/tests/test_merged_confirm_agent.sh
```

## 六、与现有机制的关系

- **独立于 CodeBuddy**：合并确认员只做 Issue 状态确认与派发，不改代码；
- **类似审查机制**：审查机制探查 PR 变更做代码质量把关；合并确认机制探查「已合并
  标签 Issue」做状态确认，两者都是事件/定时驱动、自动化推进；
- **互补**：合并确认机制在「代码合并后」承接收尾，避免 open Issue 积压。
