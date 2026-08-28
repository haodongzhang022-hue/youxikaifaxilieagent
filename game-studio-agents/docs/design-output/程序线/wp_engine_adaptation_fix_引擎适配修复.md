# 程序线 · wp_engine_adaptation_fix 引擎适配修复

> 触发：PR #79（feat: 完成wp_art_testing验收回归与游戏引擎适配层架构）合并后，游戏向经理解锁程序线引擎适配修复工作包。
> 部门统一头：cto（程序线）
> 主责角色：engine_dev + tools_dev
> 产出物：修复 `department_agents.py` 已知代码质量问题，验证引擎适配层与部门 Agent 集成正确性。

## 一、修复清单

### 修复①：`department_agents.py` L665 — 音频资源扩展名 Bug

**问题描述**：`audio_resource_extension` 使用 `engine.resource_specs()[0].extension` 取第一个资源规格，导致：

| 引擎 | 修复前（取第一个规格） | 应取（按 audio 类型筛选） |
|------|----------------------|--------------------------|
| Cocos Creator | `.png`（sprite）❌ | `.mp3`（audio）✅ |
| Unreal Engine | `.fbx`（mesh）❌ | `.wav`（audio）✅ |

**修复方案**：改为按 `resource_type == "audio"` 筛选资源规格：

```python
"audio_resource_extension": next(
    (rs.extension for rs in engine.resource_specs() if rs.resource_type == "audio"),
    ""
),
```

**验证**：
- Cocos Creator → `.mp3` ✅
- Unreal Engine → `.wav` ✅

### 修复②：`department_agents.py` L28 — 清理未使用导入

**问题描述**：`detect_engine_from_project` / `build_engine_aware_artifact` / `EngineType` 已导入但未引用。

**修复方案**：仅保留实际使用的 `get_engine`：

```python
from engine_adapters import get_engine
```

### 修复③：确认 `engine_sync.py` / `deepseek_harness.py` 存在性

**确认结果**：当前 main 分支上**不存在** `engine_sync.py` / `deepseek_harness.py` 文件。这两个模块出现在 commit `8169907` 中，但该 commit 不在 main 分支的任何 ref 链上，需后续 PR 补交落地。

## 二、组内分工表（经协作工作台 @分工 · group_audit）

| 子任务 | 承接角色 | 产出 | 状态 |
|--------|---------|------|:----:|
| `department_agents.py` L665 音频扩展名修复 | engine_dev | 代码修复 + 双引擎验证 | ✅ DONE |
| `department_agents.py` L28 未使用导入清理 | tools_dev | 代码清理 + 语法验证 | ✅ DONE |
| `engine_sync.py` / `deepseek_harness.py` 缺失确认 | cto | 缺失确认报告 | ✅ DONE |
| 引擎适配层测试验证 | tools_dev | `test_engine_adapters.sh` 16/16 全绿 | ✅ DONE |

## 三、跨部门协作记录（request_peer）

| 协作方向 | 部门 | 协作内容 | 状态 |
|---------|------|---------|:----:|
| 下游通知 | 美术线 | `audio_resource_extension` 修复后，美术线资源管线可正确获取音频扩展名 | 待验证 |
| 下游通知 | 测试线 | `test_engine_adapters.sh` / `test_art_testing.sh` CI 信号灯保持全绿 | 已确认 |
| 上游确认 | 项目管理 | 已承接 wp_release 发版门禁，程序线修复后不影响发版判定 | 已确认 |

## 四、REVIEW_RESULT

**结论：✅ 通过**

**产出物说明**：
- 修复 `department_agents.py` 两处已知代码质量问题（音频扩展名 Bug + 未使用导入清理）
- 确认 `engine_sync.py` / `deepseek_harness.py` 在 main 分支缺失（需后续 PR 补交）
- `test_engine_adapters.sh`（16 项断言）全绿
- `test_art_testing.sh`（9 项断言）全绿
- `test_dept_group_collaboration.sh`（15 项断言）全绿
- 程序线 Agent 创建与引擎感知产出验证通过
